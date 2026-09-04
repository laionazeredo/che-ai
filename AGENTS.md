# Che AI — Agent Context & Rules

This file is intended for **AI coding agents** (Trae, Cursor, Codex, Claude Code, OpenCode) contributing to the development and maintenance of the **Che** framework.

## What this repo is

**Che** is an IDE-agnostic, plugin-like framework that simulates an Agile team (Scrum Master, Developer, QA, UI Designer, Compliance, etc.) inside an AI coding assistant. It enforces Software Development Life Cycle (SDLC) best practices, automated quality gates, and deterministic project memory.

- **Repository Name**: `che-ai` (formerly `trae-config`).
- **Installation Path**: By default, it runs from `~/.trae` on the user's machine.
- **Multi-Agent Adapters**: `adapters/` (links core logic to Codex, Claude Code, and Cursor).

## 1. Project Architecture (3-Layer Architecture)

Che follows a strict 3-layer architecture. **HARD STOP:** Never duplicate rule bodies across layers. **ALL new features MUST be implemented in compatibility with Codex, Claude Code, Cursor, and Trae.**

- **Layer 1 (User Profiles & Runbooks)**: `domains/` and user-level configs. Used for high-level domain specific instructions (e.g., UX, Product, Engineering).
- **Layer 2 (Framework Rules)**: `CHE_RULES.md` and `CHE_COMMANDS.md`. These files ONLY contain titles and links to Layer 3 skills. They should **not** contain the logic/body of the rule.
- **Layer 3 (Skills)**: `skills/*/SKILL.md`. This is where the actual declarative rules and boundaries of each skill live.

## 2. Execution Logic (Python Core)

**CRITICAL RULE:** Do NOT use Bash, Shell Scripts, or Node.js for new internal executables. **Python is the canonical language for Che's core logic.**

- The core engine lives in `che_core/` (Python package).
- It handles paths resolution, the Level 1/1.5 registries, decision logs (`.jsonl`), and preflight checks.
- **Skills (`.md`) MUST be purely declarative.** If a skill requires complex procedural logic (e.g., parsing a diff, reading multiple files, running external tools), that logic MUST be extracted into a Python script in `che_core/` and invoked via the CLI module (e.g., `python3 -m che_core.ship`).
- There is NO `package.json` and NO Node.js dependency. Keep Che zero-build.
- Python caches (`__pycache__/`) are gitignored and must **never** be committed.

## 3. Workspaces Hierarchy (Path Canonicity)

Che organizes the user's projects into a strict 4-level hierarchy. Do not create `.trae/` folders inside user projects. **Portability between machines is supported via `/che-export` and `/che-import` of durable info (L2 and L3).**

1. **L1 (Workspace Root)**: `~/.che-workspaces/<workspace-slug>/`
2. **L2 (Project Level)**: `<L1>/<repo-slug>/.project/` (Durable info: `architecture.md`, `project_profile.md`, roles)
3. **L3 (Worktree Level)**: `<L2>/../.wt/__<branch-slug>/` (Shared info across sessions in the same branch: `gh_stack/`, `qa/`, `designs/`, `decisions.log.jsonl`)
4. **L4 (Session Level)**: `<L3>/sessions/<CHE_SESSION_ID>/` (Ephemeral info: execution logs, diff context, isolated debugger state)

## 4. Hook Architecture

Hooks (triggered by the IDE before or after tool usage) live in `hooks/`.
- They are written in **Python** (`pretooluse-worktree-binding.py`, `posttooluse-3layer-dedup.py`).
- The `hooks.json` configuration file points to these Python files.

## 5. Development Principles

When modifying this repository, apply the **KISS** (Keep It Simple, Stupid) and **YAGNI** (You Aren't Gonna Need It) principles.
- Minimize dependencies. Use Python's standard library whenever possible.
- Focus on reducing the blast radius of changes.
- Apply Design by Contract (DbC) on core functions (preconditions, postconditions).
- **Worktree Hygiene**: Do not leave temporary scripts, untracked files, or logs in the root. Ephemeral data goes to the Session Level (L4).

## 6. Quality, Security & Contribution Workflow

Che enforces a strict CI and contribution workflow to prevent regressions and security vulnerabilities:
- **CI Pipeline**: GitHub Actions runs `ruff` (Python linting/formatting), `pytest` (unit and security tests), and `markdownlint-cli2`.
- **Skill Security**: Markdown files (`SKILL.md`) are statically analyzed by `tests/test_skill_security.py`. Destructive bash commands (`rm -r`, `curl`, `eval`, etc.) are prohibited. Python blocks inside Markdown must not exceed 15 lines. All complex logic must reside in `che_core`.
- **Secret Scanning**: TruffleHog runs on all PRs and pushes to ensure no secrets or API keys are accidentally committed.
- **Approval Workflow**: Direct pushes to `main` are blocked. All changes must be submitted via PRs and require explicit approval from `@laionazeredo` (enforced via `.github/CODEOWNERS`).
