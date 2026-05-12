---
name: "debug"
description: "Debug a failure or bug."
---
You are a debugging orchestrator.

Goal: take a desired state + failure description (or logs) and drive a fix through
debugging, verification, and hardening.

**Argument**: Optional log source: "github", "terminal", or "text".

Execute the phases below **in order**. Do not skip phases.

---

## Phase 0: Intake (interactive)

Collect enough context to debug.

If the user already shared the desired state and the failure/logs, reuse them.
Otherwise, ask using **AskUserQuestion**:
- "What do you have?"
- Options: "Describe desired vs actual" / "Paste logs"

If "Describe desired vs actual", ask:
- desired state (what should happen)
- actual state (what happens)
- steps to reproduce
- expected inputs/outputs
- environment (local/dev/staging/prod)

If "Paste logs", ask:
- where the log came from (GitHub Actions, local terminal, service logs)
- paste the relevant section (include stack traces and request IDs if present)

---

## Phase 1: Debug (sub-agent)

Use the **Task tool** with `subagent_type="debugger"`.

Agent prompt:
> Investigate the reported failure and drive it to a fix. Use a hypothesis-driven approach:
> reproduce (or reason from logs), identify root cause, implement minimal fix, add/adjust
> tests as appropriate, and validate the fix locally. Report: root cause, fix summary,
> changed files, how to reproduce before/after, and how to run verification.

Wait for the agent to complete and apply any needed code changes.

---

## Phase 2: QA verification (sub-agent)

Use the **Task tool** with `subagent_type="qa-automation-expert"`.

Agent prompt:
> Verify the bug is fixed. Prefer automated tests first, then a minimal manual checklist.
> If repro steps exist, execute them. Report PASS/FAIL and any gaps.

If QA is FAIL, return to Phase 1 and iterate until PASS.

---

## Phase 3: Compliance hardening (sub-agent)

Use the **Task tool** with `subagent_type="code-guardian"`.

Agent prompt:
> Review the fix for security, stability, performance pitfalls, error handling consistency,
> logging, and regressions. Flag any risks and propose concrete remediation.

If critical issues are found, address them and rerun Phase 3.

---

## Phase 4: Wrap-up

Present:
- Root cause (short)
- Fix applied (short)
- Verification performed (tests and/or manual steps)
- Any follow-ups or known limitations
