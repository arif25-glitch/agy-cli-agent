---
name: manager_delegation
description: Procedure for operating as an Executive Engineering Manager, keeping primary context window compact and pristine by offloading high-context exploration, heavy file builds, and log analysis to worker subagents.
version: 1.0.0
tags: [delegation, orchestration, context_hygiene, subagents, manager]
---

# Executive Manager & Sub-Agent Offloading Procedure

Use this skill whenever handling large, data-heavy, exploratory, or multi-step engineering tasks to protect the primary context window from bloat and maintain sharp conversational memory.

### 1. High-Context Offloading Triggers
Immediately delegate to a worker sub-agent when:
- The task requires reading or searching across 3+ large files or unfamiliar directories.
- The task involves analyzing long error traces, terminal logs, or complex build output (>50 lines).
- The task requires scraping, fetching, or parsing multiple web documentation URLs.
- The task involves scaffolding a multi-file architecture or running heavy package installations.

### 2. Spawning the Right Worker Archetype
- **For Research & Discovery**:
  Spawn a `research` subagent:
  `invoke_subagent(TypeName="research", Role="Technical Codebase Researcher", Prompt="Explore X and find the exact functions responsible for Y. Return a dense 4-bullet summary with file paths and line numbers.")`
- **For Implementation & Build Scaffolding**:
  Spawn a `self` worker in an isolated branch:
  `invoke_subagent(TypeName="self", Role="Backend Feature Scaffolder", Workspace="branch", Prompt="Scaffold the models and database migration for Z, verify compilation, and return only the file diff list and test status.")`
- **Optimal Fleet Sizing (2 to 6 Workers)**:
  Technically, arbitrary sub-agents can be spawned, but operational best practice is targeted swarms of 2 to 6 specialists (e.g. Frontend Architect, Backend Developer, QA/Tester, Researcher). This prevents API rate limits, host resource contention, and synthesis noise.

### 3. Output Distillation & Context Hygiene
- Workers MUST NOT dump verbose logs back to the Manager.
- Workers return an **Executive Artifact**:
  1. *Status*: Success / Blocked / Error
  2. *Files Created/Touched*: Minimal list with line counts
  3. *Core Findings / Key Decisions*: 3–5 dense bullet points
  4. *Verification*: Pass/fail verification evidence

### 4. Manager Synthesis & Long-Term Memory
- The Manager reads the worker's distilled artifact.
- The Manager updates the project state (`ProjectManager`) and long-term memory (`MemoryStore`).
- The Manager provides a crisp, high-level, actionable summary directly to the user in Telegram.
- The primary context remains lean, sharp, and capable of weeks of continuous conversation.
