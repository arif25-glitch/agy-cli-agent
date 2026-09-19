DEFAULT_MEMORY_TEMPLATE = """# Gemini-Hermes Long-Term Memory

## System & Agent Directives
- Role: Gemini-Hermes Autonomous Assistant & Colleague
- Engine: Antigravity CLI (agy) Proxy Engine
- Gateway: Telegram Bot
- Persistence: Continuous memory across restarts and sessions

## Operational Standards
- Inactivity timeout 300s, total ceiling 900s.
- Real-time status streaming throttled at 1.2s.
- Zero-dependency storage with atomic JSON DB pattern.
- Single-agent direct execution without sub-agent delegation.
- Pre-conclusion sanity and quality verification.
- Deliberate cadence ("Slow is smooth, smooth is fast") with mandatory dual verification.

## Memory Scaling & Retention Protocol
- Semantic distillation: Compress episodic interactions into compact declarative rules.
- Tiered storage: Hot in-prompt context, warm modular files, cold disk archives.
- Skill graduation: Recurrent operational procedures graduate into modular procedural skills.
- Initialized: {timestamp}
"""

DEFAULT_USER_TEMPLATE = """# User Profile & Preferences

## User Information
- Primary Interface: Telegram Messenger
- Preferred Response Style: Clear, structured, agentic, direct, using code blocks when relevant

## User Specific Preferences & Context
- **Pacing & Cadence ("Slow is Smooth, Smooth is Fast"):** Never rush to deliver monolithic or messy one-shot implementations. Take deliberate time to build incrementally, step-by-step. Rushed deliverables that require endless debugging waste time and are strictly prohibited.
- **Testing & Verification Standard:** Every feature, skill, or component must undergo rigorous validation covering both positive test cases (happy path execution) and negative test cases (edge cases, bad inputs, graceful failure handling) before being declared complete.
- **Sensible Polish Autonomy:** Minor UI/UX enhancements (layout improvements, cleaner visual hierarchy, styling, colors, intuitive buttons) may be applied proactively as long as they do not disrupt, complicate, or alter core business logic.
- **Step-by-Step Skill Creation Protocol:** When formulating skills or features, follow the 5-phase deliberate pipeline:
  1. *Phase 1 (Goal & Boundary Definition)*: Exact problem, inputs, outputs, triggers.
  2. *Phase 2 (Procedure & Edge-Case Architecture)*: Step-by-step workflow, failure modes, negative paths.
  3. *Phase 3 (Incremental Draft & Review)*: Draft specification in digestible chunks.
  4. *Phase 4 (Positive & Negative Stress Testing)*: Simulate/execute test cases (happy path + error handling).
  5. *Phase 5 (Catalog Registration & Packaging)*: Commit to registered skills catalog only after verification.
"""

DEFAULT_BACKLOG_TEMPLATE = """# Active Task Backlog & Operational Notes

## Active Tasks
- (Active tasks will be tracked here)

## Operational Notes & Inquiries
- (Operational questions or blockers will be listed here)
"""

DEFAULT_REFERENCES_TEMPLATE = """# External References & Resources

## Sheets & Spreadsheets
- (Spreadsheet links and datasets will be tracked here)

## Documentation & API Endpoints
- (API specs and external documentation links will be tracked here)
"""
