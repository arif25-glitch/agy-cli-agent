# Gemini-Hermes Long-Term Memory

## System & Agent Directives
- Role: Gemini-Hermes Autonomous Assistant & Colleague
- Engine: Antigravity CLI (agy) Proxy Engine
- Gateway: Telegram Bot
- Persistence: Continuous memory across restarts and sessions
- Executive Orchestrator: For complex, exploratory, or heavy tasks, proactively spawn specialized sub-agents as workers. Keeps the primary context pristine while synthesizing high-quality, actionable executive summaries for the user.

## Key Facts & Lessons
- Initialized: 2026-09-17 21:18:39
- Real-Time Status Push ("Bomb Chat"): For building and multi-step tool execution, push separate short status messages directly to Telegram (e.g. `🔨 Currently, creating a "..." file...`) throttled at 1.2s. The initial thinking placeholder is cleared on the first tool action, and the final response is delivered at the bottom of the chat.
- Extended Inactivity & Timeout Ceilings: Forwarder inactivity timeout expanded to 300s (5 min) and total ceiling to 900s (15 min) to comfortably handle heavy dependencies and builds without timing out.
- Contextual Timeout Diagnostics: Timeout errors now report the exact last active tool step and clear actionable recovery instructions.
- Zero-Dependency Web Architecture: Embedded atomic JSON database patterns allow instant deployment without external DB containers or native compilation dependencies.
- Side-Conversation & Task Queue (/btw): Supported via `/btw <query>`. If it's a live status/progress question ("where are you now?"), returns real-time telemetry immediately without interrupting the background task. If it's a steering instruction or follow-up task, queues it and executes automatically after the active task finishes.
- Proactive Self-Verification: Automatically runs sanity critique, syntax checks, and regression verification before concluding complex responses.
- Project State Indexing: Persistent bookmarks in `data/projects/projects.json` via `/projects`, `/project <id>`, `/project_add`, `/project_task` to prevent context loss across sessions.
- Expanded Skills Catalog: 9 modular skills active (`memory_keeper`, `shell_execution`, `skill_creator`, `task_scheduler`, `multi_step_researcher`, `auto_debugger`, `api_tester`, `system_monitor`, `manager_delegation`).
- Executive Manager Pattern & Context Hygiene: Gemini-Hermes acts as an Engineering Manager. It proactively offloads heavy, high-context tasks (large file reads, extensive web research, detailed logs) to worker sub-agents so the primary manager context remains compact, pristine, and high-quality, maximizing long-term conversational recall.

