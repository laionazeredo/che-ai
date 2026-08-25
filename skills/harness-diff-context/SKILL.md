---
name: "harness-diff-context"
description: "Context builder for diff conversations. TWO MODES: (A) GitHub PR URL — summarizes description + diff + CI checks into a lightweight 'what this PR does' conversation brief. (B) Local Worktree via --worktree <path> — compares to default branch (ask if ambiguous) and splits analysis into already-committed vs to-commit vs untracked with risks. PURPOSE: give you ready talking points to discuss a PR/diff with another developer; NOT a blocking code review (that's harness-code-review)."
---

# Harness — Diff Context (Conversation Brief Builder)

> **SHARED REFERENCES (CANONICAL — NÃO DUPLICAR corpo aqui):**
> - Security + PII + compliance patterns (if flagged during analysis): `_shared_checklists/SECURITY_PII_COMMON.md`
> - GitHub CLI gh auth + PR metadata commands: `_shared_checklists/GITHUB_CLI_COMMON.md`
> - Worktree Session Binding rules (one session = one worktree, ask on doubt): engineering-contracts §19
> - Output shape rules (concise 4 sections + diagonal readability): engineering-contracts §18

## 🆚 Clear boundary from harness-code-review (DO NOT overlap)

| Concern | `harness-code-review` | This skill `harness-diff-context` |
|---|---|---|
| **Goal** | Block production breaks. Verdict: 🔴/🟡/🟢. | Give the user **conversation context** so they can talk to someone about this diff. No verdict, no approve/request-changes. |
| **Scope** | ONLY CRITICAL + HIGH blocking issues (Runtime / Security / Deps / Scope deviation). | EVERYTHING the user needs to understand intent + changes + CI state + talking points. Mild concerns are OK as "things to bring up". |
| **Output** | Review report with numbered blocking issues. | Lightweight brief: What / Main changes / CI / Attention points. Narrative structure for dialogue. |
| **Severity tone** | Bold red blockers. Polite but firm. | Neutral, descriptive. "Potential risk worth discussing" vs "this is broken." |
| **Call to action** | "Fix X before merge" or "Approve". | "3 things I'd ask about in review: A, B, C." |

**Rule:** User says "review this / approvação / blocking issues" → use `harness-code-review`. User says "contexto / entender o que foi feito / preparar pra conversar sobre esse diff" → use THIS skill. Never mix.

---

## 0. Preconditions — Two modes (PICK EXACTLY ONE)

### How to decide which mode
- **If user provides a GitHub PR URL** (starts with `https://github.com/` or `gh/.../pull/`) → **FORCE Mode A (PR Context)**. Worktree optional.
- **If user passes `--worktree <path>` (or equivalent explicit worktree indicator) AND NO GitHub PR URL** → **FORCE Mode B (Local Worktree vs Default Branch)**.

---

### Mode A — GitHub PR URL (Conversation Brief)

#### A.0 Preflight

1. **`gh` CLI authenticated:** Run `gh auth status` silently. If not → guide user to `gh auth login` then stop.
2. **PR URL reachable:** Validate URL format + run a tiny `gh pr view <url> --json number,title` to confirm it exists. If 404 / 403 → stop and report.
3. **Worktree binding optional:** If user also gave `--worktree <path>`, write/read session binding per §19 (ask if mismatch). If no worktree → proceed with GitHub only; report will be saved to `<WORKTREE_ROOT>/.trae/` if one is known, else to user's home `~/.trae/reports/`.

#### A.1 Context collection (3 sources)

##### A.1.1 PR description + metadata
Run:
```bash
gh pr view <PR_URL> --json \
  number,title,body,author,state,isDraft,baseRefName,headRefName,additions,deletions,changedFiles,commits,labels,reviewDecision,mergeable,createdAt,updatedAt
```
Extract fields:
- **Title + number**
- **Body summary** (1–3 sentences maximum; if body is >30 lines → pick TL;DR header or first paragraph only)
- **Author, Draft/Ready, Base → Head branch**
- **Diff stats** (lines + files + commits count)
- **Labels / linked issues** if any

##### A.1.2 Diff changes (main code areas touched)
Run:
```bash
gh pr diff <PR_URL> --name-only
```
Build:
- **Top 5–8 most meaningful files** sorted by additions+deletions. Group by folder/module (e.g., `packages/db/*`, `packages/platform/app/api/*`).
- **One-liner per group:** ex "`packages/db` — 2 new entities + 1 migration".
- **Flag obvious big groups:** if a single group has >40% of diff → highlight that as "main blast radius".

##### A.1.3 CI checks status
Run:
```bash
gh pr checks <PR_URL>
```
Build 1-line summary buckets:
- **Passing count / Total count**, plus names of any **FAILED** checks.
- For failed checks: 1-sentence log headline (from first 3 lines of run log if possible via `gh run view` on failed).
- Note "Pending" count separately.

#### A.2 Conversation Brief Canonical Output Sections (exactly 5 — match user's goal)

The output saved to disk AND presented to user uses THESE sections in THIS order. Follow §18 diagonal formatting (headings + bullets + bold key words).

```markdown
# 📋 Diff Context — PR #<N> — <Title>

**Mode:** GitHub PR URL | **Worktree:** <path or "none (GitHub-only)"> | **Generated at:** <ISO ts>

---

## 1. 🧭 O que esta PR está implementando (contexto alto-nível)
1–3 frases claras. Responde: "Qual problema ela resolve? Qual o comportamento novo?"
- Usa título + resumo do body.
- Se body tiver Acceptance Criteria → copiar em bullet máximo 5 ACs core.
- NÃO reproduz o body inteiro. Trim.

## 2. 🧩 Principais áreas de mudança (blast radius por módulo)
Max 6–8 bullets. Cada bullet = 1 módulo/grupo + 1 verb + o que mudou.
Ex:
• **packages/db — entidades + migração**: `TicketRefund` entity + SQL migration adds `refund_status` enum.
• **packages/platform/api/refunds — endpoint**: `POST /api/events/:id/refunds` + Stripe refund call.

Section end → 1 summary line: **Total:** X arquivos / +Y linhas / -Z linhas / W commits.

## 3. ✅ Status dos CI Checks
• **Global:** <passando/tem falhas/com pendências> — <M> passed / <N> failed / <P> pending de <TOTAL>.
• **Failed checks (se houver):**
  - <Check 1 nome>: <1 linha causa, ex "build platform step 42 TypeScript type error: ...">
  - <Check 2 nome>: ...
• **Review Decision do GitHub (se houver):** reviewDecision field.

## 4. 🔴 Riscos / Coisas quebradas que vejo (levemente crítico)
Aqui é o espaço para problemas claros mas NO BLOCKING verdict (diferente de code-review). Max 3 bullets.
- Se nada: dizer "Nenhum risco óbvio no diff analisado."
- Exemplos típicos: "Novo endpoint não tem check de permissão explícito (verificar se herda do middleware pai)"; "Migration DROP sem rollback documentado"; "Chave secreta apareceu 1 linha — parece placeholder dummy, confirmar".

## 5. 💬 3 Pontos de Atenção PARA VOCÊ CONVERSAR sobre esta PR
MÁXIMO 3 itens. 1 frase cada. Estes são seus tópicos pra pautar na call/comentário.
• Ponto 1: Pergunta sobre arquitetura / abordagem
• Ponto 2: Cobertura de testes ou casos edge faltando
• Ponto 3: Alinhamento com ACs do PR body / ticket
```

#### A.3 Save + delivery
Save report to:
- Worktree known → `<WORKTREE_ROOT>/.trae/diff-context_PR-<N>_<YYYYMMDD-HHMM>.md`
- Worktree unknown → `~/.trae/reports/diff-context_PR-<N>_<YYYYMMDD-HHMM>.md`

Delivery to chat follows §18 shape: **📍 Status / 🧩 Resumo / 🔗 Refs / ❓ Deep-dive**.
Never dump the full 5-section report into chat verbatim unless user says "mostra tudo". Chat summary = condensed 3 bullets from each of sections 1/2/3 + warning if section 4 > 0 items. Offer: "Quer o relatório completo salvo no disco ou o full text aqui?"

---

### Mode B — Local Worktree — Diff vs Default Branch

> **Goal same as Mode A: conversation context.** Only difference: source = LOCAL WORKTREE, and we split into 3 temporal buckets vs a PR's single diff.

#### B.0 Worktree preflight (engineering-contracts §19, NON-NEGOTIABLE)

Run BEFORE any git command.

1. **`WORKTREE_ROOT` = absolute path from `--worktree` flag.**
2. **Valid git worktree check:** `cd <WORKTREE_ROOT> && git rev-parse --is-inside-work-tree 2>/dev/null` → true. If not → stop.
3. **Session binding file read:** Read `<WORKTREE_ROOT>/.trae/session_binding.md` if exists.
   - If exists and `SESSION_WORKTREE_ROOT` ≠ provided path → BLOCK. Ask user: "Session binding says X but you asked Y. Proceed with Y anyway? (A = Y override; B = Switch back to X; C = Cancel)". Never silent override.
   - If binding file missing → create canonical 4-line format. Ask user confirms worktree once.

#### B.1 Resolve BASE BRANCH (na dúvida = pergunta)

Goal: find the branch to compare AGAINST. This is the "default comparison branch" user would open a PR against.

1. **Try auto-detect first:**
   - Fetch default remote default branch: `cd <WORKTREE_ROOT> && gh repo view --json defaultBranchRef --jq .defaultBranchRef.name 2>/dev/null`. If returns string like `main`/`master`/`dev` → that's candidate 1.
   - Local branches list sorted by most recent commit: `git branch -a --sort=-committerdate | head -20`
   - Heuristic: candidate 2 = remote `origin/dev`, `origin/develop`, `origin/main` commonly used.
2. **Ambiguity rule (§19 doubt = ask):**
   - If ≥2 equally-valid candidates (e.g., `origin/dev` AND `origin/main` both exist and both are recent) → **STOP. Ask user directly.**
   - Ask format (AskUserQuestion 2 choices max + other):
     > Comparar contra qual branch base?
     > A) `origin/dev` (mais recente, dev staging)
     > B) `origin/main` (produção)
     > (other / digitar o nome)
3. **Once BASE_BRANCH resolved:** Record variable `BASE_BRANCH_REF = origin/<name>` (remote preferred so we compare working tree vs the actual upstream base, not stale local copy).

#### B.2 Context collection (4 buckets = key difference from Mode A)

Run all git commands inside `<WORKTREE_ROOT>`.

##### B.2.1 Bucket 1 — 🟢 Already Committed (on this branch, NOT YET on BASE_BRANCH)
This = things that WILL be in a PR if opened now.
```bash
# Commit list vs base
BASE=<BASE_BRANCH_REF>
git log --oneline --decorate ${BASE}..HEAD
# Diff stat
git diff --stat ${BASE}..HEAD
# Diff names-only grouped
git diff --name-only ${BASE}..HEAD
```
Extract:
- Top 3–5 most recent commit messages (oneliner).
- Top 5–8 file groups as in Mode A.2.
- Commits count + file count.

##### B.2.2 Bucket 2 — 🟡 To Commit (STAGED + UNSTAGED tracked changes)
This = work-in-progress the user has locally but NOT in any commit on this branch yet.
```bash
git status --short  # filter M/A/D/R + space or M (not ??)
# staged only
git diff --cached --stat
git diff --cached --name-only
# unstaged only (tracked)
git diff --stat
git diff --name-only
```
Extract:
- Counts: staged N files / unstaged M tracked files.
- Key modified files (list 5–8).
- Note: "Large unstaged change = risk of accidentally shipping half-baked work".

##### B.2.3 Bucket 3 — ⚪ Untracked (?? files NOT yet added)
```bash
git ls-files --others --exclude-standard   # respect .gitignore
```
Rules:
- Skip: `node_modules/`, `.next/`, `dist/`, build artifacts even if they somehow leaked here.
- If ≤5 untracked → list them all by path.
- If >5 → list first 5 + "e mais <K>".
- Flag any **untracked `.env*` or secret-looking files** immediately (Security quick flag).

##### B.2.4 Bucket 4 — 🔧 Current branch metadata
- Current branch: `git branch --show-current`
- HEAD commit short SHA
- Worktree clean/dirty boolean
- Optional: stashes count: `git stash list | wc -l`

#### B.3 Conversation Brief Canonical Output (Mode B)

Same rule as Mode A: 5 fixed sections, §18 diagonal shape. Bucket 1/2/3 take the place of PR diff.

```markdown
# 📋 Diff Context — Local Worktree vs <BASE_BRANCH_REF>

**Mode:** Local Worktree | **Path:** <WORKTREE_ROOT> | **Branch atual:** <BRANCH> | **Generated at:** <ISO ts>
**Clean/Dirty:** <clean|dirty> | **Stashes:** <N> | **Commits ahead of base:** <W>

---

## 1. 🧭 O que esta sendo desenvolvido aqui (contexto alto-nível)
1–3 frases. Baseado nos últimos commits mensagens + arquivos principais.
- Combina top 3 commit messages oneline em narrativa curta.
- Se commits forem "WIP" / vague → dizer "Contexto em títulos de commits não claro; focar em seções 2.1–2.3 abaixo".

## 2. 🧩 Mudanças separadas por etapa (pra conversar)

### 2.1 🟢 Já Commitado (W commits / X arquivos / +Y / -Z)
Max 5 bullets:
• Últimos commits principais (3–5 oneline).
• Módulos/áreas principais afetadas (como Modo A seção 2).
• 1 linha: qual o estado geral desta parte (ex: "Pipeline refund completo em commits, refactor migration half done").

### 2.2 🟡 Por Commitar (staged N, unstaged M tracked files)
Max 5 bullets:
• Arquivos principais com alteração staged.
• Arquivos principais unstaged (WIP).
• Flag: se algum arquivo de migração/segurança tem mudanças UNSTAGED.
• Summary line: quanto % do trabalho parece em WIP vs pronto.

### 2.3 ⚪ Untracked / Novos arquivos ainda não adicionados (K)
• Listar 5 mais importantes + path.
• Flag env/secrets se aparecem.
• "K > 5" aviso.

## 3. ✅ Local build/lint status hints (se possível, 1 linha cada)
Se for fácil rodar num comando rápido e tiver pipeline conhecido (Nx/pnpm workspace):
• NÃO rode full lint+build+tests full (overkill). Apenas quick check se conhecido: roda typecheck de 1 package que mudou se ≤ 10s.
• Se não rodar nada → dizer: "Nenhum check local executado; rode `corepack pnpm nx run <pkg>:typecheck` p/ confirmar tipos na área alterada."

## 4. 🔴 Problemas / Riscos que destaco (antes mesmo de revisão formal)
Max 3 bullets. Algo claramente errado OU arriscado no estado atual.
Exemplos típicos:
• "Migration com ALTER TABLE DROP COLUMN sem comentário de rollback / down migration"
• ".env.local está untracked (contém chaves provavelmente reais — **cuidado** caso esse worktree seja compartilhado)"
• "Arquivo `refunds.ts` tem ~400 linhas mudadas unstaged — risco de trabalho half-done se abrir PR agora".
Nada = "Nenhum risco óbvio de cara".

## 5. 💬 3 Pontos de Atenção PARA VOCÊ CONVERSAR / SE PREPARAR
MÁXIMO 3, 1 frase cada:
• 1 ponto sobre escopo atual vs desejado (ainda faltando? Quais peças)
• 1 ponto sobre ordem de commitagem (o que commitar primeiro / o que deixar WIP)
• 1 ponto sobre abrir PR agora vs esperar mais alguns commits
```

#### B.4 Save + delivery
Save report to: `<WORKTREE_ROOT>/.trae/diff-context_LOCAL_<YYYYMMDD-HHMM>.md`

Chat delivery follows §18 shape (condensed, not full dump unless asked).

---

## General rules for BOTH modes

1. **No verdict.** Never "Approve / Request Changes". That is **only** `harness-code-review`.
2. **Report ≤250 lines max.** If diff is huge → pick top changes; don't enumerate every file.
3. **§18 response verbosity budget active for chat delivery.** The chat summary is 250–500w, 4 sections, 3 bullets max. Full report = saved to disk, user can open.
4. **§19 worktree binding active on any mode that touches disk writes.** Always read binding file if worktree path is known.
5. **NEVER invent PR body / commit intent.** If titles/vague → explicitly say "context from authors not clear, recommend asking".
6. **PII / secrets scanning (light):** While collecting diffs/text, a quick grep (same patterns as compliance) — if a raw key/token shows up, **flag it immediately in section 4 regardless of other content.**
