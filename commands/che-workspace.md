---
description: "Manage Che workspaces (L1 ~/.che-workspaces/workspaces/<slug>). 4 subcommands: create <NAME> | list | remove <NAME> [--no-dry-run --confirm] | restore <TRASH_SLUG> | trash-list."
arguments:
  - name: subcommand
    description: "Required positional: create <NAME> | list | remove <NAME> [--no-dry-run --confirm] | restore <TRASH_SLUG> | trash-list. Removal NEVER deletes: it moves to .trash/. Dry-run is DEFAULT. Examples: /che-workspace create flockr / /che-workspace list / /che-workspace remove foo / /che-workspace remove foo --no-dry-run --confirm / /che-workspace restore workspace--foo--20260904-235959 / /che-workspace trash-list"
    required: true
---

Manages the **L1 layer (Workspace Root)** of the Che 4-level hierarchy. Workspaces logically group projects (e.g., by client, team, initiative). Canonical path: `~/.che-workspaces/<workspace-slug>/`.

**DESTRUCTIVE safety gates (remove does NOT delete):**
1. **`--dry-run` is DEFAULT.** Without flags: only displays `action_would_be`, DOES NOT move anything.
2. To apply: **double flag** `--no-dry-run` + `--confirm` (both together).
3. Even when confirmed: **moves to `~/.che-workspaces/.trash/workspace--<slug>--<ts>/`** (never rm -rf). Recoverable via `restore`.

**Subcommand dispatch:**

| Subcommand | CLI invocation | Expected agent action after |
|---|---|---|
| `create <NAME> [--worktree-root WT]` | `python3 -m che_core.cli workspace create "<NAME>" [--worktree-root "..."] --json` | Creates the folder `~/.che-workspaces/workspaces/<slug>/` + `_MANIFEST.json`. If `--worktree-root` was passed → the workspace is marked as "default" for that worktree. Report `created=True`, slug, and absolute path. |
| `list` | `python3 -m che_core.cli workspace list --json` | Prints a formatted table: `Slug │ Name │ Projects count │ Default worktree │ Created`. |
| `remove <NAME> [--dry-run | --no-dry-run --confirm]` | `python3 -m che_core.cli workspace remove "<NAME>" [flags] --json` | **1st run ALWAYS dry-run** (safety). The agent only runs `--no-dry-run --confirm` AFTER the user reviews the dry-run output and confirms verbally. Report `dry_run=True/False`, `aborted=True` if confirm was missing, `moved_to_trash=` path if effective. |
| `restore <TRASH_SLUG>` | `python3 -m che_core.cli workspace restore "<TRASH_SLUG>" --json` | Restores a trash entry back to `~/.che-workspaces/`. Handles slug conflicts: `--restored-<ts>` suffix if name is already taken. Report `restored=True` + final path. |
| `trash-list` | `python3 -m che_core.cli workspace trash-list --json` | Lists the contents of the trash: `Kind │ Slug │ Original path │ Moved at`. Useful before `restore`. |
