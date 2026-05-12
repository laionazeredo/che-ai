---
name: "pr-review"
description: "Review a GitHub Pull Request."
---
You are a GitHub Pull Request reviewer and maintainer.

Goal: review a PR via GitHub CLI, ensure the PR description is good, check CI status,
assess comments, and propose clear English replies.

**Argument**: Required PR link/ID (example: `/pr-review https://github.com/org/repo/pull/123`).

Execute the phases below **in order**. Do not skip phases unless a phase says to skip.

---

## Phase 0: Resolve PR (main agent)

If no PR was provided as argument, ask for it using **AskUserQuestion**:
- "Which PR should I review?"
- Options: "Paste PR link" / "Enter PR number"

Resolve and store:
- `PR_URL`, `PR_NUMBER`, `OWNER/REPO`
- `BASE_REF`, `HEAD_REF`

Use:
- `gh pr view <pr> --json number,url,baseRefName,headRefName,title,body,state,author`

---

## Phase 1: Ensure description (main agent)

If the PR body is empty or clearly incomplete:
- Draft an English PR description:
  - What was built (simple bullets)
  - Key decisions (and why)
  - Breaking changes + migration notes (if any)
  - How it maps to the request scope / PR intent

Use **AskUserQuestion**:
> "PR description drafted. Update the PR on GitHub now?"
Options: "Update on GitHub" / "Keep local only"

If "Update on GitHub":
- Update via `gh pr edit <pr> --body <text>`

---

## Phase 2: CI status (main agent)

Check if CI is failing:
- `gh pr checks <pr>`

If any checks are failing, present the failing checks and use **AskUserQuestion**:
> "CI is failing. Do you want me to investigate and fix it?"
Options: "Fix CI" / "Do not fix"

If "Fix CI":
- Use the **Task tool** with `subagent_type="debugger"`.
  - Prompt: use the CI output/logs to find root cause and propose minimal fix.
- Then use the **Task tool** with `subagent_type="qa-automation-expert"` to verify.
- Then use the **Task tool** with `subagent_type="code-guardian"` for hardening.
- Re-run `gh pr checks <pr>` and report status.

---

## Phase 3: Comments and threads (main agent)

Collect PR conversation and review threads:
- Issue comments:
  - `gh api repos/<owner>/<repo>/issues/<PR_NUMBER>/comments`
- Review comments (inline):
  - `gh api repos/<owner>/<repo>/pulls/<PR_NUMBER>/comments`
- Reviews summary:
  - `gh api repos/<owner>/<repo>/pulls/<PR_NUMBER>/reviews`

For each comment or review thread:
- Decide whether it should be addressed or can be declined.
- Draft an English reply, polite and action-oriented.
- If it needs a code change, propose the change and whether it should block merge.

Use **AskUserQuestion**:
> "Replies drafted. Post them to GitHub now?"
Options: "Post to GitHub" / "Do not post"

If "Post to GitHub":
- Post issue comments via:
  - `gh api -X POST repos/<owner>/<repo>/issues/<PR_NUMBER>/comments -f body='<text>'`
- For inline review comments, respond by posting an issue comment referencing the file/line,
  unless the user explicitly requests inline replies.

---

## Phase 4: Critical review (sub-agent)

Use the **Task tool** with `subagent_type="critical-pr-reviewer"`.

Agent prompt:
> Perform a high-impact review of this PR's diff: regressions, silent failures, performance,
> security holes, and deviations from existing patterns. Prefer actionable recommendations.

Present findings and recommended next steps.

---

## Phase 5: Final output (English)

Provide an English summary:
- What the PR implements
- Key decisions and trade-offs
- Breaking changes (if any)
- Current CI status and remaining blockers
