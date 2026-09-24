"""
Gateway command and message handlers.
"""
from gemini_hermes.gateway.handlers.system_handlers import (
    handle_unauthorized,
    handle_start,
    handle_help,
    handle_status,
    handle_exec,
)
from gemini_hermes.gateway.handlers.memory_handlers import (
    handle_memory,
    handle_compact,
    handle_memory_add,
    handle_task_add,
    handle_ref_add,
    handle_memory_reset,
)
from gemini_hermes.gateway.handlers.skill_handlers import (
    handle_skills,
    handle_skill_detail,
)
from gemini_hermes.gateway.handlers.project_handlers import (
    handle_projects,
    handle_project_detail,
    handle_project_add,
    handle_project_task,
)
from gemini_hermes.gateway.handlers.queue_handlers import (
    enqueue_task,
    run_queued_task,
    handle_queue,
    handle_cancel,
    handle_reset,
)
from gemini_hermes.gateway.handlers.steering_handlers import (
    handle_btw,
    handle_btw_ephemeral_question,
    handle_steer,
)

__all__ = [
    "handle_unauthorized",
    "handle_start",
    "handle_help",
    "handle_status",
    "handle_exec",
    "handle_memory",
    "handle_compact",
    "handle_memory_add",
    "handle_task_add",
    "handle_ref_add",
    "handle_memory_reset",
    "handle_skills",
    "handle_skill_detail",
    "handle_projects",
    "handle_project_detail",
    "handle_project_add",
    "handle_project_task",
    "enqueue_task",
    "run_queued_task",
    "handle_queue",
    "handle_cancel",
    "handle_reset",
    "handle_btw",
    "handle_btw_ephemeral_question",
    "handle_steer",
]
