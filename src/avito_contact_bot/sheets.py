from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from .models import ContactEvent


class SheetsWriter:
    def __init__(self, service_account_json: Path):
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_file(str(service_account_json), scopes=scopes)
        self.service = build("sheets", "v4", credentials=credentials, cache_discovery=False)

    def append_events(
        self,
        *,
        spreadsheet_id: str,
        events: list[ContactEvent],
        timezone: ZoneInfo,
        sheet_name: str = "Лист1",
    ) -> int:
        if not events:
            return 0

        values_api = self.service.spreadsheets().values()
        current = values_api.get(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A:Q",
        ).execute()
        rows = current.get("values", [])

        start_row = self._find_first_empty_data_row(rows)
        payload_rows: list[list[str]] = []

        for event in events:
            payload_rows.append(self._event_to_sheet_row(event, timezone))

        end_row = start_row + len(payload_rows) - 1
        values_api.update(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!C{start_row}:G{end_row}",
            valueInputOption="USER_ENTERED",
            body={"values": payload_rows},
        ).execute()
        return len(payload_rows)

    @staticmethod
    def _find_first_empty_data_row(rows: list[list[str]]) -> int:
        # Rows 1-2 are header rows in the provided template.
        minimum_data_row = 3
        for row_index in range(minimum_data_row - 1, len(rows)):
            row = rows[row_index]
            date_cell = row[2].strip() if len(row) > 2 and isinstance(row[2], str) else ""
            kind_cell = row[3].strip() if len(row) > 3 and isinstance(row[3], str) else ""
            if not date_cell and not kind_cell:
                return row_index + 1
        return max(minimum_data_row, len(rows) + 1)

    @staticmethod
    def _event_to_sheet_row(event: ContactEvent, timezone: ZoneInfo) -> list[str]:
        local_dt = event.occurred_at.astimezone(timezone)
        dt_value = local_dt.strftime("%d.%m.%Y %H:%M:%S")
        return [
            dt_value,
            event.contact_type,
            event.source,
            event.contact_id,
            event.status,
        ]
