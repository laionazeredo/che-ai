# ADR-0001: Che ↔ Paperclip — seeding a multi-human agent organisation

- Status: Proposed
- Date: 2026-09-18
- Area: harness runtime / multi-human deployment

## Context

Che is a single-operator, git-native harness (see `docs/architecture-and-principles.md` §1): the
shared team brain lives in files + git, and there is no hosted dashboard. The team wants a
**shared, multi-human** control plane where several humans drive the same Che domains/experts
(PM, engineer, QA, designer, devops, …) against a **collective memory** over the same projects —
without paying token tax for filesystem + git + config that Che already owns.

Paperclip (https://docs.paperclip.ing) is a "company of agents" control plane: it does **not**
execute agents; it orchestrates them through adapters (`claude_local`, `codex_local`, …) via
heartbeat, with Postgres + UI as the source of truth, an org chart (`reportsTo`), recurring
routines (`cron` triggers), execution policies and a company-scoped skill store.

Question to settle: can a Paperclip company be **seeded directly from Che** — agents, org chart,
prompts/instructions, cron routines — as a **plug-and-play install**, rather than hand-built in
the UI?

## Decision

**Yes.** Paperclip's *company portability package* is the interchange format. A Che-shipped package
imports in a single call and reproduces the org structure, instructions bundles and cron routines
deterministically. Proven end-to-end on a throwaway `local_trusted` instance with a 3-agent seed:

```text
COMPANY.md                    # frontmatter { name, description, schema: "agentcompanies/v1", slug }
.paperclip.yaml               # schema: "paperclip/v1", schemaVersion: 7; agents + routines
agents/<slug>/AGENTS.md       # frontmatter { name, title, reportsTo }; body -> instructions bundle
tasks/<slug>/TASK.md          # frontmatter { name, assignee, recurring: true }; body -> description
```

- `agents/<slug>/AGENTS.md` frontmatter `{ name, title, reportsTo }` drives the **org chart**;
  the markdown body becomes the agent's **instructions bundle** (managed mode).
- `.paperclip.yaml` `agents.<slug>.role` sets the fixed role; `adapter.type: claude_local` binds
  the Che runtime.
- `tasks/<slug>/TASK.md` `{ name, assignee, recurring: true }` plus `.paperclip.yaml`
  `routines.<slug>.triggers[]` (`kind: schedule`, `cronExpression`, `timezone`) creates the
  **cron routine**.

## Rationale

- **No lock-in, no token tax.** The package is plain text (git-diffable), matching Che's SSoT ethic.
- **Deterministic, no LLM.** Roles, `reportsTo`, cron and instructions are data, not inference.
- **Reuses Che's existing structure.** `skills/` → company skills; `domains/*` → agent roles; the
  org chart mirrors the SDLC (PM → engineer → QA).
- **`claude_local` is the natural adapter** — the same Claude Code runtime Che targets — and it
  supports instructions bundles (`supportsInstructionsBundle: true`).

## Consequences

**Mandatory gotchas (pin in any seeder):**

1. `include.issues` defaults to `false`. A package with cron routines **silently drops them** unless
   the import body sets `include: { issues: true }`.
2. Adapters `process`/`http` are rejected only in *agent-safe* imports; the default `board_full`
   allows them. `claude_local` imports clean with `config: {}`.
3. Skill trust levels gate external imports: `skills/<name>/scripts/` → `scripts_executables` is
   **hard-blocked** from external sources. Che must not ship executable `scripts/` under skills.
   (`typescript-expert/scripts/ts_diagnostic.py` was the only offender and has been removed.)

**Open / follow-ups:**

- Not yet decided: whether Paperclip becomes the *supported* multi-human runtime, or stays a
  community recipe. This ADR records feasibility + mechanism; adoption is a separate decision.
- Human onboarding / collective-memory sync across humans is Paperclip-side (board memberships),
  not expressed by the package itself.

## Update — one-command, idempotent install (2026-09-18)

The manual UI import is gone. `paperclip/` now ships a generator plus a bootstrap:

```bash
paperclip/build-package.py    # seed/ + skills/  ->  package/  (org + skills, text-only)
paperclip/bootstrap.sh        # build -> boot local_trusted -> mint key -> import -> UI on :3210
```

Four findings make this unattended:

1. **One import = org + skills + assignment.** `importPackageFiles` runs whenever
   `include.skills || include.agents`, so a single POST brings the company, the agents, all skills
   **and** the per-agent mapping: the `skills:` list in `agents/<slug>/AGENTS.md` frontmatter is
   resolved to company-scoped skill keys and stored as `adapterConfig.paperclipSkillSync.desiredSkills`.
   Verified: pm=14, engineer=18, designer=8, qa=9 desired skills from one import.
2. **The import is idempotent.** Targeting the existing company
   (`target: { mode: "existing_company", companyId }` + `collisionStrategy: "replace"`) yields
   `company updated / agents updated / skills replaced` — no duplicates. `bootstrap.py` looks the
   company up by name and picks `new_company` only on the first run.
3. **A board API key can be minted without credentials** while the instance runs
   `local_trusted` on loopback (`POST /api/board-api-keys` succeeds with the implicit local actor),
   and it keeps working after the same container is switched to `authenticated`. This is the seam
   that makes phase 1 → phase 2 possible without a human session: `authenticated` rejects every
   anonymous request, including loopback (`403 Board access required`).
4. **Import from a GitHub path is equivalent to the inline upload.** The resolver accepts
   `https://github.com/<owner>/<repo>/tree/<ref>/<path>` and scopes the walk to `<path>`, so the
   generated package is importable straight from the repo:
   `https://github.com/laionazeredo/che-ai/tree/main/paperclip/package`.
