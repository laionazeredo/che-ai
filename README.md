# Che AI

**Che** is an **opinionated, pragmatic, end-to-end Agentic Engineering Harness built to scale entire product delivery teams** — from early creative discovery and spec writing, through code implementation and quality gates, all the way to PR gating and ship. It orchestrates AI coding agents inside **Claude Code**, **Codex**, **Cursor**, **Trae** and other code editors, giving 3–30 person teams a *single shared operating system* for software and creative product delivery.

Instead of each engineer keeping their own prompt library and each designer re-explaining the brand from scratch, Che installs a **shared team brain** with a 3-Layer Rulebook (Domains → Routers → Skills, inspired by [SpecFlow](https://www.specflow.com/) and a 4-Level Memory Model that survives IDE restarts, agent turnovers, and onboarding of new team members.

The stack of ideas behind Che comes from four battle-tested methodologies we do not pretend to have invented:

1. **[The Pragmatic Programmer](https://pragprog.com/the-pragmatic-programmer/) (Hunt & Thomas, 1999)** — Orthogonality, tracer bullets, DRY, good-enough software, plain text, and the Single-Source-of-Truth ethic. We call our opinions "pragmatic" specifically to inherit *this* body of work — not as a buzzword.
2. **[Design by Contract™](https://en.wikipedia.org/wiki/Design_by_contract) (Bertrand Meyer, 1986)** — Preconditions, postconditions, class invariants, and fail-fast at boundaries. Every public `che_core/*` function and every `/che-ship` gate is a DbC contract: scope → review → compliance → QA, four executable gates, zero opinions.
3. **[Specification by Example / SBE](https://en.wikipedia.org/wiki/Specification_by_example) (Gojko Adzic, 2011)** — Specs are written as concrete examples the *customer* understands, not as abstract imperative checklists. `/che-spec` always returns an example-led spec, not a bullet list of TODOs. If you can't write the example, you don't understand the problem well enough to start.
4. **[SpecFlow](https://specflow.org/) / Cucumber-school BDD** — The Che **3-Layer Rulebook** is directly inspired by SpecFlow's 15-year-old enterprise topology: *L1 Domains playbooks* = feature files (customer language), *L2 Router files (CHE_RULES / CHE_COMMANDS)* = step-binding registration (titles + links only, no bodies), *L3 Skills (SKILL.md)* = reusable step definitions & hooks. The terminology is ours, the topology is theirs.

The result is a harness that:
- **Scales a *whole team*, not just one agent.** Engineering + Product + UX share a single domain playbook layer. An agent writing a checkout screen and an agent writing a Figma screen both read the same product context and brand rules, without copy-pasting.
- **Never puts `.trae/` or `.che/` folders inside your repositories.** All project memory lives in a canonical `~/.che-workspaces` user home hierarchy, keeping repo roots pristine (Pragmatic Programmer orthogonality — *team process state* does not live inside the *shipped artifact*).
- **Never deletes anything permanently.** Every `remove` is a **move to trash** with a printed one-line restore command (Design by Contract postcondition: "after `remove X`, the state of X is recoverable in one deterministic command"). Hard-delete commands do not exist, and will not be added.
- **Runs structural/admin operations deterministically as a terminal CLI.** Project onboarding, workspace creation, session config, task listing, state indexing, export/import portability, and safe eject are exposed as a zero-dependency stdlib Python CLI (`che-ai` / `che`), installed once and callable from any shell or CI. This is a feature for predictability and cost discipline, not the product's headline.
- **Single-Source-of-Truth (SSoT), everywhere.** Every rule, score, playbook, template lives in exactly one canonical file. If you see the same body twice anywhere in the repo — that is a bug, report it. (DRY, The Pragmatic Programmer ch. 2.)

> ⚠️ **Slash commands inside the IDE CONTINUE TO EXIST. The terminal CLI does NOT replace them.**
>
> `/che-workspace`, `/che-project`, `/che-spec`, `/che-act`, `/che-ship`, `/che-review`, `/che-prd`, `/che-tasks`, `/che-notes`, `/che-graph` are the **built-in** command surface. Your team probably also installs community skills such as `/figma-pixel-check`, `/flockr-*` (the Flockr platform custom skill pack) or `/my-company-*` (your private team skill pack). All of them **are kept, maintained, and remain the RECOMMENDED entry point for agentic / creative work** inside **Claude Code** (spec authoring, design exploration, implementation loops, CR fixes, PR gating — any flow that benefits from LLM reasoning).
>
> The `che-ai` / `che` **terminal CLI is the administrative and structural sidecar** for team bootstrap, workspace admin, CI integration, trash-safe deletion, offline state work, and bulk listing/exporting. You use the two together: first `che workspace create` (terminal or CI), then `/che-spec` inside **Claude Code**, then `/che-act`, then `/che-ship` — not one or the other.

***

## 🧭 Where to Start

| Path | Audience | Content |
| :--- | :------- | :------ |
| **[AGENTS.md](./AGENTS.md)** | AI coding agents + core contributors | Technical contracts, 3-layer rulebook, 4-level memory, Python-only core rule. |
| **[docs/cli-reference.md](./docs/cli-reference.md)** | End users, DevOps, terminal-first engineers | Full `che-ai` / `che` binary reference, 15 commands, exit codes, troubleshooting. |
| **[docs/architecture-and-principles.md](./docs/architecture-and-principles.md)** | Architects, curious users, future maintainers | The **why** of Che: positioning, 8 opinionated stances, 5 anti-goals, methodology citations (Pragmatic, DbC, SBE, SpecFlow). |
| **[CHE_RULES.md](./CHE_RULES.md)** | Everyone (3-Layer router, L2 SpecFlow-style) | Titles + links only — routes to all domain playbooks and skills. |
| **[CHE_COMMANDS.md](./CHE_COMMANDS.md)** | Everyone (3-Layer router, L2 SpecFlow-style) | Titles + links only — routes to the full command surface (spec/act/ship/fix). |

***

## 🚀 Installation (3 Paths)

> 💻 **Platform Compatibility**
>
> | OS | Support |
> | :--- | :------ |
> | **Linux** (any distro, bash/zsh, python3 ≥ 3.9) | ✅ Fully supported (primary target) |
> | **macOS** (Monterey / 12+, bash/zsh via Homebrew) | ✅ Fully supported |
> | **Windows (PowerShell / CMD)** | ❌ Native shell NOT supported. Install **WSL2** (Ubuntu 22.04 LTS recommended) and run the installer from inside the WSL Ubuntu shell. See §1.0 in [docs/cli-reference.md](./docs/cli-reference.md) for WSL2 walkthrough. |

### 1. Quick Install Script (recommended for end users)

Installs or updates Che at `~/.trae` (Claude Code's default config repo path for Che), injects the planning-artifacts `.gitignore` snippet into every repo it touches, **and installs the `che-ai` / `che` CLI binaries globally via `pipx`** (fallback `pip install --user` if pipx is missing, with a warning):

```bash
curl -fsSL https://raw.githubusercontent.com/laionazeredo/che-ai/main/scripts/install-che.sh | bash -s -- --apply

# To skip the CLI install step (IDE only):
# curl -fsSL ... | bash -s -- --apply --no-cli
```

### 2. Install the Global CLI (recommended for terminal-first users)

Che ships as a **zero-dependency PEP-621 Python package**. The two canonical binaries are:
- **`che-ai`** — long/full name (brand)
- **`che`** — short alias for daily use

Use **pipx** (isolated user-venv, never breaks system Python):

```bash
cd ~/.trae                                    # Che config repo. Symlinked by Claude Code adapters at ~/.claude-codex/ or ~/.cursor/ if needed.
pipx install -e . --force

# ✅ Confirm install
which che-ai          # → /home/you/.local/bin/che-ai
which che             # → /home/you/.local/bin/che
che --help            # 15 subcommands, 0 tokens, 0 network
```

> **Troubleshooting:** If `che` shows "command not found" after pipx: `export PATH="$HOME/.local/bin:$PATH" ; pipx ensurepath`. See _§11 Troubleshooting_ in [docs/cli-reference.md](./docs/cli-reference.md).

### 3. Verification

```bash
che --help                                            # CLI surface
che workspace list                                    # List L1 workspaces
che config --help                                     # Session flags (LANG_CHAT etc)
python3 -m pytest tests/ -q                           # 39 unit tests (core harness)
```

***

## ⚡ 60-second Quickstart (no tokens, no agents, no API keys)

```bash
# 1) Create an L1 workspace. Repeat for each separate tenant/concern.
che workspace create acme

# 2) Bootstrap L2 project inside an existing git repo.
#    Writes 7 canonical files to ~/.che-workspaces/workspaces/acme/<slug>/
cd ~/code/my-company/web-app                # any valid git repo, any branch
che project init . \
    --workspace acme \
    --domain product \
    --name "My Company Web App" \
    --session-id onboarding-001

# 3) Configure session language flags once, not in 800 prompts.
che config onboarding-001 "$PWD" \
    --lang-chat pt-BR \
    --lang-docs pt-BR \
    --lang-report en

# 4) Inspect what was created (zero tokens burned).
che workspace list | jq
che project list --workspace acme | jq
che registry_lookup onboarding-001 | jq '.flags'
```

Then (and **only then** — after the whole structure is in place) you invoke agent work via the in-IDE slash commands inside **Claude Code**:

1. **Plan** → `/che-spec` generates a SBE (Specification-by-Example) execution spec.
2. **Execute** → `/che-act` runs the multi-domain implementation loop.
3. **Deliver** → `/che-ship` passes the four executable DbC gates (scope → review → compliance → QA) then opens a Draft PR.

The full command reference, including `task`, `state` (SQLite FTS5), `rag`, `export`/`import` portability and safe `eject`, is in [docs/cli-reference.md](./docs/cli-reference.md).

***

## 🏗️ Core Architecture (Executive Summary)

Two complementary hierarchies, one **3-layer** for the rulebook, one **4-level** for project memory.

### 3-Layer Rulebook (what ships inside `~/.trae`) — topology inspired by SpecFlow / Cucumber BDD

1. **L1 (Domains)** → SpecFlow *Feature Files (Gherkin)*: Human context, product language — playbooks in `domains/engineering/`, `domains/product/`, `domains/ux/`. What the customer asked for, in their words.
2. **L2 (Routers)** → SpecFlow *step bindings registry (links only)*: Link lists in `CHE_RULES.md` and `CHE_COMMANDS.md`. **Titles and links ONLY.** Rule bodies never live here (just like `[Binding]` C# classes in SpecFlow are a registration table, not the prose).
3. **L3 (Skills)** → SpecFlow *Step Definitions + Hooks*: Declarative rule bodies in `skills/<id>/SKILL.md`. Smallest reusable unit of behaviour.

> Why SpecFlow instead of "just a folder structure with docs"? Because this exact topology has shipped enterprise BDD for 15+ years. We're not inventing a new rulebook layout — we're reusing one that already survives 500-person release trains. See [docs/architecture-and-principles.md §4](./docs/architecture-and-principles.md#4-3-layer-rule-framework-structure) for full rationale.

### 4-Level Project Memory (what lives inside `~/.che-workspaces`)

1. **L1 (Workspace)** — `~/.che-workspaces/workspaces/<slug>/` — one tenant (My Company / Acme / Big Client), many projects. Months → years.
2. **L2 (Project)** — `<L1>/<project>/project/` — durable Markdown: `architecture.md`, `project_profile.md`, `product_context.md`, `roadmap.md`, `roles/index.md`, plus the shared `_db/` folder. Lifetime of the product.
3. **L3 (Worktree Shared)** — `<L2>/worktrees/<branch-slug>/` — `decisions.log.jsonl`, `qa/`, `designs/`. Shared across sessions on the same git branch. Lifetime of the branch.
4. **L4 (Session)** — `<L3>/sessions/<SESSION_ID>/` — ephemeral logs, single writer, isolated. Hours → days. (Pragmatic Programmer §7: "localize state with short lifetime.")

The full rationale, 8 opinionated stances, 5 anti-goals and methodology references live in [docs/architecture-and-principles.md](./docs/architecture-and-principles.md). Do **not** propose a core change without having read it first — the document explicitly lists the trade-offs we deliberately refuse to revisit.

***

## 🛠️ Command Surface at a Glance

| Command / Group        | Layer | Runs in… | Purpose |
| :--------------------- | :---- | :-------- | :------ |
| `che workspace {create,list,remove,restore,trash-list}` | L1 | Terminal CLI | L1 workspace management (trash-safe remove — DbC postcondition: recoverable). |
| `che project {create,init,add,list,remove,restore}` | L2 | Terminal CLI | L2 project bootstrap + 7 canonical templates. |
| `che config <sid> <wt>` | L3/L4 | Terminal CLI | Session flags: `--lang-chat` / `--lang-docs` / `--pt-check` etc. |
| `/che-spec` (IDE)      | L2→L3 | Agent slash-command (Claude Code) | SBE (Specification-by-Example) specs from PRD / ticket / description. |
| `/che-act` (IDE)       | L3 | Agent slash-command (Claude Code) | Multi-domain parallel implementation loop. |
| `/che-ship` (IDE)      | Delivery | Agent slash-command (Claude Code) + ✅ CLI gates | Four DbC precondition gates (scope → review → compliance → QA), then Draft PR. |
| `che task {list,show,resume,set-status,graph-summary}` | L3 | Terminal CLI | Task graph read-only inspection. |
| `che state {rebuild-index,query,search,sanitize}` | L3 | Terminal CLI | SQLite FTS5 append-only memory. |
| `che rag {build,search,list,prune}` | L3 | Terminal CLI | Local sqlite-vec hybrid search. |
| `che export` / `che import` | L2 | Terminal CLI | Portable project `.tar.gz` — no `.git`, no code, only memory. |
| `che eject {plan,execute,restore}` | All | Terminal CLI | Two-gated safe uninstall. Always trash, never rm. |

> **Full command reference with examples, exit codes and troubleshooting → [docs/cli-reference.md](./docs/cli-reference.md).**

***

## 🔍 Troubleshooting

**1. `gh` command not found or not authenticated.**
Che relies on the GitHub CLI for PR operations. Install it, then run `gh auth login`.

**2. `python3` missing or wrong version.**
Che requires Python ≥ 3.9. On Debian/Ubuntu: `sudo apt install python3-full pipx`.

**3. Decision logs, task graphs or `.md` specs appear in `git status` inside my repo.**
You're missing the Che planning-artifacts blacklist snippet. Re-run the installer to re-inject it idempotently:
```bash
curl -fsSL https://raw.githubusercontent.com/laionazeredo/che-ai/main/scripts/install-che.sh | bash -s -- --apply
```

**4. `che: command not found` after successful `pipx install -e .`.**
Your `PATH` lacks `~/.local/bin`. Run `pipx ensurepath`, then open a new shell.

***

## 🏗️ Contributing

1. **Start** by reading [AGENTS.md](./AGENTS.md) (the agent-facing technical contracts, short) then [docs/architecture-and-principles.md](./docs/architecture-and-principles.md) (the rationale, long). Proposals that don't ground themselves in Pragmatic / DbC / SBE / SpecFlow canon will be asked to justify the novelty.
2. Core logic (≥ 15 lines) lives in `che_core/` as Python ≥ 3.9 stdlib code. Skills live in `skills/*/SKILL.md` as **declarative Markdown**. Python code blocks inside skills must not exceed 15 lines — refactor the rest into the CLI.
3. CI: `ruff check .` (lint/format) and `python3 -m pytest tests/ -q` (unit). Both must pass. Public functions ship with DbC pre/post-condition docstrings or assertions.
4. Duplicating a rule body anywhere instead of linking? That is a blocking review finding. SSoT (DRY from The Pragmatic Programmer) is not a style nit — it is the whole point.
