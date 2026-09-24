"""
Comprehensive unit tests for Jev AI System-One decision engine and client service.
Dual verification covering positive execution paths and negative/fallback stress tests.
"""
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from gemini_hermes.brain.jev_types import JevCategory, JevDecisionOutcome
from gemini_hermes.services.jev_client import JevClient
from gemini_hermes.gateway.telegram_bot import TelegramBot


class TestJevAI(unittest.IsolatedAsyncioTestCase):

    async def test_positive_sandbox_decision_categories(self):
        """Positive Path 1: Verify offline sandbox correctly routes common intents with high confidence."""
        client = JevClient(api_key=None)

        # Status intent
        out_status = await client.decide("how is the system status and health?")
        self.assertEqual(out_status.category, JevCategory.SYSTEM_STATUS)
        self.assertTrue(out_status.is_high_confidence)
        self.assertFalse(out_status.requires_system_two)

        # Ephemeral side question
        out_qa = await client.decide("? what is TCP protocol?")
        self.assertEqual(out_qa.category, JevCategory.EPHEMERAL_QA)
        self.assertTrue(out_qa.is_high_confidence)

        # Task queueing
        out_task = await client.decide("task: deploy database migrations")
        self.assertEqual(out_task.category, JevCategory.TASK_QUEUE)
        self.assertTrue(out_task.is_high_confidence)

        # Code editing
        out_code = await client.decide("refactor the auth middleware to use JWT")
        self.assertEqual(out_code.category, JevCategory.CODE_EDIT)
        self.assertTrue(out_code.is_high_confidence)

        # Chat greeting
        out_chat = await client.decide("hello how are you today?")
        self.assertEqual(out_chat.category, JevCategory.CHAT_CONVERSATION)
        self.assertTrue(out_chat.is_high_confidence)

    async def test_positive_live_api_successful_decision(self):
        """Positive Path 2: Live API returns typed decision above confidence threshold."""
        client = JevClient(api_key="mock_secret_key_123", confidence_threshold=0.85)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "category": "code_edit",
            "confidence": 0.94,
            "suggested_action": "patch_source_code",
            "parameters": {"target": "gateway/telegram_bot.py"},
        }

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            outcome = await client.decide("fix typescript error in dashboard")
            self.assertEqual(outcome.category, JevCategory.CODE_EDIT)
            self.assertEqual(outcome.confidence, 0.94)
            self.assertTrue(outcome.is_high_confidence)
            self.assertFalse(outcome.requires_system_two)
            self.assertEqual(outcome.suggested_action, "patch_source_code")

    async def test_negative_low_confidence_fallback_to_system_two(self):
        """Negative Path 1: Confidence below threshold automatically forces System-Two fallback."""
        client = JevClient(api_key="mock_secret_key_123", confidence_threshold=0.85)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "category": "tool_execution",
            "confidence": 0.65,  # Below 0.85 threshold
            "suggested_action": "execute_shell",
        }

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            outcome = await client.decide("complex ambiguous directive with multiple tools")
            self.assertFalse(outcome.is_high_confidence)
            self.assertTrue(outcome.requires_system_two)
            self.assertEqual(outcome.reasoning_tier, "system_two_fallback")

    async def test_negative_empty_prompt_handling(self):
        """Negative Path 2: Empty or whitespace-only prompt requests clarification."""
        client = JevClient(api_key=None)
        outcome = await client.decide("   ")
        self.assertEqual(outcome.category, JevCategory.CLARIFICATION_NEEDED)
        self.assertEqual(outcome.confidence, 1.0)
        self.assertTrue(outcome.is_high_confidence)

    async def test_negative_api_error_graceful_fallback(self):
        """Negative Path 3: HTTP error or connection timeout triggers graceful agy fallback without crashing."""
        client = JevClient(api_key="mock_secret_key_123")

        mock_resp = MagicMock()
        mock_resp.status_code = 502
        mock_resp.text = "Bad Gateway"

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
            outcome = await client.decide("run build")
            self.assertEqual(outcome.category, JevCategory.FALLBACK_TO_AGY)
            self.assertTrue(outcome.requires_system_two)
            self.assertEqual(outcome.confidence, 0.0)

    async def test_positive_telegram_jev_command_dispatch(self):
        """Positive Path 3: Telegram /jev command evaluates query and sends formatted result."""
        bot = TelegramBot(token="fake:token")
        bot.send_message = AsyncMock(return_value=1234)

        await bot.handle_jev(chat_id=777, query="refactor auth middleware")
        bot.send_message.assert_called_once()
        sent_text = bot.send_message.call_args[0][1]
        self.assertIn("Jev AI Evaluation", sent_text)
        self.assertIn("code_edit", sent_text)
        self.assertIn("Routing Tier:", sent_text)

    async def test_negative_telegram_jev_empty_query_help(self):
        """Negative Path 4: Empty /jev command displays usage guidance."""
        bot = TelegramBot(token="fake:token")
        bot.send_message = AsyncMock(return_value=1234)

        await bot.handle_jev(chat_id=777, query="")
        bot.send_message.assert_called_once()
        sent_text = bot.send_message.call_args[0][1]
        self.assertIn("Usage: `/jev <prompt or instruction>`", sent_text)


if __name__ == "__main__":
    unittest.main()
