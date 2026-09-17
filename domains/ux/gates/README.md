# Gates — ux domain

> Every gate file in this folder MUST:
> 1. Have a PASS/FAIL rule with a NUMERIC threshold (no subjective language alone).
> 2. Have a retry policy carrying concrete remediation actions (max 1 free retry). Human required on second fail.
> 3. Fail without a threshold defined = default HARD FAIL.
> 4. Declare the machine-readable frontmatter `che-ship §0.9.5` parses: a numeric threshold
>    (`threshold_pass` or `threshold_hard_stop`), `retry_policy`, `log_format_decisions`,
>    `tool_official` (the official CLI/MCP channel per §20 — never an invented one), and `executable`.
>
> **`executable: false`** declares that the gate has no working mechanism yet. Ship then SKIPS it
> and logs `DOMAIN-GATE-SKIPPED-NOT-IMPLEMENTED` — it is never reported as PASS. It MUST come with a
> `blocked_by:` reason, because a silent skip is indistinguishable from a verification that happened.
> Before declaring `executable: true`, confirm the declared tool and command actually resolve: a gate
> naming a non-existent tool or flag is worse than a gate that admits it is not ready, because it
> sends the next agent down a path that cannot work.
>
> Pattern copy (structure + thresholds) from: `domains/ux/gates/pixel-check-gate.md`.
> It is now `executable: true` and runnable via `che pixel check`, so its §1/§2 tolerances **and** its
> §2 Execution recipe are both worth copying. Copy the shape, not the numbers: tolerances and weights
> must come from the gate's own §1 table.
