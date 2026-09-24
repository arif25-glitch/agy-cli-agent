"""
Skill command handlers: /skills and /skill <name>.
"""
from typing import Any


async def handle_skills(bot: Any, chat_id: int):
    skills = bot.skill_manager.get_all_skills()
    if not skills:
        await bot.send_message(chat_id, "No skills registered yet.")
        return

    lines = ["🛠️ *Registered Hermes Skills:*\n"]
    for s in skills.values():
        tags = f" `[{', '.join(s.tags)}]`" if s.tags else ""
        lines.append(f"• *{s.name}*{tags}\n  _{s.description}_")
    lines.append("\nUse `/skill <name>` to view full instructions.")
    await bot.send_message(chat_id, "\n".join(lines))


async def handle_skill_detail(bot: Any, chat_id: int, skill_name: str):
    skill = bot.skill_manager.get_skill(skill_name.strip())
    if not skill:
        await bot.send_message(chat_id, f"⚠️ Skill `{skill_name}` not found. Use `/skills` to list available.")
        return

    text = (
        f"📖 *Skill:* `{skill.name}` (v{skill.version})\n"
        f"*{skill.description}*\n\n"
        f"```markdown\n{skill.instructions[:3500]}\n```"
    )
    await bot.send_message(chat_id, text)
