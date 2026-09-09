"""Lectura y extracción de eventos relevantes desde los archivos .log."""

import ast
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from reporte_bot.models import LogEntry, ResetEvent, UserInfo
from reporte_bot.utils import normalize_username

ENTRY_RE = re.compile(
    r"^(?P<timestamp>\S+)\s+\|\s+INFO \[operation_Id=(?P<operation_id>[^\]]+)\]\s+\|\s+"
    r"(?P<message>.*)$"
)
RESET_REQUEST_RE = re.compile(
    r"HTTP Request:\s+(?P<url>http://apitools\.com:8000/v3/users_admin/resetuser\?[^\"]+)\s+"
    r'"HTTP/1\.1"\s+(?P<status>\d{3})'
)
SEARCH_FILTER_RE = re.compile(r"\(sAMAccountName:equal:(?P<username>[^)]*)\)")
RAW_RESPONSE_RE = re.compile(r"Raw Response:\s*(?P<body>\{.*\})\s*,\s*Raw status_code:", re.DOTALL)
ADM_BODY_RE = re.compile(
    r"ADM-Raw response\s*\|\s*status:\s*(?P<status>\d+)\s*\|\s*body:\s*(?P<body>.*)",
    re.DOTALL,
)
ADM_REASON_RE = re.compile(
    r"ADM-Raw response\s*\|\s*status:\s*(?P<status>\d+)\s*\|\s*reason:\s*(?P<reason>[^|]+)"
)


def read_log_entries(path: Path) -> list[LogEntry]:
    """Reconstruye entradas del log incluyendo líneas de continuación."""
    entries: list[LogEntry] = []
    current: dict[str, str] | None = None

    with path.open("r", encoding="utf-8", errors="replace") as file:
        for raw_line in file:
            line = raw_line.rstrip("\n")
            match = ENTRY_RE.match(line)

            if match:
                if current is not None:
                    entries.append(LogEntry(**current))
                current = {
                    "timestamp": match.group("timestamp"),
                    "operation_id": match.group("operation_id"),
                    "message": match.group("message"),
                }
            elif current is not None:
                current["message"] += f"\n{line}"

    if current is not None:
        entries.append(LogEntry(**current))

    return entries


def group_by_operation(entries: list[LogEntry]) -> dict[str, list[LogEntry]]:
    """Agrupa entradas aunque operaciones concurrentes estén intercaladas en el archivo."""
    grouped: dict[str, list[LogEntry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.operation_id].append(entry)
    return dict(grouped)


def _parse_reset_request(entry: LogEntry) -> tuple[str, str, int] | None:
    match = RESET_REQUEST_RE.search(entry.message)
    if not match:
        return None

    query = parse_qs(urlparse(match.group("url")).query)
    requester = query.get("sAMAccountName_requester", [""])[0]
    target = query.get("sAMAccountName_target", [""])[0]
    return requester, target, int(match.group("status"))


def _user_from_raw(raw_user: dict[str, object]) -> UserInfo:
    def text(field: str) -> str:
        value = raw_user.get(field, "")
        return "" if value is None else str(value).strip()

    return UserInfo(
        sam_account_name=text("SAM_ACCOUNT_NAME"),
        first_name=text("FIRST_NAME"),
        last_name=text("LAST_NAME"),
        office=text("OFFICE"),
        description=text("DESCRIPTION"),
        ou_name=text("OU_NAME"),
    )


def _parse_admanager_search(entry: LogEntry) -> tuple[str, UserInfo | None] | None:
    if "ADManagerRawClient.get_users_list_info_from_admanager invoked" not in entry.message:
        return None

    user_match = SEARCH_FILTER_RE.search(entry.message)
    raw_match = RAW_RESPONSE_RE.search(entry.message)
    if not user_match or not raw_match:
        return None

    username = user_match.group("username")
    try:
        payload = json.loads(raw_match.group("body"))
    except json.JSONDecodeError:
        return username, None

    users = payload.get("UsersList") or []
    if not users:
        return username, None

    return username, _user_from_raw(users[0])


def _extract_status_message(value: object) -> str | None:
    if isinstance(value, dict):
        message = value.get("statusMessage")
        if message:
            return str(message).strip()
        for nested in value.values():
            result = _extract_status_message(nested)
            if result:
                return result
    elif isinstance(value, list):
        for item in value:
            result = _extract_status_message(item)
            if result:
                return result
    return None


def _parse_adm_error(entries: list[LogEntry]) -> str | None:
    """Extrae el mensaje exacto de ADManager para errores 503; también tolera reason."""
    for entry in reversed(entries):
        if "ADM-Raw response" not in entry.message:
            continue

        body_match = ADM_BODY_RE.search(entry.message)
        if body_match:
            body = body_match.group("body").strip()
            parsed: object | None = None
            try:
                parsed = ast.literal_eval(body)
            except (ValueError, SyntaxError):
                try:
                    parsed = json.loads(body)
                except json.JSONDecodeError:
                    parsed = None

            message = _extract_status_message(parsed)
            if message:
                return message

        reason_match = ADM_REASON_RE.search(entry.message)
        if reason_match:
            return reason_match.group("reason").strip()

    return None


def parse_reset_events(path: Path) -> list[ResetEvent]:
    """Convierte un log completo en eventos del endpoint resetuser únicamente."""
    operations = group_by_operation(read_log_entries(path))
    events: list[ResetEvent] = []

    for operation_id, entries in operations.items():
        request_entry: LogEntry | None = None
        request_data: tuple[str, str, int] | None = None

        for entry in entries:
            parsed_request = _parse_reset_request(entry)
            if parsed_request is not None:
                request_entry = entry
                request_data = parsed_request
                break

        if request_entry is None or request_data is None:
            continue

        requester, target, api_status = request_data
        searches: dict[str, UserInfo | None] = {}

        for entry in entries:
            parsed_search = _parse_admanager_search(entry)
            if parsed_search is None:
                continue
            username, user_info = parsed_search
            searches[normalize_username(username)] = user_info

        events.append(
            ResetEvent(
                timestamp=request_entry.timestamp,
                operation_id=operation_id,
                requester=requester,
                target=target,
                api_status=api_status,
                requester_info=searches.get(normalize_username(requester)),
                target_info=searches.get(normalize_username(target)),
                adm_error=_parse_adm_error(entries),
            )
        )

    return sorted(events, key=lambda event: (event.timestamp, event.operation_id))
