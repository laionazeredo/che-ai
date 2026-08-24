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
1. **`/home/laion/.trae/HARNESS_RULES.md`** → Fluxo do harness, worktree-first, gates, paralelismo, PRD G1-G10, ship/gh rules.
2. **`/home/laion/.trae/skills/engineering-contracts/SKILL.md`** → 14 regras de engenharia com precedência ordenada, DbC, TDD, SOLID, strong typing, security/PII, RLS, conventional commits, agilidade BDD, code review optimization.
3. **`/home/laion/.trae/HARNESS_COMMANDS.md`** → 13 comandos /harness-* com sintaxe + arquitetura commands vs skills.

---

## 🟥 REGRA 0: WORKTREE-FIRST
- NÃO escreva código NEM rode comandos sem saber o worktree exato.
- Se worktree não foi fornecido: **PARE, PERGUNTE o caminho absoluto.**
- Explícito "não usar worktree" só procede com confirmação dupla.
- **Corpo completo:** `HARNESS_RULES.md` §🔴 WORKTREE-FIRST ENFORCEMENT

---

## 🟥 REGRA 1: DIRETÓRIO DE SAÍDA
- Tudo (spec, envelope, graph, decisions, summary, plans) → **`<WORKTREE_ROOT>/.trae/<task-id>/`**.
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
- **Início (especificação):** `/harness-prd` → PRD evidence-based com G1-G10 (UK/GDPR/GBP/RLS)
- **Implementação feature/longa:** `/harness-start` (auto serial vs parallel) OU `/harness-parallel` (force parallel-or-bust)
- **Bug fix:** `/harness-fix` (loop científico; reproduz ANTES)
- **Ship:** `/harness-ship` (commits atômicos conventional, push --no-verify, PR DRAFT + gh-stack se múltiplos PRs)
- **Review/comments/CI:** `/harness-review`, `/harness-pr-comments`, `/harness-ci-fix`
- **Operações leves:** `/harness-status`, `/harness-skip`, `/harness-decisions`, `/harness-summary`, `/harness-abort` (inline, NÃO viram skill)

- **Corpo completo, sintaxe e exemplos:** `HARNESS_COMMANDS.md` (canônico; 13 comandos total)

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
- Toda decisão não trivial (trade-off, exceção, arquivos não previstos, mutabilidade hot path) → `decision.log.md` com data/task-id/alternativas/razão.
- **Corpo completo:** `HARNESS_RULES.md` §🟡 BLAST RADIUS + §🟡 DECISIONS LOG SEMPRE

---

## 🟥 REGRA 8: PRD + PARALELISMO (corpo em HARNESS_RULES)
- PRD: análise repo 4D (Performance/Security/Scalability/Maintainability) ANTES de perguntas. 4 lotes. G1-G10 P0 bloqueantes.
- Paralelismo: Kahn waves + conflict graph coloring + file locks + single-writer shared artifacts. Cap 4 paralelo. Se overhead > serial, KISS vence.
- **Corpo completo:** `HARNESS_RULES.md` §🔴 PARALELISMO + §🟣 PRD Rules

---

## 🔴 REGRA 9: PII + SEGURANÇA (CORPO COMPLETO EM engineering-contracts §2)
- NUNCA loga/persiste raw email, email body, secrets, JWT, tokens, chaves Stripe/Supabase.
- Hashing de correlação PII: `NOTIFICATION_PII_HASH_SECRET` (exemplo pattern).
- Toda tabela Postgres nova: ENABLE RLS + policies. (Solicitado: agora é regra global §17).
- **Corpo completo:** `engineering-contracts` SKILL §2 (Security & PII compliance) + §17 (Supabase RLS default)
