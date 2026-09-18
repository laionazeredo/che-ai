# Che AI

**Che** is an **opinionated, pragmatic, end-to-end Agentic Engineering Harness built to scale entire product delivery teams** — from early creative discovery and spec writing, through code implementation and quality gates, all the way to PR gating and ship. It orchestrates AI coding agents inside **Claude Code**, **Codex**, **Cursor**, **Trae** and other code editors, giving 3–30 person teams a *single shared operating system* for software and creative product delivery.

Instead of each engineer keeping their own prompt library and each designer re-explaining the brand from scratch, Che installs a **shared team brain** with a 3-Layer Rulebook (Domains → Routers → Skills, inspired by [SpecFlow](https://www.specflow.com/) and a project → worktree memory model that survives IDE restarts, agent turnovers, and onboarding of new team members.

The stack of ideas behind Che comes from four battle-tested methodologies we do not pretend to have invented:

1. **[The Pragmatic Programmer](https://pragprog.com/the-pragmatic-programmer/) (Hunt & Thomas, 1999)** — Orthogonality, tracer bullets, DRY, good-enough software, plain text, and the Single-Source-of-Truth ethic. We call our opinions "pragmatic" specifically to inherit *this* body of work — not as a buzzword.
2. **[Design by Contract™](https://en.wikipedia.org/wiki/Design_by_contract) (Bertrand Meyer, 1986)** — Preconditions, postconditions, class invariants, and fail-fast at boundaries. Every public `che_core/*` function and every `/che-ship` gate is a DbC contract: scope → review → compliance → QA, four executable gates, zero opinions.
3. **[Specification by Example / SBE](https://en.wikipedia.org/wiki/Specification_by_example) (Gojko Adzic, 2011)** — Specs are written as concrete examples the *customer* understands, not as abstract imperative checklists. `/che-spec` always returns an example-led spec, not a bullet list of TODOs. If you can't write the example, you don't understand the problem well enough to start.
4. **[SpecFlow](https://www.specflow.com/) / Cucumber-school BDD** — The Che **3-Layer Rulebook** is directly inspired by SpecFlow's 15-year-old enterprise topology: *L1 Domains playbooks* = feature files (customer language), *L2 Router files (CHE_RULES / CHE_COMMANDS)* = step-binding registration (titles + links only, no bodies), *L3 Skills (SKILL.md)* = reusable step definitions & hooks. The terminology is ours, the topology is theirs.

The result is a harness that:
- **Scales a *whole team*, not just one agent.** Engineering + Product + UX share a single domain playbook layer. An agent writing a checkout screen and an agent writing a Figma screen both read the same product context and brand rules, without copy-pasting.
- **Never puts planning / state / memory folders inside your repositories.** Architecture is **four orthogonal layers**, strictly separated per Claude Code's official memory/settings docs:
  1. **L1 — Shared team brain (Che-managed, durable):** `~/.che-workspaces/` → specs, decisions, scopes, QA reports, design exports, worktree state. **Always outside user git repos.**
  2. **L2 — IDE User-scope Adapter (Claude Code official, env var `CLAUDE_CONFIG_DIR` default `~/.claude/`):** Che installs **five non-destructive injection points** here per official docs: (a) user `CLAUDE.md` symlink, (b) `skills/<slug>/` symlinks (slash commands, engineering contracts), (c) **NEW `rules/che-domains/*.md` + `che-user/*.md`** symlinks (domain playbooks loaded for every project, path-scopable), (d) legacy `commands/*.md` symlinks, and (e) **deep-merge appended hooks** in `settings.json` (PreToolUse/PostToolUse, never overwrite user plugins/theme/their own hooks).
  3. **L3 — IDE Project-scope Adapter (per user repo):** `./CLAUDE.md` or `./.claude/*`. Che does **not** touch this layer by default (team-managed via source control).
  4. **L4 — Source-of-Truth Rule Package Checkout (pipx feed, IDE-agnostic):** The Che package root directory — the folder containing `pyproject.toml`, `domains/`, `skills/` and `che_core/` from where `pipx install -e .` was run, and where the IDE adapter installers (`adapters/*/install.sh`) live. By default the quick installer clones it into `~/.che-ai/` for convenience, but it can live anywhere on disk. *This* folder is the single source of truth that feeds all symlinks of the L2 IDE adapter layer; Claude Code (or any other supported IDE) **never reads L4 directly** — it only ever sees the adapter symlinks in L2. (Pragmatic Programmer orthogonality: keep the *agent source package* and the *running IDE wiring* in separate layers so either can move without breaking the other).
  (Pragmatic Programmer orthogonality: *team process state* does not live inside the *shipped artifact*; *adapter IDE wiring* does not pollute *rule package source*).
- **Never deletes anything permanently.** Every `remove` is a **move to trash** with a printed one-line restore command (Design by Contract postcondition: "after `remove X`, the state of X is recoverable in one deterministic command"). Hard-delete commands do not exist, and will not be added.
- **Runs structural/admin operations deterministically as a terminal CLI.** Project onboarding, worktree binding, session config, task listing, state indexing, export/import portability, and safe eject are exposed as a stdlib Python CLI (`che-ai` / `che`), installed once and callable from any shell or CI. This is a feature for predictability and cost discipline, not the product's headline.
- **Single-Source-of-Truth (SSoT), everywhere.** Every rule, score, playbook, template lives in exactly one canonical file. If you see the same body twice anywhere in the repo — that is a bug, report it. (DRY, The Pragmatic Programmer ch. 2.)

***

## 🧭 Where to Start

| Path | Audience | Content |
| :--- | :------- | :------ |
| **[AGENTS.md](./AGENTS.md)** | AI coding agents + core contributors | Technical contracts, 3-layer rulebook, project → worktree memory, Python-only core rule. |
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

Installs or updates the Che source-of-truth checkout in `~/.che-ai` (or `$CHE_HOME` / `$HARNESS_HOME` if set), symlinks its skills, rules, commands and hooks into every supported IDE's adapter home, injects the planning-artifacts `.gitignore` snippet into every repo it touches, **and installs the `che-ai` / `che` CLI binaries globally via `pipx`** (fallback `pip install --user` if pipx is missing, with a warning):

```bash
curl -fsSL https://raw.githubusercontent.com/laionazeredo/che-ai/main/scripts/install-che.sh | bash -s -- --apply

# To skip the CLI install step (IDE only):
# curl -fsSL ... | bash -s -- --apply --no-cli
```

### 2. Install the Global CLI (recommended for terminal-first users)

Che ships as a **PEP-621 Python package whose only libraries are two, for one command**. The two canonical binaries are:
- **`che-ai`** — long/full name (brand)
- **`che`** — short alias for daily use

Use **pipx** (isolated user-venv, never breaks system Python):

```bash
# The source-of-truth Che package checkout lives here (install-che.sh Step 1
# already clones it for you in the quick install path). pipx needs to run
# from this folder to find pyproject.toml. setup-adapters.sh (ran auto-
# matically at the installer's end) then links skills/commands/rules into
# Claude Code's real adapter home at ~/.claude/.
cd ~/.che-ai
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
che project list                                      # List flat projects
che config --help                                     # Session flags (LANG_CHAT etc)
python3 -m pytest tests/ -q                           # 114 unit tests (core harness)
```

### 4. Keep it up to date — `che update`

One command, no flags, no dry-run gate. It fast-forwards the checkout to the remote's default
branch, and reinstalls the CLI when (and only when) `pyproject.toml` changed — the one gap a plain
`git pull` cannot close, because Che installs editable:

```bash
che update                 # aliases: che self-update, che upgrade
che update --check         # what an update would bring; changes nothing
```

It refuses, naming the remedy and changing nothing, if you have uncommitted tracked files, are on a
branch other than the default, or hold commits the remote lacks. Already being current is success.
Skills, rules and hooks are symlinked into the checkout, so they go live with the same command.
A zip/manual install (no `.git`) is pointed at `scripts/self-update-che.sh`. See §1.4 of
[docs/cli-reference.md](./docs/cli-reference.md).

***

## ⚡ 60-second Quickstart (no tokens, no agents, no API keys)

```bash
# 1) Create a project for your repo. Repeat for each product you track.
che project init ~/code/my-company/web-app --slug web-app

# 2) Bind the checkout to that project. Idempotent — re-running reuses
#    ~/.che-workspaces/<slug>/worktrees/<name>/ instead of duplicating it.
che worktree add ~/code/my-company/web-app --project web-app --name main

# 3) Configure session language flags once, not in 800 prompts.
che config onboarding-001 "$PWD" \
    --lang-chat pt-BR \
    --lang-docs pt-BR \
    --lang-report en

# 4) Inspect what was created (zero tokens burned).
che project list | jq
che worktree list --project web-app | jq
che registry_lookup onboarding-001 | jq '.flags'
```

Then (and **only then** — after the whole structure is in place) you invoke agent work via the in-IDE slash commands inside **Claude Code**. The happy path for a project that is already onboarded:

1. **Onboard** → `/che-xray` (automatic scan of the code) + `/che-onboarding` (human product context). Once per project, and the gate before the first spec.
2. **Plan** → `/che-spec` generates a SBE (Specification-by-Example) execution spec.
3. **Execute** → `/che-act` runs the multi-domain implementation loop.
4. **Deliver** → `/che-ship` passes the four executable DbC gates (scope → review → compliance → QA) then opens a Draft PR.

The full command reference, including `task`, `state` (SQLite FTS5), `rag`, `export`/`import` portability and safe `eject`, is in [docs/cli-reference.md](./docs/cli-reference.md).

***

## 🧭 Which Scenario Am I In?

The **terminal** sets the structure up once (`che project init` + `che worktree add`, above).
Everything after that is a `/che-*` slash command inside your IDE, and it follows the five phases of
the agentic SDLC (`engineering-contracts` Rule 15):

| Phase | Artifact | Command |
| :---- | :------- | :------ |
| 1 · Intent | `intent.md` | `/che-architect` (step 1) or `/che-onboarding` |
| 2 · Roadmap | `roadmap.md` | `/che-architect` (step 2) |
| 3 · Tasks | `specs/<slug>/<ts>-spec.md` | `/che-spec`, then `/che-plan` for tickets |
| 4 · Execute | task graph + code | `/che-act` (or `/che-parallel` to force fan-out) |
| 5 · Refine | Draft PR + lessons | `/che-ship` |

**Which entry you use depends on where you are right now**, not on the phase list:

| You are… | Run |
| :------- | :-- |
| Starting a project from zero, with an idea and no code | `/che-architect` then `/che-onboarding` |
| Adopting an existing repo Che has never seen | `/che-xray` then `/che-onboarding` |
| Ready to build one specific thing | `/che-spec` (or `/che-act`, which invokes it for you) |
| Implementing something that already has an Approved SPEC | `/che-act` |
| Needing a design, a design system or a logo | `/che-design` (or `/che-figma`) |
| Chasing a bug rather than building a feature | `/che-fix` |
| Reacting to a PR that is already open | `/che-diff`, `/che-review`, `/che-pr-comments`, `/che-ci-fix` |

### A. Starting from zero — an idea, no code yet

Yes, `/che-onboarding` is part of it — but not first, and not alone. Phase 1 and 2 come before there
is anything to specify:

```bash
che project init ~/code/acme/api --slug acme-api
che worktree add ~/code/acme/api --project acme-api --name main
```

```text
/che-architect      # idea → intent.md, roadmap.md, stack, C4 diagrams, ERD, first ADRs
/che-onboarding     # the human half: product_context.md, roadmap.md, manual architecture.md
```

`/che-architect` is the one that turns a business idea into a technical blueprint, iteratively, and
it declares itself for exactly this case ("Before starting a new repository"). `/che-onboarding`
then captures what no scan can infer: pitch, personas, hard invariants, compliance risks, auth
roles. From there you are on the normal feature loop (see C).

`/che-xray` is deliberately absent here: it reads *code*, so on an empty repository it has nothing
to read. Run it once the first slice has landed — it is idempotent, and re-running it preserves any
section you have edited by hand.

### B. Adopting an existing repo

```bash
che project init ~/code/acme/legacy --slug acme-legacy
che worktree add ~/code/acme/legacy --project acme-legacy --name main
```

```text
/che-xray           # automatic: stack, monorepo shape, conventions, tests, CI, DB — 12 sections
/che-onboarding     # human: product context, roadmap, manual architecture
/che-archeology     # optional: reconstruct intent + roadmap from git history and merged PRs
```

The order is not decoration. `/che-xray` is the automatic first pass (the skill that owns the
human half says to run it after), and `/che-onboarding` is the **mandatory gate before the first
`/che-spec`** in any project that has never been through it — Che reads `product_context.md` and
`architecture.md` before writing a spec. `/che-archeology` is for repos with real history: it
clusters commits and merged PRs into phases so the roadmap you inherit matches what the team
actually built.

### C. Specifying a feature

`/che-spec` takes four input sources and always ends with an approval gate:

```text
/che-spec input=desc slug=refund-flow "Refunds for cancelled orders"
/che-spec input=ticket https://linear.app/acme/issue/ACME-123 slug=refund-flow
/che-spec input=prd-flockr docs/prd/payments/refunds.md slug=refund-flow
/che-spec input=existing slug=refund-flow
```

It answers with the two lines everything downstream parses:

```text
SPEC_PATH=/abs/path/to/specs/refund-flow/20260918-spec.md
SPEC_STATUS=Approved
```

Only `Approved` unlocks execution. Optionally push the plan into your tracker first — `/che-plan`
turns an Approved SPEC into a Linear / ClickUp / Jira Epic with one sub-task per vertical slice and
BDD acceptance criteria.

### D. Implementing something that already has a SPEC

```text
/che-act
```

`/che-act` runs its SPEC gate before scope capture: it globs the worktree's specs, finds the
Approved one and proceeds. If there is none, it invokes `/che-spec` itself with whatever arguments
you passed it — so `/che-act input=ticket <url>` is a valid one-liner when you want to go straight
from ticket to code.

```text
/che-act --slug=refund-flow input=ticket https://linear.app/acme/issue/ACME-123
/che-parallel --max-parallel=4     # tasks are independent (disjoint files) — force fan-out
/che-status                        # where the task graph is (also /che-decisions, /che-summary)
/che-skip qa T3 reason:"..."       # override a gate; logged, user-approved, never silent
/che-abort                         # stop the session; nothing is deleted
```

When the work is done:

```text
/che-ship
```

`/che-ship` is not a git wrapper: it runs four executable gates in a fixed order *before* touching
git (scope → review → compliance → QA), then makes atomic conventional commits, pushes, and opens a
**Draft PR** assigned to you.

### E. Needing design

```text
/che-design B --palette "#6D28D9,#F59E0B,#111827,#F9FAFB" --tone "Minimalist luxury"
/che-figma  B     # same pipeline, explicit Figma backend
```

Four modes: **A** Social Media creatives · **B** UI/UX feature (wireframe → hi-fi → dev-spec) ·
**C** Design System (Tailwind 4 tokens ↔ variables, light/dark) · **D** Logo & Branding (SVG +
brandbook). `/che-design` and `/che-figma` are the same pipeline with a different backend
preference.

The durable half of the output is **git-native and lives inside your repo**, so it reaches the PR
diff like any other source:

```bash
che designer init <worktree_root> <session_id> --sub-product <slug>   # design/DESIGN.md + tokens/
```

That creates `design/DESIGN.md`, `design/tokens/tokens.json` and `design/<sub_product>/`. The
per-mode working directory (the spec, exported PNGs, assets) stays in the shared workspace outside
the repo. After implementation the `ux` domain gate can compare the *built* DOM against the design
numerically rather than by eyeballing screenshots:

```bash
eval "$(che pixel paths "$WORKTREE_ROOT" "$SESSION_ID" --sub-product <slug> --breakpoint lg --backend figma --related-id <id> --attempt 1)"
che pixel check --map "$CHE_PIXEL_MAP" --dom "$CHE_PIXEL_DOM_FACTS" \
  --design-source "$CHE_PIXEL_DESIGN_RAW" --design-backend figma \
  --design-facts-out "$CHE_PIXEL_DESIGN_FACTS" --breakpoint lg --out "$CHE_PIXEL_REPORT"
```

### F. Fixing a bug

Different loop, different command. `/che-fix` is not `/che-act` with a different ticket:

```text
/che-fix "HTTP 500 when submitting an order without a customer_id"
```

You supply expected behaviour, actual behaviour and numbered reproduction steps. It reproduces the
bug for real, then loops hypothesis → instrument → reproduce → confirm or refute (max 5 iterations,
after which it stops and reports which hypotheses it *eliminated*). On a confirmed root cause it
writes the failing test first, then the minimal fix, then shows you how to verify by hand.

### G. Reacting to an open PR

| Command | When |
| :------ | :--- |
| `/che-diff <PR_URL>` | You want to *understand* a diff and prepare to discuss it. No verdict. |
| `/che-review <PR_URL> --ticket <url>` | You want a blocking review: runtime breakage, security/PII, unjustified dependencies, scope deviation. |
| `/che-pr-comments <PR_URL>` | The PR has many comments; get a triage of what to fix, what to reply, what to resolve silently. |
| `/che-ci-fix <actions_run_or_pr_url>` | CI is red. Classifies the failure and applies a minimal fix — and stops without touching code when the cause is infrastructure or external. |
| `/che-manual-test --worktree <path> --task-id <slug>` | You want the manual test plan executed in a real browser with screenshot evidence per step. |

***

## 🏗️ Core Architecture (Executive Summary)

Two complementary hierarchies: one **3-layer** for the rulebook, one **project → worktree** for project memory.

### 3-Layer Rulebook (what ships inside `~/.che-ai`) — topology inspired by SpecFlow / Cucumber BDD

1. **L1 (Domains)** → SpecFlow *Feature Files (Gherkin)*: Human context, product language — playbooks in `domains/engineering/`, `domains/product/`, `domains/ux/`. What the customer asked for, in their words.
2. **L2 (Routers)** → SpecFlow *step bindings registry (links only)*: Link lists in `CHE_RULES.md` and `CHE_COMMANDS.md`. **Titles and links ONLY.** Rule bodies never live here (just like `[Binding]` C# classes in SpecFlow are a registration table, not the prose).
3. **L3 (Skills)** → SpecFlow *Step Definitions + Hooks*: Declarative rule bodies in `skills/<id>/SKILL.md`. Smallest reusable unit of behaviour.

> Why SpecFlow instead of "just a folder structure with docs"? Because this exact topology has shipped enterprise BDD for 15+ years. We're not inventing a new rulebook layout — we're reusing one that already survives 500-person release trains. See [docs/architecture-and-principles.md §4](./docs/architecture-and-principles.md#4-3-layer-rule-framework-structure) for full rationale.

### Project Memory (what lives inside `~/.che-workspaces`)

1. **Project** — `~/.che-workspaces/<project-slug>/` — durable Markdown (`architecture.md`, `project_profile.md`, `product_context.md`, `roadmap.md`, `roles/index.md`), the per-project `_db/` SQLite store and one folder per canonical domain. Identified by an explicit slug; it does **not** bind a repository path. Lifetime of the product.
2. **Worktree** — `<project>/worktrees/<name>/` — the only level that binds a git checkout (`path`, `branch` and `origin` in `.binding.json`). Born empty: artifact folders are created lazily by `che output_path` on first write, never pre-created. Holds `decisions.log.jsonl`, `specs/`, `tasks/`, `qa/evidence/`, `reports/`. Shared by every session bound to it. Lifetime of the binding.
3. **Session** — `<project>/.sessions/<SESSION_ID>/` — ephemeral logs, single writer, isolated, deliberately outside the worktree. Hours → days. (Pragmatic Programmer §7: "localize state with short lifetime.")

Session → worktree → project bindings are recorded in `~/.che-workspaces/.state/registry.jsonl`.

The full rationale, 8 opinionated stances, 5 anti-goals and methodology references live in [docs/architecture-and-principles.md](./docs/architecture-and-principles.md). Do **not** propose a core change without having read it first — the document explicitly lists the trade-offs we deliberately refuse to revisit.

***

## 🛠️ Command Surface at a Glance

| Command / Group        | Layer | Runs in… | Purpose |
| :--------------------- | :---- | :-------- | :------ |
| `che project {create,init,add,list,remove,restore,trash-list}` | Project | Terminal CLI | Flat project bootstrap + durable docs (trash-safe remove — DbC postcondition: recoverable). |
| `che worktree {add,list,show,remove}` | Worktree | Terminal CLI | Binds a git checkout to a project — the only level that binds a filesystem path. |
| `che config <sid> <wt>` | Session | Terminal CLI | Session flags: `--lang-chat` / `--lang-docs` / `--pt-check` etc. |
| `/che-spec` (IDE)      | Project → Worktree | Agent slash-command (Claude Code) | SBE (Specification-by-Example) specs from PRD / ticket / description. |
| `/che-act` (IDE)       | Worktree | Agent slash-command (Claude Code) | Multi-domain parallel implementation loop. |
| `/che-ship` (IDE)      | Delivery | Agent slash-command (Claude Code) + ✅ CLI gates | Four DbC precondition gates (scope → review → compliance → QA), then Draft PR. |
| `che task {list,show,resume,set-status,graph-summary}` | Worktree | Terminal CLI | Task graph read-only inspection. |
| `che state {rebuild-index,query,search,sanitize}` | Project | Terminal CLI | SQLite FTS5 append-only memory (`<project>/_db/`). |
| `che rag {build,search,list,prune}` | Project | Terminal CLI | Local sqlite-vec hybrid search. |
| `che export` / `che import` | Project | Terminal CLI | Portable project `.tar.gz` — no `.git`, no code, only memory. |
| `che eject {plan,execute,restore}` | All | Terminal CLI | Two-gated safe uninstall. Always trash, never rm. |
| `che update` (alias `self-update`, `upgrade`) | All | Terminal CLI | Fast-forward the checkout to the remote's default branch; reinstall the CLI only if `pyproject.toml` moved. |

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

### One-time setup — install the development dependencies

The Git hooks below and the GitHub Actions CI depend on four tools. Run the **fail-fast checker** once after cloning:

```bash
bash scripts/check-dev-dependencies.sh
```

It will print copy-pasteable install commands for **exactly what's missing on your machine**. Summary of what it checks:

| Tool | Kind | Why Che needs it | Quick install (pick one method) |
| :--- | :---: | :--------------- | :------------------------------ |
| `python3` (≥ 3.9) | **Required** | Che's core language (`pyproject.toml` requires-python). | System package manager: `sudo apt install -y python3 python3-venv python3-pip` (Ubuntu) / `brew install python` (macOS) |
| `pytest` (Python module) | **Required** | 114 unit tests. CI step `python-ci` step 5 runs it. | Venv (isolated): `python3 -m venv .venv && . .venv/bin/activate && pip install pytest ruff`<br>— or user-level: `python3 -m pip install --user pytest ruff` |
| `ruff` | **Required** | Linter + formatter in a single binary. Replaces flake8 + isort + black. CI step `python-ci` steps 3+4. | Pipx: `pipx install ruff`<br>— or inside a venv: `pip install ruff` |
| `npx` / Node.js (LTS) | *Optional* | Runs `markdownlint-cli2` (CI job `markdown-ci`). Without it the **markdown lint gates are SKIPPED locally** (CI still catches them — you just waste one CI roundtrip). | NodeSource (Ubuntu): `curl -fsSL https://deb.nodesource.com/setup_lts.x \| sudo -E bash - && sudo apt install -y nodejs`<br>— or `brew install node` (macOS). |

**Hot tip for a zero-config dev box** (combines every install method above into a single 20 s copy-paste on any Ubuntu/macOS POSIX machine):

```bash
# 1. Python + venv + pytest + ruff
python3 -m venv .venv && . .venv/bin/activate && pip install pytest ruff
# 2. Optional: global ruff (so it's on PATH even outside the venv)
pipx install ruff
# 3. Optional: Node LTS for markdownlint
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt install -y nodejs   # Ubuntu/Debian
# brew install node                                                                                   # macOS
# 4. If `pipx ensurepath` tells you to re-login — do it.
```

### Local Git hooks (pre-commit + pre-push) — CI in < 5 s + < 30 s

Stop waiting for CI to come back red. Install the local hooks **once** after cloning this repo:

```bash
# Option 1 — already ran scripts/install-che.sh with --apply on THIS repo?
#            Done. The installer invokes install-git-hooks.sh automatically
#            when the target contains .git/.

# Option 2 — standalone install:
bash scripts/install-git-hooks.sh
```

**Hook behaviour:**

| Hook       | Budget | What it gates (exactly mirrors GitHub Actions CI) | Bypass once (real emergencies only) |
| :--------- | :----: | :------------------------------------------------ | :---------------------------------- |
| pre-commit | ~ 3 s  | `ruff check` + `ruff format --check` on staged `.py` only → offline regex secret scan (GitHub PAT, AWS key, PEM, JWT) → markdownlint on the 4 canonical docs if touched → smoke pytest (only when `che_core/` or `tests/` changed). | `git commit --no-verify` or `CHE_SKIP_PRE_COMMIT=1` |
| pre-push   | ~ 30 s | **Full repo** `ruff check .` + `ruff format --check .` + `pytest tests/` (114) + `markdownlint-cli2` with exact CI globs + push-diff offline regex secret scan. | `git push --no-verify` or `CHE_SKIP_PRE_PUSH=1` |

The `pre-push` hook is calibrated so that **if it passes, GitHub Actions CI will pass too** (99 % of cases) — no more "30 s wait, click red X, fix typo" loops.

Uninstall / revert backup hooks:

```bash
bash scripts/install-git-hooks.sh --remove
```
