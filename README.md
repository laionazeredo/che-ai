# Che AI ☭

**Che** is an IDE-agnostic Agentic Engineering Harness. It orchestrates AI agents (Trae, Codex, Cursor, Claude Code) to simulate a full Agile team, enforcing rigorous SDLC practices and deterministic project memory.

---

## 🚀 Installation Guide

Che can be installed from any directory using the remote install script.

### 1. Quick Install (Recommended)

Run the following command to install or update Che (defaults to `~/.trae`):

```bash
curl -fsSL https://raw.githubusercontent.com/laionazeredo/che-ai/main/scripts/install-che.sh | bash -s -- --apply
```

### 2. Multi-Agent Setup

The installer will prompt you to select which AI agents to configure. You can select multiple:
- **Codex** (OpenAI), **Claude Code** (Anthropic), **Cursor**, and **Trae** (Native).

### 3. Verification

```bash
python3 -m che_core.cli --help  # Check CLI
ls -la ~/.trae/README.md        # Confirm path
```

---

## 🏗️ Core Architecture

Che uses a **3-Layer Architecture** to ensure clean separation of concerns:

1.  **L1 (Domains)**: High-level instructions (Engineering, UX, Product) in `domains/`.
2.  **L2 (Routers)**: Link lists in `CHE_RULES.md` and `CHE_COMMANDS.md`.
3.  **L3 (Skills)**: Declarative rules and task logic in `skills/*/SKILL.md`.

### 🧠 Structured Memory (L1-L4)

Project data is isolated into a 4-level hierarchy:
- **L1 (Workspace)**: Global container for related projects.
- **L2 (Project)**: Durable strategic memory (Intent, Roadmap).
- **L3 (Worktree)**: Tactical shared assets (Decisions, Task Graphs, QA).
- **L4 (Session)**: Ephemeral execution logs.

---

## 🛠️ Key Commands & Workflow

### Standard Operation
1.  **Setup**: Register your project with `che-workspace create` and `che-project create`.
2.  **Plan**: Generate a behavior-driven spec with `/che-spec`.
3.  **Execute**: Start the implementation loop with `/che-act`.
4.  **Deliver**: Run `/che-ship` to pass quality gates and open a PR.

### Full Command Reference
| Command | Category | Function |
| :--- | :--- | :--- |
| `/che-spec` | Strategic | Generate execution specifications (SbE). |
| `/che-act` | Execution | Start the implementation loop (Implement → Test → Ship). |
| `/che-ship` | Delivery | Automated quality gates, commits, and Draft PRs. |
| `/che-fix` | Maintenance | Scientific debugging loop for bug fixing. |
| `/che-ci-fix` | Maintenance | Diagnose and fix failing CI runs. |
| `/che-workspace` | Management | Create, list, or remove L1 workspaces. |
| `/che-project` | Management | Register, list, or remove L2 projects. |
| `/che-design` | UI/UX | Professional designs, social media, and design systems. |
| `/che-rag` | Data | Hybrid search and retrieval-augmented generation. |
| `/che-export` | Portability | Export strategic project memory to an archive. |

---

## 🔍 Troubleshooting

**1. `gh` command not found or not authenticated**
Che relies on the GitHub CLI. Install it and run `gh auth login`.

**2. `python3` missing or wrong version**
Ensure Python 3.10+ is installed and available in your PATH.

**3. Decision logs appearing in Git**
Ensure the Che snippet is present in your `.gitignore`. Run the installer again with `--apply` to re-inject if missing.

---

## 🏗 Contributing

Read **[AGENTS.md](./AGENTS.md)** for detailed technical contracts and architecture guidelines.
