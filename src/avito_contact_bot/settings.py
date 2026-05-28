from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    telegram_bot_token: str
    google_service_account_json: Path | None
    database_path: Path
    timezone: ZoneInfo
    avito_api_base: str
    request_timeout_seconds: int
    allowed_user_ids: set[int]



def _parse_allowed_users(raw: str | None) -> set[int]:
    if not raw:
        return set()
    result: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        result.add(int(part))
    return result



def load_settings(*, require_bot_token: bool = True) -> Settings:
    load_dotenv()

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if require_bot_token and not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    google_service_account_json = Path(creds_path).expanduser().resolve() if creds_path else None

    db_path = os.getenv("DATABASE_PATH", "./data/contact_tracker.db").strip()
    tz_name = os.getenv("TIMEZONE", "Europe/Moscow").strip()

    settings = Settings(
        telegram_bot_token=bot_token,
        google_service_account_json=google_service_account_json,
        database_path=Path(db_path).expanduser().resolve(),
        timezone=ZoneInfo(tz_name),
        avito_api_base=os.getenv("AVITO_API_BASE", "https://api.avito.ru").rstrip("/"),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "25")),
        allowed_user_ids=_parse_allowed_users(os.getenv("BOT_ALLOWED_USER_IDS")),
    )
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
