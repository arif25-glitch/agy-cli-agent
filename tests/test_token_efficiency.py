"""
Dual verification test suite for Token Efficiency, Differential Prompting,
Jev JIT Skill Activation, and Context Checkpointing.
"""
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import tempfile
import shutil
from pathlib import Path

from gemini_hermes.config import Config
from gemini_hermes.memory.store import MemoryStore
from gemini_hermes.memory.session_store import SessionStore
from gemini_hermes.skills.manager import SkillManager
from gemini_hermes.persona.system_prompt import (
    build_system_prompt,
    HERMES_BASE_INSTRUCTIONS,
    HERMES_FOLLOWUP_INSTRUCTIONS,
    HERMES_FAST_PATH_INSTRUCTIONS,
)
from gemini_hermes.jev.client import JevClient, JevReflexDecision
from gemini_hermes.jev.skill_selector import JevSkillSelector
from gemini_hermes.jev.adapter import JevAdapter


class TestTokenEfficiencyAndPromptOptimization(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.memory_dir = Path(self.temp_dir) / "memory"
        self.sessions_dir = Path(self.temp_dir) / "sessions"
        self.skills_dir = Path(self.temp_dir) / "skills"

        self.memory_store = MemoryStore(memory_dir=self.memory_dir, sessions_dir=self.sessions_dir)
        self.skill_manager = SkillManager(custom_skills_dir=self.skills_dir)
        self.chat_id = 123456

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Positive Test 1: Differential Prompting (Initial vs Follow-up)
    # -------------------------------------------------------------------------
    def test_initial_turn_builds_full_prompt(self):
        prompt = build_system_prompt(
            self.memory_store,
            self.skill_manager,
            current_chat_id=self.chat_id,
            is_followup=False,
        )
        self.assertIn("You are Gemini-Hermes", prompt)
        self.assertIn("### Core Architecture & Behavior", prompt)
        self.assertIn("<persistent_memory>", prompt)
        self.assertIn("### Registered Skills Catalog", prompt)
        self.assertIn("### Session Context", prompt)

    def test_followup_turn_builds_compact_differential_prompt(self):
        # Update session to turn 2
        self.memory_store.update_session(self.chat_id, conversation_id="conv-abc", input_tokens=5000, output_tokens=300)

        initial_prompt = build_system_prompt(
            self.memory_store,
            self.skill_manager,
            current_chat_id=self.chat_id,
            is_followup=False,
        )
        followup_prompt = build_system_prompt(
            self.memory_store,
            self.skill_manager,
            current_chat_id=self.chat_id,
            is_followup=True,
        )

        # Follow-up should NOT have giant base instruction or full static skills catalog
        self.assertIn("### Gemini-Hermes Active Session Continuity", followup_prompt)
        self.assertNotIn("### Core Architecture & Behavior", followup_prompt)
        self.assertNotIn("### Registered Skills Catalog", followup_prompt)

        # Huge token savings: followup prompt must be at least 60% smaller than initial prompt
        self.assertLess(len(followup_prompt), len(initial_prompt) * 0.40)

    # -------------------------------------------------------------------------
    # Positive Test 2: Cache Prefix Stabilization
    # -------------------------------------------------------------------------
    def test_cache_prefix_stabilization(self):
        prompt = build_system_prompt(
            self.memory_store,
            self.skill_manager,
            current_chat_id=self.chat_id,
            is_followup=False,
        )
        # Static base instruction MUST be at the very top (index 0)
        self.assertTrue(prompt.startswith("You are Gemini-Hermes"))
        # Dynamic Session Context MUST be at the bottom
        self.assertTrue(prompt.rstrip().endswith(f"Turn Count: 0"))

    # -------------------------------------------------------------------------
    # Positive Test 3: JIT Skill Filtering in SkillManager
    # -------------------------------------------------------------------------
    def test_skill_manager_subset_rendering(self):
        # All skills
        full_summary = self.skill_manager.render_skills_summary(skills_subset=None)
        self.assertIn("Available Skills", full_summary)
        self.assertIn("api_tester", full_summary)
        self.assertIn("auto_debugger", full_summary)

        # Filtered to single skill
        single_summary = self.skill_manager.render_skills_summary(skills_subset=["auto_debugger"])
        self.assertIn("auto_debugger", single_summary)
        self.assertNotIn("api_tester", single_summary)

        # Explicitly empty list (0 skills injected)
        empty_summary = self.skill_manager.render_skills_summary(skills_subset=[])
        self.assertEqual(empty_summary, "")

    # -------------------------------------------------------------------------
    # Positive Test 4: Jev JIT Skill Selector
    # -------------------------------------------------------------------------
    async def test_jev_skill_selector_activated_skill(self):
        mock_client = MagicMock(spec=JevClient)
        mock_client.is_available = True

        decision = JevReflexDecision(latency_ms=120.0)
        ans_mock = MagicMock()
        ans_mock.choice = "auto_debugger"
        ans_mock.confidence = 0.92
        decision.raw_answers = {"skill_match": ans_mock}

        mock_client.evaluate_reflex = AsyncMock(return_value=decision)

        selector = JevSkillSelector(mock_client, min_confidence=0.70)
        available = self.skill_manager.get_all_skills()

        selected = await selector.select_skills("Fix this python traceback exception", available)
        self.assertEqual(selected, ["auto_debugger"])

    async def test_jev_skill_selector_none_for_general_chat(self):
        mock_client = MagicMock(spec=JevClient)
        mock_client.is_available = True

        decision = JevReflexDecision(latency_ms=85.0)
        ans_mock = MagicMock()
        ans_mock.choice = "none"
        ans_mock.confidence = 0.95
        decision.raw_answers = {"skill_match": ans_mock}

        mock_client.evaluate_reflex = AsyncMock(return_value=decision)

        selector = JevSkillSelector(mock_client, min_confidence=0.70)
        available = self.skill_manager.get_all_skills()

        selected = await selector.select_skills("How is the weather today?", available)
        self.assertEqual(selected, [])

    # -------------------------------------------------------------------------
    # Positive Test 5: Session Rotation & Context Bridge Checkpointing
    # -------------------------------------------------------------------------
    def test_session_rotation_threshold_and_bridge(self):
        # 1. Below threshold: should not rotate
        self.memory_store.update_session(self.chat_id, conversation_id="conv-1", input_tokens=10000)
        self.assertFalse(self.memory_store.session_store.should_rotate_session(self.chat_id, max_tokens=50000, max_turns=15))

        # 2. Exceed token threshold: should rotate
        self.memory_store.update_session(self.chat_id, conversation_id="conv-1", input_tokens=45000)
        self.assertTrue(self.memory_store.session_store.should_rotate_session(self.chat_id, max_tokens=50000, max_turns=15))

        # 3. Rotate session with context bridge
        bridge_msg = "Completed database migration script; active focus is adding unit tests."
        rotated = self.memory_store.session_store.rotate_session_with_bridge(self.chat_id, bridge_summary=bridge_msg)

        # Verify session tokens reset, lifetime preserved
        self.assertIsNone(rotated["conversation_id"])
        self.assertEqual(rotated["turn_count"], 0)
        self.assertEqual(rotated["session_input_tokens"], 0)
        self.assertEqual(rotated["total_input_tokens"], 55000)
        self.assertEqual(rotated["lifetime_turns"], 2)

        # 4. Pop context bridge
        retrieved_bridge = self.memory_store.session_store.pop_context_bridge(self.chat_id)
        self.assertEqual(retrieved_bridge, bridge_msg)
        # Should be None after popping
        self.assertIsNone(self.memory_store.session_store.pop_context_bridge(self.chat_id))

        # 5. Build Turn 1 prompt of new session with context bridge
        prompt = build_system_prompt(
            self.memory_store,
            self.skill_manager,
            current_chat_id=self.chat_id,
            is_followup=False,
            context_bridge_summary=bridge_msg,
        )
        self.assertIn("### Context Bridge (Resumed State)", prompt)
        self.assertIn(bridge_msg, prompt)

    # -------------------------------------------------------------------------
    # Negative & Edge Cases
    # -------------------------------------------------------------------------
    async def test_jev_skill_selector_unavailable_or_timeout_fallback(self):
        mock_client = MagicMock(spec=JevClient)
        mock_client.is_available = False
        selector = JevSkillSelector(mock_client)
        self.assertIsNone(await selector.select_skills("test", {"a": "desc"}))

        # Timeout simulation
        mock_client.is_available = True
        mock_client.evaluate_reflex = AsyncMock(side_effect=TimeoutError("Timeout"))
        self.assertIsNone(await selector.select_skills("test", {"a": "desc"}))

    def test_session_rotation_on_idle_or_missing_session(self):
        # Chat ID with no active conversation_id should never trigger rotation
        self.assertFalse(self.memory_store.session_store.should_rotate_session(999999))
        # Popping bridge from empty session returns None safely
        self.assertIsNone(self.memory_store.session_store.pop_context_bridge(999999))

    def test_fast_path_eligibility_positive_and_negative(self):
        adapter = JevAdapter(cfg=Config(typesafe_api_key="ts-test", jev_enabled=True, jev_dynamic_effort=True, jev_fast_path=True))
        # Positive: low effort, casual chat intent, no deep reasoning
        dec_pos = JevReflexDecision(intent="casual_chat", needs_deep_reasoning=False)
        self.assertTrue(adapter.is_fast_path_eligible(dec_pos, "low"))

        # Negative 1: medium/high effort
        self.assertFalse(adapter.is_fast_path_eligible(dec_pos, "medium"))
        self.assertFalse(adapter.is_fast_path_eligible(dec_pos, "high"))

        # Negative 2: complex intent or needs deep reasoning
        dec_complex = JevReflexDecision(intent="coding", needs_deep_reasoning=True)
        self.assertFalse(adapter.is_fast_path_eligible(dec_complex, "low"))

        # Negative 3: disabled when jev_fast_path is False
        adapter_disabled = JevAdapter(cfg=Config(typesafe_api_key="ts-test", jev_enabled=True, jev_dynamic_effort=True, jev_fast_path=False))
        self.assertFalse(adapter_disabled.is_fast_path_eligible(dec_pos, "low"))


if __name__ == "__main__":
    unittest.main()

