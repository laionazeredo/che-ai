# Shared Engineering Che — Codex Adapter

This Codex environment uses the shared Trae/Codex Engineering Che.

## Canonical engineering rules

The authoritative engineering rulebook is:

$CHE_HOME/skills/engineering-contracts/SKILL.md

Do not duplicate engineering rules in this file.

## Canonical Che workflow

Feature/refactor workflow:

1. che-spec
2. che-act
3. che-developer
4. che-qa
5. che-compliance
6. che-scope-checker
7. che-ship

Bug workflow uses che-debugger-bugfix.

## Runtime

The Che runtime is resolved through:

$CHE_HOME/contracts/che_sessions_contract.sh

Codex sessions use CHE_SESSION_ID.
Trae compatibility continues through SESSION_ID.

## Worktree safety

One Che session is bound to one worktree.

Generated Che artifacts must use the canonical session contract and must never be written inside the user's source worktree.

## Skills

Prefer Che skills from the shared skills directory.

When a Che skill conflicts with generic agent behavior, follow the Che skill.
