---
description: "Resolve Git merge conflicts with MIN BLAST RADIUS 1 arquivo por vez. DEFAULT favorece worktree atual (ours). 3 casos: trivial auto-resolve (whitespace/newline/auto-merge), clash pergunta lado lado lado, ambiguidade NUNCA resolve sozinho → pergunta 2 opções máx + justificativa."
arguments:
  - name: worktree
    description: "Absolute worktree path (REQUIRED if in chat outside worktree). If omitted and SESSION has binding §19, uses bound WORKTREE_ROOT."
    required: false
  - name: strategy
    description: "DEFAULT = ours (favorece worktree atual, incoming perde). Optional: theirs | both-sided-by-hunk | manual-ask-all."
    required: false
  - name: path
    description: "Optional subfilter: somente conflitos DENTRO de path (dir ou arquivo). Útil para blast-radius ainda menor."
    required: false
---

IMMEDIATELY invoke **`che-merge-resolver`** Skill.

Preflight:
1. Worktree binding check §19 — `worktree` arg vs Level1 registry: mismatch → BLOCK. Ask.
2. `cd $WT && git status --short` — must show `UU` (unmerged) files. 0 conflitos → msg informativa + stop.
3. Decisão default strategy: `ours = worktree wins, incoming loses`. **Apenas use outra se user explicitamente pediu no arg.**
4. Skill default **1 ARQUIVO POR VEZ — PER-HUNK NUNCA GLOBAL.** Processa ordem alfabética. A cada hunk:
   - **Caso 1 🟢 Trivial auto:** só whitespace / newlines / ordem imports / linhas não conflitantes separadas → merge trivial, sem ask, log + avancar.
   - **Caso 2 🟡 Clash (2 sides diferentes):** mostra 2 opções — A = OURS (default worktree), B = THEIRS (incoming) + cada opção com preview 5 linhas context + **justificativa curta do agent (por que uma poderia ser a correta baseado em PR/task/semantica — NUNCA agir).** Máximo 2 opções por hunk. Pergunta NÃO tem continue-all — cada hunk é independente.
   - **Caso 3 🔴 Ambiguidade (≥3 caminhos ou semântica não óbvia ex: reescreveu função 2 jeitos ou side-effect order importante):** NUNCA decide. Mostra contexto completo + pergunta 2 alternativas (A=ours, B=theirs, OU C=user digita trecho manual se aplicável) + **explicar por que é ambíguo.** Só depois da resposta user aplica.
5. Cada decisão → log `MERGE_RESOLVE` entry no decisions.log.jsonl: hunk_hash, arquivo, nosso_lado, lado_escolhido, estrategia, justificativa_user (se houver).
6. Após último conflito: `git diff --cached --stat` (só arquivos unmerged resolvidos) → confirmar 0 `UU` remanescentes. Relatório final salvo em `$CHE_WORKSPACE_SHARED/merge-resolve_<slug>_<YYYYMMDD>.md` (header counts triviais/clashes/ambiguous por arquivo + decisions list).

**PROIBIDO:**
- ❌ `git merge -X ours` global / checkout --ours/--theirs ARQUIVO INTEIRO sem passar hunk-a-hunk (isso estoura blast radius).
- ❌ Skipar amiguidades sem perguntar. NUNCA "eu escolhi ours pq era parecido" em caso 3.
- ❌ Modificar arquivos sem `UU` status.
