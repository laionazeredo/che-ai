---
description: "Behaviour-preserving refactoring (Fowler). Applies established refactorings (extract function, inline, extract variable, replace conditional with polymorphism, split phase, ...) to improve readability, maintainability, scalability and testability WITHOUT changing observable behaviour. PRECONDITION: a green test safety net; missing coverage means characterization tests first. Never runs inside /che-ship."
arguments:
  - name: worktree
    description: "Absolute path to the git worktree to refactor."
    required: true
  - name: scope
    description: "Files / module / smell to target (e.g. --scope=packages/server/billing or --smell=long-function). Keep it narrow to bound the blast radius."
    required: true
---

IMMEDIATELY invoke **`che-refactor`** Skill.

Preflight:
- `cd <worktree> && git rev-parse --is-inside-work-tree` = `true`.
- **Safety net**: run the project tests for the scope FIRST. Red → stop. No coverage → the first commit
  is characterization tests, not a refactoring.
- Scope mandatory and narrow (a repo-wide refactor is a red flag → split into increments / gh-stack).

Output: behaviour-preserving refactored code + a refactor log (smell → refactoring → files → signal
improved), tests green.
