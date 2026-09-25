"""
Dual verification tests for Jev AI startup prerequisites and API key validation.
Tests positive paths (valid API key present) and negative paths (missing/empty key).
"""
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gemini_hermes.cli import validate_jev_prerequisites
from gemini_hermes.config import Config


class TestJevStartupValidation(unittest.TestCase):
    """Dual verification test suite for Jev API key demand and startup guardrails."""

    def test_positive_jev_key_validation(self):
        """Positive test: validate_jev_prerequisites succeeds when key is present."""
        with patch("gemini_hermes.cli.config.typesafe_api_key", "ts_live_key_test_123456"):
            result = validate_jev_prerequisites()
            self.assertTrue(result)

    def test_negative_jev_key_missing_or_empty(self):
        """Negative test: validate_jev_prerequisites fails gracefully with informative message."""
        test_cases = ["", "   ", None]
        for empty_val in test_cases:
            with patch("gemini_hermes.cli.config.typesafe_api_key", empty_val):
                with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                    result = validate_jev_prerequisites()
                    self.assertFalse(result)
                    output = mock_stdout.getvalue()
                    self.assertIn("Error: Jev AI Accelerated Mode requires a TypeSafe AI / Jev API key", output)
                    self.assertIn("console.typesafe.ai/keys", output)
                    self.assertIn("./run.sh config", output)
                    self.assertIn("./run.sh start", output)

    def test_run_sh_start_jev_validation_rejection(self):
        """Negative test: ./run.sh start-jev fails with code 1 and demands key when key is absent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Create isolated run.sh in tempdir
            repo_root = Path(__file__).resolve().parent.parent
            run_sh_content = (repo_root / "run.sh").read_text()
            (tmppath / "run.sh").write_text(run_sh_content)
            # No .env in tmpdir
            env_copy = os.environ.copy()
            env_copy.pop("TYPESAFE_API_KEY", None)
            env_copy.pop("JEV_API_KEY", None)

            res = subprocess.run(
                ["bash", str(tmppath / "run.sh"), "start-jev"],
                cwd=str(tmppath),
                env=env_copy,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 1)
            self.assertIn("Jev AI Accelerated Mode requires a TypeSafe AI / Jev API key", res.stdout + res.stderr)
            self.assertIn("./run.sh start", res.stdout + res.stderr)

    def test_run_sh_background_jev_validation_rejection(self):
        """Negative test: ./run.sh background-jev fails with code 1 and demands key when key is absent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            repo_root = Path(__file__).resolve().parent.parent
            run_sh_content = (repo_root / "run.sh").read_text()
            (tmppath / "run.sh").write_text(run_sh_content)
            # .env with empty Jev key
            (tmppath / ".env").write_text("TELEGRAM_BOT_TOKEN=123:abc\nTYPESAFE_API_KEY=\n")
            env_copy = os.environ.copy()
            env_copy.pop("TYPESAFE_API_KEY", None)
            env_copy.pop("JEV_API_KEY", None)

            res = subprocess.run(
                ["bash", str(tmppath / "run.sh"), "background-jev"],
                cwd=str(tmppath),
                env=env_copy,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 1)
            self.assertIn("Jev AI Accelerated Mode requires a TypeSafe AI / Jev API key", res.stdout + res.stderr)
            self.assertIn("./run.sh start", res.stdout + res.stderr)

    def test_run_sh_start_jev_validation_acceptance(self):
        """Positive test: ./run.sh start-jev accepts key when TYPESAFE_API_KEY is present in env or .env."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            repo_root = Path(__file__).resolve().parent.parent
            run_sh_content = (repo_root / "run.sh").read_text()
            # Replace python command with echo to avoid starting real bot
            run_sh_content = run_sh_content.replace(
                "exec $PYTHON_BIN -m gemini_hermes.cli start --jev",
                "echo 'LAUNCHED_JEV_MODE_OK'"
            )
            (tmppath / "run.sh").write_text(run_sh_content)
            (tmppath / ".env").write_text("TYPESAFE_API_KEY=test_valid_key_12345\n")

            env_copy = os.environ.copy()
            env_copy.pop("TYPESAFE_API_KEY", None)
            env_copy.pop("JEV_API_KEY", None)

            res = subprocess.run(
                ["bash", str(tmppath / "run.sh"), "start-jev"],
                cwd=str(tmppath),
                env=env_copy,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0)
            self.assertIn("LAUNCHED_JEV_MODE_OK", res.stdout)


if __name__ == "__main__":
    unittest.main()
