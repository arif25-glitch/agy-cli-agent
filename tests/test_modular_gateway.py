"""
Unit tests for the modularized gateway components:
- services/telegram_client.py
- helpers/reply_parser.py
- helpers/intent_classifier.py
- handlers/queue_handlers.py
- models.py
"""
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from gemini_hermes.gateway.models import QueuedTask
from gemini_hermes.gateway.services.telegram_client import TelegramClient
from gemini_hermes.gateway.helpers.reply_parser import extract_reply_context
from gemini_hermes.gateway.helpers.intent_classifier import classify_btw_intent


class TestModularGateway(unittest.IsolatedAsyncioTestCase):

    def test_positive_queued_task_model(self):
        """Positive Path: QueuedTask retains string behavior and custom metadata."""
        qt = QueuedTask("Perform refactoring", message_id=101, item_type="prompt")
        self.assertEqual(str(qt), "Perform refactoring")
        self.assertEqual(qt.message_id, 101)
        self.assertEqual(qt.item_type, "prompt")
        self.assertTrue(qt.startswith("Perform"))

    def test_positive_intent_classifier_patterns(self):
        """Positive Path: Verify diverse natural and prefixed intents."""
        # Prefixed questions
        intent, q = classify_btw_intent("? What is the current version")
        self.assertEqual(intent, "question")
        self.assertEqual(q, "What is the current version")

        # Prefixed tasks
        intent, t = classify_btw_intent("task: run unit tests")
        self.assertEqual(intent, "task")
        self.assertEqual(t, "run unit tests")

        # Live status
        intent, s = classify_btw_intent("what are you doing right now?")
        self.assertEqual(intent, "live_status")

        # Natural question
        intent, q2 = classify_btw_intent("how does SQLite journaling work?")
        self.assertEqual(intent, "question")

    def test_negative_intent_classifier_defaults(self):
        """Negative Path: Ambiguous or imperative statements default to task."""
        intent, t = classify_btw_intent("deploy the new service to staging")
        self.assertEqual(intent, "task")

    def test_positive_extract_reply_context_text(self):
        """Positive Path: Text reply extraction formats sender and body."""
        reply_payload = {
            "from": {"first_name": "Alice"},
            "text": "Can you check the database schema?",
        }
        res = extract_reply_context(reply_payload)
        self.assertIn('from Alice: "Can you check the database schema?"', res)

    def test_negative_extract_reply_context_edge_cases(self):
        """Negative Path: Malformed, non-dict, or empty replies return empty string."""
        self.assertEqual(extract_reply_context(None), "")
        self.assertEqual(extract_reply_context("invalid string"), "")
        self.assertEqual(extract_reply_context(12345), "")

    def test_positive_extract_reply_context_media(self):
        """Positive Path: Reply extraction for voice, sticker, and documents."""
        voice_payload = {"from": {"username": "bob_dev"}, "voice": {"duration": 12}}
        self.assertIn("[Replying to voice message from bob_dev]", extract_reply_context(voice_payload))

        doc_payload = {"from": {"first_name": "Charlie"}, "document": {"file_name": "data.csv"}}
        self.assertIn("[Replying to file (data.csv) from Charlie]", extract_reply_context(doc_payload))

        sticker_payload = {"from": {"first_name": "Dave"}, "sticker": {"emoji": "🚀"}}
        self.assertIn("[Replying to sticker 🚀 from Dave]", extract_reply_context(sticker_payload))

    async def test_positive_telegram_client_send_message(self):
        """Positive Path: TelegramClient sendMessage dispatches JSON payload cleanly."""
        client = TelegramClient(token="test_token_123")
        client._api_call = AsyncMock(return_value={"ok": True, "result": {"message_id": 42}})

        msg_id = await client.send_message(chat_id=1001, text="Hello world", reply_to_message_id=99)
        self.assertEqual(msg_id, 42)
        client._api_call.assert_called_once()
        args = client._api_call.call_args[0]
        self.assertEqual(args[0], "sendMessage")
        self.assertEqual(args[1]["chat_id"], 1001)
        self.assertEqual(args[1]["reply_to_message_id"], 99)

    async def test_negative_telegram_client_send_message_error(self):
        """Negative Path: TelegramClient returns None when API returns failure."""
        client = TelegramClient(token="test_token_123")
        client._api_call = AsyncMock(return_value={"ok": False, "error": "Bad Request"})

        msg_id = await client.send_message(chat_id=1001, text="Hello fail")
        self.assertIsNone(msg_id)


if __name__ == "__main__":
    unittest.main()
