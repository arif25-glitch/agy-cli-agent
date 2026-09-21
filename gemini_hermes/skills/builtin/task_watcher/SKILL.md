---
name: task_watcher
description: Procedure for executing, monitoring, and actively waiting for asynchronous or long-running tasks until verified completion.
version: 1.0.0
tags: [background, tasks, monitoring, build, verification, async]
---

# Task Watcher Procedure

Use this procedure whenever executing tasks that take more than a few seconds—such as compiling applications (`npm run build`, `vite build`, `cargo build`), transferring/uploading files, installing large dependencies, running background test suites, or generating assets.

## Core Rules & Principles
1. **Zero Premature Exits ("Never Abandon Running Tasks")**:
   - Strictly NEVER conclude an agent turn with *"it is running in the background, will notify you soon"* and stop executing.
   - Any long-running task initiated during a turn must be monitored or actively followed through until verified completion or failure.

2. **Execution Strategies**:
   - **Synchronous Execution (Preferred for tasks < 60s)**:
     - Run commands with sufficient `WaitMsBeforeAsync` so output returns directly within the step.
   - **Background Process Polling (For long-running CLI/Shell jobs)**:
     - If a command drops into the background (yielding a `task_id` or PID), immediately monitor its progress:
       1. Check task status via `manage_task(Action='status', TaskId=...)` or `tail -n 20 <logfile>`.
       2. Inspect process vitality using `ps -p <pid>` or `manage_task(Action='list')`.
       3. Allow execution steps to complete naturally and react to process completion signals.
   - **Scheduled Wakeup (For long-running unattended tasks > 3–5 minutes)**:
     - If a job takes substantial time, schedule an autonomous wakeup alert:
       `schedule(DurationSeconds=..., Prompt="Check task_watcher status for task <id> and notify the user")`.
       The proxy engine will proactively wake the agent upon timer expiry to verify and report results.

3. **Dual Verification Checklist Before Concluding**:
   - [ ] Verify process exit code is 0.
   - [ ] Verify generated artifacts exist on disk (`ls -la <output_path>`), check size and integrity.
   - [ ] Check logs for hidden warnings, uncaught exceptions, or fatal error lines.

4. **Failure Modes & Graceful Handling**:
   - If a background task hangs or exceeds maximum expected duration, inspect recent logs with `tail -n 50 <logfile>`.
   - If deadlocked or failed, terminate cleanly with `manage_task(Action='kill', TaskId=...)` and report the exact diagnostic error to the user with actionable next steps.
