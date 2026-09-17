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
