"""
Unit and integration tests for Fast-Path Conversational Context optimization.
Verifies prompt slimming, token reduction, and automatic context escalation.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from gemini_hermes.config import Config
from gemini_hermes.memory.store import MemoryStore
from gemini_hermes.skills.manager import SkillManager
from gemini_hermes.projects.manager import ProjectManager
from gemini_hermes.persona.system_prompt import (
    build_system_prompt,
    HERMES_FAST_PATH_INSTRUCTIONS,
    HERMES_BASE_INSTRUCTIONS,
)
from gemini_hermes.gateway.telegram_bot import TelegramBot
from gemini_hermes.gateway.runner import ExecutionRunner
from gemini_hermes.services.jev_service import JevService, JevReflexDecision
from gemini_hermes.brain.stream_parser import TokenDelta, ForwarderResult


@dataclass
class MockChoiceAnswer:
    choice: str
    confidence: float = 0.95


@dataclass
class MockScoreAnswer:
    score: float
    confidence: float = 0.85


@dataclass
class MockNoulAnswer:
    noul: float


@dataclass
class MockSystemOneResponse:
    answers: Dict[str, Any]


class TestFastPathConversationalContext(unittest.IsolatedAsyncioTestCase):
    """Test suite for Fast-Path Conversational Context."""

    def setUp(self):
        self.memory_store = MemoryStore()
        self.skill_manager = SkillManager()
        self.project_manager = ProjectManager()
        self.config = Config(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            typesafe_api_key="apik-test-key-mock",
            jev_enabled=True,
            jev_dynamic_effort=True,
            jev_dynamic_model=False,
            jev_fast_path=True,
            reasoning_effort="medium",
            stream_updates=True,
            jev_timeout=1.5,
        )

    # -------------------------------------------------------------------------
    # UNIT TESTS: PROMPT SLIMMING
    # -------------------------------------------------------------------------

    def test_fast_path_prompt_contains_user_profile_but_omits_heavy_catalogs(self):
        """Positive: fast_path=True keeps user profile & persona, omits skills & project index."""
        slim_prompt = build_system_prompt(
            self.memory_store,
            self.skill_manager,
            project_manager=self.project_manager,
            current_chat_id=8930156663,
            fast_path=True,
        )

        # Must include Hermes identity & User Profile (Arif's preferences)
        self.assertIn("Gemini-Hermes", slim_prompt)
        self.assertIn("<user_profile>", slim_prompt)
        self.assertIn("Telegram Chat ID: 8930156663", slim_prompt)

        # Must OMIT heavy engineering bloat
        self.assertNotIn("### Registered Skills Catalog", slim_prompt)
        self.assertNotIn("### Project State Index", slim_prompt)
        self.assertNotIn("<active_backlog>", slim_prompt)
        self.assertNotIn("<persistent_memory>", slim_prompt)

        # Size check: slim prompt should be significantly smaller (< 2,500 chars)
        self.assertLess(len(slim_prompt), 3000)

    def test_full_context_prompt_contains_all_engineering_layers(self):
        """Positive: fast_path=False retains all skills, memory, and project state."""
        full_prompt = build_system_prompt(
            self.memory_store,
            self.skill_manager,
            project_manager=self.project_manager,
            current_chat_id=8930156663,
            fast_path=False,
        )

        self.assertIn("Gemini-Hermes", full_prompt)
        self.assertIn("<user_profile>", full_prompt)
        self.assertIn("### Registered Skills Catalog", full_prompt)
        self.assertIn("<persistent_memory>", full_prompt)
        self.assertIn("<active_backlog>", full_prompt)

        # Size check: full prompt contains complete catalog
        self.assertGreater(len(full_prompt), 5000)

    # -------------------------------------------------------------------------
    # INTEGRATION TESTS: ROUTING & RUNNER BEHAVIOR
    # -------------------------------------------------------------------------

    async def test_casual_greeting_triggers_fast_path_in_runner(self):
        """Positive: Casual greeting triggers fast-path prompt and '--effort low'."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = MockSystemOneResponse(
            answers={
                "intent": MockChoiceAnswer(choice="casual_chat", confidence=0.99),
                "complexity": MockScoreAnswer(score=0.05, confidence=0.95),
                "needs_deep_reasoning": MockNoulAnswer(noul=0.01),
            }
        )
        jev_svc = JevService(cfg=self.config, client=mock_client)

        captured_prompts = []

        async def mock_forward_stream(prompt, conv_id=None, timeout=None, effort=None):
            captured_prompts.append({"prompt": prompt, "effort": effort})
            yield TokenDelta(text="Pagi Arif! Ada yang bisa dibantu?")
            yield ForwarderResult(
                response="Pagi Arif! Ada yang bisa dibantu?",
                status="success",
                conversation_id="conv-123",
            )

        mock_forwarder = MagicMock()
        mock_forwarder.forward_stream = mock_forward_stream

        bot = TelegramBot(token=self.config.bot_token, forwarder=mock_forwarder, jev_service=jev_svc)
        bot.send_chat_action = AsyncMock()
        bot.send_message = AsyncMock(return_value=2001)
        bot.edit_message_text = AsyncMock()

        with patch("gemini_hermes.gateway.runner.config", self.config):
            await ExecutionRunner.execute_turn(
                bot=bot,
                chat_id=8930156663,
                user_id=8930156663,
                user_text="selamat pagi hermes!",
            )

        self.assertEqual(len(captured_prompts), 1)
        sent = captured_prompts[0]
        # Verified: low effort
        self.assertEqual(sent["effort"], "low")
        # Verified: fast-path slim prompt (no skills catalog!)
        self.assertNotIn("### Registered Skills Catalog", sent["prompt"])
        self.assertIn("<user_profile>", sent["prompt"])

        # Verified: Status message displayed fast reflex
        first_send = bot.send_message.call_args_list[0]
        self.assertIn("(fast reflex)", first_send[0][1])

    async def test_engineering_task_escalates_to_full_context_in_runner(self):
        """Positive: Coding prompt escalates to full context with all skills and tools."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = MockSystemOneResponse(
            answers={
                "intent": MockChoiceAnswer(choice="code_engineering", confidence=0.98),
                "complexity": MockScoreAnswer(score=1.2, confidence=0.88),
                "needs_deep_reasoning": MockNoulAnswer(noul=0.65),
            }
        )
        jev_svc = JevService(cfg=self.config, client=mock_client)

        captured_prompts = []

        async def mock_forward_stream(prompt, conv_id=None, timeout=None, effort=None):
            captured_prompts.append({"prompt": prompt, "effort": effort})
            yield TokenDelta(text="Code explanation...")
            yield ForwarderResult(
                response="Code explanation...",
                status="success",
                conversation_id="conv-123",
            )

        mock_forwarder = MagicMock()
        mock_forwarder.forward_stream = mock_forward_stream

        bot = TelegramBot(token=self.config.bot_token, forwarder=mock_forwarder, jev_service=jev_svc)
        bot.send_chat_action = AsyncMock()
        bot.send_message = AsyncMock(return_value=2002)
        bot.edit_message_text = AsyncMock()

        with patch("gemini_hermes.gateway.runner.config", self.config):
            await ExecutionRunner.execute_turn(
                bot=bot,
                chat_id=8930156663,
                user_id=8930156663,
                user_text="Tolong buatkan unit test untuk database transaction rollback",
            )

        self.assertEqual(len(captured_prompts), 1)
        sent = captured_prompts[0]
        # Verified: medium effort
        self.assertEqual(sent["effort"], "medium")
        # Verified: FULL context with skills catalog
        self.assertIn("### Registered Skills Catalog", sent["prompt"])
        self.assertIn("<user_profile>", sent["prompt"])
        self.assertIn("<active_backlog>", sent["prompt"])


if __name__ == "__main__":
    unittest.main()
