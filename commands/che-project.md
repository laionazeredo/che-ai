---
description: "Manage flat Che projects (<CHE_WORKSPACES_ROOT>/<slug>/). 5 subcommands: init|create|add REPO_PATH --slug SLUG [--domain D] [--name N] | list | remove SLUG [--dry-run|--no-dry-run --confirm] | restore TRASH_SLUG | trash-list. Scaffolds 8 domain folders + worktrees/ + _db/ + roles/ + the durable docs. Requires an explicit slug and a git path."
arguments:
  - name: repo_path
    description: "Absolute path to the git checkout this project tracks. Mandatory for init|create|add."
    required: false
  - name: subcommand
    description: "Required positional: init <REPO_PATH> --slug <SLUG> [--domain D] [--name N] (aliases: create, add) | list | remove <SLUG> [--no-dry-run --confirm] | restore <TRASH_SLUG> | trash-list. Canonical domains: business | product | design | engineering | devops | copywriting | social | seo-analytics. Legacy aliases normalised on input: ux → design, operation|ops → devops, dev|eng → engineering. Default = engineering."
    required: true
---

Manages the **project** layer of the flat Che storage layout. A project is an
organising abstraction with a stable slug and a folder — it deliberately does
**not** bind a filesystem path. Only a **worktree** does (see `/che-worktree`).

**Location:** `<CHE_WORKSPACES_ROOT>/<project-slug>/` (default root `~/.che-workspaces`).
The `workspaces/<workspace>/<project>/` grouping level was retired in Sep 2026.

**Skeleton created by `init`:**

```
<root>/<slug>/
├── _db/                       # che_state.sqlite (FTS5) + che_rag.sqlite (optional)
├── roles/index.md             # ownership table (project level)
├── architecture.md
├── project_profile.md
├── product_context.md
├── roadmap.md
├── registry.jsonl             # first entry = PROJECT_INIT
├── business/ product/ design/ engineering/ devops/ copywriting/ social/ seo-analytics/
└── worktrees/                 # one folder per bound worktree
```

**Hard preconditions (fail fast, no partial state):**

1. A **git** `repo_path` is mandatory — a non-git directory exits `2` and creates nothing.
2. `--slug` is **mandatory and explicit**; it is never inferred from the git origin
   or from the current working directory.
3. `init` is idempotent: existing documents are never overwritten, so re-running it
   will not clobber hand-edited `roadmap.md`, `architecture.md`, etc.

**DESTRUCTIVE safety gates (`remove`):**

1. `--dry-run` is the DEFAULT and prints the plan (including the bound worktrees and
   the reminder that the repositories themselves are untouched).
2. Apply = `--no-dry-run` **plus** `--confirm` (double flag).
3. Destination = `<root>/.trash/project--<slug>--<timestamp>/` + `_MANIFEST.json`.

**Subcommand dispatch:**

| Subcommand | CLI invocation | Expected agent action after |
|---|---|---|
| `init <REPO> --slug <S> [--domain D] [--name N]` | `che project init "<REPO>" --slug "<S>" [flags]` | Recommended first step of onboarding. Agent: (1) asks for the slug if the user did not give one — never invents it; (2) shows the default domain `engineering` and asks whether to change it, listing the 8 canonical domains; (3) reports `{project_slug, project_dir, domains, skeleton_created, files_created}`; (4) then tells the user the next step is `che worktree add`. |
| `create` / `add` | same as `init` | Aliases. |
| `list` | `che project list` | Table: `Slug │ Worktrees │ Domains │ Has arch? │ Has profile? │ DB files`. If the output carries a `legacy_untouched` entry, surface it: those folders are pre-flattening leftovers, were left untouched, and should be re-created with `che project init` before being moved to `.trash/` manually. |
| `remove <SLUG> [flags]` | `che project remove "<SLUG>" [flags]` | Two-pass protocol: 1) dry-run → show the plan to the user; 2) only after explicit confirmation → `--no-dry-run --confirm`. |
| `restore <TRASH_SLUG>` | `che project restore "<TRASH_SLUG>"` | Moves the folder back to its original path. Refuses (exit 3) if the target already exists — never overwrites. |
| `trash-list` | `che project trash-list` | Lists `.trash/` entries with their manifests. |

**Exit codes:** `0` success · `2` usage/precondition failure (non-git path, missing or
invalid slug, missing `--confirm`) · `3` unknown project or trash entry.

**Never do this:** pass `--workspace` (removed), hand-edit `registry.jsonl`, or create
the project folder with `mkdir` instead of this command.
