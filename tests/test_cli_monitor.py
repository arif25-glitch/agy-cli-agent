"""
Unit tests for CLI Terminal UI Monitor (gemini_hermes/cli_monitor.py)
and Telemetry Exporter (gemini_hermes/telemetry.py).
Validates positive rendering, negative resilience, and offline daemon detection.
"""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from gemini_hermes.cli_monitor import CliMonitor, format_token_count
from gemini_hermes.telemetry import TelemetryExporter
from gemini_hermes.memory.session_store import SessionStore


class TestCliMonitorAndTelemetry(unittest.TestCase):
    """Dual tests covering positive and negative paths for CLI monitor and token usage."""

    def test_format_token_count(self):
        """Positive and negative boundary checks for token count formatter."""
        self.assertEqual(format_token_count(0), "0")
        self.assertEqual(format_token_count(500), "500")
        self.assertEqual(format_token_count(1500), "1,500 (1.5k)")
        self.assertEqual(format_token_count(2500000), "2,500,000 (2.50M)")
        self.assertEqual(format_token_count(216288161), "216,288,161 (216.29M)")
        # Edge cases: bad input types
        self.assertEqual(format_token_count("invalid"), "0")
        self.assertEqual(format_token_count(None), "0")

    def test_session_store_token_aggregations(self):
        """Positive test: SessionStore correctly computes session and global token totals."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(Path(tmpdir))
            # Initially empty
            empty_total = store.get_total_token_usage()
            self.assertEqual(empty_total["total_tokens"], 0)
            self.assertEqual(empty_total["session_count"], 0)

            empty_sess = store.get_session_token_usage(123)
            self.assertEqual(empty_sess["total_tokens"], 0)

            # Update sessions
            store.update_session(chat_id=1001, input_tokens=1000, output_tokens=250)
            store.update_session(chat_id=1001, input_tokens=500, output_tokens=150)
            store.update_session(chat_id=1002, input_tokens=2000, output_tokens=800)

            total_stats = store.get_total_token_usage()
            self.assertEqual(total_stats["total_input_tokens"], 3500)
            self.assertEqual(total_stats["total_output_tokens"], 1200)
            self.assertEqual(total_stats["total_tokens"], 4700)
            self.assertEqual(total_stats["total_turns"], 3)
            self.assertEqual(total_stats["session_count"], 2)

            sess_1001 = store.get_session_token_usage(1001)
            self.assertEqual(sess_1001["input_tokens"], 1500)
            self.assertEqual(sess_1001["output_tokens"], 400)
            self.assertEqual(sess_1001["total_tokens"], 1900)
            self.assertEqual(sess_1001["turn_count"], 2)

            # Fallback to latest when chat_id not provided
            latest_sess = store.get_session_token_usage()
            self.assertIn(latest_sess["chat_id"], [1001, 1002])

    def test_telemetry_atomic_write_and_read(self):
        """Positive test: TelemetryExporter correctly writes and reads atomic JSON with tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_state_dir = Path(tmpdir)
            with patch("gemini_hermes.telemetry.STATE_DIR", test_state_dir), \
                 patch("gemini_hermes.telemetry.TELEMETRY_FILE", test_state_dir / "telemetry.json"):

                TelemetryExporter.record_state(
                    pid=12345,
                    is_running=True,
                    active_chat_id=8930156663,
                    active_task_preview="Run diagnostics and verification",
                    active_task_elapsed=5.2,
                    active_step="Agy Streaming",
                    reasoning_effort="high",
                    is_fast_path=False,
                    queue_depth=2,
                    queue_items=["task #1", "task #2"],
                    jev_enabled=True,
                    jev_latency_ms=640.5,
                    jev_complexity=1.85,
                    jev_decision="high",
                    session_tokens={"input_tokens": 5000, "output_tokens": 1200, "total_tokens": 6200},
                    global_tokens={"total_input_tokens": 50000, "total_output_tokens": 12000, "total_tokens": 62000, "session_count": 3},
                )

                state = TelemetryExporter.read_state()
                self.assertEqual(state.get("pid"), 12345)
                self.assertTrue(state.get("is_running"))
                self.assertEqual(state.get("active_chat_id"), 8930156663)
                self.assertEqual(state.get("reasoning_effort"), "high")
                self.assertEqual(state.get("queue_depth"), 2)
                self.assertEqual(state.get("jev", {}).get("latency_ms"), 640.5)
                self.assertEqual(state.get("tokens", {}).get("session", {}).get("total_tokens"), 6200)
                self.assertEqual(state.get("tokens", {}).get("global", {}).get("total_tokens"), 62000)

    def test_monitor_renders_cleanly_when_daemon_stopped(self):
        """Negative test: Monitor handles stopped/missing daemon gracefully without crashing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_pid = Path(tmpdir) / "gemini-hermes.pid"
            fake_log = Path(tmpdir) / "gemini-hermes.log"
            fake_sessions = Path(tmpdir) / "sessions"

            with patch("gemini_hermes.cli_monitor.PID_FILE", fake_pid), \
                 patch("gemini_hermes.cli_monitor.LOG_FILE", fake_log), \
                 patch("gemini_hermes.cli_monitor.SESSIONS_DIR", fake_sessions), \
                 patch("gemini_hermes.telemetry.TELEMETRY_FILE", Path(tmpdir) / "telemetry.json"):

                monitor = CliMonitor()
                status = monitor.get_daemon_status()
                self.assertFalse(status["running"])
                self.assertIsNone(status["pid"])

                # Token panel rendering
                token_panel = monitor.build_token_usage_panel({})
                self.assertIsNotNone(token_panel)

                # Rendering layout must succeed cleanly
                layout = monitor.render_dashboard()
                self.assertIsNotNone(layout)

    def test_monitor_renders_cleanly_when_daemon_running(self):
        """Positive test: Monitor reflects active PID and live telemetry values including tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_pid = Path(tmpdir) / "gemini-hermes.pid"
            fake_log = Path(tmpdir) / "gemini-hermes.log"
            fake_sessions = Path(tmpdir) / "sessions"
            fake_pid.write_text(str(os.getpid()))  # use current live pid
            fake_log.write_text("2026-09-24 12:00:00 [INFO] Bot started\n")

            with patch("gemini_hermes.cli_monitor.PID_FILE", fake_pid), \
                 patch("gemini_hermes.cli_monitor.LOG_FILE", fake_log), \
                 patch("gemini_hermes.cli_monitor.SESSIONS_DIR", fake_sessions):

                monitor = CliMonitor()
                status = monitor.get_daemon_status()
                self.assertTrue(status["running"])
                self.assertEqual(status["pid"], os.getpid())

                logs = monitor.get_recent_logs()
                self.assertTrue(any("Bot started" in line for line in logs))

                state_with_tokens = {
                    "active_chat_id": 8930156663,
                    "tokens": {
                        "session": {"chat_id": 8930156663, "input_tokens": 10000, "output_tokens": 2500, "total_tokens": 12500, "turn_count": 5},
                        "global": {"total_input_tokens": 500000, "total_output_tokens": 125000, "total_tokens": 625000, "session_count": 4, "total_turns": 35},
                    }
                }
                token_panel = monitor.build_token_usage_panel(state_with_tokens)
                self.assertIsNotNone(token_panel)

                layout = monitor.render_dashboard()
                self.assertIsNotNone(layout)


if __name__ == "__main__":
    unittest.main()
