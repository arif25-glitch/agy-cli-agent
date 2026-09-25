# Gemini-Hermes Long-Term Memory

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
- Absolute Factual Integrity ("NEVER LIE"): Never fabricate, bluff, or hallucinate completed actions. Never claim an action is performed or saved unless verified with physical tool execution.
- Physical Memory Persistence: Memory updates must be explicitly written to `/gemini-hermes/data/memory/` files (`USER.md`, `MEMORY.md`, `BACKLOG.md`, `REFERENCES.md`) via file tools. Never state memory is locked/saved without an actual tool write.
- Dual-Mode `/btw` Sidecar: When handling mid-task side interactions, classify input into ephemeral queries vs. queued directives. Answer questions (live status, technical, general, absurd) concurrently with zero transcript pollution; enqueue action directives into sequential task queue.
- Mid-Flight Steering (`/steer`): Provide instant course correction. If a task is executing, immediately halt the active turn, capture prior progress context, update status in-place (`⏸️ Superseded by /steer`), and launch a redirected turn within the same conversation session without race conditions or premature queue firing. If idle, apply the directive as immediate top-priority guidance.
- Automatic Chat Queueing ("Zero Message Drop"): Incoming user messages and attachments sent without slash commands during active execution are automatically enqueued into a sequential FIFO queue (capacity limit 10), acknowledged with real-time queue position, and sequentially drained upon task completion without message loss or race conditions.
- Strict 2-World Architecture (Pure Core vs Jev Accelerator): All Jev AI capabilities reside exclusively inside `gemini_hermes/jev/`. Core `./run.sh start` remains 100% pure and independent (deterministic regex/keyword heuristics for `/btw`, zero external SDK calls). Accelerated `./run.sh start-jev` / `./run.sh background-jev` enforces API key demand guardrails (`TYPESAFE_API_KEY` / `JEV_API_KEY`) on startup, guiding missing keys to `./run.sh config` or informing fallback to pure `./run.sh start`. Plugs in `JevAdapter` for dynamic effort and smart sidecar classification with automatic graceful fallback.
- Dynamic Cost & Workload Model Routing: Inbound prompts are dynamically evaluated before model dispatch into 4 cost-calibrated Antigravity tiers: Tier 1 (`gemini-3.6-flash`, low effort) for cheap/fast simple interaction & casual chat; Tier 2 (`gemini-3.7-flash`, medium effort) for balanced coding & single-file edits; Tier 3 (`gemini-3.8-flash`, high effort) for higher workloads, architecture, and multi-file agentic runs; Tier 4 (`gemini-3.1-pro`, high effort) for extreme algorithmic reasoning. Manual overrides available via Telegram `/model`.
- Token Efficiency & Context Optimization: All follow-up turns (Turn > 0) use lean differential prompts, omitting redundant static base persona and full skill catalogs (>85% prompt token reduction). Cache prefix stabilization places immutable instructions at index 0 and dynamic session context at the bottom. Jev JIT skill selector dynamically activates only relevant procedures. Autonomous Context Checkpointing automatically resets and rotates sessions at token/turn ceilings (`50k` tokens / `15` turns) with a compact Context Bridge summary, resetting the $O(N^2)$ accumulation while guaranteeing 100% loss-free long-term continuity.
- Dynamic Relative Growth Rotation (Zero Rotation Loop): Sessions track `session_baseline_tokens` on Turn 1 and measure relative context expansion (`max_growth_tokens = 40,000`, `growth_ratio = 2.0`). Enforces a strict minimum turn guardrail (`min_turns = 2`), permanently preventing single-turn rotation loops even when initial prompts or memory contexts are large, backed by a safety hard ceiling (`120,000` tokens).
- Autonomous Memory Pruning & Archiving (2 Worlds): Base context is kept lean and sharp via autonomous post-turn tiering. World 1 (Pure Core) provides 100% deterministic, zero-dependency pruning for completed tasks (`BACKLOG_ARCHIVE.md`) and stale memory notes (`MEMORY_ARCHIVE.md`); World 2 (Jev AI Accelerator) leverages semantic `Choice` evaluation to classify entries as transient vs evergreen with automatic graceful fallback.



## Memory Scaling & Retention Protocol
- Semantic distillation: Compress episodic interactions into compact declarative rules.
- Tiered storage: Hot in-prompt context, warm modular files, cold disk archives.
- Skill graduation: Recurrent operational procedures graduate into modular procedural skills.
- Periodic pruning: Regularly audit and remove obsolete context to eliminate context rot.

