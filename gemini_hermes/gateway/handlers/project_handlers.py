"""
Project bookmark command handlers: /projects, /project, /project_add, /project_task.
"""
from typing import Any


async def handle_projects(bot: Any, chat_id: int):
    projects = bot.project_manager.list_projects()
    if not projects:
        await bot.send_message(
            chat_id,
            "📁 No projects currently indexed. Use `/project_add <name> <path>` to bookmark one."
        )
        return

    lines = ["📁 *Indexed Projects (Persistent State):*\n"]
    for p in projects:
        lines.append(p.to_summary() + "\n")
    lines.append("Use `/project <id>` to inspect detailed state and tasks.")
    await bot.send_message(chat_id, "\n".join(lines))


async def handle_project_detail(bot: Any, chat_id: int, identifier: str):
    if not identifier.strip():
        await handle_projects(bot, chat_id)
        return

    project = bot.project_manager.get_project(identifier.strip())
    if not project:
        await bot.send_message(chat_id, f"⚠️ Project `{identifier}` not found. Type `/projects` to list active projects.")
        return

    tasks_str = "\n".join(f"  {i+1}. {t}" for i, t in enumerate(project.active_tasks)) if project.active_tasks else "  (No pending tasks)"
    text = (
        f"📁 *Project:* `{project.name}` (`{project.id}`)\n"
        f"• *Status:* `{project.status}`\n"
        f"• *Path:* `{project.path}`\n"
        f"• *Tech Stack:* `{project.tech_stack or 'None'}`\n"
        f"• *Last Worked On:* `{project.last_worked_on[:19]}`\n\n"
        f"📝 *Description:*\n_{project.description or 'No description provided.'}_\n\n"
        f"📋 *Active Tasks:*\n{tasks_str}\n\n"
        f"💡 *Notes:*\n```\n{project.notes or 'No notes recorded.'}\n```"
    )
    await bot.send_message(chat_id, text)


async def handle_project_add(bot: Any, chat_id: int, arg_str: str):
    parts = arg_str.strip().split(maxsplit=2)
    if len(parts) < 2:
        await bot.send_message(chat_id, "⚠️ Usage: `/project_add <name> <path> [description]`")
        return
    name = parts[0]
    path = parts[1]
    desc = parts[2] if len(parts) > 2 else ""
    proj = bot.project_manager.bookmark_project(name=name, path=path, description=desc)
    await bot.send_message(
        chat_id,
        f"✅ *Successfully bookmarked project:*\n"
        f"• Name: `{proj.name}`\n"
        f"• ID: `{proj.id}`\n"
        f"• Path: `{proj.path}`\n\n"
        f"Type `/project {proj.id}` to view details."
    )


async def handle_project_task(bot: Any, chat_id: int, arg_str: str):
    parts = arg_str.strip().split(maxsplit=1)
    if len(parts) < 2:
        await bot.send_message(chat_id, "⚠️ Usage: `/project_task <project_id> <task description>`")
        return
    pid = parts[0]
    task_desc = parts[1]
    proj = bot.project_manager.add_task(pid, task_desc)
    if not proj:
        await bot.send_message(chat_id, f"⚠️ Project `{pid}` not found. Use `/projects` to list.")
        return
    await bot.send_message(chat_id, f"✅ Added task to *{proj.name}*:\n• `{task_desc}`")
