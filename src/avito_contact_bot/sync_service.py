from __future__ import annotations

from dataclasses import dataclass

from .avito_api import AvitoApiError, AvitoClient, build_chat_events
from .models import Account
from .settings import Settings
from .sheets import SheetsWriter
from .storage import Storage


@dataclass(slots=True)
class SyncResult:
    account_id: int
    account_name: str
    fetched_events: int
    new_events: int
    appended_rows: int


class SyncService:
    def __init__(self, *, settings: Settings, storage: Storage, sheets: SheetsWriter):
        self.settings = settings
        self.storage = storage
        self.sheets = sheets

    def sync_account(self, account: Account) -> SyncResult:
        avito = AvitoClient(
            client_id=account.client_id,
            client_secret=account.client_secret,
            base_url=self.settings.avito_api_base,
            timeout_seconds=self.settings.request_timeout_seconds,
        )

        try:
            token = avito.get_access_token()
            avito_account_id = avito.get_account_id(token)
            fetched = build_chat_events(
                avito,
                token=token,
                account_id=avito_account_id,
                include_calls=account.include_calls,
            )
            unique_events = self.storage.keep_new_events(account.id, fetched)
            appended_rows = self.sheets.append_events(
                spreadsheet_id=account.sheet_id,
                events=unique_events,
                timezone=self.settings.timezone,
            )
            self.sheets.append_chat_exports(
                spreadsheet_id=account.sheet_id,
                events=unique_events,
                timezone=self.settings.timezone,
            )
            self.storage.save_events(account.id, unique_events)
            self.storage.mark_sync(
                account.id,
                status="ok",
                note=f"fetched={len(fetched)} new={len(unique_events)} appended={appended_rows}",
            )
            return SyncResult(
                account_id=account.id,
                account_name=account.name,
                fetched_events=len(fetched),
                new_events=len(unique_events),
                appended_rows=appended_rows,
            )
        except AvitoApiError as exc:
            self.storage.mark_sync(account.id, status="error", note=str(exc))
            raise
        except Exception as exc:  # noqa: BLE001
            self.storage.mark_sync(account.id, status="error", note=str(exc))
            raise
