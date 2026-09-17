---
name: shell_execution
description: Procedure for executing shell commands and inspecting system environments safely and effectively.
version: 1.0.0
tags: [shell, linux, devops, tools]
---

# Shell Execution Procedure

1. **Safety First**:
   - Never run destructive commands (e.g. `rm -rf /`, formatting disks) without explicit confirmation.
   - Prefer non-interactive flags (`-y`, `-q`, non-blocking).
2. **Output Handling**:
   - Limit very large outputs using `head`, `tail`, or grep.
   - Always verify exit codes and handle stderr errors cleanly.
3. **Reproducibility**:
   - Provide clear explanations of what actions were taken and their outcomes.
