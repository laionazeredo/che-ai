---
description: "Bind a git checkout to a project: <CHE_WORKSPACES_ROOT>/<project>/worktrees/<name>/. 4 subcommands: add REPO_PATH --project SLUG --name NAME [--force] | list --project SLUG | show PROJECT NAME | remove PROJECT NAME [--dry-run|--no-dry-run --confirm]. A worktree is the ONLY Che concept that binds a filesystem path; it is shared by every session and is never created per session."
arguments:
  - name: repo_path
    description: "Absolute path to the git checkout to bind. Mandatory for `add`."
    required: false
  - name: subcommand
    description: "Required positional: add <REPO_PATH> --project <SLUG> --name <NAME> [--force] | list --project <SLUG> | show <PROJECT> <NAME> | remove <PROJECT> <NAME> [--no-dry-run --confirm]."
    required: true
---

Manages Che **worktrees**: the only concept in the flat layout that binds a
filesystem path.

A **project** is an abstraction (a slug + a folder). A **worktree** is what points
at a real repository checkout. Every command that writes artifacts must be given a
project, and — when the artifact is worktree-scoped — the worktree that owns it.

**Location:** `<CHE_WORKSPACES_ROOT>/<project-slug>/worktrees/<worktree-name>/`

```
<root>/<project>/worktrees/<name>/
├── .binding.json      # {project, name, path, branch, origin, is_git, created_at, updated_at}
├── decisions.log.jsonl
└── specs/ tasks/ reports/ reviews/ architecture/ gh_stack/ qa/ design/ ...
```

**Why this exists.** Before the flattening, each session created its own folder
inside the worktree (`sessions/<SESSION_ID>/`), so memory fragmented and the same
worktree accumulated one subtree per run. Now the worktree folder is **shared and
reusable**: sessions are registered in `<root>/.state/registry.jsonl`, and their
ephemeral files live outside the worktree in `<project>/.sessions/<id>/`.

**Hard preconditions (fail fast, no partial state):**

1. A **git** `repo_path` is mandatory. A non-git directory exits `2` and creates
   **nothing** — Che refuses rather than creating an orphan worktree you would only
   discover at `che-ship` time.
2. The project must already exist (`che project init`). An unknown project exits `3`.
3. `add` is **idempotent**: re-running it with the same project + name reuses the
   existing tree, refreshes the recorded branch, and reports `reused: true`. It never
   duplicates and never wipes existing artifacts.
4. A directory that already exists but has no `.binding.json` is refused (exit `2`) —
   `--force` is required to adopt it explicitly. Che does not silently take over a
   folder it did not create.

**DESTRUCTIVE safety gates (`remove`):**

1. `--dry-run` is the DEFAULT and prints the plan, which always records
   `repo_path_untouched: true`.
2. Apply = `--no-dry-run` **plus** `--confirm`.
3. Only the Che folder is moved — to `<root>/.trash/worktree--<project>--<name>--<ts>/`
   with a `_MANIFEST.json`. **The bound repository is never modified.**

**Subcommand dispatch:**

| Subcommand | CLI invocation | Expected agent action after |
|---|---|---|
| `add <REPO> --project <P> --name <N>` | `che worktree add "<REPO>" --project "<P>" --name "<N>"` | Always ask the user which worktree name to use if they did not say; suggest `main` for the primary checkout. Report `{added|reused, worktree_dir, branch, decisions_path}`. If the command exits `2` with "not a git repository", tell the user the path must be a git checkout — do not retry with a guess. |
| `list --project <P>` | `che worktree list --project "<P>"` | Table: `Name │ Bound path │ Branch`. Use this to resolve which worktree an artifact belongs to before writing. |
| `show <P> <N>` | `che worktree show "<P>" "<N>"` | Prints the binding record. Exit `3` when the worktree is not bound. |
| `remove <P> <N> [flags]` | `che worktree remove "<P>" "<N>" [flags]` | Two-pass protocol: 1) dry-run → show the plan; 2) only after explicit confirmation → `--no-dry-run --confirm`. State clearly that the repository is untouched. |

**Exit codes:** `0` success · `2` usage/precondition failure (non-git path, missing
flags, unmanaged directory without `--force`, missing `--confirm`) · `3` unknown
project or unbound worktree.

**Never do this:** create `sessions/` folders inside a worktree; hand-write
`.binding.json`; `rm -rf` a worktree folder (use `remove`, it is trash-safe); assume
`compute_paths` will guess the project from the current directory — it will not, and
it exits `3` with an actionable message.
