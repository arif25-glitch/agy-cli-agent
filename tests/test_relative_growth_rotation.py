"""
Dual verification test suite for Dynamic / Relative Growth Rotation.
Verifies baseline tracking, relative context growth, minimum turns guardrails,
and permanent prevention of the single-turn rotation loop.
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
from gemini_hermes.persona.system_prompt import build_system_prompt


class TestRelativeGrowthRotation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.memory_dir = Path(self.temp_dir) / "memory"
        self.sessions_dir = Path(self.temp_dir) / "sessions"
        self.memory_store = MemoryStore(memory_dir=self.memory_dir, sessions_dir=self.sessions_dir)
        self.session_store = self.memory_store.session_store
        self.chat_id = 998877

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Positive Test 1: Breaking the Single-Turn Rotation Loop on Large Initial Prompts
    # -------------------------------------------------------------------------
    def test_large_initial_prompt_does_not_rotate_on_turn_2(self):
        """
        CRITICAL TEST: If a session begins with a large initial prompt (e.g. 55,000 tokens),
        the old logic rotated immediately on Turn 2, causing an infinite rotation loop.
        Relative growth with min_turns=2 guarantees Turn 2 does NOT rotate!
        """
        # Turn 1: 55k input tokens
        self.session_store.update_session(
            self.chat_id, conversation_id="conv-large-1", input_tokens=55000, output_tokens=500
        )
        sess = self.session_store.get_session(self.chat_id)
        self.assertEqual(sess["session_baseline_tokens"], 55000)
        self.assertEqual(sess["turn_count"], 1)

        # Before Turn 2: should_rotate_session is evaluated
        # Under old logic: 55,000 >= 50,000 -> True (BUG: Rotation loop!)
        # Under new logic: turns=1 < min_turns=2, growth=0 -> False (FIXED!)
        should_rotate = self.session_store.should_rotate_session(
            self.chat_id,
            max_tokens=50000,
            max_turns=15,
            min_turns=2,
            max_growth_tokens=40000,
            growth_ratio=2.0,
            hard_max_tokens=120000,
        )
        self.assertFalse(should_rotate, "Must NOT rotate on Turn 2 despite exceeding 50k tokens!")

        # Turn 2: Adds 3,000 tokens (now 58,000 tokens)
        self.session_store.update_session(
            self.chat_id, conversation_id="conv-large-1", input_tokens=58000, output_tokens=400
        )
        sess = self.session_store.get_session(self.chat_id)
        self.assertEqual(sess["turn_count"], 2)

        # Before Turn 3: growth = 58,000 - 55,000 = 3,000 (well under 40k growth limit)
        should_rotate_turn_3 = self.session_store.should_rotate_session(
            self.chat_id,
            max_tokens=50000,
            max_turns=15,
            min_turns=2,
            max_growth_tokens=40000,
            growth_ratio=2.0,
            hard_max_tokens=120000,
        )
        self.assertFalse(should_rotate_turn_3, "Must NOT rotate when relative growth is only 3,000 tokens!")

    # -------------------------------------------------------------------------
    # Positive Test 2: Rotates When Relative Growth Limit is Exceeded
    # -------------------------------------------------------------------------
    def test_rotates_when_relative_growth_exceeded(self):
        """
        When context actually grows by more than max_growth_tokens (e.g. +40,000)
        relative to the session baseline, rotation must trigger cleanly.
        """
        # Turn 1: 15,000 tokens baseline
        self.session_store.update_session(
            self.chat_id, conversation_id="conv-rel-1", input_tokens=15000
        )
        self.assertEqual(self.session_store.get_session(self.chat_id)["session_baseline_tokens"], 15000)

        # Turn 2: Context expands to 60,000 tokens (growth = 45,000 >= 40,000)
        self.session_store.update_session(
            self.chat_id, conversation_id="conv-rel-1", input_tokens=60000
        )
        sess = self.session_store.get_session(self.chat_id)
        self.assertEqual(sess["turn_count"], 2)

        should_rotate = self.session_store.should_rotate_session(
            self.chat_id,
            max_tokens=50000,
            max_turns=15,
            min_turns=2,
            max_growth_tokens=40000,
        )
        self.assertTrue(should_rotate, "Should rotate when context grew by 45,000 tokens beyond baseline!")

    # -------------------------------------------------------------------------
    # Positive Test 3: Rotates When Turn Limit is Reached
    # -------------------------------------------------------------------------
    def test_rotates_when_turn_limit_reached(self):
        # Turn 1
        self.session_store.update_session(
            self.chat_id, conversation_id="conv-turns-1", input_tokens=5000
        )
        # Advance turns to 15
        for _ in range(14):
            self.session_store.update_session(
                self.chat_id, conversation_id="conv-turns-1", input_tokens=5000
            )

        sess = self.session_store.get_session(self.chat_id)
        self.assertEqual(sess["turn_count"], 15)

        should_rotate = self.session_store.should_rotate_session(
            self.chat_id,
            max_tokens=50000,
            max_turns=15,
            min_turns=2,
        )
        self.assertTrue(should_rotate, "Should rotate when max_turns ceiling (15) is reached!")

    # -------------------------------------------------------------------------
    # Positive Test 4: Hard Ceiling Safety Valve
    # -------------------------------------------------------------------------
    def test_hard_ceiling_safety_valve(self):
        """
        Even on Turn 1, if context breaches the hard max ceiling (e.g. 125,000 tokens),
        it must rotate immediately to prevent model context window overflow.
        """
        self.session_store.update_session(
            self.chat_id, conversation_id="conv-huge-1", input_tokens=130000
        )
        should_rotate = self.session_store.should_rotate_session(
            self.chat_id,
            max_tokens=50000,
            max_turns=15,
            min_turns=2,
            hard_max_tokens=120000,
        )
        self.assertTrue(should_rotate, "Must rotate when hard token ceiling (120,000) is breached!")

    # -------------------------------------------------------------------------
    # Positive Test 5: Context Bridge Handover on Relative Growth Rotation
    # -------------------------------------------------------------------------
    def test_rotation_resets_session_baseline_and_preserves_bridge(self):
        self.session_store.update_session(
            self.chat_id, conversation_id="conv-bridge-1", input_tokens=30000, output_tokens=500
        )
        self.session_store.update_session(
            self.chat_id, conversation_id="conv-bridge-1", input_tokens=75000, output_tokens=500
        )

        bridge_text = "Continuing backend auth refactor. Next step is JWT signing."
        rotated = self.session_store.rotate_session_with_bridge(self.chat_id, bridge_summary=bridge_text)

        self.assertIsNone(rotated["conversation_id"])
        self.assertEqual(rotated["turn_count"], 0)
        self.assertEqual(rotated["session_input_tokens"], 0)
        self.assertEqual(rotated["session_baseline_tokens"], 0)
        self.assertEqual(rotated["last_turn_input_tokens"], 0)
        self.assertEqual(rotated["total_input_tokens"], 105000)
        self.assertEqual(rotated["lifetime_turns"], 2)

        popped = self.session_store.pop_context_bridge(self.chat_id)
        self.assertEqual(popped, bridge_text)

    # -------------------------------------------------------------------------
    # Negative Test 1: Inactive or Missing Session Returns False
    # -------------------------------------------------------------------------
    def test_missing_or_inactive_session_returns_false(self):
        # Non-existent session
        self.assertFalse(self.session_store.should_rotate_session(111222))

        # Session exists but has no active conversation_id
        self.session_store.reset_session(self.chat_id)
        self.assertFalse(self.session_store.should_rotate_session(self.chat_id))

    # -------------------------------------------------------------------------
    # Negative Test 2: Reset Session Cleans Baseline and Tokens
    # -------------------------------------------------------------------------
    def test_reset_session_clears_baseline_and_last_turn(self):
        self.session_store.update_session(
            self.chat_id, conversation_id="conv-reset-1", input_tokens=40000
        )
        sess = self.session_store.get_session(self.chat_id)
        self.assertEqual(sess["session_baseline_tokens"], 40000)
        self.assertEqual(sess["last_turn_input_tokens"], 40000)

        self.session_store.reset_session(self.chat_id)
        reset_sess = self.session_store.get_session(self.chat_id)
        self.assertIsNone(reset_sess["conversation_id"])
        self.assertEqual(reset_sess["session_baseline_tokens"], 0)
        self.assertEqual(reset_sess["last_turn_input_tokens"], 0)
        self.assertEqual(reset_sess["turn_count"], 0)


if __name__ == "__main__":
    unittest.main()
