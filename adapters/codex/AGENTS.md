# Shared Engineering Harness — Codex Adapter

This Codex environment uses the shared Trae/Codex Engineering Harness.

## Canonical engineering rules

The authoritative engineering rulebook is:

$HARNESS_HOME/skills/engineering-contracts/SKILL.md

Do not duplicate engineering rules in this file.

## Canonical Harness workflow

Feature/refactor workflow:

1. harness-spec
2. harness-scrum-master
3. harness-developer
4. harness-qa
5. harness-compliance
6. harness-scope-checker
7. harness-ship

Bug workflow uses harness-debugger-bugfix.

## Runtime

The Harness runtime is resolved through:

$HARNESS_HOME/contracts/harness_sessions_contract.sh

Codex sessions use HARNESS_SESSION_ID.
Trae compatibility continues through SESSION_ID.

## Worktree safety

One Harness session is bound to one worktree.

Generated Harness artifacts must use the canonical session contract and must never be written inside the user's source worktree.

## Skills

Prefer Harness skills from the shared skills directory.

When a Harness skill conflicts with generic agent behavior, follow the Harness skill.
