# Codex Harness Capability Map

This file documents runtime mappings between the shared Harness and Codex.

| Harness capability | Trae | Codex |
|---|---|---|
| Global rules | Trae global rules | `~/.codex/AGENTS.md` |
| Skills | Trae skills | `~/.agents/skills` |
| Session identity | `SESSION_ID` | `HARNESS_SESSION_ID` |
| Harness root | `$HOME/.trae` | `HARNESS_HOME` |
| Shell | IDE command tool | Codex shell |
| Git | git | git |
| GitHub | gh | gh |
| Worktree binding | canonical contract | canonical contract |
| Durable artifacts | `$HARNESS_SESSIONS_ROOT` | `$HARNESS_SESSIONS_ROOT` |
| Figma design backend | Runtime integration | Figma MCP may be available; detect effective capability per session |
| SPEC | `/harness-spec` | `$harness-spec` |
| Start/orchestration | `/harness-start` | `$harness-scrum-master` |
| QA | Harness QA | `$harness-qa` |
| Review | `/harness-review` | `$harness-code-review` |
| Scope check | `/harness-scope-check` | `$harness-scope-checker` |
| Ship | `/harness-ship` | `$harness-ship` |

## Compatibility rule

The Harness core must not depend directly on one IDE runtime.

Use:

- `HARNESS_HOME` for the Harness installation root.
- `harness_current_session_id` for the effective session identifier.
- canonical contracts for generated artifact paths.

Figma capability is session-dependent. Until a real smoke test proves the
active integration, do not claim read, write or export support.

Trae compatibility remains available through:

- default `HARNESS_HOME=$HOME/.trae`
- fallback `SESSION_ID`
