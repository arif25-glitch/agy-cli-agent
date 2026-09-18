---
name: auto_debugger
description: Systematic procedure for error log parsing, stack trace isolation, root cause hypothesis testing, minimal reproducible test case verification, and surgical patching.
version: 1.0.0
tags: [debugging, troubleshooting, diagnostics, logs, testing]
---

# Auto-Debugger Procedure

Use this skill when diagnosing crashes, 400/500 API errors, build failures, type errors, or runtime anomalies.

### 1. Error Isolation & Evidence Gathering
- Capture the raw error message, status codes, and stack trace line numbers.
- Check relevant service/daemon logs using `tail -n 100` or `grep -n` around the exact timestamp of failure.
- Distinguish between client-side serialization errors (e.g. JSON `null` values), network/timeout issues, and server exceptions.

### 2. Root Cause Hypothesis Generation
- Formulate 1–2 testable hypotheses:
  * Why did this variable/payload take an unexpected form?
  * What changed in the upstream contract or environment?
- Inspect the offending source code lines directly using `view_file`.

### 3. Surgical Patch & Minimal Fix
- Make targeted, minimal modifications rather than broad rewrites:
  * Handle edge cases (empty strings, `None`/null values, unexpected types).
  * Add defensive guards and fallback handlers.
  * Preserve existing comments and docstrings.

### 4. Verification & Regression Testing
- Re-run the exact command or endpoint call that previously failed to verify the fix passes.
- Inspect logs to confirm no new warnings or secondary errors were introduced.
- Document the root cause and applied fix cleanly.
