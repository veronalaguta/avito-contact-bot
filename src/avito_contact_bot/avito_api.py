from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import requests

from .models import ContactEvent
from .utils import parse_iso_datetime


class AvitoApiError(RuntimeError):
    pass


@dataclass(slots=True)
class AvitoClient:
    client_id: str
    client_secret: str
    base_url: str
    timeout_seconds: int

    def _request(self, method: str, path: str, *, token: str | None = None, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = requests.request(
            method,
            url,
            headers=headers,
            timeout=self.timeout_seconds,
            **kwargs,
        )

        if response.status_code >= 400:
            raise AvitoApiError(f"{method} {path} -> {response.status_code}: {response.text[:300]}")

        try:
            return response.json()
        except ValueError as exc:
            raise AvitoApiError(f"{method} {path} returned non-JSON response") from exc

    def get_access_token(self) -> str:
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        payload = self._request("POST", "/token/", data=data)
        token = payload.get("access_token")
        if not token:
            raise AvitoApiError("token endpoint did not return access_token")
        return str(token)

    def get_account_id(self, token: str) -> str:
        payload = self._request("GET", "/core/v1/accounts/self", token=token)
        account_id = _extract_account_id(payload)
        if not account_id:
            raise AvitoApiError("cannot extract account id from /core/v1/accounts/self")
        return account_id

    def list_chats(self, token: str, account_id: str, *, page_limit: int = 100) -> list[dict[str, Any]]:
        chats: list[dict[str, Any]] = []
        offset = 0
        while True:
            payload = self._request(
                "GET",
                f"/messenger/v2/accounts/{account_id}/chats/",
                token=token,
                params={
                    "unread_only": "false",
                    "chat_types": "u2i,u2u",
                    "limit": page_limit,
                    "offset": offset,
                },
            )
            chunk = _extract_list(payload, preferred_keys=("chats", "items", "result"))
            if not chunk:
                break
            chats.extend(chunk)
            if len(chunk) < page_limit:
                break
            offset += page_limit
            if offset > 3000:
                break
        return chats

    def get_last_message(self, token: str, account_id: str, chat_id: str) -> dict[str, Any] | None:
        messages = self.get_messages(token, account_id, chat_id, limit=1)
        if not messages:
            return None
        return messages[0]

    def get_messages(
        self,
        token: str,
        account_id: str,
        chat_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            f"/messenger/v3/accounts/{account_id}/chats/{chat_id}/messages/",
            token=token,
            params={"limit": limit, "offset": offset},
        )
        messages = _extract_list(payload, preferred_keys=("messages", "items", "result"))
        return messages

    def list_calls(self, token: str) -> list[dict[str, Any]]:
        payload = self._request("POST", "/calltracking/v1/getCalls/", token=token, json={})
        return _extract_list(payload, preferred_keys=("calls", "items", "result"))



def build_chat_events(
    avito: AvitoClient,
    *,
    token: str,
    account_id: str,
    include_calls: bool,
) -> list[ContactEvent]:
    events: list[ContactEvent] = []
    sample_message_limit = 40

    chats = avito.list_chats(token, account_id)
    for chat in chats:
        chat_id = _string_from(chat, ("id", "chat_id", "chatId"))
        if not chat_id:
            continue

        messages = avito.get_messages(token, account_id, chat_id, limit=sample_message_limit)
        newest_message = None
        if messages:
            newest_message = max(
                messages,
                key=lambda item: (
                    _datetime_from(item, ("created", "created_at", "createdAt", "timestamp")) or datetime.min.replace(tzinfo=UTC)
                ),
            )

        last_message = _nested_dict(chat, ("last_message", "lastMessage")) or newest_message

        occurred_at = (
            _datetime_from(last_message, ("created", "created_at", "createdAt", "timestamp"))
            or _datetime_from(chat, ("updated", "updated_at", "updatedAt", "created", "created_at"))
            or datetime.now(UTC)
        )

        message_id = _string_from(last_message, ("id", "message_id", "messageId")) or occurred_at.isoformat()
        source = _guess_chat_source(chat)
        contact_id, contact_name = _guess_chat_contact(chat, last_message)
        text_sample = _build_text_sample(chat, messages)

        events.append(
            ContactEvent(
                event_uid=f"chat:{chat_id}:{message_id}",
                occurred_at=occurred_at,
                contact_type="Сообщение",
                source=source,
                contact_id=contact_id,
                contact_name=contact_name,
                status="Чат обработан",
                chat_id=chat_id,
                chat_label="",
                text_sample=text_sample,
            )
        )

    if include_calls:
        for call in avito.list_calls(token):
            call_id = _string_from(call, ("id", "call_id", "callId"))
            phone = _string_from(call, ("phone", "phone_number", "number"))
            occurred_at = _datetime_from(call, ("created", "created_at", "started_at", "timestamp")) or datetime.now(UTC)
            marker = call_id or occurred_at.isoformat()
            events.append(
                ContactEvent(
                    event_uid=f"call:{marker}",
                    occurred_at=occurred_at,
                    contact_type="Звонок",
                    source="",
                    contact_id=phone or marker,
                    contact_name="",
                    status="Звонок обработан",
                    chat_id=None,
                    chat_label="",
                    text_sample="",
                )
            )

    return sorted(events, key=lambda item: item.occurred_at)



def _extract_account_id(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("id", "account_id", "accountId"):
            value = payload.get(key)
            if value not in (None, ""):
                return str(value)
        for value in payload.values():
            result = _extract_account_id(value)
            if result:
                return result
    elif isinstance(payload, list):
        for item in payload:
            result = _extract_account_id(item)
            if result:
                return result
    return None



def _extract_list(payload: Any, *, preferred_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    for key in preferred_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_list(value, preferred_keys=preferred_keys)
            if nested:
                return nested

    for value in payload.values():
        nested = _extract_list(value, preferred_keys=preferred_keys)
        if nested:
            return nested
    return []



def _string_from(data: dict[str, Any] | None, keys: tuple[str, ...]) -> str | None:
    if not data:
        return None
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return str(value)
    return None



def _nested_dict(data: dict[str, Any] | None, keys: tuple[str, ...]) -> dict[str, Any] | None:
    if not data:
        return None
    for key in keys:
        value = data.get(key)
        if isinstance(value, dict):
            return value
    return None



def _datetime_from(data: dict[str, Any] | None, keys: tuple[str, ...]) -> datetime | None:
    if not data:
        return None
    for key in keys:
        value = data.get(key)
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 1_000_000_000_000:
                timestamp /= 1000.0
            try:
                return datetime.fromtimestamp(timestamp, UTC)
            except (OverflowError, OSError, ValueError):
                continue
        if isinstance(value, str):
            if value.isdigit():
                timestamp = float(value)
                if timestamp > 1_000_000_000_000:
                    timestamp /= 1000.0
                try:
                    return datetime.fromtimestamp(timestamp, UTC)
                except (OverflowError, OSError, ValueError):
                    continue
            parsed = parse_iso_datetime(value)
            if parsed:
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=UTC)
                return parsed
    return None



def _guess_chat_source(chat: dict[str, Any]) -> str:
    for key in ("url", "chat_url", "item_url", "source"):
        value = chat.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for nested_key in ("context", "item", "ad"):
        nested = chat.get(nested_key)
        if isinstance(nested, dict):
            for key in ("url", "link"):
                value = nested.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            nested_value = nested.get("value")
            if isinstance(nested_value, dict):
                for key in ("url", "link"):
                    value = nested_value.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()

    item_id = _string_from(chat, ("item_id", "itemId", "ad_id", "adId"))
    context = chat.get("context")
    if isinstance(context, dict):
        context_value = context.get("value")
        if isinstance(context_value, dict):
            context_item_id = _string_from(context_value, ("id", "item_id", "itemId", "ad_id", "adId"))
            if context_item_id:
                item_id = context_item_id
    if item_id:
        return f"https://www.avito.ru/items/{item_id}"
    return ""



def _guess_chat_contact(chat: dict[str, Any], message: dict[str, Any] | None) -> tuple[str, str]:
    users_raw = chat.get("users")
    users: list[dict[str, Any]] = []
    if isinstance(users_raw, list):
        users = [item for item in users_raw if isinstance(item, dict)]

    if users:
        owner_user_id = _guess_owner_user_id(chat)
        selected_user: dict[str, Any] | None = None
        if owner_user_id:
            for user in users:
                user_id = _string_from(user, ("id", "user_id", "userId"))
                if user_id and user_id != owner_user_id:
                    selected_user = user
                    break

        if not selected_user and message:
            author_id = _string_from(message, ("author_id", "authorId", "user_id", "userId", "sender_id", "senderId"))
            if author_id:
                for user in users:
                    user_id = _string_from(user, ("id", "user_id", "userId"))
                    if user_id == author_id:
                        selected_user = user
                        break

        if not selected_user:
            selected_user = users[0]

        if selected_user:
            name = _string_from(selected_user, ("name", "title"))
            user_id = _string_from(selected_user, ("id", "user_id", "userId"))
            if user_id or name:
                return user_id or "", name or ""

    for source in (message or {}, chat):
        value = _string_from(source, ("author_id", "authorId", "user_id", "userId", "sender_id", "senderId"))
        if value:
            return value, ""

    user = chat.get("user")
    if isinstance(user, dict):
        user_id = _string_from(user, ("id", "user_id", "userId"))
        name = _string_from(user, ("name", "title"))
        if user_id or name:
            return user_id or "", name or ""

    fallback = _string_from(chat, ("id", "chat_id", "chatId")) or ""
    return fallback, ""


def _guess_owner_user_id(chat: dict[str, Any]) -> str | None:
    context_value = chat.get("context")
    if isinstance(context_value, dict):
        ctx_value = context_value.get("value")
        if isinstance(ctx_value, dict):
            return _string_from(ctx_value, ("user_id", "userId"))
    return None


def _build_text_sample(chat: dict[str, Any], messages: list[dict[str, Any]]) -> str:
    if not messages:
        return ""

    users_by_id = _build_user_names_by_id(chat)
    owner_user_id = _guess_owner_user_id(chat)

    lines: list[str] = []
    ordered = sorted(
        messages,
        key=lambda item: (
            _datetime_from(item, ("created", "created_at", "createdAt", "timestamp")) or datetime.min.replace(tzinfo=UTC)
        ),
    )
    for message in ordered:
        text = _message_text(message)
        if not text:
            continue
        occurred = _datetime_from(message, ("created", "created_at", "createdAt", "timestamp"))
        if occurred:
            dt = occurred.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
        else:
            dt = "0000-00-00 00:00:00"

        author_id = _string_from(message, ("author_id", "authorId", "user_id", "userId", "sender_id", "senderId"))
        author_name = users_by_id.get(author_id or "")
        if author_id and owner_user_id and author_id == owner_user_id:
            speaker = "🏢 Менеджер"
        elif author_name:
            speaker = f"👤 {author_name}"
        else:
            speaker = "👤 Клиент"

        lines.append(f"[{dt}] {speaker}: {text}")

    return "\n".join(lines)[:10000]


def _build_user_names_by_id(chat: dict[str, Any]) -> dict[str, str]:
    users_raw = chat.get("users")
    if not isinstance(users_raw, list):
        return {}
    result: dict[str, str] = {}
    for item in users_raw:
        if not isinstance(item, dict):
            continue
        user_id = _string_from(item, ("id", "user_id", "userId"))
        name = _string_from(item, ("name", "title"))
        if user_id and name:
            result[user_id] = name
    return result


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    if isinstance(content, str) and content.strip():
        return content.strip()
    return ""
