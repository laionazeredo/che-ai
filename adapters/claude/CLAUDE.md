# Shared Engineering Che — Claude Code Adapter

This Claude environment uses the shared Trae/Codex/Claude Engineering Che.

## Canonical engineering rules

The authoritative engineering rulebook is:

$CHE_HOME/skills/engineering-contracts/SKILL.md

Do not duplicate engineering rules in this file.

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

## Runtime

The Che runtime is resolved through:

$CHE_HOME/contracts/che_sessions_contract.sh

Claude sessions use SESSION_ID.

## Worktree safety

One Che session is bound to one worktree.

Generated Che artifacts must use the canonical session contract and must never be written inside the user's source worktree.

## Skills

Prefer Che skills from the shared skills directory.

When a Che skill conflicts with generic agent behavior, follow the Che skill.
