---
name: multi_step_researcher
description: Systematic procedure for multi-step web research, technical documentation exploration, source triangulation, and dense executive synthesis.
version: 1.0.0
tags: [research, web, documentation, synthesis]
---

# Multi-Step Researcher Procedure

Use this skill when investigating technical topics, third-party libraries, breaking changes, architecture patterns, or complex problem spaces.

### 1. Problem Scoping & Query Formulation
- Identify key unknowns, version constraints, and technical goals.
- Generate 2–3 targeted search queries targeting official docs, GitHub issues, or RFCs rather than generic blogs.

### 2. Deep Retrieval & Source Triangulation
- For official documentation: prioritize GitHub READMEs, release notes, and authoritative documentation domains.
- Triangulate facts: cross-reference at least two independent sources or verify against real code implementations.
- Read full contents via URL fetching or repo file exploration rather than relying solely on search snippets.

### 3. Direct Targeted Inspection
- Directly extract and inspect relevant sections of documentation or source code.
- Avoid context bloat by focusing strictly on the relevant APIs, error signatures, or configurations.

### 4. Dense Executive Synthesis
- Structure the findings into:
  1. *Core Architectural Answer*: Direct solution with concrete examples.
  2. *Key Caveats & Gotchas*: Version constraints, breaking changes, or performance traps.
  3. *Actionable Recommendation*: Concrete steps or code snippets ready for implementation.
