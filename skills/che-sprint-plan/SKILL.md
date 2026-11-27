---
name: "che-sprint-plan"
description: "Build an evidence-based sprint plan from a board or a list of ticket links. Triages tasks into ready / needs-clarification / blocked, maps dependencies, asks everything unclear, then produces a day-by-day plan with parallel waves (≤ parallelism, default 3). Saves sprint-plan.md under ~/.che-workspaces/<slug>/sprints/<start>_<end>__<name>/ and supports --add/--remove updates mid-sprint."
---

# Che Sprint Plan

> **SHARED REFERENCES (CANONICAL — DO NOT DUPLICATE body here):**
> - Engineering contracts (evidence-based claims, KISS/blast-radius, DbC): `engineering-contracts` skill
> - Path resolution (`~/.che-workspaces/<slug>/` project root, `CHE_WORKSPACE_SHARED`, `CHE_SESSION_DIR`): `che` CLI — `eval "$(che compute_paths WT SID --cwd "$PWD")"` + `che project list`
> - Sprint folder canonical path: `che_core.project_layout.get_sprints_dir()` (single source of truth)
> - 2-LEVEL worktree binding: engineering-contracts §19

## §0 PURPOSE

Produce a **sprint plan** that a single developer (optionally assisted by AI agents) can execute
day by day. The plan is a **living contract**: it holds the task table with session/PR/status links
and accepts `--add`/`--remove` while the sprint runs.

The plan is **not** a SPEC and **not** a TASK GRAPH. It references tickets (from any board) and
leaves the detailed execution contract to `/che-spec` + `/che-act` per ticket.

## §1 PREFLIGHT

1. Resolve project: `che project list` → match the slug the user gave (or ask). The sprint folder is
   `~/.che-workspaces/<slug>/sprints/` (canonical: `get_sprints_dir`).
2. If no project slug is known and no worktree binding exists → ASK first. Do not guess.
3. Confirm the sprint inputs (below) are sufficient. If not, ask before drafting.

## §2 INPUTS (collect; nothing is assumed)

| Input | Source | Required |
|---|---|---|
| Board / ticket links | Linear / GitHub / Airtable / raw URL list | yes |
| Start date | user | yes |
| End date | user | yes |
| Effective working days | user | yes (each day full/half; ex: "29/11 half day") |
| Parallelism (max concurrent tasks) | user | default 3, ask to confirm |
| Contextual notes | user | optional (risks, releases, meetings) |

Dates are normalized to `YYYY-MM-DD` internally.

## §3 INTAKE — understand scope and dependencies

For every ticket link:
1. Resolve the provider (GitHub → `gh issue view`; Linear → MCP; Airtable → MCP; else `WebFetch`).
2. Extract: title, description, acceptance criteria, labels, state, assignee, and any explicit
   dependency mentions ("blocks", "depends on", "after #N").
3. Classify each ticket into exactly one bucket:

| Bucket | Definition | Action |
|---|---|---|
| **ready** | clear scope + ACs, no open dependency | goes into the plan |
| **needs-clarification** | ambiguous scope, missing ACs, or a business/PM question | collect the question, do NOT schedule until answered |
| **blocked** | clear, but depends on another ticket not yet scheduled | schedule after its dependency |

4. Derive the dependency edges (hard = blocks start; soft = blocks finish). Cite evidence for every
   edge (`issue #N mentions #M`, label, or stated by the user). An uncited edge is an assumption.

## §4 CLARIFY (mandatory before drafting)

Ask, in one consolidated message, every item that is unclear or ambiguous. Never assume. Examples:
- a ticket with no acceptance criteria (needs-clarification)
- a dependency the user did not state
- a working-day constraint (half day, holiday)
- whether two tickets touch the same files/repo (affects parallelism)

Keep to the evidence bar: every assertion is `[verified: <link>]` or `[assumption: ...]` and is
surfaced to the user for confirmation.

## §5 BUILD THE PLAN (day-by-day, with waves)

1. Lay the calendar: effective working days between start and end (respect half-days).
2. Topologically order the `ready` tickets by hard dependencies.
3. Pack each day into **waves** of ≤ `parallelism` tasks:
   - a wave must contain tasks with **disjoint files/repos** (no merge conflicts);
   - a wave must contain **no internal dependency** (no task depends on another in the same wave);
   - if a task has a hard dependency on a task in an earlier wave of the same day, it moves to the
     next wave (serial chain), not the next day.
4. Mark the critical path (longest dependency chain) and the days that carry it.
5. `blocked` tickets are scheduled immediately after their dependency resolves.
6. `needs-clarification` tickets are listed in a dedicated "open questions" section, not scheduled.

## §6 TASK TABLE (the living section)

The sprint plan MUST contain this table. It is the section updated by `--add`/`--remove` and by
`/che-spec --plan`.

| # | Ticket (link) | Scope | Ready? | Depends on | Day/Wave | Session | PRs | Repos | Status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | [issue/13](url) | design system | ready | — | D1/W1 | sess-abc | — | repo | todo | — |

- **Ready?** ∈ `ready | needs-clarification | blocked`.
- **Session** = `che` session id handling the ticket (filled when execution starts).
- **PRs** = one or more PR links (a task may span multiple PRs).
- **Repos** = one or more repos involved.
- **Status** = `todo | in-progress | done | blocked | dropped`.
- **Notes** = free-form progress/blocker notes.

## §7 SAVE

1. Sprint folder name: `<start>_<end>__<name>` (slugified; ex. `2026-11-27_2026-12-02__marketplace-mvp`).
2. Canonical path: `~/.che-workspaces/<slug>/sprints/<folder>/sprint-plan.md`.
3. Write via `che write_file_atomic <path>` (stdin → tmp → atomic mv). The path is outside any user
   worktree by construction (project root).
4. Frontmatter:
   ```yaml
   sprint_id: <folder>
   project: <slug>
   start_date: YYYY-MM-DD
   end_date: YYYY-MM-DD
   working_days: [YYYY-MM-DD, ...]
   parallelism: 3
   status: draft
   sources: [ ... ]
   ```
5. Set `status: draft`; user approval flips it to `approved`.

## §8 UPDATES (`--add` / `--remove`)

- `/che-sprint-plan --add <links>` or `--remove <links>`.
- Recover the target sprint: if the session is bound to one, use it; else list
  `~/.che-workspaces/<slug>/sprints/` and ask which sprint (prioritise the most recent `status != done`
  sprint as the default suggestion).
- `--add`: run §3 intake + §4 clarify for the new ticket(s), then insert rows and re-pack the
  remaining calendar. Show the diff before writing.
- `--remove`: remove the row(s); if a removed ticket unblocked others, note it. Show the diff before
  writing.

## §9 RETURN VALUES

Last 2 lines of the transcript:
```
SPRINT_PLAN_PATH=<absolute path>
SPRINT_STATUS=draft|approved
```
