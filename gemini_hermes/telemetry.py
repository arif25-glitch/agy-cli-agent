"""
Live Telemetry State Exporter for Gemini-Hermes.
Atomically persists runtime operational telemetry to data/state/telemetry.json
so the CLI Dashboard (./run.sh monitor) can observe real-time health with zero locking.
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from gemini_hermes.config import STATE_DIR

logger = logging.getLogger("gemini-hermes.telemetry")

TELEMETRY_FILE = STATE_DIR / "telemetry.json"


class TelemetryExporter:
    """
    Manages atomic writing and reading of bot telemetry.
    """

    @staticmethod
    def record_state(
        pid: int,
        is_running: bool,
        active_chat_id: Optional[int] = None,
        active_task_preview: Optional[str] = None,
        active_task_elapsed: float = 0.0,
        active_step: Optional[str] = None,
        reasoning_effort: str = "medium",
        selected_model: Optional[str] = None,
        is_fast_path: bool = False,
        queue_depth: int = 0,
        queue_items: Optional[List[str]] = None,
        jev_enabled: bool = False,
        jev_latency_ms: Optional[float] = None,
        jev_complexity: Optional[float] = None,
        jev_decision: Optional[str] = None,
        session_tokens: Optional[Dict[str, Any]] = None,
        global_tokens: Optional[Dict[str, Any]] = None,
        last_error: Optional[str] = None,
    ) -> None:
        """Atomically persist telemetry state snapshot to disk."""
        data = {
            "timestamp": time.time(),
            "pid": pid,
            "is_running": is_running,
            "active_chat_id": active_chat_id,
            "active_task_preview": active_task_preview,
            "active_task_elapsed": round(active_task_elapsed, 1),
            "active_step": active_step,
            "selected_model": selected_model,
            "reasoning_effort": reasoning_effort,
            "is_fast_path": is_fast_path,
            "queue_depth": queue_depth,
            "queue_items": (queue_items or [])[:5],
            "jev": {
                "enabled": jev_enabled,
                "latency_ms": round(jev_latency_ms, 1) if jev_latency_ms is not None else None,
                "complexity": round(jev_complexity, 2) if jev_complexity is not None else None,
                "last_decision": jev_decision,
            },
            "tokens": {
                "session": session_tokens or {},
                "global": global_tokens or {},
            },
            "last_error": last_error,
        }

        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            tmp_file = TELEMETRY_FILE.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_file, TELEMETRY_FILE)
        except Exception as e:
            logger.debug(f"Failed to record telemetry state: {e}")

    @staticmethod
    def read_state() -> Dict[str, Any]:
        """Read the latest telemetry snapshot safely. Returns empty dict if absent or invalid."""
        if not TELEMETRY_FILE.exists():
            return {}
        try:
            with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.debug(f"Failed to read telemetry state: {e}")
            return {}
