from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Account, ContactEvent


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    client_secret TEXT NOT NULL,
                    sheet_id TEXT NOT NULL,
                    include_calls INTEGER NOT NULL DEFAULT 0,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    last_sync_at TEXT,
                    last_sync_status TEXT,
                    last_sync_note TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS synced_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    event_uid TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    contact_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    contact_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(account_id, event_uid)
                )
                """
            )

    def add_account(
        self,
        *,
        name: str,
        client_id: str,
        client_secret: str,
        sheet_id: str,
        include_calls: bool,
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO accounts (
                    name, client_id, client_secret, sheet_id, include_calls, enabled, created_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (name, client_id, client_secret, sheet_id, int(include_calls), created_at),
            )
            return int(cursor.lastrowid)

    def list_accounts(self, *, enabled_only: bool = True) -> list[Account]:
        query = "SELECT * FROM accounts"
        params: tuple[object, ...] = ()
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY id"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._to_account(row) for row in rows]

    def get_account(self, account_id: int) -> Account | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if not row:
            return None
        return self._to_account(row)

    def account_exists(self, account_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM accounts WHERE id = ?", (account_id,)).fetchone()
        return bool(row)

    def update_account_sheet(self, account_id: int, sheet_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE accounts SET sheet_id = ? WHERE id = ?",
                (sheet_id, account_id),
            )

    def disable_account(self, account_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE accounts SET enabled = 0 WHERE id = ?", (account_id,))

    def mark_sync(self, account_id: int, *, status: str, note: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE accounts
                SET last_sync_at = ?,
                    last_sync_status = ?,
                    last_sync_note = ?
                WHERE id = ?
                """,
                (now, status, note, account_id),
            )

    def keep_new_events(self, account_id: int, events: list[ContactEvent]) -> list[ContactEvent]:
        if not events:
            return []

        new_events: list[ContactEvent] = []
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            for event in events:
                try:
                    conn.execute(
                        """
                        INSERT INTO synced_events (
                            account_id,
                            event_uid,
                            occurred_at,
                            contact_type,
                            source,
                            contact_id,
                            created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            account_id,
                            event.event_uid,
                            event.occurred_at.isoformat(),
                            event.contact_type,
                            event.source,
                            event.contact_id,
                            created_at,
                        ),
                    )
                    new_events.append(event)
                except sqlite3.IntegrityError:
                    continue
        return new_events

    @staticmethod
    def _to_account(row: sqlite3.Row) -> Account:
        return Account(
            id=int(row["id"]),
            name=str(row["name"]),
            client_id=str(row["client_id"]),
            client_secret=str(row["client_secret"]),
            sheet_id=str(row["sheet_id"]),
            include_calls=bool(row["include_calls"]),
            enabled=bool(row["enabled"]),
            last_sync_at=row["last_sync_at"],
            last_sync_status=row["last_sync_status"],
            last_sync_note=row["last_sync_note"],
        )
