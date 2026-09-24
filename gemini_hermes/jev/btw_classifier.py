"""
Jev AI System-One smart classifier for /btw sidecar interactions.
Classifies /btw queries into ephemeral_question, status_inquiry, or task_directive.
"""
import asyncio
import logging
from typing import Optional, Tuple

from gemini_hermes.jev.client import JevClient

logger = logging.getLogger("gemini-hermes.jev.btw_classifier")

try:
    from typesafe_sdk import Choice
except ImportError:  # pragma: no cover
    Choice = None


class JevBtwClassifier:
    """
    Classifies sidecar (/btw) interactions using Jev's Choice primitive.
    Returns standard bot intents: ('question' | 'live_status' | 'task', confidence).
    """

    def __init__(self, client: JevClient, default_timeout: float = 1.0, min_confidence: float = 0.85):
        self.client = client
        self.default_timeout = default_timeout
        self.min_confidence = min_confidence

    async def classify(self, text: str, timeout: Optional[float] = None) -> Optional[Tuple[str, float]]:
        """
        Classify /btw input into ('question' | 'live_status' | 'task', confidence).
        Returns None on timeout, low confidence (< min_confidence), or error.
        """
        if not self.client.is_available or not Choice:
            return None

        clean_text = text.strip() if text else ""
        if not clean_text:
            return None

        client_inst = self.client.get_client()
        if client_inst is None:
            return None

        questions = {
            "btw_intent": Choice(
                instructions="Classify this mid-task user interaction into an ephemeral side question, a live progress inquiry, or a sequential task directive.",
                criteria={
                    "ephemeral_question": "An informational, technical, or conversational question meant to be answered immediately without changing the active background task.",
                    "status_inquiry": "Checking current progress, telemetry, or status of ongoing task (e.g., 'are you done?', 'how far along are you?').",
                    "task_directive": "An instruction or task to be executed or queued after the current task finishes (e.g., 'please run tests next', 'deploy after this').",
                },
            )
        }

        effective_timeout = timeout or self.default_timeout
        try:
            res = await asyncio.wait_for(
                client_inst.system_one(
                    state=clean_text,
                    questions=questions,
                    timeout=effective_timeout,
                ),
                timeout=effective_timeout,
            )
            answers = getattr(res, "answers", res)
            if isinstance(answers, dict) and "btw_intent" in answers:
                ans = answers["btw_intent"]
                choice = getattr(ans, "choice", None)
                conf = float(getattr(ans, "confidence", 0.0))

                if choice and conf >= self.min_confidence:
                    # Map Jev's precise labels to existing bot internal intents
                    mapping = {
                        "ephemeral_question": "question",
                        "status_inquiry": "live_status",
                        "task_directive": "task",
                    }
                    mapped_intent = mapping.get(str(choice))
                    if mapped_intent:
                        return mapped_intent, conf
            return None

        except asyncio.TimeoutError:
            logger.debug("Jev /btw classification timed out (>%.1fs). Fallback to heuristics.", effective_timeout)
            return None
        except Exception as e:
            logger.debug("Jev /btw classification failed (%s). Fallback to heuristics.", e)
            return None
