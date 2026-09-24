"""
Type-safe data structures and decision contracts for the Jev AI System-One integration.
"""
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class JevCategory(str, Enum):
    """
    Standard decision categories evaluated by Jev System-One classifier.
    """
    CHAT_CONVERSATION = "chat_conversation"
    TOOL_EXECUTION = "tool_execution"
    CODE_EDIT = "code_edit"
    SYSTEM_STATUS = "system_status"
    TASK_QUEUE = "task_queue"
    EPHEMERAL_QA = "ephemeral_qa"
    CLARIFICATION_NEEDED = "clarification_needed"
    FALLBACK_TO_AGY = "fallback_to_agy"


class JevDecisionOutcome(BaseModel):
    """
    Calibrated typed decision emitted by Jev.
    Guarantees strict schema boundary compliance before downstream routing.
    """
    category: JevCategory
    confidence: float = Field(ge=0.0, le=1.0)
    suggested_action: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reasoning_tier: str = "system_one"
    is_high_confidence: bool = False
    requires_system_two: bool = False
    raw_response: Optional[Dict[str, Any]] = None

    def summary(self) -> str:
        tier_icon = "⚡ System-One (Fast)" if self.reasoning_tier == "system_one" else "🧠 System-Two (Deep)"
        return (
            f"🎯 *Jev Decision:* `{self.category.value}`\n"
            f"• *Confidence:* `{self.confidence:.1%}` ({'High' if self.is_high_confidence else 'Low/Uncertain'})\n"
            f"• *Tier:* {tier_icon}\n"
            f"• *Action:* `{self.suggested_action or 'Direct routing'}`"
        )
