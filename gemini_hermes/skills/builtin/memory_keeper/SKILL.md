---
name: memory_keeper
description: Best practices for managing persistent long-term memory (MEMORY.md and USER.md).
version: 1.0.0
tags: [memory, persistence, context]
---

# Memory Keeper Procedure

Gemini-Hermes maintains persistent state across sessions. Use this procedure to ensure memory stays relevant and compact:
1. **Differentiate Memory Types**:
   - `USER.md`: User identity, background, preferences, communication style, domains of interest, project goals.
   - `MEMORY.md`: Long-term operational knowledge, environment facts, server paths, completed milestones, key rules.
2. **When to Update**:
   - When the user explicitly asks you to remember something ("remember that...", "note down...").
   - When critical facts about the workspace or system configuration are established.
3. **Synthesis & Quality**:
   - Write declarative, concise bullet points with timestamps.
   - Avoid duplicating existing notes or recording temporary transient chat state.
