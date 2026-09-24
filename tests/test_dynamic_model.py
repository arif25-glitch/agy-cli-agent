"""
Dual-verification test suite for Jev AI System-One Dynamic Model Selection.
Validates both positive routing paths (Tier 1-4, Jev Choice overrides, Runner execution)
and negative resilience paths (timeouts, API errors, invalid models, disabled mode).
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from gemini_hermes.config import Config
from gemini_hermes.services.jev_service import JevService, JevReflexDecision
from gemini_hermes.brain.agy_forwarder import AgyForwarder
from gemini_hermes.brain.stream_parser import TokenDelta, ForwarderResult
from gemini_hermes.gateway.runner import ExecutionRunner
from gemini_hermes.gateway.telegram_bot import TelegramBot
from gemini_hermes.gateway.handlers.system_handlers import handle_model


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


class TestDynamicModelSelection(unittest.IsolatedAsyncioTestCase):
    """Rigorous dual-verification test suite for dynamic model selection."""

    def setUp(self):
        self.mock_config = Config(
            typesafe_api_key="apik-test-key-model",
            jev_enabled=True,
            jev_dynamic_effort=True,
            jev_dynamic_model=True,
            agy_model="gemini-3.7-flash",
            reasoning_effort="medium",
            jev_timeout=1.5,
        )

    # -------------------------------------------------------------------------
    # POSITIVE PATHS: TIER 1 - 4 CALIBRATION & JEV CHOICES
    # -------------------------------------------------------------------------

    async def test_positive_tier1_simple_interaction_selects_3_6_flash_low(self):
        """Positive: Trivial interaction (< 0.6 complexity) selects cheap gemini-3.6-flash + low effort."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = MockSystemOneResponse(
            answers={
                "intent": MockChoiceAnswer(choice="casual_chat", confidence=0.99),
                "complexity": MockScoreAnswer(score=0.15, confidence=0.95),
                "needs_deep_reasoning": MockNoulAnswer(noul=0.02),
            }
        )
        svc = JevService(cfg=self.mock_config, client=mock_client)
        model, effort, decision = await svc.select_model_and_effort("halo hermes apa kabar?")

        self.assertEqual(model, "gemini-3.6-flash")
        self.assertEqual(effort, "low")
        self.assertIsNotNone(decision)
        self.assertEqual(decision.recommended_model, "gemini-3.6-flash")

    async def test_positive_tier2_moderate_task_selects_3_7_flash_medium(self):
        """Positive: Moderate coding / debugging task selects balanced gemini-3.7-flash + medium effort."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = MockSystemOneResponse(
            answers={
                "intent": MockChoiceAnswer(choice="code_engineering", confidence=0.95),
                "complexity": MockScoreAnswer(score=1.1, confidence=0.85),
                "needs_deep_reasoning": MockNoulAnswer(noul=0.45),
            }
        )
        svc = JevService(cfg=self.mock_config, client=mock_client)
        model, effort, decision = await svc.select_model_and_effort("tulis fungsi parser json sederhana")

        self.assertEqual(model, "gemini-3.7-flash")
        self.assertEqual(effort, "medium")
        self.assertIsNotNone(decision)
        self.assertEqual(decision.recommended_model, "gemini-3.7-flash")

    async def test_positive_tier3_high_workload_selects_3_8_flash_high(self):
        """Positive: High workload / complex architecture selects gemini-3.8-flash + high effort."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = MockSystemOneResponse(
            answers={
                "intent": MockChoiceAnswer(choice="code_engineering", confidence=0.98),
                "complexity": MockScoreAnswer(score=1.65, confidence=0.90),
                "needs_deep_reasoning": MockNoulAnswer(noul=0.88),
            }
        )
        svc = JevService(cfg=self.mock_config, client=mock_client)
        model, effort, decision = await svc.select_model_and_effort(
            "refactor the entire async event loop across all 15 gateway modules"
        )

        self.assertEqual(model, "gemini-3.8-flash")
        self.assertEqual(effort, "high")
        self.assertIsNotNone(decision)
        self.assertEqual(decision.recommended_model, "gemini-3.8-flash")

    async def test_positive_tier4_extreme_reasoning_selects_3_1_pro_high(self):
        """Positive: Deep algorithmic / mathematical proof selects gemini-3.1-pro + high effort."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = MockSystemOneResponse(
            answers={
                "intent": MockChoiceAnswer(choice="code_engineering", confidence=0.99),
                "complexity": MockScoreAnswer(score=1.92, confidence=0.95),
                "needs_deep_reasoning": MockNoulAnswer(noul=0.96),
            }
        )
        svc = JevService(cfg=self.mock_config, client=mock_client)
        model, effort, decision = await svc.select_model_and_effort(
            "prove formal algorithmic convergence for distributed Paxos consensus"
        )

        self.assertEqual(model, "gemini-3.1-pro")
        self.assertEqual(effort, "high")
        self.assertIsNotNone(decision)
        self.assertEqual(decision.recommended_model, "gemini-3.1-pro")

    async def test_positive_explicit_model_tier_choice_override(self):
        """Positive: Jev explicit model_tier Choice takes priority when confidence >= 0.70."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = MockSystemOneResponse(
            answers={
                "intent": MockChoiceAnswer(choice="code_engineering", confidence=0.95),
                "complexity": MockScoreAnswer(score=1.0, confidence=0.80),
                "needs_deep_reasoning": MockNoulAnswer(noul=0.50),
                "model_tier": MockChoiceAnswer(choice="tier_3_8_flash", confidence=0.92),
            }
        )
        svc = JevService(cfg=self.mock_config, client=mock_client)
        model, effort, decision = await svc.select_model_and_effort("heavy batch processing script")

        self.assertEqual(model, "gemini-3.8-flash")
        self.assertEqual(effort, "high")
        self.assertEqual(decision.model_tier, "tier_3_8_flash")

    # -------------------------------------------------------------------------
    # POSITIVE PATHS: FORWARDER & RUNNER WIRING
    # -------------------------------------------------------------------------

    def test_positive_agy_forwarder_builds_model_flag(self):
        """Positive: AgyForwarder._build_command includes --model flag correctly."""
        forwarder = AgyForwarder(agy_model="gemini-3.7-flash", reasoning_effort="medium")

        # Default model from config
        cmd = forwarder._build_command("ping prompt")
        self.assertIn("--model", cmd)
        m_idx = cmd.index("--model")
        self.assertEqual(cmd[m_idx + 1], "gemini-3.7-flash")

        # Dynamic override for Tier 1
        cmd_36 = forwarder._build_command("ping prompt", model="gemini-3.6-flash", effort="low")
        m_idx = cmd_36.index("--model")
        e_idx = cmd_36.index("--effort")
        self.assertEqual(cmd_36[m_idx + 1], "gemini-3.6-flash")
        self.assertEqual(cmd_36[e_idx + 1], "low")

        # Dynamic override for Tier 3
        cmd_38 = forwarder._build_command("ping prompt", model="gemini-3.8-flash", effort="high")
        m_idx = cmd_38.index("--model")
        e_idx = cmd_38.index("--effort")
        self.assertEqual(cmd_38[m_idx + 1], "gemini-3.8-flash")
        self.assertEqual(cmd_38[e_idx + 1], "high")

    async def test_positive_execution_runner_passes_dynamic_model(self):
        """Positive: ExecutionRunner invokes Jev, selects 3.8 flash, passes to forwarder and tags status."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = MockSystemOneResponse(
            answers={
                "intent": MockChoiceAnswer(choice="code_engineering", confidence=0.95),
                "complexity": MockScoreAnswer(score=1.6, confidence=0.88),
                "needs_deep_reasoning": MockNoulAnswer(noul=0.86),
            }
        )
        jev_svc = JevService(cfg=self.mock_config, client=mock_client)

        forwarder_calls = []

        async def mock_forward_stream(prompt, conv_id=None, timeout=None, effort=None, model=None):
            forwarder_calls.append({"model": model, "effort": effort})
            yield TokenDelta(text="Executing high-workload task...")
            yield ForwarderResult(response="Done", status="success", conversation_id="conv-dyn")

        mock_forwarder = MagicMock()
        mock_forwarder.forward_stream = mock_forward_stream

        bot = TelegramBot(token="123:test", forwarder=mock_forwarder, jev_service=jev_svc)
        bot.send_chat_action = AsyncMock()
        bot.send_message = AsyncMock(return_value=1001)
        bot.edit_message_text = AsyncMock()

        with patch("gemini_hermes.gateway.runner.config", self.mock_config):
            await ExecutionRunner.execute_turn(
                bot=bot,
                chat_id=12345,
                user_id=8930156663,
                user_text="Refactor all database models and wire async transaction pool",
            )

        # Assert forward_stream received gemini-3.8-flash and high effort
        self.assertEqual(len(forwarder_calls), 1)
        self.assertEqual(forwarder_calls[0]["model"], "gemini-3.8-flash")
        self.assertEqual(forwarder_calls[0]["effort"], "high")

        # Assert thinking message included model tag and high effort
        first_send = bot.send_message.call_args_list[0]
        status_msg = first_send[0][1]
        self.assertIn("[gemini-3.8-flash]", status_msg)
        self.assertIn("(high effort)", status_msg)

    # -------------------------------------------------------------------------
    # POSITIVE PATHS: TELEGRAM /model COMMAND & ALIASES
    # -------------------------------------------------------------------------

    async def test_positive_telegram_model_command_status_view(self):
        """Positive: /model without arguments displays current model, dynamic mode, and tiers."""
        bot = MagicMock()
        bot.send_message = AsyncMock()

        with patch("gemini_hermes.gateway.handlers.system_handlers.config", self.mock_config):
            await handle_model(bot, chat_id=12345, arg="")

        bot.send_message.assert_called_once()
        msg = bot.send_message.call_args[0][1]
        self.assertIn("Active Default Model", msg)
        self.assertIn("Dynamic (Jev AI System-One Decision Machine)", msg)
        self.assertIn("gemini-3.6-flash", msg)
        self.assertIn("gemini-3.7-flash", msg)
        self.assertIn("gemini-3.8-flash", msg)
        self.assertIn("gemini-3.1-pro", msg)

    async def test_positive_telegram_model_command_switch_aliases(self):
        """Positive: /model with aliases (3.8, 3.6, pro) updates active config and forwarder."""
        bot = MagicMock()
        bot.send_message = AsyncMock()
        bot.forwarder = MagicMock()

        test_config = self.mock_config.model_copy()
        with patch("gemini_hermes.gateway.handlers.system_handlers.config", test_config):
            # Alias '3.8' -> 'gemini-3.8-flash'
            await handle_model(bot, chat_id=12345, arg="3.8")
            self.assertEqual(test_config.agy_model, "gemini-3.8-flash")
            self.assertEqual(bot.forwarder.agy_model, "gemini-3.8-flash")

            # Alias '3.6 flash' -> 'gemini-3.6-flash'
            await handle_model(bot, chat_id=12345, arg="3.6 flash")
            self.assertEqual(test_config.agy_model, "gemini-3.6-flash")

            # Alias 'pro' -> 'gemini-3.1-pro'
            await handle_model(bot, chat_id=12345, arg="pro")
            self.assertEqual(test_config.agy_model, "gemini-3.1-pro")

    # -------------------------------------------------------------------------
    # NEGATIVE & RESILIENCE PATHS: TIMEOUT, ERRORS, INVALID MODELS
    # -------------------------------------------------------------------------

    async def test_negative_timeout_fallback_to_default_model(self):
        """Negative: Jev timeout gracefully falls back to default model and effort."""
        mock_client = AsyncMock()

        async def slow_reflex(*args, **kwargs):
            await asyncio.sleep(0.3)
            return MockSystemOneResponse(answers={})

        mock_client.system_one.side_effect = slow_reflex
        svc = JevService(cfg=self.mock_config, client=mock_client, default_timeout=0.05)

        model, effort, decision = await svc.select_model_and_effort(
            "complex prompt",
            default_model="gemini-3.7-flash",
            default_effort="medium",
            timeout=0.05,
        )

        self.assertEqual(model, "gemini-3.7-flash")
        self.assertEqual(effort, "medium")
        self.assertIsNone(decision)

    async def test_negative_api_error_fallback_to_default_model(self):
        """Negative: Jev API network/server error falls back to default model without throwing."""
        mock_client = AsyncMock()
        mock_client.system_one.side_effect = ConnectionResetError("Connection refused by peer")
        svc = JevService(cfg=self.mock_config, client=mock_client)

        model, effort, decision = await svc.select_model_and_effort(
            "some query",
            default_model="gemini-3.7-flash",
            default_effort="medium",
        )

        self.assertEqual(model, "gemini-3.7-flash")
        self.assertEqual(effort, "medium")
        self.assertIsNone(decision)

    async def test_negative_disabled_dynamic_model_never_calls_jev(self):
        """Negative: When jev_dynamic_model=False and jev_dynamic_effort=False, Jev is untouched."""
        mock_client = AsyncMock()
        disabled_config = self.mock_config.model_copy(
            update={"jev_dynamic_model": False, "jev_dynamic_effort": False}
        )
        svc = JevService(cfg=disabled_config, client=mock_client)

        # In runner or svc
        forwarder_calls = []

        async def mock_forward_stream(prompt, conv_id=None, timeout=None, effort=None, model=None):
            forwarder_calls.append({"model": model, "effort": effort})
            yield TokenDelta(text="Static response")
            yield ForwarderResult(response="Done", status="success", conversation_id="conv-static")

        mock_forwarder = MagicMock()
        mock_forwarder.forward_stream = mock_forward_stream

        bot = TelegramBot(token="123:test", forwarder=mock_forwarder, jev_service=svc)
        bot.send_chat_action = AsyncMock()
        bot.send_message = AsyncMock(return_value=1002)
        bot.edit_message_text = AsyncMock()

        with patch("gemini_hermes.gateway.runner.config", disabled_config):
            await ExecutionRunner.execute_turn(
                bot=bot,
                chat_id=12345,
                user_id=8930156663,
                user_text="Normal query",
            )

        mock_client.system_one.assert_not_called()
        self.assertEqual(len(forwarder_calls), 1)
        self.assertEqual(forwarder_calls[0]["model"], "gemini-3.7-flash")
        self.assertEqual(forwarder_calls[0]["effort"], "medium")

    async def test_negative_telegram_model_command_rejects_invalid_model(self):
        """Negative: /model rejects non-existent models and does not modify config."""
        bot = MagicMock()
        bot.send_message = AsyncMock()

        orig_model = self.mock_config.agy_model
        test_config = self.mock_config.model_copy()
        with patch("gemini_hermes.gateway.handlers.system_handlers.config", test_config):
            await handle_model(bot, chat_id=12345, arg="invalid-model-foo-bar")

        # Config should remain unchanged
        self.assertEqual(test_config.agy_model, orig_model)
        msg = bot.send_message.call_args[0][1]
        self.assertIn("Unknown model", msg)


if __name__ == "__main__":
    unittest.main()
