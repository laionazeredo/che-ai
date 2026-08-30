# Harness Global — Minified User Rules
# COMO USAR: Substitua TODO o conteúdo do campo "User Rules" da IDE por este arquivo.
# Ele é ~70% menor que a versão antiga. Todas as regras completas (corpo, detalhes, exemplos)
# foram movidas para os locais canônicos abaixo. Leia-os quando precisar de detalhe.
#
# VERSÃO MINIFICADA = SÓ LEMBRETES E LINKS. NÃO DUPLICA CORPO DE REGRA.

---

## 🔝 PRINCÍPIO MAIS IMPORTANTE (hard stop, sem negociação)
> KISS + YAGNI + BLAST RADIUS REDUCTION.
> Mais simples sempre. Menos arquivos sempre. Menos linhas sempre.
> Em empate: opção de menor impacto no código existente.
>
> **Corpo completo e explícito (exemplos, thresholds):** `engineering-contracts` SKILL §1 (canônico)

---

## 📁 TRÊS ARQUIVOS CANÔNICOS — CONSULTE-OS SEMPRE
1. **`/home/laion/.trae/HARNESS_RULES.md`** → Fluxo do harness, worktree-first, gates SPEC Approved, paralelismo, ship/gh rules.
2. **`/home/laion/.trae/skills/engineering-contracts/SKILL.md`** → 18 regras de engenharia com precedência ordenada, DbC, TDD, SOLID, strong typing, security/PII, RLS, conventional commits, agilidade BDD, code review optimization, §19 Worktree Binding 2-LEVEL.
3. **`/home/laion/.trae/HARNESS_COMMANDS.md`** → 14 comandos /harness-* com sintaxe + arquitetura commands vs skills.

---

## 🟥 REGRA 0: WORKTREE-FIRST
- NÃO escreva código NEM rode comandos sem saber o worktree exato.
- Se worktree não foi fornecido: **PARE, PERGUNTE o caminho absoluto.**
- Explícito "não usar worktree" só procede com confirmação dupla.
- **Corpo completo:** `HARNESS_RULES.md` §🔴 WORKTREE-FIRST ENFORCEMENT

---

## 🟥 REGRA 1: DIRETÓRIO DE SAÍDA
- **DURÁVEL (multi-sessão, compartilhado worktree):** task_graph, decisions, manual_test_plan, gh_stack_plan, tasks/<task-id>/envelope → **`$HARNESS_WORKSPACE_SHARED/`** (fora worktree user, resolvido via `harness_compute_paths`).
- **EFÊMERO (esta sessão só):** binding Level2, reports, qa/screenshots, final_summary → **`$HARNESS_SESSION_DIR/`**.
- **MORATÓRIA HARD STOP:** NADA gerado vai em `<WORKTREE_ROOT>/.trae/*` (evita git sujo / commit acidental).
- **NUNCA** em `docs/`, raiz do repo, ou pastas de packages a menos que usuário peça explicitamente.
- **Corpo completo:** `HARNESS_RULES.md` §🔴 DIRETÓRIO DE SAÍDA DO HARNESS

---

## 🟠 REGRA 2: ENGENHARIA — 14 REGRAS COM PRECEDÊNCIA ORDENADA
1. KISS / YAGNI / BLAST RADIUS  (hard stop)
2. SEGURANÇA & PII COMPLIANCE    (hard stop)
3. REPO EXISTING STYLE + CONVENTIONS
4. REUSE BEFORE CREATE
5. STRICT STRONG TYPING  (qualquer linguagem)
6. DESIGN BY CONTRACT  (públicas, pré/pós/invariantes)
7. FUNCTIONAL CORE / IMPERATIVE SHELL
8. FUNCTIONAL STYLE PREFERRED (map/filter/reduce, early return, Result)
9. RUST-STYLE ERROR MANAGEMENT (Result / Option / tagged union)
10. ATDD + TDD (test-first antes de mudar comportamento)
11. ACCEPTANCE CRITERIA + STOP CONDITION clara
12. OBSERVABILITY & LOGGING inteligente + PII-safe
13. IDIOMA: CÓDIGO/COMMIT/DOCS/HARNESS_FILES = EN; CHAT/RESPOSTAS = PT-BR
14. CONVENTIONAL COMMITS atômicos

- **Corpo completo + Hard Conflict Resolution Table + Appendix B (commit types regex):** `engineering-contracts` SKILL §1–§14 + Appendices A/B.
- **Novas regras agora adicionadas (solicitado):**
  - §15 — DESENVOLVIMENTO ÁGIL BDD / INCREMENTOS PEQUENOS (só entrega solicitado; NÃO antecipa edge/futuro; easy-to-evolve structure com SOLID; múltiplos PRs parciais via gh-stack)
  - §16 — CODE REVIEW OPTIMIZATION (código limpo, não verboso, max 2 linhas comentário bloco por arquivo a menos que realmente necessário; gh-stack hierarquia PRs)
  - §17 — SUPABASE POSTGRES: ENABLE RLS DEFAULT (toda tabela nova tem RLS + policies; hard rule)

---

## 🟠 REGRA 3: TIME ÁGIL SIMULADO — ORDEM OBRIGATÓRIA
1. SCRUM MASTER (`harness-scrum-master`) → scope + task graph + envelopes.
2. DEVELOPER (`harness-developer`) → SÓ por SM com envelope formal. Primeiro invoca `engineering-contracts`.
3. SCOPE VALIDATION (SM ↔ Dev). Máx 2 iterações → PERGUNTE ao user.
4. QA (`harness-qa`) → build/lint/typecheck/tests (terceira pessoa).
5. COMPLIANCE LIGHT per-task + COMPLIANCE HEAVY final.
6. REPETE por task.

- **Corpo completo + handoff gates + timeouts:** `HARNESS_RULES.md` §🟠 TIME ÁGIL SIMULADO + §🟢 LOOP TIMEOUTS (2/5/3)

---

## 🟠 REGRA 4: MAPEAMENTO DE COMANDOS (use o certo por fase)
- **Início (especificação):** `/harness-spec` → SPEC otimizado p/ agente + harness (4 fontes: existente/ticket URL/PRD Flockr/inline). 7 seções + YAML frontmatter + gate Approved ANTES scope capture.
- **Implementação feature/longa:** `/harness-start` (auto serial vs parallel) OU `/harness-parallel` (force parallel-or-bust). SM invoca `/harness-spec` automaticamente no preflight §0.5 se não houver Approved.
- **Bug fix:** `/harness-fix` (loop científico; reproduz ANTES)
- **Ship:** `/harness-ship` (commits atômicos conventional, push --no-verify, PR DRAFT + gh-stack se múltiplos PRs)
- **Review/comments/CI:** `/harness-review`, `/harness-pr-comments`, `/harness-ci-fix`
- **Operações leves:** `/harness-status`, `/harness-skip`, `/harness-decisions`, `/harness-summary`, `/harness-abort` (inline, NÃO viram skill)

- **Corpo completo, sintaxe e exemplos:** `HARNESS_COMMANDS.md` (canônico; 14 comandos total)

---

## 🔴 REGRA 5: GITHUB / SHIP REGRAS NÃO NEGOCIÁVEIS
- Sempre `gh` CLI para API GitHub. Navegador só UI visual se pedido.
- Plano de commits SEMPRE aprovado pelo usuário ANTES.
- Push default `--no-verify`; `--force` só com 2 confirmações duplas.
- PR default **DRAFT**; nunca mergeia automaticamente; base = default branch do repo.
- NUNCA commita `.env*` com valores reais, secrets, PII.
- NUNCA desabilita teste/job com `continue-on-error` para mascarar falha sem aprovação.
- **Multi-PR hierárquico:** usar `gh-stack` CLI para links/ordem em PRs parciais.
- **Corpo completo + gh-stack workflow:** `HARNESS_RULES.md` §🔴 GITHUB INTEGRATION / SHIP RULES + Appendix gh-stack

---

## 🟢 REGRA 6: FERRAMENTAS PREFERENCIAIS (sistema/cli)
| Sistema | Ferramenta |
|---|---|
| GitHub | `gh` CLI + `gh-stack` para multi-PR hierárquico |
| Linear/Jira/Confluence | APIs GraphQL/REST via env vars (FLOCKR_LINEAR_API_KEY, DO_JIRA_*, DO_CONFLUENCE_*) |
| Figma | Figma REST API → LAION_FIGMA_PAT |
| Railway / Vercel | seus CLIs; 1º uso confirma conta logada |
| Nx | SEMPRE `--tui false` |
| CLIs genéricas | flags `-y`, `--non-interactive`, `--tui false`, `--no-tty`. Evitar prompts interrompidos. |
| Browser integrado | só sites genéricos. Produtos específicos usar API. |

- **Corpo completo:** `HARNESS_RULES.md` §🟢 FERRAMENTAS PREFERENCIAIS

---

## 🟡 REGRA 7: BLAST RADIUS 10 ARQUIVOS + DECISION LOG
- Task tocar > 10 arquivos → justificar CADA um em decision.log.
- Toda decisão não trivial (trade-off, exceção, arquivos não previstos, mutabilidade hot path) → `decisions.log.jsonl` com data/task-id/alternativas/razão.
- **Corpo completo:** `HARNESS_RULES.md` §🟡 BLAST RADIUS + §🟡 DECISIONS LOG SEMPRE

---

## 🟢 REGRA 7.5: TOKEN REDUCTION (CAVEAN-STYLE 5 HEURÍSTICAS)
**GOAL:** reduzir tokens sem perder semântica. Bypass global: `export HARNESS_FULL_OUTPUT=1`.
| H# | Quando aplicar | Helper | Ação |
|---|---|---|---|
| H1 | `git diff` / `git show` output grande | `\| harness_tr_diff` | Só linhas +/- changed (sem headers ---/+++/@@). Cap HARNESS_TR_DIFF_MAX_LINES=500. |
| H2 | Read tool de arquivo >300 linhas | `cat arquivo \| harness_tr_read TOTAL_LINES` | Trunca em 300 linhas + aviso `[...TRUNCADO lines X-Y]`. Bypass: passar offset/Limit no Read tool. |
| H3 | Output com muitas blank lines / trailing ws | `\| harness_tr_collapse_blank` | ≥2 blank lines → 1; strip trailing whitespace. |
| H4 | RunCommand stdout/stderr MUITO longo (builds, logs) | `\| harness_tr_stdout` | Cap chars HARNESS_TR_STDOUT_MAX_CHARS=4000 + footer aviso. |
| H5 | Grep default metadata verbose | `harness_tr_grep PATTERN PATH [type]` | lines-only match; default context=0. Ajustar via HARNESS_TR_GREP_CONTEXT. |

**Helpers definidos em:** `~/.trae/contracts/harness_sessions_contract.sh` (sourcear antes de usar).

---

## 🟢 REGRA 7.75: MVP SCRIPT MODE (DEEPSEEK-INSPIRED, SEM OVERENGENHARIA)

**PROBLEMA:** Fluxo Read → Grep → Edit → Write demora N turnos chat-tool. Cada turno = 1 roundtrip LLM + 1 tool call = mais lento + mais caro.

**REGRA MVP:** Quando o batch lógico for ≥3 tool calls QUE SÃO PURAMENTE LOCAIS (Read, cat, grep, sed, python, Write equivalente, git status/diff — tudo o que dá pra rodar em 1 RunCommand bash/node), escreva **1 script curto (≤20 linhas bash ou ≤40 linhas node)** e execute tudo em **1 ÚNICA tool call RunCommand**.

### Quando usar Script Mode
- Sim: Ler 3 arquivos, grep um pattern, fazer substituição em massa, gravar diff.
- Sim: Criar 5 arquivos boilerplate de uma vez (com python heredoc).
- Sim: Batch de pequenos ajustes + validação de sintaxe.
- **NÃO usar:** Precisa de interação humana no meio, precisa de browser/UI, precisa de escrita em múltiplos worktrees.

### Workflow padrão (3 passos)
1. **Descreva o batch em 1 bullet PT-BR** antes de rodar: "Batch Script Mode: Ler A,B,C; grep pattern X; substituir old→new em A; write diff.txt report."
2. **Escreva o script em 1 RunCommand com fail-fast:** `set -euo pipefail` + tudo atômico.
3. **No final do script, imprima um relatório curto (≤15 linhas):** "Arquivos alterados: 3. Linhas modificadas: 12. Diff head-5: ...". Não imprima outputs gigantes.

### Exemplo real (mesmo da task T1 route handler anterior)
**ANTES (3 turnos, 3 tool calls separados):**
- Turno1: Read `route.ts` → recebe 200 linhas
- Turno2: Grep `fetch` no `route.ts` → recebe 5 matches
- Turno3: Edit old_string/new_string no `route.ts`

**DEPOIS (1 turno, SCRIPT MODE):**
```bash
# 1 RunCommand só. Todos os passos juntos. Fail-fast.
set -euo pipefail
WT=/home/laion/code/flockr/Lumos.worktrees/test-worktree
FILE="$WT/apps/platform/app/api/health/route.ts"

# Passo1: Ler e contar linhas (anterior = Read)
LINES=$(wc -l < "$FILE")
echo "INFO: route.ts tem $LINES linhas"

# Passo2: Grep fetch + health pattern (anterior = Grep)
echo "MATCHES fetch/gzip:"
grep -nH "fetch\|gzip" "$FILE" || true

# Passo3: Substituição atômica (anterior = Edit)
python3 - "$FILE" <<'PY'
import sys
p = sys.argv[1]
with open(p) as f: c = f.read()
old = 'export const runtime = "nodejs"'
new = 'export const runtime = "edge"\nexport const dynamic = "force-dynamic"'
assert old in c, "old_string nao encontrado; abortando sem alterar"
c2 = c.replace(old, new, 1)
with open(p,"w") as f: f.write(c2)
PY

# Relatório curto (≤15 linhas)
echo "=== BATCH OK: 1 arquivo alterado ==="
git -C "$WT" diff --stat "$FILE"
```

### Limites MVP (NÃO implementar agora)
- Sem worker thread isolado (isolated-vm): não precisa.
- Sem gerar .d.ts de SDK dinâmico: não precisa.
- Sem `run_code` transport único: reutiliza RunCommand normal.
- Se script falhar → rollback manual ou volte para "1 tool call por vez" normal.

### Anti-padrões a evitar
- Não escreva scripts de >50 linhas: quebre em 2 batches.
- Não imprima saídas de >2000 chars no stdout do script: aplique H4 `| harness_tr_stdout`.
- Não misture interação dentro do script.

---

## 🟢 REGRA 7.8: REGISTRY DE BINDING GLOBAL É JSONL (ÚNICA FONTE: REGISTRY.JSONL)

**REGISTRY_PATH canônico:** `$HOME/.trae/bindings/registry.jsonl` (**NÃO existe mais registry.md**, deletado em 2026-08-30, sem dual-write, sem drift).

**1 entry = 1 linha JSONL schema v1:**
```
{ts ISO8601, event:BIND_BOOTSTRAP|BIND_APPEND|BIND_FLAGS_UPDATE, session_id,
 status: BOUND|UNBOUND|FLAGS, worktree_root, workspace_name?, worktree_slug?,
 branch?, friendly_name?, harness_session_dir?, harness_workspace_shared?,
 workspace_file?, reason?, flags:{LANG_PT_CHECK:ENABLED|DISABLED}, data:{extra...}, _v:1}
```

**ESCRITA (única maneira permitida — NÃO use Edit/Write manual):**
```bash
source $HOME/.trae/contracts/harness_sessions_contract.sh
harness_registry_append_jsonl "<sess-id>" "BOUND" "/abs/wt" \
  '{"workspace_name":"Flockr","worktree_slug":"Lumos__x","friendly_name":"feat-abc",
    "harness_session_dir":"/abs/sess","harness_workspace_shared":"/abs/ws",
    "workspace_file":"/abs/Flockr.code-workspace","branch":"feat/x","reason":"sm explicit",
    "flags":{"LANG_PT_CHECK":"DISABLED"}}'
```
- Dedup sha256 por linha (idempotente). JSON safe python3 heredoc.

**LEITURA (única maneira — não awk/grep manual):**
```bash
source harness_sessions_contract.sh
harness_registry_lookup_last "sess-abc123"  # → full JSON entry indentado
# extrair campo:
harness_registry_lookup_last "sess-abc123" | jq -r .worktree_root
# flags.LANG_PT_CHECK:
harness_registry_lookup_last "sess-abc123" | jq -r '.flags.LANG_PT_CHECK // "ENABLED"'
```

**Anti-padrões (nunca faça):**
- ❌ `Edit $HOME/.trae/bindings/registry.jsonl old new`
- ❌ `echo "SESSION_ID=x..." >> registry.jsonl` (sem schema)
- ❌ awk/grep parse `WORKTREE_ROOT:` (formato legado extinto)

---

## 🟥 REGRA 8: SPEC + PARALELISMO (corpo em HARNESS_RULES)
- **SPEC**: substitui PRD legacy; 4 fontes input (existente / ticket URL / PRD Flockr path / inline breve); 7 seções canônicas + YAML frontmatter required fields; gate **Approved obrigatório** ANTES scope capture no §0.5 do harness-scrum-master; override SPEC-OVERRIDE com log em decisions.
- **Paralelismo:** Kahn waves + conflict graph coloring + file locks + single-writer shared artifacts. Cap 4 paralelo. Se overhead > serial, KISS vence.
- **Corpo completo:** `HARNESS_RULES.md` §🔴 PARALELISMO + §🟣 SPEC Rules (gate + validation + approval loop)

---

## 🔴 REGRA 9: PII + SEGURANÇA (CORPO COMPLETO EM engineering-contracts §2)
- NUNCA loga/persiste raw email, email body, secrets, JWT, tokens, chaves Stripe/Supabase.
- Hashing de correlação PII: `NOTIFICATION_PII_HASH_SECRET` (exemplo pattern).
- Toda tabela Postgres nova: ENABLE RLS + policies. (Solicitado: agora é regra global §17).
- **Corpo completo:** `engineering-contracts` SKILL §2 (Security & PII compliance) + §17 (Supabase RLS default)
