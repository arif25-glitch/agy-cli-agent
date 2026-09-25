"""
Dual verification test suite for Autonomous Memory Pruning & Archiving across 2 Worlds.
Validates Pure Core deterministic backlog/notes pruning, Jev AI smart semantic pruning,
preservation of root operational directives, graceful fallbacks, and Telegram /compact handling.
"""
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import tempfile
import shutil
from pathlib import Path

from gemini_hermes.config import Config
from gemini_hermes.memory.store import MemoryStore
from gemini_hermes.memory.archiver import BacklogArchiver, MemoryNotesArchiver, MemoryPruner
from gemini_hermes.jev.client import JevClient, JevReflexDecision
from gemini_hermes.jev.memory_pruner import JevMemoryPruner
from gemini_hermes.jev.adapter import JevAdapter
from gemini_hermes.gateway.handlers.memory_handlers import handle_compact


class TestAutonomousMemoryPruning(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.memory_dir = Path(self.temp_dir) / "memory"
        self.sessions_dir = Path(self.temp_dir) / "sessions"
        self.memory_store = MemoryStore(memory_dir=self.memory_dir, sessions_dir=self.sessions_dir)
        self.chat_id = 554433

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Positive Test 1: Pure Core Backlog Archiving
    # -------------------------------------------------------------------------
    def test_pure_core_backlog_archiving_threshold(self):
        # Populate BACKLOG.md with 8 completed tasks and 2 active tasks
        backlog_lines = [
            "# Active Task Backlog & Operational Notes",
            "",
            "## Active Tasks",
            "- [ ] Active task Alpha",
            "- [ ] Active task Beta",
        ]
        for i in range(1, 9):
            backlog_lines.append(f"- [x] Completed task #{i}")
        backlog_lines.extend(["", "## Operational Notes & Inquiries", "- Note 1"])

        self.memory_store.backlog_file.write_text("\n".join(backlog_lines), encoding="utf-8")

        res = BacklogArchiver.archive_completed_backlog(
            self.memory_store.backlog_file,
            self.memory_store.backlog_archive_file,
            keep_recent=5,
        )

        self.assertEqual(res["status"], "archived")
        self.assertEqual(res["archived_count"], 3)  # 8 - 5 = 3
        self.assertEqual(res["retained_count"], 5)
        self.assertEqual(res["active_count"], 2)

        # Verify BACKLOG_ARCHIVE.md on disk
        archive_content = self.memory_store.backlog_archive_file.read_text(encoding="utf-8")
        self.assertIn("Completed task #1", archive_content)
        self.assertIn("Completed task #2", archive_content)
        self.assertIn("Completed task #3", archive_content)

        # Verify hot BACKLOG.md retains recent 5 completed and both active
        new_backlog = self.memory_store.backlog_file.read_text(encoding="utf-8")
        self.assertIn("Active task Alpha", new_backlog)
        self.assertIn("Active task Beta", new_backlog)
        self.assertIn("Completed task #8", new_backlog)
        self.assertIn("Completed task #4", new_backlog)
        self.assertNotIn("Completed task #1", new_backlog)

    # -------------------------------------------------------------------------
    # Positive Test 2: Pure Core Memory Notes Archiving & Directives Preservation
    # -------------------------------------------------------------------------
    def test_pure_core_memory_notes_archiving_and_directive_integrity(self):
        # Populate MEMORY.md with core directives and 14 notes under ## Key Facts & Lessons
        for i in range(1, 15):
            self.memory_store.append_to_memory(f"Fact entry #{i} operational lesson")

        orig_mem = self.memory_store.memory_file.read_text(encoding="utf-8")
        self.assertIn("## System & Agent Directives", orig_mem)
        self.assertIn("## Operational Standards", orig_mem)
        self.assertIn("## Memory Scaling & Retention Protocol", orig_mem)

        res = MemoryNotesArchiver.archive_notes(
            self.memory_store.memory_file,
            self.memory_store.memory_archive_file,
            keep_recent=10,
        )

        self.assertEqual(res["status"], "archived")
        self.assertEqual(res["archived_count"], 4)  # 14 - 10 = 4
        self.assertEqual(res["retained_count"], 10)

        # Verify MEMORY_ARCHIVE.md contains archived notes
        archive_content = self.memory_store.memory_archive_file.read_text(encoding="utf-8")
        self.assertIn("Fact entry #1", archive_content)
        self.assertIn("Fact entry #4", archive_content)

        # Verify MEMORY.md still has all core directives 100% intact!
        new_mem = self.memory_store.memory_file.read_text(encoding="utf-8")
        self.assertIn("## System & Agent Directives", new_mem)
        self.assertIn("## Operational Standards", new_mem)
        self.assertIn("## Memory Scaling & Retention Protocol", new_mem)
        self.assertIn("Fact entry #14", new_mem)
        self.assertNotIn("Fact entry #1 ", new_mem)

    # -------------------------------------------------------------------------
    # Positive Test 3: Unified MemoryStore.autonomous_prune in Pure Core Mode
    # -------------------------------------------------------------------------
    async def test_unified_autonomous_prune_pure_core(self):
        # Add 7 completed tasks and 12 notes
        for i in range(1, 8):
            self.memory_store.append_to_backlog(f"[x] Milestone #{i}")
        for i in range(1, 13):
            self.memory_store.append_to_memory(f"Debug note #{i}")

        res = await self.memory_store.autonomous_prune(jev_adapter=None, keep_recent_backlog=5, max_notes=10)
        self.assertEqual(res["status"], "archived")
        self.assertEqual(res["mode"], "pure_core")
        self.assertEqual(res["backlog"]["archived_count"], 2)
        self.assertEqual(res["notes"]["archived_count"], 2)
        self.assertIn("Archived 2 completed tasks, 2 stale memory notes", res["summary"])

    # -------------------------------------------------------------------------
    # Positive Test 4: Jev Smart Semantic Memory Pruning
    # -------------------------------------------------------------------------
    async def test_jev_smart_semantic_memory_pruning(self):
        # Create notes: mix of transient debug notes and evergreen directives
        notes = [
            "- [2026-09-25 10:00:00] Ephemeral scratch debug test 1",
            "- [2026-09-25 10:01:00] Ephemeral scratch debug test 2",
            "- [2026-09-25 10:02:00] Ephemeral scratch debug test 3",
            "- [2026-09-25 10:03:00] Evergreen Rule: Always enforce strict type safety",
            "- [2026-09-25 10:04:00] Evergreen Rule: Maintain O(1) telemetry broadcasting",
        ]
        # Extend to 12 notes
        for i in range(4, 11):
            notes.append(f"- [2026-09-25 10:0{i}:00] Transient trial run #{i}")

        mem_content = f"{self.memory_store.get_long_term_memory()}\n\n## Key Facts & Lessons\n" + "\n".join(notes)
        self.memory_store.memory_file.write_text(mem_content, encoding="utf-8")

        mock_client = MagicMock(spec=JevClient)
        mock_client.is_available = True

        # Mock Jev decision: classifies scratch/transient as 'transient', evergreen as 'evergreen'
        async def mock_evaluate(text, custom_questions=None, timeout=None):
            dec = JevReflexDecision()
            ans = MagicMock()
            if "Evergreen" in text:
                ans.choice = "evergreen"
                ans.confidence = 0.95
            else:
                ans.choice = "transient"
                ans.confidence = 0.90
            dec.raw_answers = {"retention_type": ans}
            return dec

        mock_client.evaluate_reflex = AsyncMock(side_effect=mock_evaluate)

        pruner = JevMemoryPruner(mock_client, min_confidence=0.70)
        adapter = JevAdapter(cfg=Config(jev_enabled=True), client=mock_client)
        adapter.memory_pruner = pruner

        res = await self.memory_store.autonomous_prune(
            jev_adapter=adapter, keep_recent_backlog=5, max_notes=5
        )

        self.assertEqual(res["status"], "archived")
        self.assertEqual(res["mode"], "jev_smart")
        self.assertGreater(res["notes"]["archived_count"], 0)

        # Check that evergreen rules were kept in MEMORY.md
        current_mem = self.memory_store.memory_file.read_text(encoding="utf-8")
        self.assertIn("Evergreen Rule: Always enforce strict type safety", current_mem)
        self.assertIn("Evergreen Rule: Maintain O(1) telemetry broadcasting", current_mem)

    # -------------------------------------------------------------------------
    # Positive Test 5: Telegram /compact Handler Reporting
    # -------------------------------------------------------------------------
    async def test_handle_compact_telegram_reporting(self):
        mock_bot = MagicMock()
        mock_bot.memory_store = self.memory_store
        mock_bot.jev_adapter = None
        mock_bot.send_message = AsyncMock()

        # Add items requiring pruning
        for i in range(1, 8):
            self.memory_store.append_to_backlog(f"[x] Milestone #{i}")

        await handle_compact(mock_bot, self.chat_id)
        mock_bot.send_message.assert_called_once()
        msg_text = mock_bot.send_message.call_args[0][1]

        self.assertIn("Memory Compaction & Tiering Complete", msg_text)
        self.assertIn("Archived Completed Tasks", msg_text)
        self.assertIn("Pure Core Deterministic", msg_text)

    # -------------------------------------------------------------------------
    # Negative Test 1: Jev Unavailable Fallback to Pure Core
    # -------------------------------------------------------------------------
    async def test_jev_unavailable_fallback_to_pure_core(self):
        # Add tasks to trigger pruning
        for i in range(1, 8):
            self.memory_store.append_to_backlog(f"[x] Milestone #{i}")

        mock_adapter = MagicMock(spec=JevAdapter)
        mock_adapter.is_available = False

        res = await self.memory_store.autonomous_prune(jev_adapter=mock_adapter, keep_recent_backlog=5)
        self.assertEqual(res["status"], "archived")
        self.assertEqual(res["mode"], "pure_core")
        self.assertEqual(res["backlog"]["archived_count"], 2)

    # -------------------------------------------------------------------------
    # Negative Test 2: Jev Exception/Timeout Fallback to Pure Core
    # -------------------------------------------------------------------------
    async def test_jev_exception_fallback_to_pure_core(self):
        for i in range(1, 8):
            self.memory_store.append_to_backlog(f"[x] Milestone #{i}")

        mock_adapter = MagicMock(spec=JevAdapter)
        mock_adapter.is_available = True
        mock_adapter.prune_memory = AsyncMock(side_effect=TimeoutError("Jev API timeout"))

        res = await self.memory_store.autonomous_prune(jev_adapter=mock_adapter, keep_recent_backlog=5)
        self.assertEqual(res["status"], "archived")
        self.assertEqual(res["mode"], "pure_core")
        self.assertEqual(res["backlog"]["archived_count"], 2)

    # -------------------------------------------------------------------------
    # Negative Test 3: Idempotency & Clean Empty/Under-Threshold Handling
    # -------------------------------------------------------------------------
    async def test_idempotent_noop_when_under_threshold(self):
        # Empty / default memory files
        res = await self.memory_store.autonomous_prune(jev_adapter=None, keep_recent_backlog=5, max_notes=10)
        self.assertEqual(res["status"], "noop")
        self.assertEqual(res["total_archived"], 0)

        # Run again
        res2 = await self.memory_store.autonomous_prune(jev_adapter=None, keep_recent_backlog=5, max_notes=10)
        self.assertEqual(res2["status"], "noop")


if __name__ == "__main__":
    unittest.main()
