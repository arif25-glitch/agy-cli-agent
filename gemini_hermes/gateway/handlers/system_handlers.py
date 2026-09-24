"""
System command handlers: /start, /help, /status, /exec, and access control.
"""
import asyncio
from typing import Any
from gemini_hermes.config import config


async def handle_unauthorized(bot: Any, chat_id: int, user_id: int):
    msg = (
        f"⛔ *Access Restricted*\n\n"
        f"Your Telegram User ID: `{user_id}`\n"
        f"Chat ID: `{chat_id}`\n\n"
        f"To access Gemini-Hermes, add your User ID to `TELEGRAM_ALLOWED_USERS` in your `.env` configuration."
    )
    await bot.send_message(chat_id, msg)


async def handle_start(bot: Any, chat_id: int, user_id: int):
    skills_count = len(bot.skill_manager.get_all_skills())
    text = (
        f"🤖 *Welcome to Gemini-Hermes (v{config.app_version})!*\n\n"
        f"I am an autonomous, persistent AI agent colleague inspired by *Nous Research's Hermes*, "
        f"powered by *Google Antigravity CLI (`agy`)* as my proxy model execution engine.\n\n"
        f"⚙️ *Engine:* Antigravity CLI Proxy (`agy`)\n"
        f"📦 *App Version:* `v{config.app_version}`\n"
        f"🧠 *Reasoning Effort:* `{config.reasoning_effort}`\n"
        f"💾 *Persistent Memory:* Active (`MEMORY.md` & `USER.md`)\n"
        f"🛠️ *Skills Catalog:* `{skills_count}` active skills\n\n"
        f"💡 *Commands:*\n"
        f"• `/new` or `/reset` - Start a fresh conversation\n"
        f"• `/status` - Check agent health and statistics\n"
        f"• `/memory` - Inspect persistent memory modules (MEMORY, USER, BACKLOG, REFERENCES)\n"
        f"• `/memory_add <text>` - Save a permanent fact or instruction\n"
        f"• `/task_add <task>` - Add a task to the active backlog\n"
        f"• `/ref_add <title> | <url>` - Save an external link or sheet reference\n"
        f"• `/skills` - View all available modular skills\n"
        f"• `/skill <name>` - View skill procedure details\n"
        f"• `/exec <bash>` - Execute host shell command\n"
        f"• `/help` - Show this guide\n\n"
        f"Send me any question, project task, or instruction to begin!"
    )
    await bot.send_message(chat_id, text)


async def handle_help(bot: Any, chat_id: int):
    text = (
        f"📚 *Gemini-Hermes Command Reference:*\n\n"
        f"• `/new` / `/reset` - Clears the current conversation thread and begins a fresh session.\n"
        f"• `/status` - Shows active conversation ID, turns, token metrics, and engine status.\n"
        f"• `/memory` - Displays all active persistent memory modules.\n"
        f"• `/compact` - Archives older completed tasks to data/memory/archive/ and keeps prompt context sharp.\n"
        f"• `/memory_add <note>` - Manually saves a new note to persistent operational memory.\n"
        f"• `/task_add <task>` - Adds a task to the active backlog (`BACKLOG.md`).\n"
        f"• `/ref_add <title> | <url>` - Saves an external link or sheet to references (`REFERENCES.md`).\n"
        f"• `/memory_reset` - Resets persistent memory to default initial state.\n"
        f"• `/skills` - Lists all modular procedural skills currently registered.\n"
        f"• `/skill <name>` - Displays the exact instructions and metadata of a skill.\n"
        f"• `/projects` - List all bookmarked projects and their state.\n"
        f"• `/project <id>` - Inspect detailed state, tasks, and tech stack of a project.\n"
        f"• `/project_add <name> <path>` - Bookmark a new active project into persistent state.\n"
        f"• `/project_task <id> <task>` - Add a new task or milestone to a project.\n"
        f"• `/btw <note/query>` - Ask a side question, steer, or queue a task while an operation is running.\n"
        f"• `/steer <instruction>` - Immediately redirects or course-corrects the agent (mid-flight or idle).\n"
        f"• `/queue` - View active task and pending /btw queue.\n"
        f"• `/cancel` - Abort the active background task and clear the queue.\n"
        f"• `/exec <command>` - Runs a shell command on the host machine and streams the output.\n"
        f"• `/help` - Displays this menu.\n\n"
        f"💬 *Natural Conversation:*\n"
        f"You can also ask me directly to learn new skills, recall previous discussions, "
        f"research topics, analyze complex problems, and run multi-step workflows."
    )
    await bot.send_message(chat_id, text)


async def handle_status(bot: Any, chat_id: int):
    sess = bot.memory_store.get_session(chat_id)
    health = await bot.forwarder.check_health()
    status_symbol = "🟢 Online" if health.get("ok") else "🔴 Error"

    text = (
        f"📊 *Gemini-Hermes Status:*\n\n"
        f"• *App Version:* `v{config.app_version}`\n"
        f"• *Model Engine:* {status_symbol}\n"
        f"• *Binary:* `{bot.forwarder.agy_bin}`\n"
        f"• *Reasoning Effort:* `{config.reasoning_effort}`\n"
        f"• *Current Conversation ID:* `{sess.get('conversation_id') or 'None (Fresh Session)'}`\n"
        f"• *Session Turns:* `{sess.get('turn_count', 0)}`\n"
        f"• *Tokens Used:* ~{sess.get('total_input_tokens', 0) + sess.get('total_output_tokens', 0):,}\n"
        f"• *Registered Skills:* `{len(bot.skill_manager.get_all_skills())}`\n"
        f"• *Indexed Projects:* `{len(bot.project_manager.list_projects())}`\n"
        f"• *Memory File:* `data/memory/MEMORY.md`"
    )
    await bot.send_message(chat_id, text)


async def handle_exec(bot: Any, chat_id: int, command: str):
    if not command.strip():
        await bot.send_message(chat_id, "⚠️ Usage: `/exec <bash command>`")
        return

    await bot.send_chat_action(chat_id, "typing")
    status_msg_id = await bot.send_message(chat_id, f"⚡ *Executing:* `{command}`...")

    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    out_str = stdout.decode("utf-8", errors="replace")
    err_str = stderr.decode("utf-8", errors="replace")

    result = f"*Exit Code:* `{proc.returncode}`\n"
    if out_str.strip():
        result += f"**Output:**\n```\n{out_str[:3500]}\n```\n"
    if err_str.strip():
        result += f"**Errors:**\n```\n{err_str[:3500]}\n```"

    if status_msg_id:
        await bot.edit_message_text(chat_id, status_msg_id, result)
    else:
        await bot.send_message(chat_id, result)


