import json

import httpx
import respx

from app.services.telegram import TelegramClient, TelegramDelivery


def test_send_message_uses_the_configured_destination() -> None:
    with respx.mock:
        route = respx.post("https://api.telegram.org/bottest-token/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})
        )

        with httpx.Client() as http_client:
            client = TelegramClient("test-token", "-100123", client=http_client)
            delivery = client.send_message("A new job was found")

        assert delivery == TelegramDelivery(success=True, message_id=42)
        assert json.loads(route.calls[0].request.content) == {
            "chat_id": "-100123",
            "text": "A new job was found",
        }


def test_send_message_can_override_the_configured_destination() -> None:
    with respx.mock:
        route = respx.post("https://api.telegram.org/bottest-token/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})
        )

        with httpx.Client() as http_client:
            telegram = TelegramClient("test-token", "default-chat", client=http_client)
            delivery = telegram.send_message("Hello", chat_id="other-chat")

        assert delivery.success is True
        assert json.loads(route.calls[0].request.content)["chat_id"] == "other-chat"


def test_send_message_returns_telegram_errors() -> None:
    with respx.mock:
        respx.post("https://api.telegram.org/bottest-token/sendMessage").mock(
            return_value=httpx.Response(
                403,
                json={"ok": False, "description": "Forbidden: bot was kicked from the group chat"},
            )
        )

        with httpx.Client() as http_client:
            telegram = TelegramClient("test-token", "-100123", client=http_client)
            delivery = telegram.send_message("Hello")

        assert delivery == TelegramDelivery(
            success=False, error="Forbidden: bot was kicked from the group chat"
        )


def test_send_message_reports_missing_configuration_without_calling_telegram() -> None:
    delivery = TelegramClient(None).send_message("Hello")

    assert delivery == TelegramDelivery(success=False, error="Telegram bot token is not configured")
