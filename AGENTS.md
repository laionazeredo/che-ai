# Che AI — Agent Technical Contracts

This document defines the rules and architectural boundaries for **AI coding agents** contributing to or using the **Che** framework.

---

## 1. Core Architecture (3-Layer Rule)

Che follows a strict 3-layer architecture. **NEVER** duplicate rule bodies across layers.

- **L1 (Domains)**: `domains/` — Domain-specific human context (UX, Engineering, etc.).
- **L2 (Framework)**: `CHE_RULES.md` and `CHE_COMMANDS.md` — Routers containing **titles and links ONLY**.
- **L3 (Skills)**: `skills/*/SKILL.md` — Declarative rules and task boundaries.

## 2. Execution Logic (Python-Only)

**CRITICAL:** Python is the canonical language for Che's core logic.
- Procedural logic must reside in `che_core/`.
- Skills (`.md`) must be declarative. Complex logic (> 15 lines) **MUST** be extracted to Python and invoked via CLI.
- No `package.json` or Node.js dependencies are allowed for core execution.

## 3. Workspaces Hierarchy (Path Canonicity)

Che organizes project data into a 4-level hierarchy. **Do not create `.trae/` folders inside user projects.**

1.  **L1 (Workspace Root)**: `~/.che-workspaces/workspaces/<workspace-slug>/`
2.  **L2 (Project Level)**: `<L1>/<project-slug>/project/` (Durable info: `architecture.md`, `project_profile.md`).
3.  **L3 (Worktree Level)**: `<L1>/<project-slug>/worktrees/<wt-slug>/` (Shared info: `decisions.log.jsonl`, `qa/`, `designs/`).
4.  **L4 (Session Level)**: `<L3>/sessions/<SESSION_ID>/` (Ephemeral info: logs, isolated state).

### Agent Guidance:
- **L1 Creation**: `che-workspace create <name>`
- **L2 Registration**: `che-project create <worktree-path> --workspace <name>`
- **L3 Execution**: `che-spec` and `che-act` **REQUIRE** `--project` and `--worktree` parameters.

## 4. Development Principles

- **KISS & YAGNI**: Minimize dependencies and avoid over-engineering.
- **Design by Contract (DbC)**: Apply preconditions and postconditions on core functions.
- **Storytelling Commits**: Use conventional commits with a CDJ body (Context, Decision, Justification).
- **Worktree Hygiene**: Never leave temporary files or logs in the repository root. Ephemeral data belongs in L4.
- **Language Policy**: Code and internal docs in strict English (British spelling for public UI/strings).
- **Blast Radius**: Keep changes focused. Large refactors require explicit justification in `decisions.log.jsonl`.

## 5. Quality & Security

- **CI Pipeline**: All changes must pass `ruff` (lint/format) and `pytest` (unit/security).
- **PII & Secrets**: **NEVER** log or persist raw emails, JWTs, or API keys. Use `NOTIFICATION_PII_HASH_SECRET` for correlation.
- **Skill Security**: Markdown files are analyzed for destructive bash commands. Python blocks in Markdown must not exceed 15 lines.
