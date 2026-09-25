"""
Jev AI Just-In-Time (JIT) Skill Selector.
Dynamically evaluates user requests and picks only the relevant procedure skill(s)
to inject into the prompt, preventing token bloat and context clutter.
"""
import logging
from typing import Dict, List, Optional, Any

from gemini_hermes.jev.client import JevClient

logger = logging.getLogger("gemini-hermes.jev.skill_selector")

try:
    from typesafe_sdk import Choice
    HAS_TYPESAFE_SDK = True
except ImportError:  # pragma: no cover
    Choice = None
    HAS_TYPESAFE_SDK = False


class JevSkillSelector:
    """
    Evaluates inbound requests against the registered skills catalog to choose
    only the necessary skill(s), or returns an empty list for standard coding / conversation.
    """

    def __init__(self, client: JevClient, min_confidence: float = 0.70):
        self.client = client
        self.min_confidence = min_confidence

    async def select_skills(
        self,
        text: str,
        available_skills: Dict[str, Any],
        timeout: Optional[float] = None,
    ) -> Optional[List[str]]:
        """
        Dynamically selects relevant skill names using Jev System-One Choice primitive.
        Returns:
          - [] (empty list) if no specialized skill is needed (lean context)
          - [skill_name, ...] if a specific skill is matched with high confidence
          - None if Jev is disabled, unavailable, or encounters a timeout (fallback)
        """
        if not self.client.is_available or not available_skills or not HAS_TYPESAFE_SDK:
            return None

        clean_text = text.strip() if text else ""
        if not clean_text:
            return []

        # Build dynamic criteria from available skills
        criteria: Dict[str, str] = {
            "none": "General conversation, routine coding, file editing, or basic queries requiring no specialized skills.",
        }
        for name, skill in list(available_skills.items())[:8]:
            desc = getattr(skill, "description", str(skill))
            criteria[name] = desc[:120]

        questions = {
            "skill_match": Choice(
                instructions="Determine if the user's task requires a specialized skill procedure or if standard assistance suffices.",
                criteria=criteria,
            )
        }

        try:
            decision = await self.client.evaluate_reflex(
                clean_text, custom_questions=questions, timeout=timeout
            )
            if decision and "skill_match" in decision.raw_answers:
                ans = decision.raw_answers["skill_match"]
                choice = getattr(ans, "choice", None)
                conf = float(getattr(ans, "confidence", 0.0))

                if choice == "none" or conf < self.min_confidence:
                    logger.debug(
                        f"Jev JIT skill selector: 'none' selected (conf={conf:.2f}). Injecting 0 skills."
                    )
                    return []

                if choice in available_skills:
                    logger.info(
                        f"Jev JIT skill selector: activated skill '{choice}' (conf={conf:.2f}, latency={decision.latency_ms:.1f}ms)."
                    )
                    return [choice]

            return []
        except Exception as e:
            logger.debug(f"Jev JIT skill selection error: {e}. Falling back gracefully.")
            return None
