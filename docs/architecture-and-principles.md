# Che AI — Architecture, Design Principles & Opinionated Positions

> This document explains the **why** behind Che. If you only want the operating manual, go to [docs/cli-reference.md](./cli-reference.md) first. Come back here when you want to understand the trade-offs we chose, the anti-patterns we defend against, and the things Che will **never** do.

---

## 1. The Positioning Problem Che Is Trying to Solve

Most agent harnesses on the market fall into one of two buckets — and **both buckets are broken for professional product delivery teams**:

| Bucket A: "Give me an agent, I will prompt it myself" | Bucket B: "Enterprise all-in-one, bring your credit card" |
| :----------------------------------------------------- | :-------------------------------------------------------- |
| + Flexible. Works with any model.                      | + Has guardrails, audit trail, team UI.                   |
| — Zero shared team memory. Zero SDLC opinion. Each engineer builds their own private prompt library. Brand/UX/product rules get copy-pasted 12 times. | — Lock-in. 6-figure bill before first delivery.           |
| — Same 5 prompts rewritten in 12 places (SSoT missing). /che-review passes today, fails tomorrow because the agent forgot team rules. | — No way to customise the actual *flow* without enterprise sales. No way to add a UX skill or a Figma skill without waiting 2 quarters. |
| — "It worked yesterday, why did it forget today?" No durable team brain. Onboarding a new engineer means re-explaining the product from scratch. | — Slow onboarding, custom IAM, platform tax on every change. The team spends more time configuring the platform than shipping product. |

**Che is Bucket C: the opinionated pragmatic engineering harness for 3–30 person product delivery teams that (a) ship both creative product *and* software end-to-end, (b) need a durable shared team brain and a real SDLC (not a prompt playground), (c) want SSoT everywhere, (d) refuse to pay token tax for things that are just filesystem + git + config, and (e) don't want lock-in, don't need a hosted dashboard, and want the harness to live *next to* their repos, not *own* them.**

Che treats your team like a coordinated multi-agent system, not like a single chat window with a single prompt. The same durable product context, brand rules, engineering contracts and decision history are visible to (a) the agent writing a checkout screen, (b) the agent designing a Figma marketing screen, (c) the agent reviewing a PR, (d) the new human engineer on their first day, and (e) the script running in CI before deploy.

### The methodology stack Che reuses (we did not invent these)

The opinions above are **not new**. Che is a concrete, opinionated *implementation* of four battle-tested ideas from the last 25+ years of software engineering — applied to AI agent teams:

1. **[The Pragmatic Programmer](https://pragprog.com/the-pragmatic-programmer/) (Hunt & Thomas, 1999)** — Orthogonality, tracer bullets, DRY, good-enough software, plain-text ground truth, and the SSoT ethic. Every stance in §2 below traces back to one chapter.
2. **[Design by Contract™](https://en.wikipedia.org/wiki/Design_by_contract) (Bertrand Meyer, 1986)** — Preconditions, postconditions, invariants, fail-fast boundaries. Every public `che_core/*` function and every `che-ai` argparse subcommand is a DbC contract. `/che-ship` is a four-gate DbC validator (scope → review → compliance → QA).
3. **[Specification by Example / SBE](https://en.wikipedia.org/wiki/Specification_by_example) (Gojko Adzic, 2011)** — `/che-spec` always returns a spec *led by concrete customer examples*, never a TODO list. If you can't write the example, you don't understand the problem well enough to start. The whole team (Eng + Product + UX) signs off on examples, not on abstractions.
4. **[SpecFlow](https://www.specflow.com/) / Cucumber-school BDD** — Che's 3-Layer Rulebook (§4) is **directly inspired by SpecFlow's 15-year enterprise onion topology**: L1 Domains = Feature Files (Gherkin customer language, readable by non-engineers), L2 Routers = Step Bindings Registry (titles + links only, like C# `[Binding]` classes), L3 Skills = Step Definitions + Hooks. The terminology is Che's; the topology is proven for 500-person release trains.

> **Che's team-delivery promise.** If you onboard five repos to Che, then bring a sixth online six months later with a new agent and a new human engineer, all six participants (old agent + new agent + new engineer + CI + PR reviewer + spec writer) share the *exact same* team context, contracts and decision history. No one has to re-explain the brand or the SDLC.

That promise is why the `che-ai`/`che` binary exists as a **zero-dependency stdlib Python package, installable via pipx** — and why structural commands are implemented first in the CLI *before* any skill is allowed to touch them. It is not the headline; it is the plumbing that makes the shared-team-brain promise survive agent turnovers.

---

## 2. The Opinionated Stance

"Opinionated" gets thrown around a lot. Here, it means **we pick a side on every hard trade-off and do not expose a knob for it**. You either agree with the full stance (adopt Che) or you don't (fork it or pick another tool). We will **never** add a flag to choose between two contradictory design positions.

### 2.1 Opinions that are never negotiable

Each stance is grounded in one of the four canonical methodologies from §1. If you disagree with a stance, read the methodology reference first before proposing change.

1. **Teams first, single-agent second** ([Pragmatic Programmer](https://pragprog.com/the-pragmatic-programmer/) ch. 1 — *Tracer Bullets* + *Orthogonality*, and SpecFlow topology). Che is designed for a *squad*: a coordinated group of agents + humans*. A lone prompt-engineer with a single chat window is a supported but non-default edge case — never the target persona. Everything — L1 Domain Playbooks (product/ux/engineering) are shared; L3 Skills are composable across them. An agent doing code review and an agent doing Figma design read the same product_context.md and the same decision history.
2. **Shared team memory is durable. Agent memory is ephemeral.** ([Pragmatic Programmer](https://pragprog.com/the-pragmatic-programmer/) ch. 5 — *Plain Text as Ground Truth*). The durable team brain (L1/L2 + L2 project templates) lives in plain-text Markdown under `~/.che-workspaces/`,  Agent chat history or context window is ephemeral and will be forgotten. If it is not written to durable memory, it never happened.
3. **Blast radius > cleverness** ([DbC](https://en.wikipedia.org/wiki/Design_by_contract) *invariants* + *orthogonality*). Given a choice between a clever 1-line refactor across 12 files and a boring 8-line change touching 1 file, we ship the boring one. *"Explicit justification required"* is encoded into every remove/eject command via the double-gated safety workflow.
4. **Trash, not delete** ([DbC](https://en.wikipedia.org/wiki/Design_by_contract) *postcondition recoverable* — every destructive operation must have a one-line inverse). There is exactly zero legitimate reason to `rm -rf` anything that lives under `~/.che-workspaces/`. If a `remove` command is invoked, the target is **moved** to `.trash/<kind>--<slug>--<timestamp>` with a printed restore command. A "hard delete forever" command does not exist and will not be added.
5. **SSoT, everywhere** ([Pragmatic Programmer](https://pragprog.com/the-pragmatic-programmer/) ch. 2 — *DRY Principle, Orthogonality, Single Source of Truth*). A rule, a score, a playbook, a decision, or a project template lives in **exactly one canonical file**. If you see the same rule body twice anywhere in the repo, that is a bug — report it, don't rationalize it.
6. **Python + plain-text memory, always — for core logic** ([Pragmatic Programmer](https://pragprog.com/the-pragmatic-programmer/) ch. 7 — *Good-Enough Software* + *Plain Text as Ground Truth*). Che's runtime logic is in stdlib Python ≥ 3.9. Skills live in declarative `.md`. No Node, no TypeScript, no Rust, no Go in the core. If the logic you're writing exceeds ~15 lines in a Markdown code block, extract it to Python and route it through the CLI. This is not negotiable.
7. **Structural operations go to the terminal CLI. Creative work goes to the agent slash-commands.** This is the structural-first principle (§3). Structural/admin operations are implemented first as deterministic Python CLI commands — before any skill is allowed to do them. LLMs never get a vote on L1–L4 path canonicity. Token tax only for creative work: spec authoring, diff review, SQL migration drafting, PR bodies.
8. **No UI. Ever.** (Che is a **framework**, not a product. It has no server, no login screen, no dashboard, no hosted environment. Its surfaces are: (a) the two CLI binaries, (b) the Markdown contracts you read/write, (c) the agent skills run inside **Claude Code** (or another supported IDE).
9. **Workspaces live *outside* user repos.** You will never be told "add `.trae/` at your repo root and commit it." Che's L1–L4 hierarchy lives in `~/.che-workspaces` (the user's home directory) by design. The shipped artifact (your code) stays pristine.

---

## 3. The Structural-First Principle (CLI before skill)

Che's **structural-first principle** says: before an agent skill is allowed to *perform* any structural/admin operation (create a workspace, init a project, set session flags, eject, export, list tasks), that operation must be implemented and shipped as a **deterministic, unit-tested, offline-capable Python CLI command in `che_core/`** *and* exposed via an argparse subcommand. Agents call the CLI; they do **not** reimplement the logic in a Python block inside a Markdown skill.

### 3.1 Why we require a canonical CLI implementation first

Three reasons, ordered by importance to the *shared team brain* promise:

1. **Predictability across the whole team.** A deterministic CLI command returns the same output every run. The 100th execution of `che project init` is byte-identical to the 1st for the same inputs. The 100th LLM-generated `architecture.md` is not. A new agent joining the team six months from now will produce *identical* workspace/project structure to the agents of today — because the CLI, not the prompt, defines canonicity.
2. **Token cost discipline.** A medium-sized team onboarding 10 repos and doing 20 admin operations per week would otherwise burn ~10k tokens/week on pure filesystem busywork. Those tokens should go to things LLMs are actually good at: writing specs, reviewing diffs, generating migration SQL, drafting PR bodies, designing creative screens.
3. **Disaster recovery & CI portability.** If your provider has an outage, or your keys are rotated, or you want to run workspace cleanup from a GitHub Action, or you just want to tidy an old workspace on a plane with no Wi-Fi: the harness still works. You can still move data, restore projects, list tasks, rebuild indexes, export/import portability bundles. The shared team brain does not go dark when an LLM provider goes dark.

### 3.2 Structural commands never require an API key

If you set `CHE_OFFLINE=true` and unplug your network, the following still all work identically:

```
che workspace create x
che project init ~/code/repo --workspace x --domain product
che config s1 ~/code/repo --lang-chat pt-BR
che workspace list | jq
che project list
che state rebuild-index ~/code/repo
che export slug --workspace x --out /tmp/x.tar.gz
che import /tmp/x.tar.gz --workspace x
che eject plan
```

No token. No auth. No feature flags. If any of these ever requires a network call in the future, it is a regression and should be reverted.

---

## 4. 3-Layer Rule (Framework Structure) — topology inspired by SpecFlow / Cucumber BDD

Che's rulebook (the part that lives *inside* the `~/.che-ai` installation, not inside a project) is a 3-layer onion. **No layer may embed a copy of a deeper layer's body.** A router layer links; it never repeats.

This 3-layer topology is **directly inspired by [SpecFlow](https://www.specflow.com/)'s BDD onion** (used at enterprise .NET teams for 15+ years). The exact mapping:

| Che Layer | SpecFlow Equivalent | What that means in practice
| :--- | :--- | :--- |
| **L1 — Domains** (`domains/`) | **Feature Files** (Gherkin) | Customer-language, domain-specific human context. Playbooks for Engineering, Product, UX. "What good X looks like for this team." Readable by non-engineers. |
| **L2 — Routers** (`CHE_RULES.md`, `CHE_COMMANDS.md`) | **Step Bindings Registry** (C# `[Binding]` classes) | TITLES + LINKS ONLY. No body text, no rule bodies. Acts exactly like a SpecFlow step binding table: it tells you *where* the rule lives, it never repeats the rule. |
| **L3 — Skills** (`skills/<id>/SKILL.md`) | **Step Definitions + Hooks** | Declarative rule bodies + task boundaries. The actual executable part. Each skill references L1 via links, never verbatim copy. |

```
~/.che-ai/
├─ domains/                   ← L1 = SpecFlow Feature Files (Gherkin). Human context.
│   ├─ engineering/           ← "What good engineering looks like for Che teams."
│   ├─ product/               ← "How we write PRDs and map outcomes (SBE)."
│   └─ ux/                    ← "Design principles, Figma discipline, UX contract."
│
├─ CHE_RULES.md               ← L2 = SpecFlow Step Bindings Registry. TITLES + LINKS ONLY. No rule bodies.
├─ CHE_COMMANDS.md            ← L2 = SpecFlow Step Bindings Registry. TITLES + LINKS ONLY. No command bodies.
│
└─ skills/<id>/SKILL.md       ← L3 = SpecFlow Step Definitions + Hooks. Declarative rule bodies + task boundaries.
                               Each skill references L1 domains via links.
```

### 4.1 Why 3 layers, not 2 or 4 (and why SpecFlow topology, not something new)

- **1 layer** (a single 10,000 line `RULES.md`) was tried and failed: it drifts, gets copy-pasted, nobody reads it end-to-end. SpecFlow solved this exact problem 15 years ago with Feature Files vs Step Definitions separation.
- **2 layers** (skills + one router) was almost enough but collapsed the **domain context** into skills, making skills non-composable across domains (the same code-review skill should read *different* L1 guidance when invoked in a UX-heavy project vs a pure-infra project).
- **4+ layers** becomes bureaucracy. Che is not an ISO standard; it is a harness for 5–30 person teams. 3 layers hit the sweet spot — same conclusion SpecFlow reached for 500-person release trains.

### 4.2 Hard consequences of violating the 3-layer rule

If you write a skill that contains a **verbatim copy** of a paragraph from a domain playbook, instead of linking it:

1. The next time the domain playbook is updated, that skill silently becomes stale.
2. A reader can't tell which version is authoritative.
3. You just burned the whole point of SSoT (Pragmatic Programmer ch. 2 DRY).

This is treated as a **blocking review finding**, not a style nit. Fix it by deleting the duplicate text and replacing it with a `(→ domains/<area>/playbook.md §4)` link.

---

## 5. 4-Level Worktree Hierarchy (Project Memory Model)

The other half of the architecture is **project memory** — where Che puts the things it learns and the things it generates. The model is **4 concentric levels** with strict durability, visibility, and sharing semantics.

### 5.1 The Diagram

```
$CHE_WORKSPACES_ROOT
  (default: ~/.che-workspaces, never ~/.che-ai, never inside a user repo)
│
└─ workspaces/<ws-slug>/                 ← L1 WORKSPACE. One per "concern space"
   │                                      (example per-company: "acme", "my-company").
   │                                      Shared: yes, across all projects inside.
   │                                      Durability: long-lived (months → years).
   │
   └─ <project-slug>/                    ← L2 PROJECT. One per product/system.
      │                                   Shared: yes, across all worktrees.
      │                                   Durability: lifetime of the system.
      │
      ├─ project/                        ← CANONICAL DURABLE MEMORY (Markdown).
      │   ├─ architecture.md             ←   Decisions that won't change often.
      │   ├─ project_profile.md          ←   Stack, onboarding, key contacts.
      │   ├─ product_context.md          ←   Intent, personas, constraints.
      │   ├─ roadmap.md                  ←   Outcomes, timeline, priorities.
      │   ├─ roles/index.md              ←   Who (human or agent) plays what role.
      │   └─ registry.jsonl              ←   Append-only bindings/flags stream.
      │
      ├─ _db/                            ←   Shared blobs: SQLite DBs, CSVs.
      │
      └─ worktrees/<wt-slug>/            ← L3 WORKTREE SHARED. One per git branch.
         │                                Shared: yes, all sessions on that branch.
         │                                Durability: lifetime of the branch.
         │
         ├─ decisions.log.jsonl          ←   ADR-style decisions (CDJ body).
         ├─ qa/                          ←   QA reports, screenshots, evidence.
         ├─ designs/                     ←   Figma exports, Penpot files, imagery.
         │
         └─ sessions/<session_id>/       ← L4 SESSION. One agent run.
                                          Shared: NO (single writer).
                                          Durability: hours → days. Ephemeral.
```

### 5.2 The Visibility Contract

| Level | Who writes            | Who reads                     | Mutable?  | Backed up? |
| :---- | :-------------------- | :---------------------------- | :-------- | :--------- |
| L1    | Humans + CLI          | Everything                    | Rare      | ✅ Yes     |
| L2    | Humans + `/che-spec`  | Every skill, every agent      | Rare      | ✅ Yes     |
| L3    | CLI + agent skills    | Every agent, every human      | Often     | ✅ Yes     |
| L4    | Exactly one agent     | That agent + `/che-act` dispatcher | Append-only | ⚠️ Optional |

### 5.3 Why the hierarchy nests this way

Four anti-patterns we've repeatedly seen in other agent harnesses, and directly defend against:

1. **"Everything in the repo root"** — Repos end up with 40 `.jsonl` files and a 200-line `.gitignore`. Che deliberately lives in `~/.che-workspaces` to keep repo roots pristine.
2. **"Every session knows about every branch"** — Decisions made on branch `stripe-webhook-fix` leak into the session on branch `homepage-redesign`, polluting context. L3 = 1 worktree per branch closes the leak.
3. **"Durable architecture.md lives next to logs"** — Mixing lifetimes in the same folder means backups and restores are a coin flip. L2 = durable; L4 = disposable — separate folders, separate backup policy.
4. **"Two agents writing to the same state file"** — Corruption. L4 has exactly one writer. Parallelism happens *across* L4 folders, never inside one.

---

## 6. Engineering Contracts — Non-negotiables

These are the "rules for writing rules." They apply to every code change in `che_core/` and every new skill in `skills/`. Documented here rather than scattered because **the reason each contract exists is the point**, not just the rule itself. Every contract in this section is a concrete instance of either [The Pragmatic Programmer](https://pragprog.com/the-pragmatic-programmer/) ethic (ch. 1–8) or [Design by Contract™](https://en.wikipedia.org/wiki/Design_by_contract) (Meyer 1986).

### 6.1 KISS & YAGNI (Pragmatic Programmer — ch. 7 *Good-Enough Software* + ch. 2 *Orthogonality*)

> **Rule:** Given two implementation paths, pick the one with fewer concepts, fewer files, and no new dependencies. If you can't explain why the feature exists in one sentence to a teammate, don't ship it this cycle.

Why: Harnesses die under feature accretion. Every flag you add is a flag every future skill has to read, understand, and not conflict with. Every dep you add is a future supply-chain incident waiting to happen.

Corollary: **`dependencies = []` in `pyproject.toml` is a feature, not a bug.** If you need Typer/Click/Rich/Pydantic for developer ergonomics, first make the case that argparse + stdlib JSON is genuinely insufficient. 95% of the time it isn't.

### 6.2 Design by Contract (DbC) — [Meyer 1986](https://en.wikipedia.org/wiki/Design_by_contract)

> **Rule:** Every public function in `che_core/` states its preconditions, its postconditions, and its invariants — either in docstrings or (preferably) assertions at the function boundary. If the function is exported as a CLI subcommand, the argparse schema is the contract for that surface.

Why: Agent code will call these functions with surprising inputs. Contracts fail fast with a clear message instead of corrupting state 4 steps later.

### 6.3 Storytelling Commits (CDJ body)

> **Rule:** Every non-trivial commit (anything other than a typo fix) has a body of exactly three paragraphs:
> 1. **Context** — what was true before.
> 2. **Decision** — what I changed, line-level if helpful.
> 3. **Justification** — why *this* change instead of the 3 other obvious alternatives.

Why: A year from now you (or a teammate) will find that line that looks obviously wrong and be tempted to "fix" it. The CDJ body tells you why it was obviously right at the time and lets you re-evaluate the trade-off honestly instead of repeating it.

### 6.4 Worktree Hygiene

> **Rule:** Never leave logs, traces, screenshots, caches, temp `.md` spec drafts or generated reports at the root of a user repository. Ephemeral output belongs in L4 (`sessions/<id>/`). Shared evidence belongs in L3 (`qa/`, `designs/`).

Why: Teams stop using harnesses the moment `git status` inside their project shows 12 untracked harness files. This is a hard psychological threshold; cross it once and you lose trust permanently.

### 6.5 Language Policy (Dual Register)

> **Rule:** Code, identifiers, symbols, internal docs, and contract canonical text are **strict English**. Public UI strings (CLI help, user-facing error messages, playbooks intended to be read by non-engineers) default to English with **British spelling** and may receive pt-BR companion translations where the project's LANG_DOCS flag is set to `pt-BR`. See [§9](#9-language-policy--dual-register-documentation).

### 6.6 Blast Radius

> **Rule:** Any diff touching > 5 files or spanning a package boundary requires an explicit ADR row written to `decisions.log.jsonl` *before* the code is written. The CDJ commit body alone is not enough.

Why: Refactors that "seemed like a good idea at the time" are the #1 cause of harness regressions. The 2 minutes spent writing the ADR cost far less than the 2 days spent bisecting the 17-commit "cleanup" PR 6 months later.

---

## 7. The "Blast Radius + Trash-Safe" Principle

This pair is Che's most **visibly opinionated** UX choice — and the one we get the most pushback on from new users, until the first accidental `remove` on a 9-month project. Then the complaints stop.

The combined principle, in one line:

> **Before any destructive operation, show me what would happen and make it trivially reversible. If I can't restore it in < 1 command, the feature is not shipped.**

Applied uniformly across `workspace remove`, `project remove`, `eject execute`, and every future command that mutates durable state, this means:

1. **Double-gated API.** All destructive commands have a `--dry-run` mode that prints the plan and stops, and an execute mode that requires `--confirm` (explicit).
2. **Move, don't unlink.** The execute step calls `shutil.move(target, trash_path)`, **never** `shutil.rmtree(target)`.
3. **Deterministic restore.** Every successful move prints the one-liner `che <kind> restore <trash-slug>` that reverses it. No searching for timestamps, no re-typing paths.
4. **Trash-listing visibility.** `che workspace trash-list` always shows the full contents of `.trash/` so users can self-serve a restore without asking support.

Yes, this costs a few lines of code. Yes, it is worth every one.

---

## 8. Append-only Deterministic Memory (SSoT — Pragmatic DRY + SBE canon)

### 8.1 Two rules that look similar and are not

These are often confused. Keep them distinct — the distinction comes directly from [The Pragmatic Programmer](https://pragprog.com/the-pragmatic-programmer/) ch. 2 (DRY Principle) and the append-only contract comes from DbC invariants:

- **SSoT (Single Source of Truth)** = a given fact lives in exactly one canonical file across the whole installation. `LANG_CHAT` default value lives in `che_core/constants.py`. The scores table lives in the domain playbook that owns it. It does **not** also appear in 3 skill files. This is the Pragmatic DRY principle, verbatim.
- **Append-only** = a given file grows by lines at the end; lines already written are never edited in place. Applies to: `registry.jsonl`, `decisions.log.jsonl`, any log, any binding stream. This is a DbC *immutability invariant* on audit streams — once a row is written, it is never overwritten.

### 8.2 Why append-only for the JSONL files

Three separate reasons:

1. **Reproducibility.** If a session behaved weirdly on Tuesday, you can replay the JSONL from Monday 00:00 and get byte-identical memory state on another machine.
2. **Concurrency safety.** Multiple writers doing atomic `O_APPEND` writes don't step on each other. JSONL doesn't require a lock for readers.
3. **Audit trail.** If someone (human or agent) flips `LANG_CHAT = pt-BR → en`, you can find the exact row, the exact `session_id`, and the exact timestamp that happened. Mutable YAML would just show you the final state, with no clue who or why.

---

## 9. Language Policy & Dual-Register Documentation

Che is written by a Brazilian UK-first team for a bilingual audience. The language policy is a deliberately pragmatic compromise that avoids both the "English-only forever" extreme (which excludes non-technical stakeholders in pt-BR projects) and the "translate everything" extreme (which doubles the maintenance burden and guarantees drift).

**The policy in 4 bullets:**

1. **Canonical register = English.** All source, all identifiers, all CLI subcommand names, `AGENTS.md`, this document (`architecture-and-principles.md`), and engineering contracts are English. The default `LANG_CODE` for code is `en`.
2. **User-facing dialogue = project-localized via flags.** The four session flags `LANG_CHAT`, `LANG_DOCS`, `LANG_REPORT`, `PT_CHECK` are the single way to switch register. They live in `registry.jsonl` on a per-session basis. If a project's stakeholders speak pt-BR, set the flags once via `che config`, not via 800 scattered copy-pastes.
3. **No machine translation in canonical docs.** A pt-BR translation of `architecture.md` in an L2 project is written by a human or not at all. Raw MT output committed directly to the canonical file is a blocking review finding.
4. **British spelling for public UI strings.** "Behaviour" not "behavior", "colour" not "color", in docs and CLI help — Che's reference deployment is UK-GDPR and UK-market-facing (e.g. "My Company Ltd" registered in London). If your tenant is US, override via flags in a `domains/` layer, not in core.

---

## 10. What Che Deliberately Does NOT Do (Anti-goals)

Writing down anti-goals is as important as goals — they tell you which PRs to close unmerged.

1. **Che is not a hosted platform.** There will never be a `console.che.ai` login page, a per-seat SaaS bill, or a cloud-side agent runner. If you want to run Che on a server, you run your own.
2. **Che is not a general-purpose agent framework.** Che does one thing well: agentic engineering on small-to-medium monorepos following the SDLC. It will never ship a "call any API from any skill, write any workflow" surface.
3. **Che does not wrap every LLM provider in the universe.** A thin adapter layer is acceptable; a 1:1 mirror of every vendor's feature matrix is explicitly out of scope. Che picks ~3 providers that matter for engineering and integrates them well.
4. **Che never manages cloud infrastructure on your behalf.** The line is: "Che can write Terraform/HCL/Pulumi code for you, and Che can plan a change. Che will never apply a change to your AWS account without you running `terraform apply` yourself in your own shell." Two-person rule applies to infra.
5. **Che will never have a "fancy UI mode" that hides the CLI.** If you don't like terminals, Che is probably not your harness. That is fine. The ecosystem is big.

---

## 11. Appendix: Glossary & Equivalents

| Term in this doc | What it means |
| :--------------- | :------------ |
| **Harness** | The full Che installation: rulebook + skills + `che_core/` Python + CLI. |
| **Tenant** | A real team using Che (e.g., "Acme", "My Company", "Big Client"). |
| **L1 Workspace** | The top-level grouping folder under `~/.che-workspaces/workspaces/`. One per tenant usually. |
| **L2 Project** | One product or system inside a workspace. Owns `architecture.md`, etc. |
| **L3 Worktree** | Shared memory for a specific git branch. Shared across sessions, not projects. |
| **L4 Session** | One agent run, one writer, ephemeral. |
| **Skill** | Declarative `.md` file under `skills/<id>/SKILL.md`, the smallest unit of reusable Che behaviour. |
| **Router (L2 of the rulebook)** | `CHE_RULES.md` / `CHE_COMMANDS.md`. Titles + links only. No body text. |
| **CDJ** | Context / Decision / Justification — the canonical three-paragraph commit body format. |
| **SSoT** | Single Source of Truth. |
| **DbC** | Design by Contract. |
| **Trash-safe** | Any destructive command that *moves* to `.trash/` instead of unlinking, with a restore command. |
| **Structural-first principle** | All structural/admin commands implemented first as deterministic Python+CLI. Agent skills call the CLI; they never reimplement L1–L4 filesystem logic in Markdown blocks.

---

_See also: [docs/cli-reference.md](./cli-reference.md) for the exact command surfaces that implement every principle above._

_The agent-facing summary version of this document lives at the top of [AGENTS.md](../AGENTS.md) (the router) — read that first before contributing code or skills._
