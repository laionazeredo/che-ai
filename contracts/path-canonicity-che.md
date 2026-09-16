# PATH CANONICITY CONTRACT — CHE

> Single source of truth for the **flat** project/worktree storage layout under `CHE_WORKSPACES_ROOT`.
> Corresponding python helpers: `compute_paths` + `ensure_session_dirs` in `che_core/paths.py`, built on the
> canonical primitives in `che_core/project_layout.py` (paths, domains, JSONL append) and `che_core/worktrees.py`
> (worktree lifecycle — the only concept that binds a filesystem path).
> Invariants: NEVER break these contracts. If you need to evolve, update this file FIRST, THEN the python helpers, FINALLY the skills.

---

## 0. CANONICAL ENVIRONMENT VARIABLES

| Env | Default | Valid Values | Purpose |
|-----|---------|--------------|---------|
| `CHE_WORKSPACES_ROOT` | `$HOME/.che-workspaces` | Any existing absolute path with write permission | **Root of EVERYTHING** (projects, `.state/`, `.trash/`). The legacy `HARNESS_SESSIONS_ROOT` is honoured as a fallback name, and the pre-2026 `$HOME/code/harness-sessions` tree is reused only while it is the only one present. |
| `CHE_HOME` | `$HOME/.che-ai` | Any absolute path with `skills/` + `contracts/` + `commands/` + `domains/` | **Config repo** root (skills, rules, commands). Never mixed with `CHE_WORKSPACES_ROOT` (user data). Legacy `$HOME/.trae` is honoured only while it still contains `CHE_RULES.md`. |
| `CHE_HOST_IDE` | `trae` | `trae`, `codex`, `cursor`, `claude-code`, `opencode` | Agnostic IDE host identifier. Future adapters in `adapters/<host_ide>/`. |
| `CHE_SESSION_ID` | (3-level fallback: `CHE_SESSION_ID` → `HARNESS_SESSION_ID` → `SESSION_ID` → `slug-safe-date`) | UUID / slug-safe session id | Agent session UNIQUE identifier. It names the ephemeral session folder, **not** a folder inside the worktree. |

---

## 1. THE FLAT LAYOUT (DIAGRAM)

```
CHE_WORKSPACES_ROOT ($HOME/.che-workspaces/)   ← storage root — CLI, hooks and skills resolve every path from here
│
├─ .state/
│  └─ registry.jsonl                           ← session → worktree → project bindings (append-only JSONL, v2 schema)
│
├─ .trash/                                     ← every destructive operation lands here (never `rm -rf`)
│  ├─ project--<slug>--<ts>/
│  └─ worktree--<project>--<name>--<ts>/
│
└─ acme/                                       ← PROJECT (stable slug, owns no filesystem binding of its own)
   ├─ _db/                                     ← per-project SQLite (durable across branch / worktree switches)
   │  ├─ che_state.sqlite                      ← FTS5 state store (rebuildable: `che state rebuild-index`)
   │  ├─ che_rag.sqlite                        ← optional sqlite-vec RAG store (rebuildable: `che rag build-index`)
   │  └─ README.txt
   ├─ roles/
   │  └─ index.md                              ← role / owner table for the project
   ├─ architecture.md                          ← durable project docs (C4, ADR index, quality attributes)
   ├─ project_profile.md                       ← stack, deployment, patterns
   ├─ product_context.md                       ← pitch, personas, success metrics, constraints
   ├─ roadmap.md                               ← Now / Next / Later
   ├─ registry.jsonl                           ← project-level append-only event log (`PROJECT_INIT`, …)
   ├─ business/ product/ design/ engineering/  ← one folder per canonical domain (see §7), for handoff docs
   ├─ devops/ copywriting/ social/ seo-analytics/
   ├─ .sessions/
   │  └─ 6a981dc48684a64a52ebd487/             ← ephemeral, single-writer session data (`CHE_SESSION_DIR`)
   │     ├─ execution/ debugger/ temp/
   │     └─ binding.md                         ← `CHE_LEVEL2_BINDING`
   └─ worktrees/
      └─ main/                                 ← WORKTREE — the ONLY thing that binds a filesystem path
         ├─ .binding.json                      ← {project, name, path, branch, origin, is_git, created_at, updated_at}
         ├─ decisions.log.jsonl                ← this worktree's decision log (`CHE_DECISIONS_PATH`)
         ├─ specs/ tasks/ reports/ reviews/
         ├─ architecture/ gh_stack/
         ├─ qa/ qa/evidence/ qa/screenshots/
         ├─ design/ diff_contexts/ pr_comments/
         └─ merge_audits/ debugger/
```

Level-by-level reading of the tree:

| Level | Path | What it is | Lifetime |
|-------|------|------------|----------|
| Root | `<root>/` | The whole Che storage. Resolved by `CHE_WORKSPACES_ROOT`. | Permanent |
| State | `<root>/.state/registry.jsonl` | Session → worktree → project bindings. User state, deliberately **outside** the Che source package (`$CHE_HOME`). | Permanent, append-only |
| Trash | `<root>/.trash/` | Destination of every removal. Restored with `che project restore` / `che worktree remove --dry-run` plan reversal. | Until a human cleans it |
| Project | `<root>/<project-slug>/` | An organising abstraction: slug + folder. It groups durable documents, domain folders, the per-project DB and its worktrees. | Lifetime of the product |
| Durable docs | `<project>/*.md`, `<project>/roles/index.md`, `<project>/registry.jsonl` | Human-written, version-able project memory. Never inside a worktree, so it survives worktree deletion. | Lifetime of the product |
| Domain folders | `<project>/<canonical-domain>/` | Canonical handoff documents per domain (PRD, architecture handoffs, copy, SEO, …). | Lifetime of the product |
| DB | `<project>/_db/` | `che_state.sqlite` (FTS5) + optional `che_rag.sqlite`. The filesystem is the SSoT; both DBs are rebuildable. | Lifetime of the product |
| Sessions | `<project>/.sessions/<session_id>/` | Ephemeral, isolated, single-writer session state. **Outside** the worktree on purpose. | Hours → days |
| Worktrees | `<project>/worktrees/<worktree-name>/` | Shared tactical memory of every session bound to one git checkout. | Lifetime of the binding |
| Binding | `<worktree>/.binding.json` | The record that makes a directory a Che worktree: absolute repo path, branch, origin, git flag. | Lifetime of the binding |

---

## 2. PROJECT vs WORKTREE

These are two different concepts and the flattening made the split explicit:

- A **project** is an organising abstraction with a **stable slug** and a folder. It does **not** bind a filesystem path.
  Creating a project for a repository never means "Che now owns your checkout" — it only means "this slug owns the durable memory".
- A **worktree** is the **only** concept that binds a path. It is created on demand by
  `che worktree add <repo_path> --project <slug> --name <name>` and recorded in
  `<project>/worktrees/<name>/.binding.json`.

Consequences:

- Every worktree-scoped artifact (specs, tasks, reports, reviews, QA evidence, decisions, …) lives under
  `<project>/worktrees/<name>/`, and every session bound to that worktree shares the same tree. **There are no per-session folders inside a worktree anymore.**
- Durable artifacts live one level up, under `<project>/`, so removing a worktree never destroys project memory.
- The reverse lookup (`find_worktree_by_path`) answers "which (project, worktree) pair binds this repository path?" without
  ever falling back to `os.getcwd()`.

---

## 3. CREATION RULES (EXPLICIT SLUG · GIT · IDEMPOTENT REUSE)

| Rule | Behaviour | Failure mode |
|------|-----------|--------------|
| **Explicit slug** | The project slug is mandatory (`--slug`). It is **never** inferred from the git origin, the folder name or the current working directory. `slug_from_origin()` exists only to *suggest* a slug, never to decide one. | Missing/invalid slug → exit `2`, nothing created. Blank slug reaching a creating command raises `AssertionError` (`assert_project_slug`). |
| **Git required** | Both `che project init` and `che worktree add` require the target to be inside a git working tree (contract R4, `is_git_repo`). | Non-git path → exit `2`, nothing created. |
| **Idempotent worktree reuse** | Re-adding the same `project + name` **reuses** the existing `<project>/worktrees/<name>/`, refreshes the recorded branch/origin and reports `reused: true` (`added: false`). It never creates a duplicate tree and never forks one folder per session. | A directory that exists without a `.binding.json` is refused (`exit 2`) unless `--force` is passed to adopt it. |
| **Slug format** | `^[a-z0-9][a-z0-9-]*$`, max 63 characters (`validate_slug`). Applies to project slugs, worktree names and canonical domains. | Invalid slug → `ValueError` at the boundary; creating commands convert it into exit `2`. |
| **Trash-safe removal** | `project remove` and `worktree remove` are `shutil.move` into `<root>/.trash/`, never `rm -rf`, and they never touch the bound repository. `--dry-run` is the default; applying requires `--no-dry-run --confirm`. | Missing `--confirm` → exit `2`. Unknown target → exit `3`. |

---

## 4. SINGLE-FORMULA RULE (`compute_paths` IS THE ONLY PATH RESOLVER)

`che_core/paths.py::compute_paths` is the **only** place in Che where a storage path may be computed.

- `che_core/decisions.py` **must** delegate (`get_decisions_path` → `compute_paths(...)["CHE_DECISIONS_PATH"]`).
- `che_core/portability.py` **must** delegate (`export_project` → `compute_paths(...)` for `CHE_PROJECT_DIR`,
  `CHE_WORKSPACE_SHARED` and `CHE_DB_DIR`; `import_project` resolves through `get_project_dir` / `get_worktree_dir`).
- Every other module, hook, skill and shell snippet **must** consume the variables printed by
  `che compute_paths` (or call the same helper) rather than rebuild the layout by hand.

**A second path formula is a bug.** This is precisely the regression the flat layout fixed: `decisions.py` used to
carry its own formula (`<root>/<workspace>/<worktree-slug>/.wt/`) that resolved the workspace from `os.getcwd()`,
while `paths.py` computed another one. The two disagreed, so a worktree's decision history and its artifacts
silently landed in different trees — the memory of a project never met itself.

Resolution is **argument-driven only**:

- `compute_paths <worktree_root> <session_id> [--cwd ...]` never reads `os.getcwd()` to pick a project.
  `--cwd` is accepted for backward compatibility with existing skills and is deliberately ignored for resolution.
- If the path is not bound, `compute_paths` prints an actionable message to stderr
  (`che worktree add …`, `che project list`) and exits `3`. It never guesses.
- `assert_no_cwd_dependency` crashes when a resolved storage path is not absolute — a relative path means some caller
  let the current directory leak into the layout.

Canonical keys returned by `compute_paths`:

| Key | Resolves to |
|-----|-------------|
| `CHE_PROJECT_SLUG` | Project slug. |
| `CHE_WORKTREE_NAME` | Worktree name. |
| `CHE_PROJECT_DIR` | `<root>/<project-slug>`. |
| `CHE_WORKTREE_DIR` | `<project>/worktrees/<name>`. |
| `CHE_STATE_DIR` | `<root>/.state`. |
| `CHE_DB_DIR` | `<project>/_db`. |
| `CHE_ROLES_DIR` | `<project>/roles`. |
| `CHE_DECISIONS_PATH` | `<worktree>/decisions.log.jsonl`. |
| `CHE_SESSION_DIR` | `<project>/.sessions/<session_id>`. |
| `CHE_REGISTRY_PATH` | `<root>/.state/registry.jsonl`. |
| `CHE_ARCHITECTURE_DOC`, `CHE_PROJECT_PROFILE`, `CHE_PRODUCT_CONTEXT`, `CHE_ROADMAP_DOC` | The four durable project docs at `<project>/`. |
| `CHE_PROJECT_REGISTRY` | `<project>/registry.jsonl`. |
| `CHE_DOMAIN_<NAME>_DIR` | `<project>/<canonical-domain>` (one per domain, dashes become underscores). |
| `CHE_PROJECT_GRAPH_DIR` | `<project>/graphify`. |
| `CHE_LEVEL2_BINDING` | `<session>/binding.md`. |

Deprecated aliases are still exported so existing skills keep resolving while the L1 "workspace" concept is retired:
`CHE_WORKSPACE_NAME` (= project slug), `CHE_WORKSPACE_DIR` (= project dir), `CHE_WORKSPACE_SHARED` (= worktree dir),
`CHE_WORKTREE_SLUG` (= worktree name).

`ensure_session_dirs` is the materialising counterpart: it creates the project skeleton (8 domain folders +
`worktrees/` + `_db/` + `roles/`), the worktree's shared subfolders, and the ephemeral session folder. It is
idempotent (`mkdir -p` semantics) and never overwrites an existing file.

---

## 5. STORAGE-BOUNDARY INVARIANT

Che artifacts are **never** written inside the user's repository. If they were, they would be accidentally committed
into PRs (`decisions.log`, task graphs, manual test plans, specs, QA reports, …).

- `assert_outside_worktree(candidate_path, worktree_root, label)` is the hard-stop guard. When the candidate falls
  inside the worktree it prints the violation report to stderr and **exits `99`**.
- `output_path(...)` and `write_file_atomic(...)` call the guard before every write.
- `compute_paths` itself asserts that `CHE_PROJECT_DIR`, `CHE_WORKTREE_DIR` and `CHE_SESSION_DIR` are outside the
  bound worktree.
- An empty candidate path or worktree root is a silent no-op (matching the legacy bash contract).

The fix is always the same: never build a path from `$PWD` or `<worktree>/.che/`; resolve it once with
`eval "$(che compute_paths "$WORKTREE_ROOT" "$SESSION_ID")"` and write to `$CHE_WORKSPACE_SHARED` / `$CHE_SESSION_DIR`.

---

## 6. SESSION MODEL

- A session **no longer owns a folder inside a worktree**. The old `<worktree>/sessions/<id>/` level is gone, which is
  what lets one worktree accumulate memory across many sessions instead of one subtree per run.
- Ephemeral session data lives in `<project>/.sessions/<session_id>/` (`CHE_SESSION_DIR`), with the `execution/`,
  `debugger/` and `temp/` subfolders created on demand. This folder is outside the worktree, so it is also outside the
  user's repository.
- The binding of a session to a worktree and of that worktree to a project lives in `<root>/.state/registry.jsonl`
  (`CHE_REGISTRY_PATH`), an append-only JSONL written through `append_line_atomic` (one atomic `O_APPEND` write per
  record; oversized records are refused rather than truncated). The registry used to live inside the Che source
  package; it is user state and now belongs to the storage root.
- Worktree-scoped artifacts are shared by every session bound to that worktree, and are written under
  `<project>/worktrees/<name>/`.

---

## 7. CANONICAL DOMAINS

Eight canonical domains name both the harness playbooks (`domains/<slug>/`) and the per-project artifact folders
(`<project>/<slug>/`):

`business` · `product` · `design` · `engineering` · `devops` · `copywriting` · `social` · `seo-analytics`

Legacy input aliases are accepted and normalised by `normalise_domain()`:

| Input alias | Canonical domain |
|-------------|------------------|
| `ux` | `design` |
| `operation`, `ops` | `devops` |
| `dev`, `eng` | `engineering` |

The `ux` → `design` rename of the harness playbook folder (`domains/ux/`) is **deliberately deferred**: we alias on
input instead of breaking the playbook tree.

---

## 8. INVARIANTS (NON-NEGOTIABLE — HARD FAIL)

| # | Invariant | Violation example (prohibited) |
|---|-----------|--------------------------------|
| I1 | **Only a worktree binds a filesystem path.** A project is a slug + a folder. | Storing a repo path on the project record, or teaching a command to "find the project" from a path. |
| I2 | **The project slug is explicit and mandatory** (`--slug`). | Deriving the slug from git origin or `os.getcwd()` on a creating command. |
| I3 | **Projects and worktrees require git.** | Creating a project/worktree for a non-git directory (must exit `2` and create nothing). |
| I4 | **`che worktree add` is idempotent.** Same `project + name` reuses the existing tree. | Creating a second folder for the same worktree, or one folder per session. |
| I5 | **`compute_paths` never reads `os.getcwd()`.** Resolution is argument-driven only. | Any code path where the current directory influences which project is selected. |
| I6 | **There is exactly one path formula.** Every module delegates to `compute_paths`. | A second formula (historical: `<root>/<workspace>/<worktree-slug>/.wt/` in `decisions.py`). |
| I7 | **Nothing Che writes lands inside the user repository.** | `decisions.log`, task graphs, specs or QA evidence under the bound repo (must exit `99`). |
| I8 | **No per-session folders inside a worktree.** Ephemeral state lives under `<project>/.sessions/<id>/`. | Re-introducing `<worktree>/sessions/<id>/`. |
| I9 | **Slugs are lowercase and slug-safe** (`^[a-z0-9][a-z0-9-]*$`, ≤ 63 chars). | Folder names with spaces, uppercase or unicode. |
| I10 | **Removals are trash-safe moves** (`shutil.move` into `.trash/`), and the bound repo is never touched. | `rm -rf` of a project or worktree, or deleting the user checkout. |
| I11 | **Canonical domains are data.** Adding a domain is a `DOMAIN_SLUGS` change, never an inline string in a skill. | Hardcoding `domains/ux/` or `"product"` where `DOMAIN_SLUGS` is the source of truth. |
| I12 | **JSONL records are atomic and bounded** (`MAX_JSONL_LINE_BYTES = 8192`). | Appending a truncated line that would corrupt every later reader. |

---

## 9. MIGRATING FROM THE PRE-FLATTENING LAYOUT

The pre-flattening hierarchy had an extra "workspace" grouping level and per-session folders inside worktrees:

| Legacy path (no longer read) | Current equivalent |
|------------------------------|--------------------|
| `<root>/<workspace>/<project>/` | `<root>/<project>/` |
| `<root>/<workspace>/<project>/project/` | `<root>/<project>/` (durable docs now at the project root) |
| `<root>/<workspace>/<worktree>/.wt/` | `<root>/<project>/worktrees/<name>/` |
| `<root>/<worktree>/sessions/<id>/` (inside a worktree) | `<root>/<project>/.sessions/<id>/` |
| `<root>/.registry/projects/` | `<root>/.state/registry.jsonl` |
| `<project>/che_state.sqlite` (at the project root) | `<project>/_db/che_state.sqlite` |

Rules for the transition:

1. **Legacy folders are left untouched on disk.** Che never reads, rewrites or removes them on its own.
2. `che project list` detects them heuristically (a flat project always carries a `registry.jsonl` and/or a
   `worktrees/` folder; legacy leftovers carry neither) and reports them under a `legacy_untouched` entry with a
   remediation note, so nothing is silently ignored.
3. To adopt a legacy tree, re-create the project explicitly (`che project init <repo> --slug <slug>`) and bind its
   checkout (`che worktree add <repo> --project <slug> --name <name>`), then move the old folder to `.trash/` once you
   are satisfied with the new one. Trash, never delete.
