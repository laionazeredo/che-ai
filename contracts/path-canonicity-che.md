# PATH CANONICITY CONTRACT — CHE

> Single source of truth for the L1→L2→L3→L4 hierarchical structure of `CHE_WORKSPACES_ROOT`.
> Corresponding python helpers: `compute_paths` + `ensure_session_dirs` in `che_core/paths.py`.
> Invariants: NEVER break these contracts. If you need to evolve, update this file FIRST, THEN the python helpers, FINALLY the skills.

---

## 0. CANONICAL ENVIRONMENT VARIABLES

| Env | Default | Valid Values | Purpose |
|-----|---------|--------------|---------|
| `CHE_WORKSPACES_ROOT` | `$HOME/.che-workspaces` | Any existing absolute path with write permission | **Root of EVERYTHING** in Che (L1 workspaces). 1-release fallback: if new path DOES NOT exist AND old `$HOME/code/harness-sessions` exists → reuse the old one. |
| `CHE_HOST_IDE` | `trae` | `trae`, `codex`, `cursor`, `claude-code`, `opencode` | Agnostic IDE host identifier. Future adapters in `adapters/<host_ide>/`. |
| `CHE_SESSION_ID` | (3-level fallback: `CHE_SESSION_ID` → `HARNESS_SESSION_ID` → `SESSION_ID` → `slug-safe-date`) | UUID / slug-safe session id |agent session UNIQUE identifier. Same value used in Level 1 registry JSONL. |
| `CHE_HOME` | `$HOME/.che-ai` | Any absolute path with `skills/` + `contracts/` + `commands/` + `domains/` | **Config repo** root (skills, rules, commands). Not to be confused with CHE_WORKSPACES_ROOT (user data). Legacy `$HOME/.trae` is honoured only while it still contains `CHE_RULES.md`. |

---

## 1. L1→L2→L3→L4 HIERARCHY (DIAGRAM)

```
CHE_WORKSPACES_ROOT ($HOME/.che-workspaces/)  ← L1 — WORKSPACE (IDE workspace = set of repos)
│
├─ manifesto48/                                 ← L1 EXAMPLE: workspace name (a set of projects/repos)
│  │
│  ├─ vc-educar-corp-website/                  ← L2 — PROJECT (1 git repo, slug-safe name)
│  │  │
│  │  ├─ project/                              ← L2-DURABLE: EVERYTHING that lasts BETWEEN worktrees and BETWEEN sessions
│  │  │  ├─ xray.md                             ←   project X-ray (stack, entrypoints, languages, tests, CI, DB)
│  │  │  ├─ architecture.md                     ←   architectural diagram + durable decisions (Out of RADAR)
│  │  │  ├─ roles.md                            ←   roles, stakeholders, PM, design, dev, GitHub/Linear owner
│  │  │  ├─ decisions/                          ←   architectural ADRs (Out of RADAR registry)
│  │  │  ├─ onboarding.md                       ←   new dev onboarding step-by-step (setup, seeds, login)
│  │  │  ├─ product/                            ←   product docs, PRDs, roadmap (Out of RADAR)
│  │  │  └─ _legacy_uncategorized/              ←   ⛑️ UNCATEGORIZED ITEMS (old harness-sessions origin
│  │  │                                            DO NOT DELETE. Keep for 1 release, then human review.)
│  │  │
│  │  ├─ __main/                                ← L3 — WORKTREE (default branch = main). Always __ prefix for branches.
│  │  │  │
│  │  │  ├─ .wt/                                ← L3-SHARED: EVERYTHING shared BETWEEN sessions IN THE SAME worktree
│  │  │  │  ├─ decisions.log.jsonl              ←   this worktree's decision log (single append, via helper)
│  │  │  │  ├─ envelopes/                       ←   TASK ENVELOPES (SM→Dev templates) for this worktree
│  │  │  │  ├─ gh_stack/                        ←   gh-stack plan + PRs (#1,#2,#3 hierarchical stack)
│  │  │  │  ├─ reports/                         ←   shared reports (QA, scope-check, code-review audit,
│  │  │  │  │                                     compliance scan, merge audit) with YYYY-MM-DD prefix
│  │  │  │  ├─ specs/                           ←   Approved SPEC files (.md + machine-parsable YAML frontmatter)
│  │  │  │  ├─ state.jsonl                      ←   pointer "which session is active in this worktree"
│  │  │  │  ├─ qa/                              ←   shared QA fixtures, seed data, durable evidence
│  │  │  │  └─ designs/                         ←   shared design artifacts (OpenPencil export, tokens)
│  │  │  │
│  │  │  └─ sessions/                           ← L4 — SESSIONS (each folder = 1 agent session)
│  │  │     │
│  │  │     ├─ 6a981dc48684a64a52ebd487/       ← L4 EXAMPLE: 1 session id (slug-safe UUID/date)
│  │  │     │  ├─ manifest.json                  ←   METADATA: session_id, worktree_path, user_prompt,
│  │  │     │  │                                   started_at, status, CHE_HOST_IDE, start/end commit hash
│  │  │     │  ├─ debugger/                      ←   debugger: stack traces, reproductions, hypotheses
│  │  │     │  ├─ diffs_context/                 ←   diffs conversation brief, extracted PR context
│  │  │     │  ├─ execution/                     ←   executed shell commands + outputs + exit codes
│  │  │     │  ├─ gh_stack/                      ←   this session's gh_stack artifacts (if any)
│  │  │     │  ├─ qa/                            ←   this session's QA: ephemeral evidence, screenshots
│  │  │     │  │                                    (TTL 30d policy: harness/qa skill policies)
│  │  │     │  ├─ reports/                       ←   this session's reports (ephemeral, copied to .wt if durable)
│  │  │     │  └─ decisions.log.jsonl            ←   this session's decisions (append; also duplicated
│  │  │                                             in .wt/decisions.log.jsonl via helper = single writer)
│  │  │
│  │  └─ feat-FLO-513--Process-a-refund/        ← L3 EXAMPLE: feature branch worktree (same __main structure above)
│  │     ├─ .wt/                                 ← L3-SHARED for this specific worktree (decisions, envelopes, reports)
│  │     └─ sessions/                           ← L4 sessions ONLY for this worktree
│  │
│  ├─ other-project-xyz/                        ← L2 ANOTHER PROJECT within the same manifesto48 workspace
│  │  ├─ project/                               ← L2-DURABLE
│  │  └─ __main/                                 ← L3 + L4
│  │
│  └─ .migration_reports/                       ← L1-OPTIONAL: migration reports from when this workspace was moved
│     └─ 2026-09-03_migration_manifesto48.md
│
└─ flockr/                                       ← L1 ANOTHER workspace: set of Flockr repos (Lumos etc.)
   └─ Lumos/                                     ← L2 PROJECT Flockr Lumos git repo
      ├─ project/
      ├─ __main/
      └─ feat-FLO-732--Create-dedicated-S3/
```

---

## 2. INVARIANTS (NON-NEGOTIABLE — HARD FAIL)

### 2.1. Layer Invariants
| # | Invariant | VIOLATION Example (prohibited) |
|---|-----------|--------------------------------|
| I1 | **Sessions ALWAYS stay within an L3 worktree.** | Creating `sessions/` directly inside L2 project or L1 workspace = FAIL. |
| I2 | **Durable info (xray, architecture, roles) stays in L2 `project/` OUTSIDE any worktree.** | Placing `architecture.md` inside `__main/.wt/` = FAIL (it will disappear if worktree is deleted). |
| I3 | **Shared info IN THE SAME worktree stays in L3 `.wt/`.** | Placing `decisions.log.jsonl` inside a specific session = FAIL (other sessions won't see it). |
| I4 | **Worktree branch name = `__<branch-slug-safe>` (TWO underscores prefix).** Branch `main` → `__main`. Branch `feat/FLO-513/refund` → `feat-FLO-513--refund` (with TWO dashes replacing `/`, TWO underscores prefix). | Creating `main/` folder without `__` prefix = FAIL. |
| I5 | **NO folder named `workspace/` (IDE L1 workspace semantic collision).** Durable worktree assets use `.wt/`. | Any path with literal name `workspace/` at L2/L3 level = FAIL. |
| I6 | **NEVER delete `project/_legacy_uncategorized/` (1 release minimum retention).** | `rm -rf` uncategorized items automatically = FAIL. Requires human review. |
| I7 | **Migration ALWAYS NON-DESTRUCTIVE (only `mv -n`, never `cp -r` then `rm -rf`).** | Copying everything, then deleting the old folder all at once = FAIL. Zero loss principle. |
| I8 | **Paths never have spaces or unicode characters.** Always slug-safe: `[a-z0-9._-]`, space → `-`, uppercase → lowercase. | Folder name `My Proposal/` with space = FAIL. |

### 2.2. Python Helper Invariants
| Function | Precondition | Post-condition |
|----------|--------------|----------------|
| `compute_paths WORKTREE_ROOT SESSION_ID [--cwd CWD]` | Worktree root is an absolute path; session ID is slug-safe. `--cwd` optional (defaults to current dir, used to resolve the workspace name). | Returns 17 canonical variables (`CHE_WORKSPACE_DIR`, `CHE_PROJECT_DIR`, `CHE_WORKTREE_DIR`, `CHE_SESSION_DIR`, `CHE_DECISIONS_PATH`, `CHE_REGISTRY_PATH`, `CHE_LEVEL2_BINDING`, `CHE_PROJECT_REGISTRY`, …). |
| `ensure_session_dirs` | $WORKTREE_ROOT exists. | Creates `.wt/` with 7 subdirs + `sessions/<ID>/` with 6 subdirs. NEVER overwrites anything existing (`mkdir -p`). |
| `append_decision_jsonl` | Valid $SESSION_ID. | **Append in DUAL LOCATION**: (a) `.wt/decisions.log.jsonl` (shared worktree single writer); (b) `sessions/<ID>/decisions.log.jsonl` (session-specific copy). Fixed v1 schema. |

---

## 3. SLUG-SAFE CONVERSION FOR NAMES (PYTHON HELPER: `_slugify`)

Algorithm (12 rules, idempotent):
1. Unicode → ASCII translit (if available, otherwise remove)
2. All lowercase
3. Space ` ` → `-`
4. Slash `/` → `--` (TWO dashes = indicates branch hierarchy)
5. `_` → maintain (except system reserved initial underscore)
6. Any character outside `[a-z0-9._-]` → remove
7. `--+` multiple → reduce to 1 `--`
8. `-+` multiple → reduce to 1 `-`
9. Remove `-` `.` at the beginning and end
10. Default `main` branch ALWAYS converts to `__main` (TWO underscores prefix, I4)
11. Workspace name: if from IDE (TRAE workspace name), applies slug safe
12. Project name: if from git repo `owner/repo` → extracts `repo` + applies slug safe

Examples:
| Input | Slug-safe Output |
|-------|------------------|
| Workspace "Manifesto 48 Projetos" | `manifesto-48-projetos` |
| Repo `vc-educar/corp-website` | `vc-educar--corp-website` |
| Branch `main` | `__main` |
| Branch `feat/FLO-513/process refund` | `feat-FLO-513--process-refund` |

---

## 4. BACKWARD COMPATIBILITY (MINIMUM 1 RELEASE)

### 4.1. Root CHE_WORKSPACES_ROOT Fallback
Logic in helper (`che_core/paths.py`):
```python
if not os.environ.get("CHE_WORKSPACES_ROOT"):
    old_default = Path.home() / "code" / "harness-sessions"
    new_default = Path.home() / ".che-workspaces"
    if old_default.is_dir() and not new_default.is_dir():
        return old_default
    return new_default
```

### 4.2. "Spurious" Old Structure (harness-sessions) — How it's read
If the user hasn't migrated a workspace yet (e.g.: `manifesto48/` is in the `$HOME/code/harness-sessions` fallback with the old MESSY structure):
- Skills first **TRY** to read from the NEW L1-L4 structure (`project/`, `.wt/`, `sessions/<ID>/`).
- If it fails (new structure doesn't exist), **IT FALLS BACK TO READING THE OLD STRUCTURE** (compat mode).
- **NEVER write to the old structure** in compat mode — first execute the G3 item-by-item migration (ask for user confirmation if old structure is detected).

### 4.3. Legacy JSONL Registry Keys (dual-read)
In Level 1 registry (`registry_append_jsonl`), **both keys are written and read**:
```json
{
  "che_session_dir": "/home/laion/.che-workspaces/manifesto48/proj/__main/sessions/123",
  "harness_session_dir": "/home/laion/code/harness-sessions/manifesto48/proj/sessions/123"   // legacy compat
}
```
Reading: tries `che_*` first, if it doesn't exist tries `harness_*` (1 release).

---

## 5. MIGRATION (G3 manifesto48 — OFFICIAL PROCESS)

NON-NEGOTIABLE order (0 loss, simple rollback):

| Step | Action | Command / Log |
|------|--------|---------------|
| M1 | Deep LS of old workspace → text file. | `find /harness-sessions/manifesto48 -maxdepth 6 \| sort > /tmp/pre-migration-filelist.txt` |
| M2 | CSV Classification A/B/C for each item: | 3 columns: `original_path \| CATEGORY \| new_destination_path` |
| | **A = project (L2 durable)** | xray.md, architecture.md, roles/, product/, durable decisions/, onboarding.md |
| | **B = .wt (L3 shared worktree)** | decisions.log.jsonl, envelopes/, gh_stack/, SHARED reports, specs/, designs/, durable qa |
| | **C = session-specific (L4)** | everything inside sessions/<ID>/, debugger, diffs_context, execution, ephemeral reports |
| | **UNCATEGORIZED** | item that doesn't fall into any A/B/C → `project/_legacy_uncategorized/<original-path-maintained>` |
| M3 | mkdir NEW EMPTY structure. | `mkdir -p` L1→L2→L3→L4 (project + __main/.wt + __main/sessions — NO file moving yet) |
| M4 | CSV loop for each line → `mv -n SOURCE DESTINATION`. | Log in `.migration_reports/2026-09-03_migration_manifesto48.csv` for each item (status: OK/ALREADY_EXISTED/SKIP). |
| M5 | `rmdir` (EMPTY directories only) in old folders (`workspace/`, `sessions/` of the old project). | If `rmdir` FAILS (there are files no one classified in M2) → **EVERYTHING that remains** moves to `project/_legacy_uncategorized/` with ORIGINAL subdirectory structure intact. |
| M6 | Write final md report with A/B/C/UNCAT counts + rollback command. | File: `.migration_reports/YYYY-MM-DD_migration_<workspace-name>_report.md` |
| M7 | Documented ROLLBACK command (if things go wrong): | `rsync -a --remove-source-files $NEW $OLD` (1 command, undoes everything — item-by-item back to original). |
