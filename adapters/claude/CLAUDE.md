# Che — Claude Code User-Scope Adapter

This is the **canonical user-scope Che adapter** (official path: `~/.claude/CLAUDE.md`).
The Che shared rule package loads into Claude Code via **five orthogonal injection points**:

1. **This file** (`CLAUDE.md`) — team-wide default agent posture, referenced by every project in this IDE user home.
2. **User-scope skills** in `~/.claude/skills/<slug>/` — symlinked from the Che source-of-truth checkout. All Che slash commands and engineering contracts live here; they are auto-discovered by Claude Code per official docs.
3. **User-scope rules** in `~/.claude/rules/che-domains/*.md` + `che-user/*.md` — loaded for every project, path-scopable via frontmatter `paths:`. Domain rulebooks (engineering, product, UX, etc.) and local user overrides live here.
4. **Legacy commands** in `~/.claude/commands/*.md` — backward-compatibility symlinks; use skills instead for new work.
5. **Settings hooks** (non-destructive deep-merge in `~/.claude/settings.json`) — PreToolUse/PostToolUse events binding the Che worktree session contract, so the agent never writes planning artifacts inside the user repo.

## Canonical engineering rules

The authoritative engineering rulebook is the **engineering-contracts skill** (loaded via the skills folder above).
Do **not** duplicate engineering rules in this file; follow the skill.

## Canonical Che workflow

Feature/refactor workflow:

1. che-architect
2. che-onboarding
3. che-spec
4. che-plan
5. che-act
6. che-developer
7. che-qa
8. che-compliance
9. che-scope-checker
10. che-ship

Bug workflow uses che-fix.

## Runtime & Session Contract

The Che runtime is resolved via the settings hooks above (PreToolUse worktree binding + PostToolUse cleanup / dedup / language check). Session state lives outside the user source tree in the canonical 4-level worktree hierarchy under `~/.che-workspaces/`, not in the user's git repos.

Claude sessions use the `SESSION_ID` from the IDE context; the Che CLI (`che` / `che-ai` installed via pipx) is the canonical sidecar for all structural operations (workspace create, project init, config set, etc.) before any skill is allowed to touch the filesystem.

## Worktree safety

One Che session is bound to one worktree.

Generated Che artifacts must use the canonical session contract and must **never** be written inside the user's source worktree. Ephemeral logs go in the session level; shared evidence (QA reports, design exports, decision logs) goes in the worktree level.

## Precedence & Conflict Resolution

When a Che skill, rule, or domain rulebook conflicts with generic agent behaviour, **follow the Che layer** in this order: user-scope rules (`che-user/` take precedence over `che-domains/`) → skills → this CLAUDE.md. Follow the official Claude Code memory/settings precedence layer for anything beyond Che.

## Customising the adapter home

Per official Claude Code settings docs, override the user config home with:
```bash
export CLAUDE_CONFIG_DIR="<path>"  # default: $HOME/.claude
```
The Che installer reads this env var too, so all five injection points move together.
