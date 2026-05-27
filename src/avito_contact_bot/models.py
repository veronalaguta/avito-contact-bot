from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Account:
    id: int
    name: str
    client_id: str
    client_secret: str
    sheet_id: str
    include_calls: bool
    enabled: bool
    last_sync_at: str | None
    last_sync_status: str | None
    last_sync_note: str | None


@dataclass(slots=True)
class ContactEvent:
    event_uid: str
    occurred_at: datetime
    contact_type: str
    source: str
    contact_id: str
    status: str
