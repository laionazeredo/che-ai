# Cursor Che Capability Map

This file documents runtime mappings between the shared Che and Cursor.

| Che capability | Trae | Cursor |
|---|---|---|
| Global rules | Trae global rules | `.cursorrules` or `.cursor/rules/` |
| Skills | Trae skills | `.cursor/rules/*.mdc` |
| Session identity | `SESSION_ID` | `SESSION_ID` |
| Che root | `$HOME/.trae` | `CHE_HOME` |
| Shell | IDE command tool | Cursor terminal |
| Git | git | git |
| GitHub | gh | gh |
| Worktree binding | canonical contract | canonical contract |
| Durable artifacts | `$CHE_SESSIONS_ROOT` | `$CHE_SESSIONS_ROOT` |
| Strategic design | `/che-architect` | `/che-architect` |
| SPEC | `/che-spec` | `/che-spec` |
| Plan/Tickets | `/che-plan` | `/che-plan` |
| Start/orchestration | `/che-act` | `/che-act` |
| QA | Che QA | `/che-qa` |
| Review | `/che-review` | `/che-review` |
| Scope check | `/che-scope-check` | `/che-scope-check` |
| Ship | `/che-ship` | `/che-ship` |

## Compatibility rule

The Che core must not depend directly on one IDE runtime.

Use:

- `CHE_HOME` for the Che installation root.
- `che_current_session_id` for the effective session identifier.
- canonical contracts for generated artifact paths.
