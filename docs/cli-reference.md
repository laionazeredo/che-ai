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

### 1.4 Updating an existing install — `che update`

One command, no flags, no dry-run gate. It moves the checkout to the remote's default branch and
reloads the CLI if it has to:

```bash
che update              # aliases: che self-update, che upgrade
```

```bash
che update --check      # report what an update would bring; change nothing
che update --json       # same envelope for scripts and agents
che update --che-home /path/to/checkout
```

What it does, in order:

1. Resolves the checkout (`$CHE_HOME` → `$HARNESS_HOME` → `~/.che-ai` → `~/.trae`) and refuses
   anything that is not a Che install.
2. Fetches the remote and reports the incoming commits.
3. `git merge --ff-only` onto the remote's default branch.
4. If — and only if — `pyproject.toml` was among the changed files, reinstalls the CLI
   (`pipx install -e … --force`, falling back to `pip install --user -e …`) so a changed
   dependency list actually takes effect.
5. Re-runs the installer of every adapter already wired to this checkout, so the symlinks match
   the files that are now on disk. This runs on **every** real run, including when the checkout
   was already current.

**Why step 4 exists.** Che installs *editable*, so `import che_core` resolves into the checkout: a
pull makes every code change live immediately, while a change to `dependencies` sits in the file
doing nothing until something reinstalls. That is the one gap a plain `git pull` cannot close, and
it is why this is a command rather than a documented sequence of shell steps.

**Why step 5 exists.** A pull moves the *checkout*, not the *installation*. The adapters link each
command, skill and hook one at a time, walking whatever exists at that moment — so a command
renamed upstream gains no new symlink and keeps the old one, which now dangles. The user is left
with a completion list offering a command that resolves to nothing. `che update` therefore re-runs
the adapters, and `scripts/prune-che-symlinks.sh` removes the orphans as part of each install.
Adapters that were never installed are left alone: Che does not wire itself into a host the user
never asked it to touch.

`che update` is safe to run blind. It is fast-forward-only — it cannot invent a merge commit or
rewrite a local one — and every state it will not touch fails closed with the remedy named:

| State | Result |
| :---- | :----- |
| Already on the latest default branch | **Success.** Nothing is downloaded and nothing is reinstalled — but the host wiring is still refreshed (step 5). |
| Modified *tracked* files | **Refused** (exit 3). Commit or `git stash push` first. Personal state (`user_rules/`, `bindings/`, `memory/`) is gitignored and never counts. |
| On a branch other than the default | **Refused** (exit 3). "Get the latest from main" does not mean "move me off my branch". |
| Local commits the remote lacks | **Refused** (exit 3). A fast-forward would discard them. |
| Not reachable | **Refused** (exit 4). Nothing was changed. |
| Code updated, reinstall failed | **Partial** (exit 5). The command that failed is printed; run it yourself. |

Skills, rules and hooks are symlinked into the checkout, so a pull makes them live the moment it
lands. What a pull cannot do is create a symlink that was never there — that is step 5's job.

A zip/manual install (no `.git`) is **refused** by design, pointing at
`scripts/self-update-che.sh`, which owns that path. Two implementations of one merge would be two
chances to disagree.

### 1.5 Uninstall

```bash
pipx uninstall che-ai
# or
pip uninstall che-ai
# Then optionally delete ~/.che-ai
```

---

## 2. Command Map

| Group          | Subcommands                                                         | Scope    | Surface      |
| :------------- | :------------------------------------------------------------------ | :------- | :----------- |
| `capabilities` | (flags: `--command`, `--errors`, `--json`) — see §2.3               | All      | Terminal CLI |
| `project`      | `create` (`add`, `init`), `list`, `remove`, `restore`, `trash-list` | Project  | Terminal CLI |
| `worktree`     | `add`, `list`, `show`, `remove`                                     | Worktree | Terminal CLI |
| `config`       | (flags: `--lang-chat`, `--lang-docs`, `--lang-report`, `--pt-check`, `--flags`) | Session | Terminal CLI |
| `task`         | `list`, `show`, `resume`, `set-status`, `graph-summary`             | Worktree | Terminal CLI |
| `state`        | `rebuild-index`, `query`, `search`, `sanitize`                      | Project  | Terminal CLI |
| `rag`          | `build`, `search`, `list`, `prune`                                  | Project  | Terminal CLI |
| `export`       | (project → portable `.tar.gz`)                                      | Project  | Terminal CLI |
| `import`       | (portable `.tar.gz` → project)                                      | Project  | Terminal CLI |
| `eject`        | `plan`, `execute`, `restore`                                        | All      | Terminal CLI |
| `update`       | (alias: `self-update`, `upgrade`) — flags: `--check`, `--che-home`, `--remote`, `--json` | All | Terminal CLI |
| `pixel`        | `check`                                                             | Worktree | Terminal CLI |
| plumbing       | `compute_paths`, `ensure_dirs`, `output_path`, `write_file_atomic`, `assert_outside_worktree`, `registry_append`, `registry_lookup`, `decision_append` | Any | Terminal CLI |

### 2.1 Help Discovery

Every group and subcommand responds to `--help`:

```bash
che --help
che project --help
che worktree --help
che worktree add --help
che config --help
che eject plan --help
che update --help
```

### 2.2 Every failure is machine-readable

A **failure** always comes out of the same envelope, whether or not `--json` was passed:

```jsonc
{
  "status": "error",
  "code": "UNKNOWN_PROJECT",          // stable identity — branch on this, never on the number
  "stage": "resolve",                 // which part of the command failed
  "message": "project 'web-app' does not exist.",
  "hint": "Projects are created explicitly; nothing is inferred from a path.",
  "retryable": false,
  "next_actions": ["che project init <repo> --slug web-app", "che project list"],
  "exit_code": 3,
  "details": { "project_slug": "web-app" }
}
```

- **`code` is the contract.** Several failures share exit `2`, so the number cannot tell them apart;
  the string can. Codes are declared once in `che_core/diagnostics.py` (`ERROR_CATALOG`), and a test
  fails if a call site raises a code the catalog does not describe.
- **`hint` is the remedy, `next_actions` are the commands.** When a Che command fixes the problem it
  is named there; run it rather than working out the fix from the message.

**`--json` goes before the command and governs both channels:**

```bash
che --json project list          # failure → the envelope on stdout
che --json worktree show web-app main
che --json output_path spec web-app onboarding session md   # success → {"path": "…"}
```

Without it, the same failure is three lines on stderr (`Error:` / `Hint:` / `Next:`) and stdout stays
empty. With it, the envelope goes to **stdout** — so a caller that asked for JSON always finds JSON
there, on stdout, for any command, success or failure. `che capabilities --json` describes each
command's default shape; see the scope note below and §2.3.

> **Scope of the guarantee.** `--json` is a promise about the **channel**, not about the schema:
> stdout carries no prose and no shell, and carries one JSON value — or nothing at all. What that
> value *contains* is per-command, and `che capabilities --json` declares it. The `output` field is
> the **default** shape: what a caller gets without asking, which is what a caller deciding whether
> to ask needs to know.
>
> | Shape | Commands | Why |
> | :--- | :--- | :--- |
> | JSON object | `project`, `worktree`, `task`, `state`, `rag`, `import`, `eject`, `update`, `pixel check/diff/crop`, `capabilities` | Consumed by `jq` and by skills directly. |
> | `export K="v"` lines | `compute_paths`, `pixel paths` | The recipes are `eval "$(che …)"`. The default must stay shell; JSON here would break every skill. |
> | `K=v` lines | `che designer …` | Same reason, for the design-gate recipes. |
> | A bare path | `output_path` | One value, printed to be captured. |
> | Prose | `config`, `export`, a few confirmations | Written for a human reading a terminal. |
> | Nothing | `ensure_dirs`, `write_file_atomic`, `assert_outside_worktree`, `registry_append`, `decision_append` | The side effect *is* the result; exit 0 says it happened. |
>
> Under `--json` every row above renders as a JSON value, except the last: a command with no result
> has nothing to report, and inventing `{"status":"ok"}` would not match the domain payloads the
> always-JSON commands return. **The defaults do not move**, so the ~30 recipes that do
> `eval "$(che compute_paths …)"` are unaffected — none of them passes `--json`, which was verified
> by searching for the flag next to every recipe rather than assumed from the fact that they work.
>
> Three modules are outside this contract because they are not `che` commands: `che_core/ship.py`,
> `che_core/xray.py` and `che_core/decisions_query.py` are invoked as `python3 -m che_core.<module>`,
> so a `che` flag can never reach them. They keep their `K=v` and prose output. Everything a skill
> reaches as `python3 -m che_core.cli <command>` is the same parser and the same contract as `che`.

### 2.3 The surface is data — `che capabilities`

The commands, their arguments, the exit codes and the failure catalogue are emitted as JSON from the
**same parser that runs them**. Read this before guessing a flag.

```bash
che capabilities                                # human list: every command + one-line meaning
che capabilities --json                         # the whole surface, compact
che capabilities --json --command "worktree add"  # one command, with its arguments
che capabilities --json --errors                # + the failure catalogue (§2.2)
```

```jsonc
{
  "global_options": [
    { "name": "--json", "dest": "json_global", "kind": "option", "type": "boolean",
      "required": false, "default": false, "help": "Render any failure as a JSON envelope…" }
  ],
  "exit_codes": [ { "code": 0, "name": "OK", "meaning": "Success." }, … ],  // §10
  "commands": [
    {
      "name": "worktree add",
      "aliases": [],
      "summary": "Bind a git checkout to a project. Idempotent: re-running reuses the existing tree.",
      "mutates": true,
      "requires_bound_worktree": false,
      "output": "json",
      "arguments": [ /* present only when narrowed with --command */ ]
    }
  ],
  "errors": [ /* present only with --errors */ ]
}
```

| Field                     | Meaning                                                                              |
| :------------------------ | :----------------------------------------------------------------------------------- |
| `summary`                 | One sentence stating what the command does — enough to decide whether to run it.      |
| `mutates`                 | The command writes state. A caller checks this before running it unattended.          |
| `requires_bound_worktree` | `che worktree add` must have run first; without it the command exits 3.               |
| `output`                  | Which success shape the command emits **by default** — `json`, `shell`, `kv`, `text`, `prose`, `none`. Under `--json` each becomes a JSON value except `none` (§2.2). |
| `arguments[]`             | `name` (longest form), `dest`, `kind` (`positional`\|`option`), `type`, `required`, `default`, `choices` when constrained, `aliases` for the short forms, `group` for a mutually-exclusive set. |

`-h`/`--help` is omitted from `arguments` on purpose: it exists on all 45 commands and would be noise.

Sizes are what make progressive disclosure work: **12.7 KB** for the whole surface, **~2 KB** for one
command, **~29 KB** with `--errors`. Read the compact form first; narrow only when you need arguments.

**Why it cannot drift.** `build_manifest()` walks the live `argparse` parser (`_SubParsersAction`,
`_actions`, `_mutually_exclusive_groups`) instead of a hand-written table, so it cannot advertise a
flag that does not exist. `che designer …` is dispatched before `argparse` sees it, so the walk
reaches it through a declared delegated parser. The four semantic fields per command are declared in
`che_core/manifest.py` (`COMMAND_SEMANTICS`), and tests fail in **both** directions: a command
without a declared meaning, and a declared meaning whose command no longer exists. Reading private
`argparse` state is the price of that guarantee, and it is pinned by a test rather than assumed.

An unknown `--command` is a catalogued failure, not a traceback:

```bash
che --json capabilities --command "worktree destroy"
# → {"status":"error","code":"UNKNOWN_COMMAND","exit_code":2,"next_actions":["che capabilities"], …}
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

### 3.4 Domain Gate CLI — `che pixel check` / `che pixel paths` / `che pixel diff` / `che pixel crop`

The runner behind `domains/ux/gates/pixel-check-gate.md`. It compares design properties against
rendered DOM properties **numerically** — never screenshot against screenshot — and is the only
supported way to execute that gate. See the gate's §2 Execution for the recipe that `che-ship §0.9.5`
follows.

Resolve the artifact set **first**. `che pixel paths` is the single source of truth for where the gate's
files live (gate §2.3, §4.1–§4.3), and its output is meant to be `eval`'d:

```bash
eval "$(che pixel paths "$WORKTREE_ROOT" "$SESSION_ID" \
  --sub-product <sub_product> --breakpoint lg --backend figma \
  --related-id "$RELATED_ID" --attempt 1)"

che pixel check \
  --map "$CHE_PIXEL_MAP" \
  --dom "$CHE_PIXEL_DOM_FACTS" \
  --design-source "$CHE_PIXEL_DESIGN_RAW" --design-backend figma \
  --design-facts-out "$CHE_PIXEL_DESIGN_FACTS" \
  --breakpoint lg \
  --out "${DOMAIN_GATE_REPORT:-$CHE_PIXEL_REPORT}"
```

The resolved set is split by lifetime, and the split is load-bearing:

| Variable | Lives | Why there |
| :--- | :--- | :--- |
| `CHE_PIXEL_DIR` | inside the worktree: `design/<sub_product>/pixel-check/` | the folder holding the frozen references |
| `CHE_PIXEL_MAP` | inside the worktree, `<breakpoint>.map.json` | human-approved and **frozen as regression**: a timestamped name would stop the next run from finding it |
| `CHE_PIXEL_DESIGN_FACTS` | inside the worktree, `<breakpoint>.design-facts.json` | the per-element record a reviewer reads in the PR diff |
| `CHE_PIXEL_DESIGN_RAW` | inside the worktree — `<breakpoint>.design-raw.txt` (`figma`), or `design/<sub_product>/source/home.op` (`openpencil`, where it already lives) | the bytes the numbers were read from, so a re-run derives them from the same reference |
| `CHE_PIXEL_DOM_FACTS` | session, `design/<related_id>/<timestamp>-<sub_product>-<breakpoint>-dom-facts.json` | a measurement of one attempt; never committed |
| `CHE_PIXEL_REPORT` | session, `…-check-attempt<N>.json` | retry budget is `2` (§5), so the attempt number is in the name: attempt 2 must not overwrite attempt 1 |
| `CHE_PIXEL_DESIGN_IMAGE` · `CHE_PIXEL_DOM_SCREENSHOT` · `CHE_PIXEL_VISUAL_DIFF` | session, `…-design.png` · `…-dom.png` · `…-visual-diff.png` | the gate §4.5 evidence: the design raster, the browser screenshot, and the composite. Nothing scores them, so nothing commits them |
| `CHE_PIXEL_CROP_REPORT` · `CHE_PIXEL_CROP_SHEET` | session, `…-crop-report-attempt<N>.json` · `…-crop-sheet-attempt<N>.png` | the per-element crop (§4.5): same instrument narrowed to each element's box, because a whole-frame percentage is dominated by everything that is not the element. The report carries the attempt, since it is what says *which* element differs |

`che pixel paths` refuses (`2`) when `--sub-product` has no design tree at `design/<sub_product>/`
(create it with `che designer init`), when `--breakpoint` cannot name a file, when `--attempt` is below
`1`, or when `worktree_root` is not a directory. It writes nothing itself.

| Flag | Required | Meaning |
| :--- | :------- | :------ |
| `--sub-product` | yes | Sub-product slug; its design tree must already exist. |
| `--breakpoint` | yes | Breakpoint label, e.g. `lg`. One map per breakpoint. |
| `--backend` | yes | `figma` or `openpencil`. Decides what `CHE_PIXEL_DESIGN_RAW` points at — no inference (gate §3). `penpot` is a declared backend with no capture convention, so it is refused (`2`) with its reason rather than as an invalid choice. |
| `--related-id` | no | Ticket/feature id; groups the session artifacts under one folder. |
| `--attempt` | no | Pass number (default `1`); it becomes part of the report filename. |

| Flag | Required | Meaning |
| :--- | :------- | :------ |
| `--map` | yes | `$CHE_PIXEL_MAP`: `{element: {design_node, selector}}` — the **only** join between the two sides. |
| `--dom` | yes | `$CHE_PIXEL_DOM_FACTS`, keyed by CSS selector. Validated for shape and units before anything is scored; a malformed bag is refused (`2`) rather than scored. |
| `--design-source` | one of | `$CHE_PIXEL_DESIGN_RAW`: the raw `get_figma_data` response, or an OpenPencil `.op` file. |
| `--design` | one of | Design facts already extracted, keyed by design node id. |
| `--design-facts-out` | no | Write gate §4.1's per-element record here — pass `$CHE_PIXEL_DESIGN_FACTS`. It is committed beside the map **inside the worktree**, so it is the one output that deliberately bypasses the outside-worktree guard. Written only after the run is scored, so a refused run leaves no file. |
| `--design-backend` | with `--design-source` | `figma` or `openpencil`. **Never inferred** from the file — guessing picks the wrong extractor and yields plausible-but-wrong numbers. `penpot` is *declared* by the UX domain but has no extractor (its MCP server exposes `execute_code`, not a fact export), so it is refused with that reason instead of an invalid-choice message. With `--design` it is provenance only, so any declared backend is accepted there. |
| `--breakpoint` | no | Label recorded as report provenance. |
| `--design-viewport` | no | Width the design frame was captured at, in px. |
| `--dom-viewport` | no | Width the DOM was measured at, in px. A **mismatch** with `--design-viewport` is refused (`2`) rather than scored, because it makes every measurement meaningless. When either is omitted the report records `viewport_binding: "undeclared"`. |
| `--attempt` | no | Pass number over this screen (default `1`). The retry budget is `2` — the first measurement plus one free retry (§5). A higher value is **refused** (`2`) unless `--override-reason` is given. |
| `--override-reason` | no | The user's verbatim acceptance, recorded in the report. Required to exceed `--attempt 2`; empty means no override was claimed. |
| `--out` | no | Write the JSON report atomically. `che-ship §0.9.5` sets the generic `$DOMAIN_GATE_REPORT` per gate — pass it when it exists, `$CHE_PIXEL_REPORT` standalone. |
| `--json` | no | Print the full report instead of the one-line summary. |

The report also carries `coverage` (the fraction of the gate's 18 reachable categories the run actually
verified), `unverified_categories` (their names — `position` and `opacity` from `.op`,
`letter_spacing` from Figma, `asset` wherever the map declares no digest), `unreachable_categories`
(`margin`, held out of the fraction because no design backend emits one — see the gate §2.6), and the
`viewport_binding`. A `PASS` should be quoted *with* those, never alone: the score is computed over the
verified rows only, so `score=9.5` does not mean "visually identical".

Exit codes — branch on these, not on the text:

| Exit | Verdict | Meaning |
| :--- | :------ | :------ |
| `0` | `PASS` | The gate's three numeric conditions held. |
| `1` | `FAIL` | A condition broke, **or** a designed element is absent from the DOM. |
| `3` | `INCONCLUSIVE` | Could not be decided honestly: a critical category measured on no element, an element with no design reference, or nothing measurable at all. **Never a pass.** |
| `2` | usage | Unreadable artefact, an incomplete map entry, an unknown backend, a missing `--design-backend`, or a **viewport mismatch**. |

The summary line on stdout already matches the gate's `log_format_decisions`, so it can be passed
straight to `che decision_append`.

#### The evidence lane — `che pixel diff` / `che pixel crop`

Gate §4.5's two pictures. Neither is scored, and neither exits non-zero because two rasters differ: a
screen that changed is the finding, not a failure to run. Both take rasters of **equal size** — a
comparison across two sizes returns a number computed against the wrong pixels rather than an error, so
`diff` refuses it with exit `2`.

```bash
che pixel diff \
  --design "$CHE_PIXEL_DESIGN_IMAGE" --dom "$CHE_PIXEL_DOM_SCREENSHOT" \
  --out "$CHE_PIXEL_VISUAL_DIFF"

che pixel crop \
  --design "$CHE_PIXEL_DESIGN_IMAGE" --dom "$CHE_PIXEL_DOM_SCREENSHOT" \
  --map "$CHE_PIXEL_MAP" --dom-facts "$CHE_PIXEL_DOM_FACTS" \
  --out "$CHE_PIXEL_CROP_REPORT" --sheet "$CHE_PIXEL_CROP_SHEET"
```

This is the only part of the CLI that imports anything outside the standard library (`Pillow` and
`numpy`, declared in `pyproject.toml` and installed with the CLI). The comparison itself is a port of
`pixelmatch` 7.2.0 — a YIQ distance behind an anti-aliasing detector — held to that package's own counts
by `tests/test_pixel_visual.py`. It replaced two `.mjs` scripts that no test could execute, which is how
one of them came to carry two false claims in its own docstring.

| Flag | Required | Meaning |
| :--- | :------- | :------ |
| `--design` | yes | Design raster — `$CHE_PIXEL_DESIGN_IMAGE`. |
| `--dom` | yes | Implementation screenshot — `$CHE_PIXEL_DOM_SCREENSHOT`. |
| `--out` | yes | `diff`: the composite PNG. `crop`: the report JSON, written atomically. |
| `--map` | `crop` only | `$CHE_PIXEL_MAP`. Each entry needs a `design_box` in the design image's own pixels; without it the element is **refused**, not guessed. |
| `--dom-facts` | `crop` only | `$CHE_PIXEL_DOM_FACTS` — the same bag `check` validates. |
| `--sheet` | no | `$CHE_PIXEL_CROP_SHEET`: the design \| implementation \| diff strip, one row per element. Omitted from the report when every element was refused, so a path that was requested but never written never reads as evidence of a file. |
| `--threshold` | no | `pixelmatch`'s matching threshold (default `0.1`, which is what §4.5 fixes). Smaller is more sensitive. |
| `--json` | no | `diff`: the counts. `crop`: the full report, on stdout — the per-element progress lines go to stderr so the two never interleave. |

`diff` reports `pixels`, `differing_pixels`, `antialiased_pixels` and `ratio`. The ratio is **not** a
threshold and must never be quoted as one: text antialiasing, DPR and font-loading dominate it, while a
2px radius error barely moves it.

`crop` gives every element exactly one row, whatever happened to it — `compared`, `size_mismatch` (both
crops shown **unscaled**, because resampling would invent the pixels it then compares and erase the drift
that is itself the finding), or `refused` with its reason, which is both printed and recorded so a gap
cannot hide in the JSON.

---

## 4. State & Memory (SQLite FTS5)

Che ships a built-in **append-only** state store on SQLite FTS5, one `che_state.sqlite` per **project**, kept in
`<project>/_db/` so it survives worktree and branch switches. It is **not** a general-purpose database — the primary
workload is full-text search over structured decisions, task graphs, and QA evidence.

```bash
che state rebuild-index ~/code/my-company/web-app   # indexes the bound worktree into <project>/_db/che_state.sqlite
che state query --worktree-root ~/code/my-company/web-app \
  --sql 'SELECT key, json_extract(body,"$.owner") FROM kv WHERE key LIKE "task:%";'
che state search ~/code/my-company/web-app "stripe webhook signature"
che state sanitize ~/code/my-company/web-app         # PII + secrets scrubbing pass
```

`che state query` is read-only by default: only `SELECT`, `EXPLAIN` and `PRAGMA` run. Anything else is
refused with `STATE_QUERY_NEEDS_FORCE` (exit `2`) naming the statement, and needs `--force` — a write is
never something a caller stumbles into. Use `--bind` for `?` placeholders and `--json` for rows instead
of the table.

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
|  1   | Unexpected failure — a Che bug, not a mistake in your input. |
|  2   | Usage / precondition failure: bad argument, non-git path, missing required `--slug` / `--project` / `--name`, refused oversized write, or a destructive operation applied without `--confirm`. |
|  3   | Unknown project / worktree, or a worktree path that is not bound to any project. |
|  3   | `che update`: the working tree is not in a state it will move (dirty tracked files, wrong branch, local commits the remote lacks). Nothing was changed. |
|  4   | `che update`: the remote could not be reached. Nothing was changed. |
|  5   | `che update`: the code was updated but the CLI could not be reinstalled, so its dependencies may be stale. |
|  98  | Fatal missing dependency: the `che` CLI is not on `PATH` (guard raised by the skills before any write). |
|  99  | Storage-boundary violation: a Che artifact would land inside the user's repository. |

Notes:

- `0`, `1`, `2`, `3` and `99` are raised by the CLI itself; `2` is also argparse's default for an unknown flag or a
  missing argument.
- Exit `3` is deliberately overloaded — "not found" and the pixel gate's `INCONCLUSIVE` are different
  outcomes that happened to share a number before there was anywhere to record the difference. Read
  `code` in the envelope (§2.2) rather than the number.
- `98` is not raised by `che_core`: it is the guard the skills run (`command -v che >/dev/null 2>&1 || exit 98`) so
  that nothing is written without a resolved storage boundary.
- `che registry_lookup` exits `1` when the session has no registry row yet; the failure is
  `NO_REGISTRY_ENTRY` and it names the session it looked for.

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
