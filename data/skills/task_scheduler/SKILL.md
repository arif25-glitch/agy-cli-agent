---
name: task_scheduler
description: Procedure and guidelines for scheduling delayed tasks, one-shot reminders, and recurring cron operations.
version: 1.0.0
tags: [scheduling, cron, automation, reminders, background]
---

# Task Scheduler Procedure

Use this procedure whenever the user requests delayed reminders, periodic checks, recurring background workflows, or automated triggers.

## 1. Engine-Level Scheduling (Antigravity Proxy Engine)
The engine provides built-in scheduling capabilities for autonomous execution:

### A. One-Shot Timers
Used for delayed reminders or single-event wakeups.
- **Tool**: `schedule`
- **Parameters**:
  - `DurationSeconds`: Number of seconds until trigger (e.g. 1800 for 30m, 3600 for 1h).
  - `Prompt`: The exact instruction or reminder to execute upon waking up.
  - `TimerCondition`:
    - `'never'` (default): Always fires at expiry regardless of messages.
    - `'any'`: Cancels if any message arrives before duration expires.
    - `<sender-id>`: Cancels only if a specific sender ID responds.

### B. Recurring Cron Jobs
Used for periodic checks, monitoring, or recurring updates.
- **Tool**: `schedule`
- **Parameters**:
  - `CronExpression`: Standard 5-field cron syntax (`minute hour day-of-month month day-of-week`).
    - Every 10 minutes: `*/10 * * * *`
    - Every hour at minute 0: `0 * * * *`
    - Every day at 09:00: `0 9 * * *`
  - `Prompt`: The action to execute at each trigger.
  - `MaxIterations`: (Optional) Limit total executions before stopping.

### C. Inspection & Cancellation
- List active schedules: `manage_task(Action='list')`.
- Cancel an active schedule: `manage_task(Action='kill', TaskId='<task_id>')`.

---

## 2. Host-Level Linux Scheduling
For tasks requiring persistent OS-level execution independent of active CLI sessions:

### A. Crontab Scheduling
- Inspect current cron jobs: `crontab -l`
- Add or update cron jobs safely using atomic file editing:
  1. Export current jobs: `crontab -l > /tmp/current_cron 2>/dev/null || true`
  2. Append entry with full paths and log redirection:
     `0 8 * * * /usr/bin/python3 /path/to/script.py >> /var/log/my_task.log 2>&1`
  3. Load updated crontab: `crontab /tmp/current_cron`

### B. Systemd User Timers
For robust service dependencies and automatic retry policies:
- Define `.service` unit and matching `.timer` unit in `~/.config/systemd/user/`.
- Enable and start: `systemctl --user daemon-reload && systemctl --user enable --now <name>.timer`.

---

## 3. Communication Guidelines
- Always verify the user's timezone when discussing specific wall-clock hours.
- Clearly state:
  - What task was scheduled.
  - The exact duration or cron frequency.
  - How the user can inspect or cancel it at any time.
