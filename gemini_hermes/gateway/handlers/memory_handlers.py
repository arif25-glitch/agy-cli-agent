"""
Memory command handlers: /memory, /compact, /memory_add, /task_add, /ref_add, /memory_reset.
"""
from typing import Any


async def handle_memory(bot: Any, chat_id: int):
    mem = bot.memory_store.get_long_term_memory().strip()
    usr = bot.memory_store.get_user_profile().strip()
    backlog = bot.memory_store.get_backlog().strip()
    refs = bot.memory_store.get_references().strip()

    sections = []
    if mem:
        sections.append(f"🧠 *Operational Directives (`MEMORY.md`):*\n```markdown\n{mem[:800]}\n```")
    if usr:
        sections.append(f"👤 *User Profile (`USER.md`):*\n```markdown\n{usr[:800]}\n```")
    if backlog:
        sections.append(f"📋 *Task Backlog (`BACKLOG.md`):*\n```markdown\n{backlog[:800]}\n```")
    if refs:
        sections.append(f"🔗 *External References (`REFERENCES.md`):*\n```markdown\n{refs[:800]}\n```")

    text = "\n\n".join(sections) if sections else "ℹ️ No memory files found."
    await bot.send_message(chat_id, text)


async def handle_compact(bot: Any, chat_id: int):
    jev_adapter = getattr(bot, "jev_adapter", None)
    if hasattr(bot.memory_store, "autonomous_prune"):
        res = await bot.memory_store.autonomous_prune(
            jev_adapter=jev_adapter,
            keep_recent_backlog=5,
            max_notes=10,
        )
    else:
        res = bot.memory_store.archive_completed_backlog(keep_recent=5)

    stats = bot.memory_store.get_memory_stats()
    mode_label = "Jev Smart Semantic" if res.get("mode") == "jev_smart" else "Pure Core Deterministic"

    backlog_info = res.get("backlog", res)
    notes_info = res.get("notes", {})
    backlog_archived = backlog_info.get("archived_count", 0)
    notes_archived = notes_info.get("archived_count", 0)

    if res.get("status") in ("archived", "pruned"):
        text = (
            f"🧹 *Memory Compaction & Tiering Complete ({mode_label})*\n\n"
            f"• *Archived Completed Tasks:* `{backlog_archived}` (migrated to `BACKLOG_ARCHIVE.md`)\n"
            f"• *Archived Stale Notes/Lessons:* `{notes_archived}` (migrated to `MEMORY_ARCHIVE.md`)\n"
            f"• *Recent Completed in Hot Context:* `{backlog_info.get('retained_count', 0)}`\n"
            f"• *Active Tasks Kept:* `{backlog_info.get('active_count', 0)}`\n"
            f"• *Current Hot Memory Footprint:* ~`{stats['hot_tokens']:,}` tokens\n"
            f"• *Total Memory Preserved on Disk:* ~`{stats['total_tokens']:,}` tokens\n"
            f"• *Archive Location:* `data/memory/archive/`"
        )
    else:
        text = (
            f"✨ *Memory is Already Compact & Sharp ({mode_label})*\n\n"
            f"• *Completed Tasks in Backlog:* `{backlog_info.get('retained_count', 0)}` (under threshold of 5)\n"
            f"• *Active Tasks:* `{backlog_info.get('active_count', 0)}`\n"
            f"• *Memory Notes in Hot Context:* `{notes_info.get('retained_count', 0)}` (under threshold of 10)\n"
            f"• *Current Hot Memory Footprint:* ~`{stats['hot_tokens']:,}` tokens\n"
            f"• *Archived Off-Prompt Tokens:* ~`{stats['archived_tokens']:,}` tokens\n"
            f"No archiving was needed."
        )
    await bot.send_message(chat_id, text)


async def handle_memory_add(bot: Any, chat_id: int, note: str):
    if not note.strip():
        await bot.send_message(chat_id, "⚠️ Please provide text to save: `/memory_add <text>`")
        return
    bot.memory_store.append_to_memory(note)
    await bot.send_message(chat_id, f"✅ Successfully saved to persistent memory:\n`{note.strip()}`")


async def handle_task_add(bot: Any, chat_id: int, task: str):
    if not task.strip():
        await bot.send_message(chat_id, "⚠️ Please provide a task: `/task_add <description>`")
        return
    bot.memory_store.append_to_backlog(task)
    await bot.send_message(chat_id, f"✅ Successfully added to Task Backlog (`BACKLOG.md`):\n`{task.strip()}`")


async def handle_ref_add(bot: Any, chat_id: int, arg: str):
    if not arg.strip() or "|" not in arg:
        await bot.send_message(chat_id, "⚠️ Please provide format: `/ref_add <title> | <url>`")
        return
    parts = arg.split("|", 1)
    title = parts[0].strip()
    url = parts[1].strip()
    bot.memory_store.append_to_references(title, url)
    await bot.send_message(chat_id, f"✅ Saved to References (`REFERENCES.md`):\n*{title}*: `{url}`")


async def handle_memory_reset(bot: Any, chat_id: int):
    bot.memory_store.reset_long_term_memory()
    await bot.send_message(chat_id, "🧹 Long-term memory has been reset to defaults.")
