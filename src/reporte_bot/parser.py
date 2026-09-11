"""Lectura y extracción de eventos relevantes desde los archivos .log."""

import ast
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from reporte_bot.models import LogEntry, ReportEvent, ResetEvent, SapRegisterEvent, UserInfo
from reporte_bot.utils import normalize_username

ENTRY_RE = re.compile(
    r"^(?P<timestamp>\S+)\s+\|\s+INFO \[operation_Id=(?P<operation_id>[^\]]+)\]\s+\|\s+"
    r"(?P<message>.*)$"
)
RESET_REQUEST_RE = re.compile(
    r"HTTP Request:\s+(?P<url>http://apitools\.com:8000/v3/users_admin/resetuser\?[^\"]+)\s+"
    r'"HTTP/1\.1"\s+(?P<status>\d{3})'
)
SAP_REGISTER_REQUEST_RE = re.compile(
    r"HTTP Request:\s+(?P<url>http://apitools\.com:8000/v2/sap/register_user\?[^\"]+)\s+"
    r'"HTTP/1\.1"\s+(?P<status>\d{3})'
)
SEARCH_FILTER_RE = re.compile(r"\((?P<field>sAMAccountName|employeeID):equal:(?P<value>[^)]*)\)")
RAW_RESPONSE_RE = re.compile(r"Raw Response:\s*(?P<body>\{.*\})\s*,\s*Raw status_code:", re.DOTALL)
ADM_BODY_RE = re.compile(
    r"ADM-Raw response\s*\|\s*status:\s*(?P<status>\d+)\s*\|\s*body:\s*(?P<body>.*)",
    re.DOTALL,
)
ADM_REASON_RE = re.compile(
    r"ADM-Raw response\s*\|\s*status:\s*(?P<status>\d+)\s*\|\s*reason:\s*(?P<reason>[^|]+)"
)
SAP_RAW_RESPONSE_RE = re.compile(r"SAP raw response:\s*(?P<body>\{.*\})", re.DOTALL)


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


def _parse_sap_register_request(entry: LogEntry) -> tuple[str, str, str, str, int] | None:
    match = SAP_REGISTER_REQUEST_RE.search(entry.message)
    if not match:
        return None

    query = parse_qs(urlparse(match.group("url")).query)
    requester = query.get("requester_username", [""])[0]
    target = query.get("target_employee_id", [""])[0]
    treatment = query.get("treatment", [""])[0]
    job = query.get("job", [""])[0]
    return requester, target, treatment, job, int(match.group("status"))


def _user_from_raw(raw_user: dict[str, object]) -> UserInfo:
    def text(field: str) -> str:
        value = raw_user.get(field, "")
        return "" if value is None else str(value).strip()

    return UserInfo(
        sam_account_name=text("SAM_ACCOUNT_NAME"),
        employee_id=text("EMPLOYEE_ID"),
        first_name=text("FIRST_NAME"),
        last_name=text("LAST_NAME"),
        office=text("OFFICE"),
        description=text("DESCRIPTION"),
        ou_name=text("OU_NAME"),
    )


def _parse_admanager_search(entry: LogEntry) -> tuple[str, str, UserInfo | None] | None:
    if "ADManagerRawClient.get_users_list_info" not in entry.message:
        return None

    filter_match = SEARCH_FILTER_RE.search(entry.message)
    raw_match = RAW_RESPONSE_RE.search(entry.message)
    if not filter_match or not raw_match:
        return None

    field = filter_match.group("field")
    value = filter_match.group("value")

    try:
        payload = json.loads(raw_match.group("body"))
    except json.JSONDecodeError:
        return field, value, None

    users = payload.get("UsersList") or []
    if not users:
        return field, value, None

    return field, value, _user_from_raw(users[0])


def _index_admanager_searches(
    entries: list[LogEntry],
) -> tuple[dict[str, UserInfo | None], dict[str, UserInfo | None]]:
    by_sam: dict[str, UserInfo | None] = {}
    by_employee_id: dict[str, UserInfo | None] = {}

    for entry in entries:
        parsed = _parse_admanager_search(entry)
        if parsed is None:
            continue

        field, value, user_info = parsed
        key = normalize_username(value)
        if field == "sAMAccountName":
            by_sam[key] = user_info
        elif field == "employeeID":
            by_employee_id[key] = user_info

    return by_sam, by_employee_id


def _extract_nested_text(value: object, key: str) -> str | None:
    if isinstance(value, dict):
        found = value.get(key)
        if found:
            return str(found).strip()
        for nested in value.values():
            result = _extract_nested_text(nested, key)
            if result:
                return result
    elif isinstance(value, list):
        for item in value:
            result = _extract_nested_text(item, key)
            if result:
                return result
    return None


def _parse_python_or_json(body: str) -> object | None:
    try:
        return ast.literal_eval(body)
    except (ValueError, SyntaxError):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None


def _parse_adm_error(entries: list[LogEntry]) -> str | None:
    """Extrae el mensaje exacto de ADManager para errores 503; también tolera reason."""
    for entry in reversed(entries):
        if "ADM-Raw response" not in entry.message:
            continue

        body_match = ADM_BODY_RE.search(entry.message)
        if body_match:
            parsed = _parse_python_or_json(body_match.group("body").strip())
            message = _extract_nested_text(parsed, "statusMessage")
            if message:
                return message

        reason_match = ADM_REASON_RE.search(entry.message)
        if reason_match:
            return reason_match.group("reason").strip()

    return None


def _parse_sap_message(entries: list[LogEntry]) -> str | None:
    for entry in reversed(entries):
        match = SAP_RAW_RESPONSE_RE.search(entry.message)
        if not match:
            continue
        parsed = _parse_python_or_json(match.group("body").strip())
        message = _extract_nested_text(parsed, "Mensaje")
        if message:
            return message
    return None


def _sap_was_called(entries: list[LogEntry]) -> bool:
    return any(
        "RESTAdapter/segMttoUsuario" in entry.message or "SAP input:" in entry.message
        for entry in entries
    )


def _ticket_was_created(entries: list[LogEntry]) -> bool:
    return any(
        "ProactivanetRawClient, method = POST, url = incidents, proactivanet_raw_response:"
        in entry.message
        for entry in entries
    )


def _ticket_was_closed(entries: list[LogEntry]) -> bool:
    return any(
        "ProactivanetRawClient, method = PUT, url = incidents/" in entry.message
        and "/close, proactivanet_raw_response:" in entry.message
        and "'Status': 'Closed'" in entry.message
        for entry in entries
    )


def _build_reset_event(
    operation_id: str, entries: list[LogEntry], by_sam: dict[str, UserInfo | None]
) -> ResetEvent | None:
    for entry in entries:
        request_data = _parse_reset_request(entry)
        if request_data is None:
            continue

        requester, target, api_status = request_data
        return ResetEvent(
            timestamp=entry.timestamp,
            operation_id=operation_id,
            requester=requester,
            target=target,
            api_status=api_status,
            requester_info=by_sam.get(normalize_username(requester)),
            target_info=by_sam.get(normalize_username(target)),
            adm_error=_parse_adm_error(entries),
        )

    return None


def _build_sap_register_event(
    operation_id: str,
    entries: list[LogEntry],
    by_sam: dict[str, UserInfo | None],
    by_employee_id: dict[str, UserInfo | None],
) -> SapRegisterEvent | None:
    for entry in entries:
        request_data = _parse_sap_register_request(entry)
        if request_data is None:
            continue

        requester, target, treatment, job, api_status = request_data
        return SapRegisterEvent(
            timestamp=entry.timestamp,
            operation_id=operation_id,
            requester=requester,
            target=target,
            api_status=api_status,
            requester_info=by_sam.get(normalize_username(requester)),
            target_info=by_employee_id.get(normalize_username(target)),
            treatment=treatment,
            job=job,
            sap_message=_parse_sap_message(entries),
            sap_called=_sap_was_called(entries),
            ticket_created=_ticket_was_created(entries),
            ticket_closed=_ticket_was_closed(entries),
        )

    return None


def parse_events(path: Path) -> list[ReportEvent]:
    """Convierte un log completo en todas las acciones soportadas por el reporte."""
    operations = group_by_operation(read_log_entries(path))
    events: list[ReportEvent] = []

    for operation_id, entries in operations.items():
        by_sam, by_employee_id = _index_admanager_searches(entries)

        reset_event = _build_reset_event(operation_id, entries, by_sam)
        if reset_event is not None:
            events.append(reset_event)
            continue

        sap_register_event = _build_sap_register_event(
            operation_id, entries, by_sam, by_employee_id
        )
        if sap_register_event is not None:
            events.append(sap_register_event)

    return sorted(events, key=lambda event: (event.timestamp, event.operation_id))
