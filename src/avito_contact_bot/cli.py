from __future__ import annotations

import argparse
import sys

from .settings import load_settings
from .sheets import SheetsWriter
from .storage import Storage
from .sync_service import SyncService
from .utils import parse_sheet_id



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Avito contact tracker CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add-account", help="Add a new Avito account")
    add.add_argument("--name", required=True)
    add.add_argument("--client-id", required=True)
    add.add_argument("--client-secret", required=True)
    add.add_argument("--sheet", required=True, help="Sheet URL or sheet id")
    add.add_argument("--include-calls", action="store_true")

    sub.add_parser("list-accounts", help="Show configured accounts")

    sync = sub.add_parser("sync", help="Sync one account")
    sync.add_argument("account_id", type=int)

    disable = sub.add_parser("disable-account", help="Disable account")
    disable.add_argument("account_id", type=int)

    update_sheet = sub.add_parser("update-sheet", help="Update sheet id/url for account")
    update_sheet.add_argument("account_id", type=int)
    update_sheet.add_argument("--sheet", required=True)

    return parser



def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    settings = load_settings(require_bot_token=False)
    storage = Storage(settings.database_path)

    if args.command == "add-account":
        sheet_id = parse_sheet_id(args.sheet)
        account_id = storage.add_account(
            name=args.name,
            client_id=args.client_id,
            client_secret=args.client_secret,
            sheet_id=sheet_id,
            include_calls=bool(args.include_calls),
        )
        print(f"Account added: id={account_id}, sheet={sheet_id}")
        return 0

    if args.command == "list-accounts":
        accounts = storage.list_accounts(enabled_only=False)
        if not accounts:
            print("No accounts yet")
            return 0

        for account in accounts:
            status = "enabled" if account.enabled else "disabled"
            print(
                f"[{account.id}] {account.name} ({status}) sheet={account.sheet_id} "
                f"calls={account.include_calls} last_sync={account.last_sync_at or '-'} "
                f"last_status={account.last_sync_status or '-'}"
            )
        return 0

    if args.command == "disable-account":
        if not storage.account_exists(args.account_id):
            print(f"Account {args.account_id} not found", file=sys.stderr)
            return 1
        storage.disable_account(args.account_id)
        print(f"Account {args.account_id} disabled")
        return 0

    if args.command == "update-sheet":
        if not storage.account_exists(args.account_id):
            print(f"Account {args.account_id} not found", file=sys.stderr)
            return 1
        sheet_id = parse_sheet_id(args.sheet)
        storage.update_account_sheet(args.account_id, sheet_id)
        print(f"Account {args.account_id} sheet updated: {sheet_id}")
        return 0

    if args.command == "sync":
        account = storage.get_account(args.account_id)
        if not account:
            print(f"Account {args.account_id} not found", file=sys.stderr)
            return 1

        sheets = SheetsWriter(settings.google_service_account_json)
        service = SyncService(settings=settings, storage=storage, sheets=sheets)
        result = service.sync_account(account)
        print(
            f"Synced account #{result.account_id} ({result.account_name}): "
            f"fetched={result.fetched_events}, new={result.new_events}, appended={result.appended_rows}"
        )
        return 0

    print(f"Unknown command: {args.command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
