# Codex Che Capability Map

This file documents runtime mappings between the shared Che and Codex.

| Che capability | Trae | Codex |
|---|---|---|
| Global rules | Trae global rules | `~/.codex/AGENTS.md` |
| Skills | Trae skills | `~/.agents/skills` |
| Session identity | `SESSION_ID` | `CHE_SESSION_ID` |
| Che root | `$HOME/.trae` | `CHE_HOME` |
| Shell | IDE command tool | Codex shell |
| Git | git | git |
| GitHub | gh | gh |
| Worktree binding | canonical contract | canonical contract |
| Durable artifacts | `$CHE_SESSIONS_ROOT` | `$CHE_SESSIONS_ROOT` |
| Figma design backend | Runtime integration | Figma MCP may be available; detect effective capability per session |
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

Figma capability is session-dependent. Until a real smoke test proves the
active integration, do not claim read, write or export support.

Trae compatibility remains available through:

- default `CHE_HOME=$HOME/.trae`
- fallback `SESSION_ID`
