from __future__ import annotations

from datetime import datetime
from urllib.parse import parse_qs, urlparse



def parse_sheet_id(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise ValueError("sheet id is empty")

    if "/spreadsheets/d/" in value:
        parsed = urlparse(value)
        parts = parsed.path.split("/d/")
        if len(parts) < 2:
            raise ValueError("cannot parse sheet id from URL")
        tail = parts[1]
        return tail.split("/")[0]

    parsed = urlparse(value)
    if parsed.query:
        qs = parse_qs(parsed.query)
        if "id" in qs and qs["id"]:
            return qs["id"][0]

    return value



def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw)
    except ValueError:
        return None
