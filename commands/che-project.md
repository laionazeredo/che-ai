---
description: "Manage Che projects (L2 .registry/projects/<slug>/). 4 subcommands: create WTPATH (aliases: add, init) | list | remove SLUG [--dry-run|--no-dry-run --confirm] | restore TRASH_SLUG. Initializes deterministic scaffold: architecture.md + project_profile.md + product_context.md + roadmap.md + roles/ + registry.jsonl + _db/ and ensures L3 .wt/__<branch>/."
arguments:
  - name: worktree
    description: "Absolute worktree path (mandatory for `create`). For list/remove/restore, uses current bindings if omitted."
    required: false
  - name: subcommand
    description: "Required positional: create <WORKTREE_ROOT> (aliases: add, init) --workspace <WS> [--domain engineering] [--name FRIENDLY] [--session-id SID] | list | remove <PROJECT_SLUG> [--no-dry-run --confirm] | restore <TRASH_SLUG>. Valid Politburo domains: engineering | ux | product | devops | copywriting | social | seo-analytics. Default=engineering."
    required: true
---

Manages the **L2 layer (Project Durable Registry)** of the Che 4-level hierarchy. Projects live in:
- **Che registry path**: `~/.che-workspaces/<workspace-slug>/.registry/projects/<project-slug>/` — durable, cross-worktree, contains the 8 canonical artifacts.
- **In the worktree**: `.wt/__<branch-slug>/` folder (L3 shared per branch) created/guaranteed during `create`.

**Scaffold `create` initializes 8 deterministic artifacts** in `.registry/projects/<slug>/`:
1. `architecture.md` (C4 L1/L2 + ADR index + Data Model + QA)
2. `project_profile.md` (auto-detected stack via file probe: pnpm/uv/go/Cargo/etc + git origin + workspace + deployment roles)
3. `product_context.md` (pitch, personas placeholder, roadmap skeleton)
4. `roadmap.md` (milestones placeholder, epic templates)
5. `roles/index.md` (PO/TechLead/UX/DevOps/QA ownership table + CODEOWNERS placeholder)
6. `registry.jsonl` (Level 2 registry, append-only. First entry = `PROJECT_INIT`.)
7. `_db/README.txt` (location for SQLite state+rag; rebuild/backup/purge instructions)
8. **In the target worktree**: guarantees existence of `.wt/__<branch>/sessions/` (L3) + `.che-export-manifest.json`.

**DESTRUCTIVE safety gates (remove = same rules as workspace):**
1. `--dry-run` DEFAULT.
2. Apply = `--no-dry-run` + `--confirm` (double flag).
3. Destination = `~/.che-workspaces/.trash/project--<slug>--<ts>/` + `_MANIFEST.json`.

**Subcommand dispatch:**

| Subcommand | CLI invocation | Expected agent action after |
|---|---|---|
| `create <WT> --workspace <WS> [--domain D] [--name N] [--session-id S]` | `python3 -m che_core.cli project create "<WT>" --workspace "<WS>" [flags] --json` | **Recommended entry for onboarding:** run `che project create` BEFORE che-xray/che-onboarding. Agent: (1) validates if workspace `<WS>` exists; if not, asks whether to create a new one; (2) shows default domain=engineering and asks whether to change (only lists 7 valid Politburo); (3) detects stack via file probe + git remote origin; (4) defines `friendly_name` as `<workspace>--<folder>` if omitted; (5) scaffold 8 files + ensure L3 dirs; (6) report `{project_slug, workspace, domain, stack, origin, files_created: 8, l3_created: true}`. |
| `add <WT> --workspace <WS>` | `python3 -m che_core.cli project add "<WT>" --workspace "<WS>" --json` | Alias for `create`. |
| `init <WT> --workspace <WS>` | `python3 -m che_core.cli project init "<WT>" --workspace "<WS>" --json` | Alias for `create`. |
| `list` | `python3 -m che_core.cli project list --json` | Table: `Slug │ Workspace │ Domain │ Stack │ Has arch? │ Has profile? │ Has DB?` |
| `remove <SLUG> [flags]` | `python3 -m che_core.cli project remove "<SLUG>" [flags] --json` | Same 2-pass protocol as `/che-workspace remove`: 1) dry-run → show plan to user; 2) user confirms → run with `--no-dry-run --confirm`. |
| `restore <TRASH_SLUG>` | `python3 -m che_core.cli project restore "<TRASH_SLUG>" --json` | Restores project from trash. Slug conflict → `--restored-<ts>` suffix. |
