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

from gemini_hermes.cli_monitor import CliMonitor
from gemini_hermes.telemetry import TelemetryExporter


class TestCliMonitorAndTelemetry(unittest.TestCase):
    """Dual tests covering positive and negative paths for CLI monitor."""

    def test_telemetry_atomic_write_and_read(self):
        """Positive test: TelemetryExporter correctly writes and reads atomic JSON."""
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
                )

                state = TelemetryExporter.read_state()
                self.assertEqual(state.get("pid"), 12345)
                self.assertTrue(state.get("is_running"))
                self.assertEqual(state.get("active_chat_id"), 8930156663)
                self.assertEqual(state.get("reasoning_effort"), "high")
                self.assertEqual(state.get("queue_depth"), 2)
                self.assertEqual(state.get("jev", {}).get("latency_ms"), 640.5)

    def test_monitor_renders_cleanly_when_daemon_stopped(self):
        """Negative test: Monitor handles stopped/missing daemon gracefully without crashing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_pid = Path(tmpdir) / "gemini-hermes.pid"
            fake_log = Path(tmpdir) / "gemini-hermes.log"

            with patch("gemini_hermes.cli_monitor.PID_FILE", fake_pid), \
                 patch("gemini_hermes.cli_monitor.LOG_FILE", fake_log), \
                 patch("gemini_hermes.telemetry.TELEMETRY_FILE", Path(tmpdir) / "telemetry.json"):

                monitor = CliMonitor()
                status = monitor.get_daemon_status()
                self.assertFalse(status["running"])
                self.assertIsNone(status["pid"])

                # Rendering layout must succeed cleanly
                layout = monitor.render_dashboard()
                self.assertIsNotNone(layout)

    def test_monitor_renders_cleanly_when_daemon_running(self):
        """Positive test: Monitor reflects active PID and live telemetry values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_pid = Path(tmpdir) / "gemini-hermes.pid"
            fake_log = Path(tmpdir) / "gemini-hermes.log"
            fake_pid.write_text(str(os.getpid()))  # use current live pid
            fake_log.write_text("2026-09-24 12:00:00 [INFO] Bot started\n")

            with patch("gemini_hermes.cli_monitor.PID_FILE", fake_pid), \
                 patch("gemini_hermes.cli_monitor.LOG_FILE", fake_log):

                monitor = CliMonitor()
                status = monitor.get_daemon_status()
                self.assertTrue(status["running"])
                self.assertEqual(status["pid"], os.getpid())

                logs = monitor.get_recent_logs()
                self.assertTrue(any("Bot started" in line for line in logs))

                layout = monitor.render_dashboard()
                self.assertIsNotNone(layout)


if __name__ == "__main__":
    unittest.main()
