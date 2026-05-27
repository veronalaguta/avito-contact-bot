from __future__ import annotations

import asyncio
import logging
from typing import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from .settings import Settings, load_settings
from .sheets import SheetsWriter
from .storage import Storage
from .sync_service import SyncService

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("avito_contact_bot")



def _is_allowed(settings: Settings, user_id: int | None) -> bool:
    if user_id is None:
        return False
    if not settings.allowed_user_ids:
        return True
    return user_id in settings.allowed_user_ids



def _build_accounts_keyboard(storage: Storage) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for account in storage.list_accounts(enabled_only=True):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"Выгрузить #{account.id} · {account.name}",
                    callback_data=f"sync:{account.id}",
                )
            ]
        )

    rows.append([InlineKeyboardButton(text="Обновить список", callback_data="menu:refresh")])
    return InlineKeyboardMarkup(rows)



def _access_denied_text() -> str:
    return "Нет доступа. Добавьте ваш Telegram user_id в BOT_ALLOWED_USER_IDS в .env"



def require_access(handler: Callable[[Update, ContextTypes.DEFAULT_TYPE], asyncio.Future]):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
        settings: Settings = context.application.bot_data["settings"]
        user_id = update.effective_user.id if update.effective_user else None
        if not _is_allowed(settings, user_id):
            target = update.message or update.callback_query
            if target:
                if update.message:
                    await update.message.reply_text(_access_denied_text())
                elif update.callback_query:
                    await update.callback_query.answer(_access_denied_text(), show_alert=True)
            return
        return await handler(update, context)

    return wrapped


@require_access
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.application.bot_data["storage"]
    keyboard = _build_accounts_keyboard(storage)
    await update.message.reply_text(
        "Трекер Avito готов. Нажмите кнопку для ручной выгрузки в таблицу.",
        reply_markup=keyboard,
    )


@require_access
async def accounts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage: Storage = context.application.bot_data["storage"]
    items = storage.list_accounts(enabled_only=False)
    if not items:
        await update.message.reply_text("Аккаунтов пока нет. Добавьте через CLI: avito-contact-cli add-account ...")
        return

    lines = []
    for item in items:
        state = "активен" if item.enabled else "выключен"
        lines.append(
            f"#{item.id} {item.name} ({state})\n"
            f"sheet: {item.sheet_id}\n"
            f"last sync: {item.last_sync_at or '-'} ({item.last_sync_status or '-'})"
        )

    await update.message.reply_text("\n\n".join(lines))


@require_access
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Команды:\n"
        "/start - кнопки ручной выгрузки\n"
        "/accounts - список аккаунтов\n"
        "/myid - показать ваш Telegram user_id"
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id if update.effective_user else None
    await update.message.reply_text(f"Ваш user_id: {user_id}")


@require_access
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not query.data:
        return

    storage: Storage = context.application.bot_data["storage"]

    if query.data == "menu:refresh":
        await query.edit_message_reply_markup(reply_markup=_build_accounts_keyboard(storage))
        return

    if not query.data.startswith("sync:"):
        await query.edit_message_text("Неизвестная команда кнопки")
        return

    try:
        account_id = int(query.data.split(":", 1)[1])
    except ValueError:
        await query.edit_message_text("Неверный account_id")
        return

    account = storage.get_account(account_id)
    if not account or not account.enabled:
        await query.edit_message_text("Аккаунт не найден или отключен")
        return

    await query.edit_message_text(f"Запускаю выгрузку для #{account.id} {account.name}...")

    service: SyncService = context.application.bot_data["sync_service"]
    try:
        result = await asyncio.to_thread(service.sync_account, account)
        await query.message.reply_text(
            f"Готово: #{result.account_id} {result.account_name}\n"
            f"получено: {result.fetched_events}\n"
            f"новых: {result.new_events}\n"
            f"добавлено строк: {result.appended_rows}"
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("sync failed")
        await query.message.reply_text(f"Ошибка синхронизации: {exc}")



def main() -> None:
    settings = load_settings(require_bot_token=True)
    storage = Storage(settings.database_path)
    sheets = SheetsWriter(settings.google_service_account_json)
    sync_service = SyncService(settings=settings, storage=storage, sheets=sheets)

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.bot_data["settings"] = settings
    app.bot_data["storage"] = storage
    app.bot_data["sync_service"] = sync_service

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("accounts", accounts))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CallbackQueryHandler(on_callback))

    logger.info("Bot is starting")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
