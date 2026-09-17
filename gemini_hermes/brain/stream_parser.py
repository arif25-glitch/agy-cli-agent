from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class TokenDelta:
    text: str


@dataclass
class ThinkingDelta:
    thought: str


@dataclass
class ToolExecutionUpdate:
    tool_name: str
    action: str


@dataclass
class ForwarderResult:
    conversation_id: str
    status: str
    response: str
    error: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    duration_seconds: float = 0.0


def parse_ndjson_line(data: Dict[str, Any]) -> Optional[Any]:
    event_type = data.get("event")

    if event_type == "step_update":
        su = data.get("step_update", {})
        # Check text delta
        if "text_delta" in su and su["text_delta"]:
            return TokenDelta(text=su["text_delta"])

        # Check tool execution
        tool_name = su.get("tool_name") or su.get("canonical_tool")
        if tool_name:
            action = su.get("tool_action", f"Running {tool_name}")
            return ToolExecutionUpdate(tool_name=tool_name, action=action)

    elif event_type == "result":
        res = data.get("result", {})
        usage = res.get("usage", {})
        return ForwarderResult(
            conversation_id=res.get("conversation_id", ""),
            status=res.get("status", "SUCCESS"),
            response=res.get("response", ""),
            error=res.get("error"),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            thinking_tokens=usage.get("thinking_tokens", 0),
            duration_seconds=res.get("duration_seconds", 0.0),
        )

    return None
