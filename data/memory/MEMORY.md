# Gemini-Hermes Long-Term Memory

## Operational Directives & Standards
- Live Status Push: Throttled at 1.2s; push short Telegram updates; clear thinking placeholder on tool 1.
- Timeouts: Inactivity timeout 300s, total ceiling 900s; errors must include last active tool step.
- Zero-Dependency Storage: Use atomic JSON DB pattern for instant zero-dependency deployments.
- Side-Channel (/btw): `/btw <query>` returns instant telemetry; queues steering tasks without interrupting active job.
- Pre-Conclusion Verification: Run sanity checks, consistency scans, and quality verification before concluding tasks.
- Project Bookmarks: Manage active projects via `/projects`, `/project <id>`, `/project_add`, `/project_task`.
- Subagent Policy: Sub-agent delegation is strictly disabled. Perform all tasks directly.
- Memory Discipline: Only persist permanent rules, architecture decisions, and explicit preferences; avoid routine churn.
