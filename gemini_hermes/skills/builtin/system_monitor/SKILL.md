---
name: system_monitor
description: Procedure for inspecting host system resources, monitoring background daemon health, managing PID locks, and tracking execution metrics.
version: 1.0.0
tags: [monitoring, system, devops, cron, healthcheck]
---

# System Monitor Procedure

Use this skill when auditing agent health, checking server resources, diagnosing slow execution, or configuring periodic cron health checks.

### 1. Process & Daemon Health Check
- Check running agent processes and PIDs:
  `ps aux | grep -E "python3.*gemini_hermes|agy"`
- Inspect memory and CPU consumption of active tasks.
- Verify PID file integrity (`gemini-hermes.pid`).

### 2. Host Resource Inspection
- Disk Space: Check disk utilization (`df -h /`) to ensure storage is not filling up with media or build artifacts.
- Memory: Inspect RAM usage (`free -m`).
- Ports & Sockets: Check active listening ports (`netstat -tuln` or `ss -tuln`).

### 3. Log Stream Analysis
- Audit recent daemon warnings or exceptions:
  `tail -n 50 /gemini-hermes/gemini-hermes.log`
- Look for repeating patterns (e.g. 400 Bad Request, rate limits, unhandled promise rejections).

### 4. Background Task Telemetry
- Check active subagent or background task status.
- Ensure orphaned processes are safely terminated before launching new build loops.
