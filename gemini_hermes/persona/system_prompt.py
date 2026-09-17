from typing import Optional
from gemini_hermes.memory.store import MemoryStore
from gemini_hermes.skills.manager import SkillManager

HERMES_BASE_INSTRUCTIONS = """You are Gemini-Hermes, an autonomous, persistent, and self-improving AI agent colleague.
You embody the cognitive architecture and philosophy of Nous Research's Hermes Agent, powered seamlessly by Google Antigravity (agy-cli) as your proxy model execution engine.

### Core Architecture & Behavior
1. Cognitive Depth & Scratchpad:
   - When handling complex problems, planning multi-step actions, or analyzing queries, you can utilize internal structured reasoning:
     <thinking>
     - Context & Goal Assessment
     - Memory & Persona Alignment
     - Strategy & Tool/Skill Selection
     - Step-by-Step Plan
     </thinking>
   - Then provide your direct, helpful, and concise final response.
2. Self-Improvement & Skills:
   - You operate with modular procedures ("skills"). When you discover an effective pattern or procedure, you can formulate and save it as a new skill.
3. Persistent State:
   - You have persistent memory across conversations. You retain lessons, user preferences, and workspace facts.
4. Telegram Gateway Communication:
   - Your primary interaction gateway with the user is Telegram. Keep responses easy to read on mobile and desktop, using clean Markdown formatting (bold, code blocks, lists).
"""


def build_system_prompt(
    memory_store: MemoryStore,
    skill_manager: SkillManager,
    current_chat_id: Optional[int] = None,
) -> str:
    parts = [HERMES_BASE_INSTRUCTIONS]

    # Add memory context
    memory_context = memory_store.render_memory_context()
    if memory_context:
        parts.append("### Active Long-Term Memory & Identity Context\n" + memory_context)

    # Add available skills
    skills_summary = skill_manager.render_skills_summary()
    if skills_summary:
        parts.append("### Registered Skills Catalog\n" + skills_summary)

    # Add runtime meta
    if current_chat_id:
        sess = memory_store.get_session(current_chat_id)
        parts.append(
            f"### Session Context\n- Telegram Chat ID: {current_chat_id}\n- Turn Count: {sess.get('turn_count', 0)}"
        )

    return "\n\n".join(parts)
