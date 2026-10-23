---
description: "Triage ALL PR comments: classify human/bot, actionable vs nit, produce implementation plan + polite reply drafts."
arguments:
  - name: pr_url
    description: "GitHub PR URL (REQUIRED)."
    required: true
---

IMMEDIATELY invoke **`che-pr-comments`** Skill.

Preflight: `gh auth status` OK.

Skill: pull all comments via `gh pr view --json comments,reviews` → classify (CORRECTNESS, SECURITY, ARCHITECTURE, SCOPE CREEP, QUESTION, NIT, PRAISE, DISCUSSION, OUTDATED, DUPLICATE) → save `$CHE_WORKSPACE_SHARED/pr_comments/pr-<N>_<YYYYMMDD>.md` (resolved via `che compute_paths`; NEVER inside the worktree) → deliver 5 buckets (TO IMPLEMENT / DRAFT RESPONSES / DISCUSSION PENDING / NIT / RESOLVED SILENTLY) → user approves → implement fixes + optionally post replies.

Reply drafts: 1-2 sentences, in the same language as the comment, thanking the review first, and citing the implementing commit (`Fixed in <SHORT_SHA>`) whenever the suggestion is accepted.
