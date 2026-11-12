---
description: "Writes a plain-language, step-by-step guide so a NON-TECHNICAL person can verify the increment by hand: what was implemented/changed/fixed, how to test it locally or on the PR preview, and — when neither is possible — the exact route to a deployed environment. Captures the evidence to collect (logs, screenshots, video). Writes the guide; does NOT execute it (that is /che-manual-test) and gives no verdict (that is /che-review)."
arguments:
  - name: target
    description: "GitHub PR URL, ticket URL or key (FLO-745), branch name, or absolute worktree path. Optional when --worktree is given."
    required: false
  - name: worktree
    description: "Absolute worktree path (REQUIRED for local analysis). If missing and no PR URL is given → ASK."
    required: false
  - name: base
    description: "Base branch to diff against. Default: repository default branch; ask when two candidates are equally plausible."
    required: false
  - name: lane
    description: "Force the verification lane: auto (default) | local | preview | remote."
    required: false
---

IMMEDIATELY invoke **`che-manual-verification`** Skill.

Preflight dispatch:

1. **Worktree** — confirm the absolute path (§19 binding; mismatch or missing → AskUserQuestion). Required for lane A and for reading the diff.
2. **Input classification, first match wins** — PR URL → collect `gh pr view` / `gh pr diff --name-only` / `gh pr checks`; ticket URL or key → retrieve via the matching MCP tool; branch or path → resolve the base branch; nothing → ask.
3. **Context sources** — latest SPEC in `$CHE_WORKSPACE_SHARED/specs/`, `manual_test_plan.md` when present (reuse its AC wording and setup commands), existing QA evidence, and the repository's own scripts for setup commands.
4. **Lane decision** — local vs PR preview vs after deploy, using the cheapest lane that can observe the expected result. Honour `--lane` when given.
5. **Write the nine-section guide** — what changed · prerequisites · lane · lane A steps · lane B preview · lane C deployed path · evidence checklist · failure report template · not-verifiable-by-hand.
6. **Save** via `che output_path "verification" "che-manual-verification" "<related_id>" "workspace" "md"` → `$CHE_WORKSPACE_SHARED/verification/<related_id>/` (NEVER inside the worktree). Deliver a condensed four-section summary in the chat language.

Hard rules: never invent a command, URL, port, env-var name or role (`unknown — ask <role>` instead); never include a secret (names only); never execute the steps; never emit a merge verdict.
