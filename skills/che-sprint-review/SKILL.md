---
name: "che-sprint-review"
description: "Review a finished sprint: gather ticket terminal statuses and dates per provider (GitHub via gh api, Linear/Airtable via MCP; else ask), verify delivery against sprint-plan.md, and produce sprint-review.md with a per-task report and project metrics (throughput, cycle time, plan accuracy, carry-over, blocker rate)."
---

# Che Sprint Review

> **SHARED REFERENCES (CANONICAL — DO NOT DUPLICATE body here):**
> - Evidence-based claims (E1–E3) + plain-language two-layer reports: `engineering-contracts` skill
> - Sprint folder canonical path: `che_core.project_layout.get_sprints_dir()`
> - Board access: GitHub `gh` CLI · Linear `linear` skill / MCP · Airtable MCP
> - Sprint plan contract (task table + day-by-day): `che-sprint-plan` skill

## §0 PURPOSE

At the end of a sprint, produce a **review** that answers: what was delivered, what was not, what was
blocked, whether delivery matched the plan (per planned day), and how the planning itself is performing
over time. Output is `sprint-review.md` next to `sprint-plan.md`, ready to feed PM/stakeholder reports.

## §1 PREFLIGHT

1. Resolve the target sprint: if the session is bound to one, use it; else list
   `~/.che-workspaces/<slug>/sprints/` and ask (prioritise the sprint that just ended).
2. Read `sprint-plan.md` (the plan is the source of truth for what was committed).
3. Resolve the ticket provider for each ticket link in the task table.

## §2 GATHER EVIDENCE (per task)

For every task in the plan's task table, resolve its **terminal state** and **dates**:

| Provider | Status/date resolution |
|---|---|
| GitHub | `gh issue view <n> --json state,closedAt,updatedAt,labels,comments` + `gh pr list --search` for linked PRs |
| Linear | `linear` skill / MCP (`list_issues`, `get_issue`) |
| Airtable | MCP (`list_records`, `get_record`) |
| Other / unknown | ask the user; never fabricate |

For "started" (when execution began): prefer a concrete signal (PR opened, branch created, ticket moved
to `in-progress`, session binding) — otherwise ask the user. Record `[unknown: ...]` rather than guessing.

## §3 VERIFY DELIVERY VS PLAN

Build a comparison:
- **done on planned day** — terminal state reached, and the terminal date ≤ the planned day.
- **done, late** — terminal state reached after the planned day.
- **not done** — no terminal state.
- **blocked** — terminal state is blocked or an explicit blocker is recorded.
- **dropped** — removed mid-sprint (from plan updates).

Cite the evidence per row.

## §4 PER-TASK REPORT

`sprint-review.md` MUST contain one row per task:

| Ticket (link) | Started | Ended | Result | Open items | Depends on | Blocks | Difficulties | PRs |
|---|---|---|---|---|---|---|---|---|
| [issue/13](url) | 27/11 | 27/11 | done | — | — | #18 | — | #74 |

- **Result** ∈ `done | done-late | not-done | blocked | dropped`.
- **Open items** = follow-ups (separate issues, TODOs, unreviewed PRs).
- **Difficulties** = what actually slowed the task (from comments, PR threads, or the user).

## §5 PROJECT METRICS

Compute, at minimum:

| Metric | Formula | Answers |
|---|---|---|
| Throughput | tasks `done` in sprint | how much shipped |
| Plan accuracy | `done-on-day / planned` | is the plan realistic |
| Carry-over rate | `not-done / planned` | how much slipped |
| Blocker rate | `blocked / planned` | dependency health |
| Cycle time | median(ended − started) per task | speed of execution |
| Scope churn | added + removed mid-sprint | plan stability |

Only compute metrics the evidence supports; mark the rest `[unknown: <how to obtain>]`.

## §6 SAVE

1. Path: `~/.che-workspaces/<slug>/sprints/<folder>/sprint-review.md` (same folder as the plan).
2. Write via `che write_file_atomic <path>`.
3. Structure (5-line header, then): §1 verdict · §2 delivery-vs-plan · §3 task-by-task report ·
   §4 metrics · §5 carried-over backlog + recommendations.
4. Language: two layers — plain-language summary first, machine tables after (engineering-contracts §23).

## §7 RETURN VALUES

Last 2 lines of the transcript:
```
SPRINT_REVIEW_PATH=<absolute path>
SPRINT_VERDICT=delivered|partial|off-track
```
