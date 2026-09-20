---
name: memory_keeper
description: Best practices for managing persistent modular memory (MEMORY.md, USER.md, BACKLOG.md, REFERENCES.md).
version: 1.2.0
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
4. **Long-Term Memory Scaling & Lifecycle**:
   - *Semantic Distillation*: Condense multi-turn dialogues into concise declarative rules (e.g. compress 1,000 conversation tokens into 2 high-signal bullet points).
   - *Tiered Storage*: Hot in-prompt active state, warm modular markdown files (`data/memory/`), and cold disk archives for completed tasks.
   - *Skill Graduation*: When a problem-solving pattern recurs repeatedly, graduate it into a standalone modular skill via `skill_creator` rather than accumulating procedural bloat in memory files.
   - *Periodic Pruning*: Regularly audit and prune stale context, temporary test endpoints, and completed backlog items.
5. **Absolute Factual Integrity ("NEVER LIE")**:
   - Updates must be physical: When the user shares identity details, project facts, or preferences, the agent MUST physically execute file editing tools (`replace_file_content` or `write_to_file`) on the target file in `data/memory/`.
   - Never claim or state "saved in persistent memory" if no tool call was actually executed to modify the file on disk.
   - Zero tolerance for hallucinating or bluffing completed memory operations.


