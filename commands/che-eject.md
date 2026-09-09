---
description: "Eject Che safely and reversibly: uninstall multi-agent adapters, move whitelist files to trash, clean up .gitignore snippets from client projects, and allow restore. 4 subcommands: plan [flags] | trash-list | restore TRASH_SLUG [flags]. 3 mandatory safety gates for destructive operations. NEVER uses rm — only moves to .trash/che-eject/. Absolute blacklist (never touched): user_rules/, bindings/registry.jsonl, memory/, .git/, node_modules/."
arguments:
  - name: subcommand
    description: "Required positional: plan [--che-home=PATH] [--keep-git-repo|--no-keep-git-repo] [--scan-client-repos PATH ...] [--dry-run (DEFAULT)|--apply --confirmed --i-know-what-im-doing] | trash-list | restore TRASH_SLUG [--dry-run (DEFAULT)|--apply --confirmed]. Examples: /che-eject plan / /che-eject plan --apply --confirmed --i-know-what-im-doing / /che-eject plan --scan-client-repos ~/code/foo ~/code/bar / /che-eject trash-list / /che-eject restore che-eject--abc123--20260904-235959 --apply --confirmed"
    required: true
---

Canonical command to **uninstall (eject) Che in a 100% reversible way**, returning the agent environment to its original state before installation. Implements the same safety gate philosophy as workspace/project commands:

**3 DESTRUCTIVE Safety Gates (operations NEVER delete, only move):**
1. **`--dry-run` is DEFAULT.** Without flags: only displays the complete `eject_plan` (`would_uninstall_adapters`, `would_move_to_trash`, `would_cleanup_gitignores`), without writing anything to disk.
2. To apply the eject: **THREE flags together** `--apply --confirmed --i-know-what-im-doing` (all 3; missing one = block with error).
3. Even when confirmed: **moves to `~/.che-workspaces/.trash/che-eject/<slug--ts>/`** (never rm -rf). Fully recoverable via `restore`.

**Automatically detected Install Kinds:**
- `git-clone`: `che_home/.git/` exists → DEFAULT `--keep-git-repo=True` (keeps user's clone/fork as a regular Git repo; only uninstalls adapters and cleans up client snippets; DOES NOT move whitelist files). Use `--no-keep-git-repo` explicitly if you want to move everything (including .git).
- `copy-install`: no `.git/` → always moves whitelist to trash (blacklist remains intact).

**Absolute Blacklist (NEVER touched under any circumstances):**
`user_rules/`, `bindings/registry.jsonl`, `memory/`, `.git/`, `node_modules/`.

**Subcommand dispatch:**

| Subcommand | CLI invocation | Expected agent action after |
|---|---|---|
| `plan [flags]` (default) | `python3 -m che_core.cli eject plan [--che-home PATH] [--keep-git-repo\|--no-keep-git-repo] [--scan-client-repos PATH ...] [--dry-run\|--apply --confirmed --i-know-what-im-doing]` | **1st run ALWAYS dry-run** (safety). The agent only runs `--apply --confirmed --i-know-what-im-doing` AFTER the user reviews the dry-run output and confirms verbally. Reports: `install_kind`, `adapters_detected`, `kept_blacklist_count`, `moved_count`, `uninstalled_adapters`, `cleaned_gitignores`, `trash_destination`. |
| `trash-list` | `python3 -m che_core.cli eject trash-list [--trash-root PATH]` | Lists the contents of the `che-eject` trash: shows `trash_slug`, `original_che_home`, `ejected_at`, `install_kind`, `manifest_entries_count`. Useful before `restore`. |
| `restore <TRASH_SLUG> [flags]` | `python3 -m che_core.cli eject restore "<TRASH_SLUG>" [--dry-run\|--apply --confirmed]` | Restores an eject from the trash back to the original `che_home`. Handles slug conflicts: does not overwrite (warns with error). Post-restore: automatically executes `scripts/setup-adapters.sh` to reconnect Codex/Claude/Cursor symlinks. |
