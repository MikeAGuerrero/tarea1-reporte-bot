"""Modelos internos usados por el parser y el pipeline."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LogEntry:
    timestamp: str
    operation_id: str
    message: str


@dataclass(frozen=True)
class UserInfo:
    sam_account_name: str = ""
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
