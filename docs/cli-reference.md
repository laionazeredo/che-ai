# Che AI — CLI Reference

> **Binaries:** `che-ai` (canonical) and `che` (short alias). Both point to the same entry point.
> **Runtime:** All commands listed in this document run against your local filesystem, SQLite, and local `git` subprocess. No network calls to any LLM provider are made. No token spend.
> **Install:** See _Installation_ below. After install, type `che --help` or `che-ai --help` at any terminal.

---

## Table of Contents

1. [Installation](#1-installation)
2. [Command Map](#2-command-map)
3. [Project & Worktree Commands](#3-project--worktree-commands)
   1. [Worktrees](#31-worktree-cli)
   2. [Projects](#32-project-cli)
   3. [Session & Config](#33-session--config)
4. [State & Memory (SQLite FTS5)](#4-state--memory-sqlite-fts5)
5. [Task Graph Engine](#5-task-graph-engine)
6. [RAG (Hybrid Search)](#6-rag-hybrid-search)
7. [Portability: Export / Import](#7-portability-export--import)
8. [Safe Eject / Uninstall](#8-safe-eject--uninstall)
9. [Low-level Plumbing](#9-low-level-plumbing)
10. [Exit Codes & Convention](#10-exit-codes--convention)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Installation

> ⚠️ **This CLI does NOT replace in-IDE slash commands. It is the structural administrative sidecar that complements them.**
>
> `/che-project`, `/che-spec`, `/che-act`, `/che-ship`, `/che-review`, `/che-prd`, `/che-tasks`, `/che-notes`, `/che-graph` **(built-in) plus community custom skills (examples: `/figma-pixel-check`, `/flockr-*`, `/my-company-*`) continue to exist and are maintained**. They remain the recommended entry point for flows that require LLM reasoning (spec authoring, implementation loops, code review, PR gating) — **used inside Claude Code by default**.
>
> Use **this `che-ai` CLI** for team bootstrap, project & worktree admin, CI wiring, trash-safe operations, offline state work, bulk listing, and portable export/import. A standard team flow is: `che project init <repo> --slug <slug>` + `che worktree add <repo> --project <slug> --name main` (terminal or CI setup) → `/che-spec` (IDE agent) → `/che-act` (IDE agent) → `/che-ship` (IDE agent).

### 1.0 Platform Compatibility

The installer and the CLI target **POSIX bash/zsh userlands only**.

| OS | Support | Notes |
| :- | :------ | :---- |
| **Linux** (any distro, GNU coreutils + bash ≥ 4.4 + python3 ≥ 3.9) | ✅ Fully supported. Primary target. | `apt` / `dnf` / `pacman` / `nix`. |
| **macOS** (Monterey / 12+, zsh or bash via Homebrew) | ✅ Fully supported. | Use `brew install pipx git python@3.12`. File paths inside `~/.che-ai` are case-insensitive on APFS by default — don't rely on case-only folder names. |
| **Windows PowerShell / CMD** | ❌ Not supported. | Use **WSL2 with Ubuntu 22.04 LTS** (recommended), then run the installer from inside the WSL Ubuntu shell. Claude Code on Windows supports WSL remotes natively, so the workflow is transparent after setup. |

#### WSL2 walkthrough for Windows users

1. Admin PowerShell: `wsl --install -d Ubuntu-22.04` → reboot.
2. Open "Ubuntu 22.04 LTS" app, create your Linux user.
3. Inside Ubuntu:
   ```bash
   sudo apt-get update && sudo apt-get install -y python3-pip pipx git curl ca-certificates
   pipx ensurepath
   source ~/.bashrc   # or ~/.zshrc if you use zsh
   ```
4. Continue with the Quick Install Script below.

### 1.1 Quick Install Script (recommended, installs `~/.che-ai` + CLI)

Runs the full installer: backs up any existing `~/.che-ai`, symlinks the official whitelist into every supported IDE adapter home, re-injects the planning-artifacts `.gitignore` snippet into client repos you touch, **and installs the `che` / `che-ai` CLI binaries globally via `pipx`** (fallback `pip install --user` if pipx is not available — with a loud warning telling you to install pipx).

```bash
curl -fsSL https://raw.githubusercontent.com/laionazeredo/che-ai/main/scripts/install-che.sh | bash -s -- --apply

# Skip CLI install (IDE-only usage):
# curl -fsSL ... | bash -s -- --apply --no-cli

# Non-destructive update (preserves user_rules/, registry, memory):
# curl -fsSL ... | bash -s -- --update --apply
```

### 1.2 CLI-only — pipx (user-level, isolated)

If you already have a `~/.che-ai` folder from a previous install and just want to install / upgrade the binaries:

```bash
cd ~/.che-ai                              # path where che-ai lives
pipx install -e . --force                # editable = updates to source immediately reflected

which che-ai      # → ~/.local/bin/che-ai
which che         # → ~/.local/bin/che   (short alias)
```

This is the **canonical and safest** install for end-user machines. It creates a private venv at `~/.local/pipx/venvs/che-ai/` and links the two binaries into your `PATH`.

### 1.3 Container / throwaway — `pip install --break-system-packages`

Only inside Docker, CI runners, or throwaway containers. Do **not** use on your developer workstation.

```bash
cd ~/.che-ai
pip install -e . --break-system-packages
```

### 1.4 Uninstall

```bash
pipx uninstall che-ai
# or
pip uninstall che-ai
# Then optionally delete ~/.che-ai
```

---

## 2. Command Map

| Group        | Subcommands                                                         | Scope    | Surface |
| :----------- | :------------------------------------------------------------------ | :------- | :------ |
| `project`    | `create` (`add`, `init`), `list`, `remove`, `restore`, `trash-list` | Project  | Terminal CLI |
| `worktree`   | `add`, `list`, `show`, `remove`                                     | Worktree | Terminal CLI |
| `config`     | (flags: `--lang-chat`, `--lang-docs`, `--lang-report`, `--pt-check`, `--flags`) | Session | Terminal CLI |
| `task`       | `list`, `show`, `resume`, `set-status`, `graph-summary`           | Worktree | Terminal CLI |
| `state`      | `rebuild-index`, `query`, `search`, `sanitize`                     | Project  | Terminal CLI |
| `rag`        | `build`, `search`, `list`, `prune`                                 | Project  | Terminal CLI |
| `export`     | (project → portable `.tar.gz`)                                     | Project  | Terminal CLI |
| `import`     | (portable `.tar.gz` → project)                                     | Project  | Terminal CLI |
| `eject`      | `plan`, `execute`, `restore`                                       | All      | Terminal CLI |
| `pixel`      | `check`                                                            | Worktree | Terminal CLI |
| plumbing     | `compute_paths`, `ensure_dirs`, `output_path`, `write_file_atomic`, `assert_outside_worktree`, `registry_append`, `registry_lookup`, `decision_append` | Any | Terminal CLI |

### 2.1 Help Discovery

Every group and subcommand responds to `--help`:

```bash
che --help
che project --help
che worktree --help
che worktree add --help
che config --help
che eject plan --help
```

---

## 3. Project & Worktree Commands

### 3.1 Worktree CLI

Worktrees are the **only** Che concept that binds a filesystem path. Every worktree lives at
`~/.che-workspaces/<project-slug>/worktrees/<worktree-name>/`, holds that worktree's shared artifacts
(`decisions.log.jsonl`, `specs/`, `tasks/`, `qa/`, …) and is described by a `.binding.json` record.

A worktree requires git: binding a non-git path exits `2` and creates nothing. `add` is idempotent — re-adding
the same project + name reuses the existing tree, so one worktree accumulates the memory of every session bound
to it instead of one subtree per session.

#### `che worktree add <repo_path> --project <slug> --name <name> [--force]`

Binds a git checkout to a project.

| Argument / flag | Required | Meaning |
| :-------------- | :------: | :------ |
| `repo_path` | yes | Path to the git checkout (resolved to an absolute path). |
| `--project` | yes | Owning project slug (the project must already exist). |
| `--name` | yes | Worktree name, e.g. `main`, `feat-checkout`. Slug-safe, ≤ 63 chars. |
| `--force` | no | Adopt a directory that exists but holds no `.binding.json`. |

```bash
# First bind — creates ~/.che-workspaces/web-app/worktrees/main/ + .binding.json
che worktree add ~/code/my-company/web-app --project web-app --name main

# Second run with the same project + name → REUSED, no duplicate tree
che worktree add ~/code/my-company/web-app --project web-app --name main
# { "added": false, "reused": true, "project": "web-app", "worktree": "main", ... }
```

Output JSON: `added`, `reused`, `project`, `worktree`, `path`, `branch`, `worktree_dir`, `decisions_path`.

Exit codes: `0` bound/reused; `2` `repo_path` missing or not a directory, a non-git path, or an existing
unmanaged directory without `--force`; `3` the project does not exist.

#### `che worktree list --project <slug>`

Prints every binding of a project, sorted by worktree name (`[]` when the project has none).

```bash
che worktree list --project web-app | jq -r '.[] | "\(.name)\t\(.branch)\t\(.path)"'
```

Exit codes: `0` (possibly with an empty array); `2` when `--project` is omitted.

#### `che worktree show <project_slug> <worktree_name>`

Prints a single binding, including the resolved `worktree_dir`.

```bash
che worktree show web-app main | jq '.path, .branch, .worktree_dir'
```

Exit codes: `0` found; `3` no worktree with that name in that project.

#### `che worktree remove <project_slug> <worktree_name> [--dry-run | --no-dry-run --confirm]`

**Never touches the bound repository.** Moves `<project>/worktrees/<name>/` to
`.trash/worktree--<project>--<name>--<timestamp>/` with a `_MANIFEST.json` restore hint. `--dry-run` is the default.

**SAFETY FIRST.** Always dry-run before any destructive action:

```bash
# Step 1 — inspect the plan (default)
che worktree remove web-app main --dry-run

# Step 2 — apply when you are sure
che worktree remove web-app main --no-dry-run --confirm
```

Exit codes: `0` plan returned / move applied; `2` `--no-dry-run` without `--confirm`; `3` no worktree with that
name in that project.

---

### 3.2 Project CLI

A project is the durable home for strategy, architecture, product context, roles, roadmap, the per-project SQLite
DB and its worktrees. It is identified by an **explicit slug** and it does **not** bind a filesystem path — only a
worktree does. There is no workspace argument anywhere in this group.

The flat directory for a project of slug `<s>` is:

```
~/.che-workspaces/<s>/
  ├─ architecture.md            (durable, human-writable)
  ├─ project_profile.md
  ├─ product_context.md
  ├─ roadmap.md
  ├─ roles/index.md
  ├─ registry.jsonl             (project-level append-only event log)
  ├─ _db/                       (SQLite: che_state.sqlite + optional che_rag.sqlite + README.txt)
  ├─ <domain>/                  (one folder per canonical domain: business, product, design, engineering,
  │                              devops, copywriting, social, seo-analytics)
  └─ worktrees/<name>/          (one per bound git checkout — see §3.1)
```

#### `che project init <repo_path> --slug <slug> [--domain <domain>] [--name "<friendly name>"]`

Canonical first-run. Given a path inside a git repository, creates/refreshes the project skeleton and the four
durable documents. `--slug` is **mandatory** and never inferred; there is no `--workspace` and no `--session-id`.

```bash
# Inside or outside your repo. The path must be inside a git working tree.
che project init ~/code/my-company/web-app \
    --slug web-app \
    --domain product \
    --name "My Company Web App"
```

`create`, `add` and `init` are aliases of the same subcommand.

Output JSON: `initialised`, `already_existed`, `project_slug`, `friendly_name`, `domain`, `project_dir`,
`repo_root`, `domains`, `skeleton_created`, `files_created`, plus human-readable `next_steps`.

Exit codes: `0` created/refreshed; `2` `repo_path` missing, invalid `--slug` or `--domain`, path not a directory,
or a non-git path (nothing is created in any of those cases).

> **Tip:** If you have a fresh new repo with zero commits, run `git commit --allow-empty -m "chore: initial empty commit"` first.

#### `che project list`

Lists every flat project with `architecture_exists`, `project_profile_exists`, `db_files` (the contents of `_db/`),
`worktrees` and `domains`. There is no `--workspace` filter: projects live directly under the storage root. Legacy
pre-flattening folders (no `registry.jsonl` / no `worktrees/`) are reported in a trailing `legacy_untouched` entry
and are left untouched on disk.

```bash
che project list | jq '.[] | select(.slug) | .slug'
```

#### `che project remove <slug> [--dry-run | --no-dry-run --confirm]`

Same trash-safe pattern as worktrees. Moves `<root>/<slug>/` to `.trash/project--<slug>--<ts>/`. Does **not**
touch any repository bound to the project's worktrees, and never deletes the worktrees' `.binding.json` records
from the bound checkouts.

Exit codes: `0` plan returned / move applied; `2` `--no-dry-run` without `--confirm`; `3` unknown project.

#### `che project restore <trash-slug>`

Restores a previously-removed project to its original flat location. Exit `3` when the trash entry is missing, its
`_MANIFEST.json` has no `original_path`, or the destination already exists (it never overwrites).

#### `che project trash-list`

Prints the manifest of every entry sitting in `.trash/`.

---

### 3.3 Session & Config

Every AI session against a worktree is addressed by a **stable `session_id`**. A session no longer owns a folder
inside the worktree: its ephemeral data lives in `<project>/.sessions/<session_id>/`, while the session → worktree
→ project bindings are append-only JSONL written to `<root>/.state/registry.jsonl` (`CHE_REGISTRY_PATH`) and never
mutated in-place.

#### `che config <session_id> <worktree_root> [flags]`

Sets the per-session language, style and behaviour flags.

```bash
che config my-session-42 ~/code/my-company/web-app \
    --lang-chat pt-BR \
    --lang-docs pt-BR \
    --lang-report en \
    --pt-check ENABLED

# Raw JSON escape hatch for arbitrary flag dicts
che config my-session-42 ~/code/my-company/web-app \
    --flags '{"BLAST_RADIUS":"low","NO_REBASE":true}'
```

Valid choices (see `che config --help` for the up-to-date list):

| Flag              | Domain                 | Choices                | Default |
| :---------------- | :--------------------- | :--------------------- | :------ |
| `--lang-chat`     | Agent↔Human dialogue   | `en`, `pt-BR`          | `en`    |
| `--lang-docs`     | Docs & commit style    | `en`, `pt-BR`          | `en`    |
| `--lang-report`   | Generated reports      | `en`, `pt-BR`          | `en`    |
| `--pt-check`      | Portuguese hook        | `ENABLED`, `DISABLED`  | `DISABLED` |
| `--flags`         | Escape hatch (JSON)    | free-form object       | `{}`    |

The canonical flags enum lives in `che_core/constants.py`. Always treat that file as SSoT — do **not** copy the flag list into docs, specs, or prompt templates.

---

### 3.4 Domain Gate CLI — `che pixel check`

The runner behind `domains/ux/gates/pixel-check-gate.md`. It compares design properties against
rendered DOM properties **numerically** — never screenshot against screenshot — and is the only
supported way to execute that gate. See the gate's §2 Execution for the recipe that `che-ship §0.9.5`
follows.

```bash
che pixel check \
  --map "$DESIGN_MAP" \
  --dom "$DOM_FACTS" \
  --design-source "$DESIGN_RAW" --design-backend figma \
  --breakpoint lg \
  --out "$DOMAIN_GATE_REPORT"
```

| Flag | Required | Meaning |
| :--- | :------- | :------ |
| `--map` | yes | `design-map.json`: `{element: {design_node, selector}}` — the **only** join between the two sides. |
| `--dom` | yes | DOM facts, keyed by CSS selector. |
| `--design-source` | one of | Raw design artefact: a `get_figma_data` response, or an OpenPencil `.op` file. |
| `--design` | one of | Design facts already extracted, keyed by design node id. |
| `--design-backend` | with `--design-source` | `figma` or `openpencil`. **Never inferred** from the file — guessing picks the wrong extractor and yields plausible-but-wrong numbers. |
| `--breakpoint` | no | Label recorded as report provenance. |
| `--design-viewport` | no | Width the design frame was captured at, in px. |
| `--dom-viewport` | no | Width the DOM was measured at, in px. A **mismatch** with `--design-viewport` is refused (`2`) rather than scored, because it makes every measurement meaningless. When either is omitted the report records `viewport_binding: "undeclared"`. |
| `--out` | no | Write the JSON report atomically. |
| `--json` | no | Print the full report instead of the one-line summary. |

The report also carries `coverage` (the fraction of the gate's 14 categories the run actually verified),
`unverified_categories` (their names — `margin` always, `position` from `.op`, `letter_spacing` from
Figma), and the `viewport_binding`. A `PASS` should be quoted *with* those, never alone: the score is
computed over the verified rows only, so `score=9.5` does not mean "visually identical".

Exit codes — branch on these, not on the text:

| Exit | Verdict | Meaning |
| :--- | :------ | :------ |
| `0` | `PASS` | The gate's three numeric conditions held. |
| `1` | `FAIL` | A condition broke, **or** a designed element is absent from the DOM. |
| `3` | `INCONCLUSIVE` | Could not be decided honestly: a critical category measured on no element, an element with no design reference, or nothing measurable at all. **Never a pass.** |
| `2` | usage | Unreadable artefact, an incomplete map entry, an unknown backend, a missing `--design-backend`, or a **viewport mismatch**. |

The summary line on stdout already matches the gate's `log_format_decisions`, so it can be passed
straight to `che decision_append`.

---

## 4. State & Memory (SQLite FTS5)

Che ships a built-in **append-only** state store on SQLite FTS5, one `che_state.sqlite` per **project**, kept in
`<project>/_db/` so it survives worktree and branch switches. It is **not** a general-purpose database — the primary
workload is full-text search over structured decisions, task graphs, and QA evidence.

```bash
che state rebuild-index ~/code/my-company/web-app   # indexes the bound worktree into <project>/_db/che_state.sqlite
che state query ~/code/my-company/web-app 'SELECT key, json_extract(body,"$.owner") FROM kv WHERE key LIKE "task:%";'
che state search ~/code/my-company/web-app "stripe webhook signature"
che state sanitize ~/code/my-company/web-app         # PII + secrets scrubbing pass
```

---

## 5. Task Graph Engine

Che's task graph is the bridge between a human-approved Spec and the parallel multi-agent execution engine. The CLI is **read-only** for tasks; mutations happen inside agent sessions via the `/che-act` skill.

```bash
che task list ~/code/my-company/web-app
che task show ~/code/my-company/web-app WEB-42
che task resume  ~/code/my-company/web-app WEB-42        # resumes a stopped task
che task set-status ~/code/my-company/web-app WEB-42 BLOCKED
che task graph-summary ~/code/my-company/web-app         # topo-sort, critical path
```

---

## 6. RAG (Hybrid Search)

The RAG layer is built on sqlite-vec. Everything runs locally; you can opt-in at any time and opt-out at any time (no network calls made by `che rag` itself).

```bash
che rag build ~/code/my-company/web-app      # ingests markdown, code, decisions
che rag search ~/code/my-company/web-app "RLS policy on events"
che rag list   ~/code/my-company/web-app
che rag prune  ~/code/my-company/web-app     # removes stale chunks
```

---

## 7. Portability: Export / Import

Any project can be snapshotted into a self-contained `.tar.gz` and moved between machines. The exporter never copies
`.git/` and never copies the worktree code — **only** the durable project directory plus the worktree's shared folder,
and by default it does **not** include the SQLite databases.

```bash
# Export the project bound to this checkout (positional: worktree_root, output_file)
che export ~/code/my-company/web-app ~/Desktop/web-app-20260909.tar.gz

# ...move the file to another machine...

# Import: the project slug and worktree name come from the archive metadata
che import ~/Downloads/web-app-20260909.tar.gz
```

`che import` still accepts `--workspace`, but the flag is **deprecated and ignored**: the slug comes from the archive
(`metadata.json`) and the flat layout has no workspace level. `--include-db` (on both commands) opts the SQLite files
in; the default limit is 250 MB, above which a `_db/SKIPPED.txt` note is written instead.

See `che export --help` and `che import --help` for the full blacklist.

---

## 8. Safe Eject / Uninstall

If you ever want to stop using Che without losing anything, the eject flow is a **two-gate** safety check:

1. **`che eject plan`** — prints exactly what would move to `.trash/`, every adapter that would be unlinked, and the exact restore command. **Makes no changes.**
2. **`che eject execute --confirm`** — performs the plan.
3. **`che eject restore <ts>`** — undoes step 2 at any time.

We intentionally do not provide a "hard delete" command. Everything is trash + restore.

---

## 9. Low-level Plumbing

These commands exist for agent skills and shell integrations. Humans rarely need them but they are stable and public.

### `che compute_paths <worktree> <session_id> [--cwd ...]`

Prints the canonical flat-layout paths as shell-exportable variables. Use this from bash or from `$()` scripts
instead of hard-coding `~/.che-workspaces`. Resolution is argument-driven: if the path is not bound yet, the command
prints how to bind it and exits `3`.

```bash
eval "$(che compute_paths ~/code/my-company/web-app onboarding-003)"
echo "$CHE_PROJECT_DIR"     # <root>/<project-slug> — durable project dir
echo "$CHE_WORKTREE_DIR"    # <project>/worktrees/<name> — shared worktree dir
echo "$CHE_SESSION_DIR"     # <project>/.sessions/<id> — ephemeral session dir
echo "$CHE_DB_DIR"          # <project>/_db — SQLite state + RAG
echo "$CHE_REGISTRY_PATH"   # <root>/.state/registry.jsonl
```

`--cwd` is accepted for backward compatibility with existing skills and is ignored for resolution (it is never used
to guess which project the path belongs to).

### `che ensure_dirs <worktree> <session_id> [--cwd ...]`

Creates the missing roots for a bound worktree: the project skeleton (8 domain folders + `worktrees/` + `_db/` +
`roles/`), the worktree folder, and the ephemeral session folder. It does **not** pre-create artifact subfolders
(`specs/`, `tasks/`, `reports/`, …): `che output_path` creates the parent of every artifact on first write, so a
freshly bound worktree holds nothing but `.binding.json`. Idempotent, safe to re-run.

### `che output_path` / `che write_file_atomic` / `che assert_outside_worktree`

Storage-boundary plumbing. `output_path` resolves the canonical path for an artifact under `$CHE_SESSION_DIR`
(scope `session`) or `$CHE_WORKSPACE_SHARED` (scope `workspace`) and creates its parent directory.
`write_file_atomic` writes stdin to a target through a sibling temp file + rename. `assert_outside_worktree` is the
hard-stop guard: a candidate path inside the worktree prints the violation report and exits `99`.

### `che registry_append` / `che registry_lookup <session_id>`

Append-only JSONL registry at `<root>/.state/registry.jsonl`. `registry_append <session_id> <status> <worktree_root> [payload]` takes the same flags as `config` plus arbitrary event JSON; `registry_lookup` returns the last row for a session (exit `1` when there is none).

### `che decision_append <worktree_root> <event_type> [payload] [--session-id <id>] [--spec-id <id>]`

Writes one structured row to the worktree's `decisions.log.jsonl` (`<project>/worktrees/<name>/decisions.log.jsonl`).
Required by the engineering contracts before every non-trivial refactor.

```bash
che decision_append ~/code/my-company/web-app ARCH \
    '{"title":"Move analytics storage to dedicated S3 bucket","tags":["WEB-42","storage","RLS"]}' \
    --session-id onboarding-003 --spec-id WEB-42
```

---

## 10. Exit Codes & Convention

| Code | Meaning                                           |
| :--: | :------------------------------------------------ |
|  0   | Success. JSON on stdout for commands that report a result. |
|  2   | Usage / precondition failure: bad argument, non-git path, missing required `--slug` / `--project` / `--name`, refused oversized write, or a destructive operation applied without `--confirm`. |
|  3   | Unknown project / worktree, or a worktree path that is not bound to any project. |
|  98  | Fatal missing dependency: the `che` CLI is not on `PATH` (guard raised by the skills before any write). |
|  99  | Storage-boundary violation: a Che artifact would land inside the user's repository. |

Notes:

- `0`, `2`, `3` and `99` are raised by the CLI itself; `2` is also argparse's default for an unknown flag or a
  missing argument.
- `98` is not raised by `che_core`: it is the guard the skills run (`command -v che >/dev/null 2>&1 || exit 98`) so
  that nothing is written without a resolved storage boundary.
- `che registry_lookup` exits `1` when the session has no registry row yet.

All successful structured output is **line-delimited JSON** on `stdout`. All human-readable progress is on `stderr`. Safe to `| jq` everything.

---

## 11. Troubleshooting

### 11.1 `che: command not found` after `pipx install -e .`

Either `~/.local/bin` is not on your PATH or the install silently failed. Fix:

```bash
export PATH="$HOME/.local/bin:$PATH"          # bash/zsh — add to ~/.profile
pipx ensurepath
pipx reinstall-all
```

### 11.2 `pip install` says PEP 668 / externally-managed-environment

This is **intentional on Debian/Ubuntu**. Do **not** use `--break-system-packages`. Use `pipx` instead.

### 11.3 `che compute_paths` exits 3: the path is not bound

Flat-layout commands never guess a project from the current directory. Bind the checkout to a project first, then re-run:

```bash
che worktree add ~/code/my-company/web-app --project web-app --name main
che compute_paths ~/code/my-company/web-app onboarding-003
```

If the project itself does not exist yet, create it first with an explicit slug:
`che project init ~/code/my-company/web-app --slug web-app`.

### 11.4 Decision logs or task graphs appear in `git status` inside my repo

You do not have the Che blacklist snippet in your repo's `.gitignore`. Re-run the installer:

```bash
curl -fsSL https://raw.githubusercontent.com/laionazeredo/che-ai/main/scripts/install-che.sh | bash -s -- --apply
```

The installer only appends missing lines — idempotent.

---

_Full rationale for the flat project/worktree layout and the trash-safe design lives in [docs/architecture-and-principles.md](./architecture-and-principles.md) and [contracts/path-canonicity-che.md](../contracts/path-canonicity-che.md)._
