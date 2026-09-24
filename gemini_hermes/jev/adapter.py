"""
Jev AI Modular Adapter.
Provides a unified, decoupled facade for all Jev AI capabilities.
When running './run.sh start' (Jev disabled), this adapter safely reports
is_available = False and all methods return None or fallback values with zero overhead.
"""
import logging
from typing import Any, Optional, Tuple

from gemini_hermes.config import Config, config as default_config
from gemini_hermes.jev.client import JevClient, JevReflexDecision
from gemini_hermes.jev.effort_selector import JevEffortSelector
from gemini_hermes.jev.btw_classifier import JevBtwClassifier

logger = logging.getLogger("gemini-hermes.jev.adapter")


class JevAdapter:
    """
    Modular integration adapter for Jev AI System-One.
    Encapsulates:
      - Dynamic reasoning effort selection
      - Fast-path conversational context evaluation
      - /btw sidecar smart intent classification
    """

    def __init__(self, cfg: Optional[Config] = None, client: Optional[Any] = None):
        self.config = cfg or default_config
        timeout_val = getattr(self.config, "jev_timeout", 3.0)
        self.client = JevClient(cfg=self.config, client=client, default_timeout=timeout_val)
        self.effort_selector = JevEffortSelector(self.client)
        self.btw_classifier = JevBtwClassifier(
            self.client,
            default_timeout=timeout_val,
            min_confidence=getattr(self.config, "jev_confidence_threshold", 0.85),
        )

    @property
    def is_available(self) -> bool:
        """True only if Jev is enabled in config/env and SDK/API key are ready."""
        return self.client.is_available

    async def select_model_and_effort(
        self,
        text: str,
        default_model: str = "gemini-3.7-flash",
        default_effort: str = "medium",
        timeout: Optional[float] = None,
    ) -> Tuple[str, str, Optional[JevReflexDecision]]:
        """Determine both Antigravity model and reasoning effort dynamically."""
        if not self.is_available or not (
            getattr(self.config, "jev_dynamic_effort", False)
            or getattr(self.config, "jev_dynamic_model", False)
        ):
            return default_model, default_effort, None
        return await self.effort_selector.select_model_and_effort(
            text,
            default_model=default_model,
            default_effort=default_effort,
            timeout=timeout,
        )

    async def select_reasoning_effort(
        self,
        text: str,
        default_effort: str = "medium",
        timeout: Optional[float] = None,
    ) -> Tuple[str, Optional[JevReflexDecision]]:
        """Determine reasoning effort dynamically."""
        if not self.is_available or not getattr(self.config, "jev_dynamic_effort", False):
            return default_effort, None
        return await self.effort_selector.select_reasoning_effort(
            text, default_effort=default_effort, timeout=timeout
        )

    async def classify_btw(self, text: str, timeout: Optional[float] = None) -> Optional[Tuple[str, float]]:
        """Classify /btw query intent with Jev. Returns None if disabled or unconfident."""
        if not self.is_available:
            return None
        return await self.btw_classifier.classify(text, timeout=timeout)

    async def close(self) -> None:
        """Close underlying client connections."""
        await self.client.close()
