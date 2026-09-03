---
description: "Triage ALL PR comments: classify human/bot, actionable vs nit, produce implementation plan + polite reply drafts."
arguments:
  - name: pr_url
    description: "GitHub PR URL (REQUIRED)."
    required: true
---

IMMEDIATELY invoke **`che-pr-comments`** Skill.

Preflight: `gh auth status` OK.

Skill: pull all comments via `gh pr view --json comments,reviews` → classify (CORRECTNESS, SECURITY, ARCHITECTURE, SCOPE CREEP, QUESTION, NIT, PRAISE, DISCUSSION, OUTDATED, DUPLICATE) → save `.trae/pr-<N>-comments_<YYYYMMDD>.md` → deliver 5 buckets (TO IMPLEMENT / DRAFT RESPONSES / DISCUSSION PENDING / NIT / RESOLVED SILENTLY) → user approves → implement fixes + optionally post replies.
