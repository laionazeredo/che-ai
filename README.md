# Che AI 🧉

**Che** is an IDE-agnostic Agentic Engineering Harness designed to run inside modern AI coding assistants (such as Trae, Codex, Cursor, Claude Code, and OpenCode). 

Instead of treating the AI as just an autocomplete tool, Che acts as a "plugin" that orchestrates the AI to simulate a full Agile team—including a Scrum Master, Software Engineer, QA, UX Designer, and Compliance Officer. It enforces strict Software Development Life Cycle (SDLC) practices, deterministic project memory, and automated quality gates.

## 🚀 Quick Install

To install Che into your local environment (defaults to `~/.trae`), run:

```bash
curl -fsSL https://raw.githubusercontent.com/laionazeredo/che-ai/main/scripts/install-che.sh | bash
```

## 🧠 Core Concepts

Che is built on the philosophy that **Agentic Engineering requires boundaries and memory**. 

1. **Zero-Build Core**: The core logic of Che is written in pure Python (`che_core/`), avoiding heavy Node.js dependencies and compilation steps.
2. **Declarative Skills**: AI behaviors and boundaries are defined in simple, declarative Markdown files (`skills/*/SKILL.md`).
3. **Structured Memory**: Che isolates generated artifacts (design tokens, QA reports, decisions, and execution logs) from your user code. It uses a strict 4-level hierarchy:
   - **L1 (Workspace Root)**: `~/.che-workspaces/<workspace-slug>/`
   - **L2 (Project Level)**: `<L1>/<repo-slug>/.project/` (Durable architecture & product knowledge)
   - **L3 (Worktree Level)**: `<L2>/../.wt/__<branch-slug>/` (Shared info across sessions in the same branch)
   - **L4 (Session Level)**: `<L3>/sessions/<CHE_SESSION_ID>/` (Ephemeral logs & debug context)
4. **Automated Quality Gates**: When you ship code via `/che-ship`, Che automatically enforces Scope Checks, Code Review, Security Compliance, and runs your test suite before opening a Draft PR.

## 🛠 Usage (Slash Commands)

Once installed, Che exposes its capabilities directly inside your AI assistant's chat interface via slash commands. For example:

- `/che-start` — Decomposes a feature request into a task graph and begins implementation.
- `/che-ship` — Runs quality gates, commits, and opens a Pull Request.
- `/che-xray` — Scans a new repository and generates a technical profile (stack, patterns, DB, CI/CD).
- `/che-design` — Orchestrates a complete UX/UI design pipeline (Social Media, Web Features, Design Systems).
- `/che-review` — Performs a strict code review against the default branch.

## 🏗 Contributing & Architecture

If you are an AI agent or developer looking to extend Che, please read **[AGENTS.md](./AGENTS.md)** first. It outlines the strict 3-Layer Architecture, the Python core rule, and how to safely manipulate the file system.

## 🔄 Updating

To fetch the latest version of Che:

```bash
curl -fsSL https://raw.githubusercontent.com/laionazeredo/che-ai/main/scripts/update-che.sh | bash
```
