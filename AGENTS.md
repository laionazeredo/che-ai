# Che AI — Agent Technical Contracts

This document defines the rules and architectural boundaries for **AI coding agents** contributing to or using the **Che** framework. It is the L2 Router for all engineering and architecture contracts inside Che's **3-Layer Rulebook** (Domains → Routers → Skills, topology inspired by [SpecFlow](https://www.specflow.com/)).

**Che's purpose, in one line, for the agents reading this:** Che is the *shared team operating system* that lets an entire product delivery squad (Engineering, Product, UX, QA) run as a coordinated multi-agent system inside **Claude Code** (or any supported IDE). You are one *skill executor* inside that team — your job is to play your position cleanly, not to reinvent the game.

**Start here** → this is the router. Deep rationale, opinions, anti-goals, and trade-offs live in [docs/architecture-and-principles.md](./docs/architecture-and-principles.md). The operational terminal manual lives in [docs/cli-reference.md](./docs/cli-reference.md). Read both before opening a PR against `che_core/` or adding a new skill.

---

## 0. Distribution & Entry Points (September 2026)

> 🔴 **MANDATORY NOTICE for agents and humans — slash commands stay.**
>
> `/che-workspace`, `/che-project`, `/che-spec`, `/che-act`, `/che-ship`, `/che-review`, `/che-prd`, `/che-tasks`, `/che-notes`, `/che-graph` **(built-in) plus community custom skills (examples: `/figma-pixel-check`, `/flockr-*`, `/my-company-*`) and every other in-IDE slash command are kept, maintained and continue to be the RECOMMENDED entry point for agentic / creative work inside Claude Code** (spec writing, implementation, reviews, PR gating — flows that require LLM reasoning).
>
> The `che-ai` / `che` terminal CLI **is NOT a replacement** — it is the **structural administrative sidecar** for team bootstrap, workspace admin, CI wiring, trash-safe removal, bulk listing/exporting, and offline structural operations. A normal team flow is **(1) `che workspace create` (terminal or CI setup) → (2) in-IDE `/che-spec` (inside Claude Code) → (3) `/che-act` → (4) `/che-ship`**. Not one or the other.

Che ships as a **zero-dependency PEP-621 Python package** installable via `pipx`. Two binaries are globally registered on the user's `PATH`:

| Binary | Canonical | Purpose | Entry point |
| :----- | :-------: | :------ | :---------- |
| `che-ai` | ✅ Yes | Branded full name. Use in scripts/docs for disambiguation. | `che_core.cli:main` (argparse) |
| `che` | alias | Short daily-use convenience. Same function, same code. | `che_core.cli:main` (argparse) |

**Installation (agents should never reimplement this; assume already installed. The `scripts/install-che.sh --apply` command runs this as its final step, and also configures the Claude Code global rules adapter automatically):**
```bash
cd ~/.trae                         # Che config repo. Symlinked by Claude Code adapters at ~/.claude-codex/ or ~/.cursor/ if needed.
pipx install -e . --force          # user-isolated venv, ~/.local/bin/ on PATH
which che        # → ~/.local/bin/che
che --help       # 15 structural subcommands: workspace/project/config/task/state/rag/export/import/eject + plumbing
```

> 💻 **Platform Compatibility (installer fail-fast):** `scripts/install-che.sh` runs ONLY on **Linux + macOS POSIX bash/zsh shells**. On Windows PowerShell / CMD, the installer exits with error code 5; users must use **WSL2 Ubuntu 22.04 LTS** and run the installer from inside the Linux userland.

All structural/admin operations (`workspace create`, `project init`, `config` flags, state rebuild, export/import, eject) are implemented first as deterministic Python in `che_core/` and routed through the CLI before any agent skill is allowed to perform them. This is the Che **structural-first principle**: CLI gives you the canonical behaviour; agent skills call the CLI; agent skills **never** reimplement L1–L4 filesystem logic inside Markdown Python blocks. The full CLI contract with flags, exit codes, and examples lives at [docs/cli-reference.md](./docs/cli-reference.md).

---

## 1. Core Architecture (3-Layer Rulebook)

Che follows a strict 3-layer rulebook architecture. **NEVER** duplicate rule bodies across layers. A router layer links; it never repeats.

This 3-layer topology is **directly inspired by [SpecFlow](https://www.specflow.com/) / Cucumber-school BDD**, where:
- **L1 (Domains)**: `domains/` ↔ **SpecFlow Feature Files** (Gherkin, customer-language playbooks). Domain-specific human context (UX, Engineering, Product, etc.). Playbooks and principles live here; skill files reference them via links, not verbatim copy.
- **L2 (Framework)**: `CHE_RULES.md` and `CHE_COMMANDS.md` ↔ **SpecFlow Step Bindings Registry** (`[Binding]` classes in C#). Routers containing **titles and links ONLY**, never rule bodies.
- **L3 (Skills)**: `skills/*/SKILL.md` ↔ **SpecFlow Step Definitions + Hooks**. Declarative rules and task boundaries. Smallest reusable unit of Che behaviour.

Why three layers and why SpecFlow? Short answer plus full trade-off rationale in [docs/architecture-and-principles.md §4](./docs/architecture-and-principles.md#4-3-layer-rule-framework-structure).

---

## 2. Execution Logic (Python-Only, DbC contracts)

**CRITICAL:** Python is the canonical language for Che's core logic. Procedural logic contracts follow [Design by Contract™](https://en.wikipedia.org/wiki/Design_by_contract) (Bertrand Meyer, 1986) — assert preconditions at the argparse boundary, invariants mid-flight, and postconditions before returning JSON.
- Procedural logic must reside in `che_core/`.
- Skills (`.md`) must be declarative. Complex logic (> 15 lines) **MUST** be extracted to Python and invoked via CLI (the `che` / `che-ai` binaries). Do NOT write 80-line Python blocks inside `.md` skills; move it to `che_core/`, expose an argparse subcommand, and call that.
- No `package.json` or Node.js dependencies are allowed for core execution.

---

## 3. Workspaces Hierarchy (Path Canonicity)

Che organizes project data into a 4-level hierarchy. **Do not create `.trae/` folders inside user projects.** Che memory lives outside repositories, inside `~/.che-workspaces/` (the user's home directory), by design.

1.  **L1 (Workspace Root)**: `~/.che-workspaces/workspaces/<workspace-slug>/`
2.  **L2 (Project Level)**: `<L1>/<project-slug>/project/` (Durable info: `architecture.md`, `project_profile.md`, `product_context.md`, `roadmap.md`, `roles/index.md`, `registry.jsonl`; plus shared `_db/` folder).
3.  **L3 (Worktree Level)**: `<L1>/<project-slug>/worktrees/<wt-slug>/` (Shared info: `decisions.log.jsonl`, `qa/`, `designs/`).
4.  **L4 (Session Level)**: `<L3>/sessions/<SESSION_ID>/` (Ephemeral info: logs, isolated state. Exactly one writer per session).

Full diagram + visibility/durability contract + anti-patterns defended against: [docs/architecture-and-principles.md §5](./docs/architecture-and-principles.md#5-4-level-worktree-hierarchy-project-memory-model).

### Agent Guidance — Invoke the CLI, do NOT hardcode paths:
- **L1 Creation**: `che workspace create <name>` → **never** `mkdir` directly.
- **L2 Registration**: `che project init <worktree-path> --workspace <name> --domain <d> --name "<n>" --session-id <sid>` → never write the 7 template files by hand.
- **Config flags**: `che config <session_id> <worktree_root> --lang-chat pt-BR --lang-docs pt-BR` → never edit `registry.jsonl` directly.
- **L3 Execution**: `che-spec` and `che-act` **REQUIRE** `--project` and `--worktree` parameters, never infer them from CWD alone.
- **Destructive ops**: Always dry-run first. `che workspace remove <name> --dry-run` then `--no-dry-run --confirm`. Outputs are always trash + restore, never `rm -rf`. See _Trash-safe principle_ in [docs/architecture-and-principles.md §7](./docs/architecture-and-principles.md#7-the-blast-radius--trash-safe-principle).

---

## 4. Development Principles

Based on [The Pragmatic Programmer](https://pragprog.com/the-pragmatic-programmer/) (Hunt & Thomas, 1999) — orthogonality, tracer bullets, DRY, good-enough software, plain-text ground truth. Spec writing is [Specification by Example](https://en.wikipedia.org/wiki/Specification_by_example) (Adzic, 2011): `/che-spec` always returns a spec led by concrete customer examples, never a TODO list.

- **KISS & YAGNI (Pragmatic orthogonality)**: Minimize dependencies and avoid over-engineering. `pyproject.toml` declares `dependencies = []` on purpose — argparse + stdlib sqlite3 + stdlib subprocess is the feature set. Add a dep only when you can prove stdlib is genuinely insufficient.
- **Design by Contract (DbC)**: Apply [Design by Contract™](https://en.wikipedia.org/wiki/Design_by_contract) preconditions and postconditions on core public `che_core/*` functions via assertions / docstring contracts / argparse schemas. Fail fast at the boundary instead of corrupting state 4 steps later.
- **Storytelling Commits**: Use conventional commits with a **CDJ body** (Context → Decision → Justification, one paragraph each). Two lines is a style nit; three paragraphs is the contract.
- **Worktree Hygiene**: Never leave temporary files, logs, screenshots, caches, or generated `.md` spec drafts at the **root of a user repository**. Ephemeral data belongs in L4 (`sessions/<id>/`); shared evidence belongs in L3 (`qa/`, `designs/`). Cross this line once and the team loses trust permanently.
- **Language Policy**: Code and internal docs in strict English. Public UI strings default to English with British spelling. Localisation of user dialogue happens exclusively via the four `--lang-*` flags on `che config`, never via 800 scattered copy-pastes. Contract: [docs/architecture-and-principles.md §9](./docs/architecture-and-principles.md#9-language-policy--dual-register-documentation).
- **Blast Radius**: Keep changes focused. Large refactors (> 5 files or spanning package boundaries) require an explicit ADR row written to the worktree's `decisions.log.jsonl` **before** the code, via `che decision_append <wt> --kind ARCH --title "…" --body-file path.md --tags …`.

---

## 5. Quality & Security

- **CI Pipeline**: All changes must pass `ruff check .` (lint/format) and `python3 -m pytest tests/ -q` (unit tests). CI = 0 ruff errors + 39 tests passing is the bar.
- **PII & Secrets**: **NEVER** log or persist raw emails, JWTs, or API keys. Use `NOTIFICATION_PII_HASH_SECRET` for correlation when you need to link a log entry to a recipient without leaking the address.
- **Skill Security**: Markdown files are analyzed for destructive bash commands. Python blocks in Markdown must not exceed 15 lines. If your agent wrote 20 lines of Python inside a `SKILL.md`, that is your signal to move it into `che_core/` as a proper CLI subcommand.
- **Planning-artifact hygiene**: Che deliberately ships a fail-closed gitignore blacklist (see root `.gitignore`, section **CHE PLANNING ARTIFACTS — NEVER COMMIT**). If a spec file, decision log or task graph ends up in a user repo's `git status`, treat that as a bug in `install-che.sh` or the skill that wrote it — not as user error.
