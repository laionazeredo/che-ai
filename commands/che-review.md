---
description: "High-impact BLOCKING-only code review on a GitHub PR. Runtime/Security/Deps/SCope only — never style bikeshed."
arguments:
  - name: pr_url
    description: "GitHub PR URL (REQUIRED — first positional arg)."
    required: true
  - name: ticket
    description: "Linear/Jira ticket URL for scope context."
    required: false
  - name: scope
    description: "Free-text scope description (if no ticket)."
    required: false
---

IMMEDIATELY invoke **`che-code-review`** Skill.

Preflight:
1. `gh auth status` must be OK.
2. PR URL must be reachable and parseable.
3. Pull ticket context / scope from args.
4.21→4. Skill: 4-category review (Runtime / Security+PII / Deps-blast-radius / Scope deviation) → report saved at `$CHE_SESSION_DIR/reviews/` → verdict 🔴 REQUEST CHANGES / 🟡 APPROVE WITH COMMENTS / 🟢 APPROVE in English.
