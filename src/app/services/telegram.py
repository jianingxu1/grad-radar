"""Telegram message delivery for backend jobs and workers."""

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class TelegramDelivery:
    """The outcome of one Telegram send attempt."""

    success: bool
    message_id: int | None = None
    error: str | None = None
    retry_after: int | None = None
    status_code: int | None = None


class TelegramClient:
    """Small wrapper around Telegram's Bot API sendMessage endpoint.

    ``default_chat_id`` lets workers send to a configured channel or chat without
    carrying a destination through every call. Pass ``chat_id`` to ``send_message``
    when a message has a different destination.
    """

    def __init__(
        self,
        bot_token: str | None,
        default_chat_id: str | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._default_chat_id = default_chat_id
        self._client = client or httpx.Client(timeout=10)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "TelegramClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def send_message(self, text: str, *, chat_id: str | None = None) -> TelegramDelivery:
        """Send plain text and return a delivery outcome instead of raising.

        Telegram chat IDs may represent a private chat, group, or channel. The
        bot must be allowed to post there; Telegram reports access problems in
        its error description.
        """
        destination = chat_id or self._default_chat_id
        if not self._bot_token:
            return TelegramDelivery(False, error="Telegram bot token is not configured")
        if not destination:
            return TelegramDelivery(False, error="Telegram chat ID is not configured")
        if not text.strip():
            return TelegramDelivery(False, error="Telegram message must not be empty")

        try:
            response = self._client.post(
                f"https://api.telegram.org/bot{self._bot_token}/sendMessage",
                json={
                    "chat_id": destination,
                    "text": text,
                    "parse_mode": "HTML",
                    "link_preview_options": {"is_disabled": True},
                },
            )
        except httpx.HTTPError as error:
            return TelegramDelivery(False, error=f"Telegram request failed: {error}")

        try:
            payload = response.json()
        except ValueError:
            return TelegramDelivery(False, error=f"Telegram returned HTTP {response.status_code}")

        if not isinstance(payload, dict):
            return TelegramDelivery(False, error="Telegram returned an invalid response")

        if response.is_success and payload.get("ok") is True:
            result = payload.get("result", {})
            message_id = result.get("message_id") if isinstance(result, dict) else None
            if type(message_id) is int:
                return TelegramDelivery(True, message_id=message_id)
            return TelegramDelivery(True)

        description = payload.get("description")
        if isinstance(description, str):
            parameters = payload.get("parameters")
            retry_after = parameters.get("retry_after") if isinstance(parameters, dict) else None
            return TelegramDelivery(
                False,
                error=description,
                retry_after=retry_after if type(retry_after) is int else None,
                status_code=response.status_code,
            )
        return TelegramDelivery(
            False,
            error=f"Telegram returned HTTP {response.status_code}",
            status_code=response.status_code,
        )
