"""Modelos internos usados por el parser y el pipeline."""

from dataclasses import dataclass, field

from reporte_bot.config import (
    RESET_ACTION,
    RESET_SYSTEM,
    SAP_REGISTER_ACTION,
    SAP_REGISTER_SYSTEM,
)


@dataclass(frozen=True)
class LogEntry:
    timestamp: str
    operation_id: str
    message: str


@dataclass(frozen=True)
class UserInfo:
    sam_account_name: str = ""
    employee_id: str = ""
    first_name: str = ""
    last_name: str = ""
    office: str = ""
    description: str = ""
    ou_name: str = ""

    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.first_name, self.last_name) if part).strip()


@dataclass(frozen=True)
class ResetEvent:
    timestamp: str
    operation_id: str
    requester: str
    target: str
    api_status: int
    requester_info: UserInfo | None
    target_info: UserInfo | None
    adm_error: str | None
    action: str = field(init=False, default=RESET_ACTION)
    system: str = field(init=False, default=RESET_SYSTEM)


@dataclass(frozen=True)
class SapRegisterEvent:
    timestamp: str
    operation_id: str
    requester: str
    target: str
    api_status: int
    requester_info: UserInfo | None
    target_info: UserInfo | None
    treatment: str
    job: str
    sap_message: str | None
    sap_called: bool
    ticket_created: bool
    ticket_closed: bool
    action: str = field(init=False, default=SAP_REGISTER_ACTION)
    system: str = field(init=False, default=SAP_REGISTER_SYSTEM)


ReportEvent = ResetEvent | SapRegisterEvent
