# Che AI — CLI Reference

> **Binaries:** `che-ai` (canonical) and `che` (short alias). Both point to the same entry point.
> **Runtime:** All commands listed in this document run against your local filesystem, SQLite, and local `git` subprocess. No network calls to any LLM provider are made. No token spend.
> **Install:** See _Installation_ below. After install, type `che --help` or `che-ai --help` at any terminal.

---

## Table of Contents

1. [Installation](#1-installation)
2. [Command Map](#2-command-map-by-layer)
3. [Layered Commands (L1 → L4)](#3-layered-commands-l1--l4)
   1. [L1 Workspaces](#31-l1-workspace-cli)
   2. [L2 Projects](#32-l2-project-cli)
   3. [L3 / L4 Session & Config](#33-l3--l4-session--config)
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
> `/che-workspace`, `/che-project`, `/che-spec`, `/che-act`, `/che-ship`, `/che-review`, `/che-prd`, `/che-tasks`, `/che-notes`, `/che-graph` **(built-in) plus community custom skills (examples: `/figma-pixel-check`, `/flockr-*`, `/my-company-*`) continue to exist and are maintained**. They remain the recommended entry point for flows that require LLM reasoning (spec authoring, implementation loops, code review, PR gating) — **used inside Claude Code by default**.
>
> Use **this `che-ai` CLI** for team bootstrap, workspace admin, CI wiring, trash-safe operations, offline state work, bulk listing, and portable export/import. A standard team flow is: `che workspace create` (terminal or CI setup) → `/che-spec` (IDE agent) → `/che-act` (IDE agent) → `/che-ship` (IDE agent).

### 1.0 Platform Compatibility

The installer and the CLI target **POSIX bash/zsh userlands only**.

| OS | Support | Notes |
| :- | :------ | :---- |
| **Linux** (any distro, GNU coreutils + bash ≥ 4.4 + python3 ≥ 3.9) | ✅ Fully supported. Primary target. | `apt` / `dnf` / `pacman` / `nix`. |
| **macOS** (Monterey / 12+, zsh or bash via Homebrew) | ✅ Fully supported. | Use `brew install pipx git python@3.12`. File paths inside `~/.trae` are case-insensitive on APFS by default — don't rely on case-only folder names. |
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

### 1.1 Quick Install Script (recommended, installs `~/.trae` + CLI)

Runs the full installer: backs up any existing `~/.trae`, copies the official whitelist, re-injects the planning-artifacts `.gitignore` snippet into client repos you touch, **and installs the `che` / `che-ai` CLI binaries globally via `pipx`** (fallback `pip install --user` if pipx is not available — with a loud warning telling you to install pipx).

```bash
curl -fsSL https://raw.githubusercontent.com/laionazeredo/che-ai/main/scripts/install-che.sh | bash -s -- --apply

# Skip CLI install (IDE-only usage):
# curl -fsSL ... | bash -s -- --apply --no-cli

# Non-destructive update (preserves user_rules/, registry, memory):
# curl -fsSL ... | bash -s -- --update --apply
```

### 1.2 CLI-only — pipx (user-level, isolated)

If you already have a `~/.trae` folder from a previous install and just want to install / upgrade the binaries:

```bash
cd ~/.trae                               # path where che-ai lives
pipx install -e . --force                # editable = updates to source immediately reflected

which che-ai      # → ~/.local/bin/che-ai
which che         # → ~/.local/bin/che   (short alias)
```

This is the **canonical and safest** install for end-user machines. It creates a private venv at `~/.local/pipx/venvs/che-ai/` and links the two binaries into your `PATH`.

### 1.3 Container / throwaway — `pip install --break-system-packages`

Only inside Docker, CI runners, or throwaway containers. Do **not** use on your developer workstation.

```bash
cd ~/.trae
pip install -e . --break-system-packages
```

### 1.4 Uninstall

```bash
pipx uninstall che-ai
# or
pip uninstall che-ai
# Then optionally delete ~/.trae
```

---

## 2. Command Map (by Layer)

| Group        | Subcommands                                                         | Layer | Surface |
| :----------- | :------------------------------------------------------------------ | :---- | :------ |
| `workspace`  | `create`, `list`, `remove`, `restore`, `trash-list`               | L1    | Terminal CLI |
| `project`    | `create` (`add`, `init`), `list`, `remove`, `restore`             | L2    | Terminal CLI |
| `config`     | (flags: `--lang-chat`, `--lang-docs`, `--lang-report`, `--pt-check`, `--flags`) | L3/L4 | Terminal CLI |
| `task`       | `list`, `show`, `resume`, `set-status`, `graph-summary`           | L3    | Terminal CLI |
| `state`      | `rebuild-index`, `query`, `search`, `sanitize`                     | L3    | Terminal CLI |
| `rag`        | `build`, `search`, `list`, `prune`                                 | L3    | Terminal CLI |
| `export`     | (project → portable `.tar.gz`)                                     | L2    | Terminal CLI |
| `import`     | (portable `.tar.gz` → project)                                     | L2    | Terminal CLI |
| `eject`      | `plan`, `execute`, `restore`                                       | All   | Terminal CLI |
| plumbing     | `compute_paths`, `ensure_dirs`, `registry_append`, `registry_lookup`, `decision_append` | Any | Terminal CLI |

### 2.1 Help Discovery

Every group and subcommand responds to `--help`:

```bash
che --help
che workspace --help
che workspace create --help
che config --help
che eject plan --help
```

---

## 3. Layered Commands (L1 → L4)

### 3.1 L1 Workspace CLI

Workspaces are the **highest-level grouping** in Che. They live under `~/.che-workspaces/workspaces/<slug>/`.

#### `che workspace create <name>`

Creates a new empty L1 workspace.

```bash
che workspace create acme
che workspace create my-company
```

Output is JSON with the absolute path and next-step hint.

#### `che workspace list`

Prints every L1 workspace + project count.

```json
[
  {
    "name": "acme",
    "path": "/home/laion/.che-workspaces/workspaces/acme",
    "projects_count": 2,
    "projects": ["web-app", "github-com-acme-web-app"]
  }
]
```

#### `che workspace remove <name> [--dry-run | --no-dry-run --confirm]`

**Never does `rm -rf`.** Always **moves** the workspace to `~/.che-workspaces/.trash/workspace--<slug>--<timestamp>` with a deterministic restore command.

**SAFETY FIRST.** Always dry-run before any destructive action:

```bash
# Step 1 — inspect what will happen
che workspace remove acme --dry-run

# Step 2 — confirm when you are sure
che workspace remove acme --no-dry-run --confirm
```

#### `che workspace restore <trash-slug>`

Undoes a remove. The exact `<trash-slug>` is printed by both `remove --dry-run` and `trash-list` (see below).

```bash
che workspace restore workspace--acme--20260909-190810
```

#### `che workspace trash-list`

Lists every currently-restorable workspace and project sitting in `.trash/`:

```bash
che workspace trash-list | jq -r '.[] | "\(.kind)\t\(.slug)\t\(.restore_hint)"'
```

---

### 3.2 L2 Project CLI

An L2 project is the durable home for strategy, architecture, product context, roles, roadmap, and the shared shared DB folder. Every project **must** be attached to exactly one L1 workspace.

The L2 directory for a project of slug `s` in workspace `w` is:

```
~/.che-workspaces/workspaces/<w>/<s>/
  ├─ project/         (version-able templates, human-writable)
  │    ├─ architecture.md
  │    ├─ project_profile.md
  │    ├─ product_context.md
  │    ├─ roadmap.md
  │    ├─ roles/index.md
  │    └─ registry.jsonl
  ├─ worktrees/       (one per git branch / repo copy)
  │    └─ <wt-slug>/  ← L3 shared memory
  └─ _db/             (SQLite files, CSVs, other shared data blobs)
       └─ README.txt
```

#### `che project init <worktree-path> --workspace <ws> --domain <domain> --name "<f.name>" --session-id <id>`

Canonical first-run. Given a local git repository path, bootstraps the seven standard L2 files.

```bash
# Inside or outside your repo. Worktree must be a valid git repo (at least one commit).
cd ~/code/my-company/web-app
che project init . \
    --workspace acme \
    --domain product \
    --name "My Company Web App" \
    --session-id onboarding-001
```

Output JSON lists `files_created_count`, the `paths` env-vars dictionary, and four human-readable `next_steps`.

> **Tip:** If you have a fresh new repo with zero commits, run `git commit --allow-empty -m "chore: initial empty commit"` first.

#### `che project create` / `che project add` / `che project init`

All three are aliases. Behaviour is identical. Use whichever mnemonic you prefer.

#### `che project list [--workspace <ws>]`

Lists all known L2 projects with `architecture_exists`, `project_profile_exists`, and `db_files` (files under `_db/`). Filter to one workspace with `--workspace`.

#### `che project remove <slug> <workspace> --dry-run | --no-dry-run --confirm`

Same trash-safe pattern as workspaces. Moves the whole L2 tree to `.trash/project--<slug>--<ts>`. Does **not** touch the original git repo.

#### `che project restore <trash-slug>`

Restores a previously-removed project.

---

### 3.3 L3 / L4 Session & Config

Every AI session against a worktree is addressed by a **stable `session_id`**. Session flags and bindings are append-only JSONL written to the project `registry.jsonl` and never mutated in-place.

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

## 4. State & Memory (SQLite FTS5)

Che ships a built-in **append-only** state store on SQLite FTS5, one `.db` per worktree (L3). It is **not** a general-purpose database — the primary workload is full-text search over structured decisions, task graphs, and QA evidence.

```bash
che state rebuild-index ~/code/my-company/web-app   # re-indexes L3 artefacts
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

Any L2 project can be snapshotted into a self-contained `.tar.gz` and moved between machines, or between workspaces on the same machine. The exporter never copies `.git/` and never copies the worktree code — **only** the durable L2 directory plus the L3 shared folder.

```bash
che export web-app --workspace acme --out ~/Desktop/acme-web-app-20260909.tar.gz
# ...move file to another machine...
che import ~/Downloads/acme-web-app-20260909.tar.gz --workspace acme
```

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

### `che compute_paths <worktree> <session_id>`

Prints the canonical L1–L4 paths as shell-exportable variables. Use this from bash or from `$()` scripts instead of hard-coding `~/.che-workspaces`:

```bash
eval "$(che compute_paths ~/code/my-company/web-app onboarding-003)"
echo "$CHE_PROJECT_DIR"     # L2 project/templates dir
echo "$CHE_WORKSPACE_DIR"   # L1 workspace dir
echo "$CHE_WORKTREE_DIR"    # L3 shared dir
echo "$CHE_SESSION_DIR"     # L4 ephemeral dir
```

### `che ensure_dirs <worktree> <session_id>`

Creates every missing directory in the L1–L4 hierarchy. Idempotent, safe to re-run.

### `che registry_append` / `che registry_lookup <session_id>`

Append-only JSONL registry. `registry_append` takes the same flags as `config` plus arbitrary event JSON. `registry_lookup` returns the last known FLAGS + BINDING row for a session.

### `che decision_append`

Writes one structured row to the canonical `decisions.log.jsonl` for the worktree (L3). Required by the engineering contracts before every non-trivial refactor.

```bash
che decision_append ~/code/my-company/web-app \
    --kind ARCH \
    --title "Move analytics storage to dedicated S3 bucket" \
    --body-file /tmp/WEB-42-body.md \
    --tags WEB-42,storage,RLS
```

---

## 10. Exit Codes & Convention

| Code | Meaning                                           |
| :--: | :------------------------------------------------ |
|  0   | OK, JSON on stdout for read commands              |
|  2   | argparse usage error / missing flags              |
|  3   | Safety gate not passed (e.g. `--confirm` missing) |
|  4   | Workspace / project / session not found           |
|  5   | Worktree path is not a valid git repo             |
|  130 | Interrupted (SIGINT)                              |

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

### 11.3 Project create wrote templates to `default/` workspace instead of the one I asked

A known one-line bug in some pre-release versions of `che_core.workspaces.init_project`. Workaround before the fix:

```bash
# Move manually + re-register
mv ~/.che-workspaces/workspaces/default/my-slug ~/.che-workspaces/workspaces/target-ws/my-slug
che project list --workspace target-ws
```

### 11.4 Decision logs or task graphs appear in `git status` inside my repo

You do not have the Che blacklist snippet in your repo's `.gitignore`. Re-run the installer:

```bash
curl -fsSL https://raw.githubusercontent.com/laionazeredo/che-ai/main/scripts/install-che.sh | bash -s -- --apply
```

The installer only appends missing lines — idempotent.

---

_Full rationale for the L1–L4 hierarchy and the trash-safe design lives in [docs/architecture-and-principles.md](./architecture-and-principles.md)._
