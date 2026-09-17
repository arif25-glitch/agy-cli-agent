import re
from typing import List

MAX_TELEGRAM_MESSAGE_LENGTH = 4000


def escape_markdown_v1(text: str) -> str:
    # Standard telegram markdown escapes if needed
    return text


def split_message(text: str, max_length: int = MAX_TELEGRAM_MESSAGE_LENGTH) -> List[str]:
    if len(text) <= max_length:
        return [text]

    chunks = []
    lines = text.splitlines(keepends=True)
    current_chunk = []
    current_len = 0

    for line in lines:
        if current_len + len(line) > max_length:
            if current_chunk:
                chunks.append("".join(current_chunk))
                current_chunk = []
                current_len = 0

            # If a single line exceeds max_length, split it by characters
            while len(line) > max_length:
                chunks.append(line[:max_length])
                line = line[max_length:]

        current_chunk.append(line)
        current_len += len(line)

    if current_chunk:
        chunks.append("".join(current_chunk))

    return chunks


def format_hermes_output(text: str) -> str:
    # 1. Protect preformatted code blocks and inline code
    code_blocks = []
    def save_code_block(m):
        code_blocks.append(m.group(0))
        return f"__HERMES_CODE_BLOCK_{len(code_blocks)-1}__"

    text = re.sub(r"```[\s\S]*?```", save_code_block, text)

    inline_codes = []
    def save_inline_code(m):
        inline_codes.append(m.group(0))
        return f"__HERMES_INLINE_CODE_{len(inline_codes)-1}__"

    text = re.sub(r"`[^`\n]+`", save_inline_code, text)

    # 2. Format <thinking> blocks neatly
    def format_thinking(match):
        thoughts = match.group(1).strip()
        quoted = "\n".join(f"> {line}" for line in thoughts.splitlines())
        return f"💭 *Cognitive Scratchpad:*\n{quoted}\n\n"

    text = re.sub(r"<thinking>(.*?)</thinking>", format_thinking, text, flags=re.DOTALL)

    # 3. Convert markdown headers (# Title, ## Title, ### Title) to bold *Title*
    def format_header(match):
        header_text = match.group(1).strip()
        # Strip asterisks inside header to avoid nesting errors
        header_text = re.sub(r"\*+", "", header_text).strip()
        return f"*{header_text}*"

    text = re.sub(r"^\s*#{1,6}\s+(.+)$", format_header, text, flags=re.MULTILINE)

    # 4. Remove standalone markdown horizontal rules (--- or ***)
    text = re.sub(r"^\s*[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

    # 5. Convert asterisk list bullets to unicode bullet dots to prevent Telegram entity collisions
    text = re.sub(r"^\s*\*\s+", "• ", text, flags=re.MULTILINE)

    # 6. Convert double/triple asterisks **bold** to Telegram single asterisk *bold*
    text = re.sub(r"\*{2,3}(.*?)\*{2,3}", r"*\1*", text)

    # 7. Restore code blocks
    for i, c in enumerate(inline_codes):
        text = text.replace(f"__HERMES_INLINE_CODE_{i}__", c)
    for i, c in enumerate(code_blocks):
        text = text.replace(f"__HERMES_CODE_BLOCK_{i}__", c)

    return text.strip()


def sanitize_streaming_markdown(text: str) -> str:
    """Closes unclosed markdown entities during real-time streaming to prevent Telegram parsing errors."""
    if not text:
        return text
    # Close unclosed triple backtick code blocks
    if text.count("```") % 2 != 0:
        text += "\n```"
    # Close unclosed inline backticks
    elif text.count("`") % 2 != 0:
        text += "`"
    # Close unclosed bold asterisks
    if text.count("*") % 2 != 0:
        text += "*"
    # Close unclosed italic underscores
    if text.count("_") % 2 != 0:
        text += "_"
    return text


def humanize_error(error_str: str, context: str = "", last_action: str = "") -> str:
    """Transforms raw internal errors or exception strings into clear, friendly, and actionable explanations."""
    err_raw = (error_str or "").strip()
    err_lower = err_raw.lower()

    if "timeout" in err_lower or "timed out" in err_lower:
        last_step_info = f"\n*Last Active Step:*\nCurrently, {last_action}\n" if last_action else ""
        return (
            "⏳ *Execution Timed Out*\n\n"
            "The model engine took longer than expected to complete the current operation.\n"
            f"{last_step_info}\n"
            "*Why this happens:*\n"
            "• Heavy tasks (such as scaffolding, dependency installations, or extensive file builds) can pause output while processing.\n"
            "• If no output is detected for 5 minutes (or 15 minutes total ceiling), the forwarder safely stops to avoid hanging indefinitely.\n\n"
            "*How to continue:*\n"
            "1. Type `/status` to inspect current system state and thread ID.\n"
            "2. If files were partially created, ask me to 'continue the build' to pick up right where I left off.\n"
            "3. Type `/reset` if you would like to clear the conversation and start with a fresh thread."
        )

    if "lock" in err_lower or "busy" in err_lower or "already running" in err_lower or "presence" in err_lower:
        return (
            "🔒 *Session Busy / Locked*\n\n"
            "The conversation is currently occupied or a previous background process didn't release the session lock.\n\n"
            "*How to fix it directly:*\n"
            "• Type `/reset` to immediately clear the active lock and initialize a fresh thread."
        )

    if "rate limit" in err_lower or "quota" in err_lower or "429" in err_lower or "resource_exhausted" in err_lower:
        return (
            "🛑 *API Rate Limit / Quota Reached*\n\n"
            "The model execution engine encountered a temporary upstream rate limit or quota boundary.\n\n"
            "*How to fix it directly:*\n"
            "• Please wait 30–60 seconds before sending your next message, then try again."
        )

    if "cant find end of the entity" in err_lower or "parse entities" in err_lower or "bad request" in err_lower:
        return (
            "📝 *Formatting Parsing Error*\n\n"
            "Telegram had trouble rendering special characters or formatting tags in the output stream.\n\n"
            "*How to fix it directly:*\n"
            "• The text has been sanitized. You can also type `/reset` to refresh the thread."
        )

    if "no such file" in err_lower or "not found" in err_lower:
        return (
            "📁 *File Not Accessible*\n\n"
            "I could not locate or open the specified file on disk.\n\n"
            "*How to fix it directly:*\n"
            "• Please try re-sending or uploading the file directly into this chat."
        )

    # General error fallback with simplified explanation
    clean_err = err_raw.replace("`", "'")
    if len(clean_err) > 250:
        clean_err = clean_err[:250] + "..."

    return (
        "⚠️ *Execution Interrupted*\n\n"
        f"An error occurred while processing: `{clean_err}`\n\n"
        "*How to fix it directly:*\n"
        "• Type `/reset` to wipe current thread cache and start fresh.\n"
        "• Type `/status` to check engine and model proxy connectivity."
    )

