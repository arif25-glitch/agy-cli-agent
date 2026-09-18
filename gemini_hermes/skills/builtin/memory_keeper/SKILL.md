---
name: memory_keeper
description: Best practices for managing persistent modular memory (MEMORY.md, USER.md, BACKLOG.md, REFERENCES.md).
version: 1.1.0
tags: [memory, persistence, context]
---

# Memory Keeper Procedure

Gemini-Hermes maintains persistent state across sessions. Use this procedure to ensure memory stays modular, relevant, and compact:
1. **Differentiate Memory Domains**:
   - `USER.md`: User identity, communication preferences, formatting constraints, git push rules.
   - `MEMORY.md`: Long-term operational standards, proxy engine configurations, timeouts, architecture standards.
   - `BACKLOG.md`: Active task queue, in-progress items, operational inquiries, and blockers.
   - `REFERENCES.md`: External spreadsheets, documentation URLs, test case datasets, and API specs.
2. **When to Update**:
   - When the user gives an explicit preference or formatting instruction -> update `USER.md`.
   - When operational rules or architecture decisions are finalized -> update `MEMORY.md`.
   - When new tasks, bugs, or operational questions arise -> update `BACKLOG.md`.
   - When external links, sheets, or documentation are shared -> update `REFERENCES.md`.
3. **Synthesis & Quality Standards**:
   - Keep domain files focused and compact to avoid context dilution.
   - Write declarative, concise bullet points.
   - Avoid routine chat churn and ephemeral debug traces in persistent memory files.
