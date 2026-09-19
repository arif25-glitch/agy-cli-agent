---
name: skill_creator
description: Procedure for autonomously formulating and saving new reusable skills into the agent's knowledge base.
version: 1.1.0
tags: [meta, self-improvement, skills]
---

# Skill Creator Procedure

Follow the core engineering principle: **"Slow is smooth, and smooth is fast."** 
Never rush to generate a monolithic, untested skill in a single pass. Formulate and register new skills incrementally through this 5-phase deliberate protocol:

### Phase 1: Goal & Boundary Definition
- Clearly define the exact problem the skill solves.
- Specify input parameters, expected outputs, and precise trigger conditions.
- Define what the skill explicitly does NOT do to prevent scope creep.

### Phase 2: Procedure & Edge-Case Architecture
- Map out the sequential step-by-step procedure.
- Identify all potential failure points, dependency risks, and negative paths.
- Define explicit fallback and recovery mechanisms for each failure mode.

### Phase 3: Incremental Draft & Review
- Draft the procedural specification following the `agentskills.io` standard:
  * Frontmatter: `name`, `description`, `version`, `tags`.
  * Detailed markdown instructions, guidelines, common pitfalls, and practical examples.
- Review structure in digestible sections to maintain clarity.

### Phase 4: Positive & Negative Stress Testing
- **Positive Test**: Execute or simulate the standard happy-path workflow with valid inputs to confirm the expected outcome.
- **Negative Test**: Test boundary cases, invalid inputs, missing prerequisites, or error scenarios to verify graceful handling and informative diagnostics.

### Phase 5: Catalog Registration & Packaging
- Save the validated skill definition to `data/skills/<skill_name>/SKILL.md`.
- Register the skill in the active catalog and verify discoverability via `SkillManager`.
- Update documentation and commit changes.

