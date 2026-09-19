from dataclasses import dataclass
from typing import Optional, Dict, Any, Union
import json


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

        # Check thinking delta
        if "thinking_delta" in su and su["thinking_delta"]:
            return ThinkingDelta(thought=su["thinking_delta"])
        if "thought" in su and su["thought"]:
            return ThinkingDelta(thought=su["thought"])

        # Check tool execution
        tool_name = su.get("tool_name") or su.get("canonical_tool")
        if tool_name:
            tool_info = su.get("tool_info", {})
            params = tool_info.get("parameters", {}) if isinstance(tool_info, dict) else {}

            action = su.get("tool_action") or params.get("toolAction") or params.get("toolSummary")
            if tool_name in ("write_to_file", "write_file"):
                tgt = params.get("TargetFile") or params.get("target_file") or params.get("file_path") or ""
                fname = tgt.split("/")[-1] if tgt else ""
                action = f'creating a "{fname}" file' if fname else "creating a file"
            elif tool_name in ("replace_file_content", "edit_file"):
                tgt = params.get("TargetFile") or params.get("target_file") or params.get("file_path") or ""
                fname = tgt.split("/")[-1] if tgt else ""
                action = f'updating "{fname}" file' if fname else "updating file content"
            elif tool_name in ("run_command", "execute_command", "bash"):
                cmd = params.get("CommandLine") or params.get("command") or ""
                short_cmd = (cmd[:35] + "...") if len(cmd) > 35 else cmd
                action = f'running "{short_cmd}"' if short_cmd else "running command"
            elif tool_name in ("view_file", "read_file"):
                tgt = params.get("AbsolutePath") or params.get("file_path") or ""
                fname = tgt.split("/")[-1] if tgt else ""
                action = f'reading "{fname}" file' if fname else "reading file"
            elif tool_name in ("list_dir", "list_directory"):
                action = "inspecting project directory"
            elif tool_name in ("find_by_name", "grep_search", "search_code"):
                action = "searching project files"
            elif not action:
                action = f"executing {tool_name}"
            else:
                # Strip markdown ticks or asterisks from existing action text
                action = str(action).replace("`", "").replace("*", "").strip()

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
