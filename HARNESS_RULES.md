---
name: "HARNESS GLOBAL RULES"
description: "Global rules (process + flow) for the Flockr harness. Loaded as user_rules on every session. Defines worktree-first enforcement, .trae/<task-id>/ output directory, agile BDD process, GitHub/ship + gh-stack, parallelism and PRD G1-G10 critical gaps. Pure engineering rules (precedence 1-14, DbC, TDD, SOLID, strong typing, security, conventional commits, RLS, code review optimization) now live in the engineering-contracts SKILL and must NOT be duplicated here."
---

# 🌍 Harness — Global Process & Flow Rules (Always-On)

These rules apply to **every session, every repo, every worktree.**
They have HIGHER precedence than any repo-level `AGENTS.md` or `CLAUDE.md` when a conflict occurs.

> **Conteúdo deste arquivo (PROCESSO + FLUXO apenas — NÃO duplica regras de engenharia pura):**
> - Regras de operação do harness: worktree-first, .trae output, ordem do time ágil, gates, timeouts
> - Paralelismo (Kahn + conflict graph + locks)
> - PRD generation rules + G1-G10 critical gap check (UK/GDPR/GBP/RLS)
> - GitHub integration + ship + **gh-stack multi-PR hierárquico**
> - Ferramentas preferenciais por integração
>
> **REGRAS PURAS DE ENGENHARIA (14 precedência, KISS/YAGNI, strong typing, DbC, TDD, SOLID, agile BDD, security, PII, conventional commits, Supabase RLS default, code review optimization, max 2 lines comments) → CANÔNICO = `engineering-contracts` SKILL. NÃO DUPLICAR AQUI.**

---

## 🔴 WORKTREE-FIRST ENFORCEMENT (não negocia)

> O agente SEMPRE prefere trabalhar em Git worktree. NUNCA atue em código sem saber exatamente EM QUAL worktree.

1. Se o usuário forneceu explicitamente um caminho de worktree na requisição →
   - Confirme que existe e contém `.git` dentro.
   - Use exclusivamente esse caminho como `WORKTREE_ROOT` para toda a sessão.
2. Se o usuário NÃO forneceu um caminho de worktree →
   - **PARE IMEDIATAMENTE.** Não escreva código, não crie arquivos, não rode comandos.
   - **PERGUNTE ao usuário via ferramenta apropriada:**
     - "Em qual Git worktree devo executar esta tarefa? Forneça o caminho absoluto."
   - Aguarde a resposta. Não prossiga até tê-la.
   - Somente se o usuário disser explicitamente "não usar worktree, usar raiz do repo" é que você pode proceder, e somente após confirmação explícita.

---

## 🔴 DIRETÓRIO DE SAÍDA DO HARNESS

> TUDO o que o harness produzir de documentos durante a execução (spec, tasks, envelope, decision.log, testes manuais, resumo final, PR stacks gh-stack) deve ir obrigatoriamente para `.trae/<task-id>/` DENTRO DO WORKTREE.

1. Determinado o `WORKTREE_ROOT` e o `<task-id>` (slug da feature/bug):
   - Crie imediatamente o diretório `<WORKTREE_ROOT>/.trae/<task-id>/` se ele não existir.
2. **Arquivos obrigatórios que SEMPRE são criados neste diretório:**
   - `session.md` — metadata da sessão
   - `task_graph.md` — grafo completo de tarefas, dependências, status, gh-stack PR plan se >1 PR
   - `task_envelope_<TASK-ID>.md` — UM por tarefa, antes de começar
   - `decision.log.md` — append a cada decisão não óbvia / trade-off
   - `manual_test_plan.md` — no final, quando todas tasks forem DONE
   - `final_summary.md` — resumo final e estatísticas
   - `gh_stack_plan.md` — (OPCIONAL, se múltiplos PRs parciais) → plano hierárquico de stacks gh-stack
3. **NUNCA** crie esses arquivos em outros locais (docs/, raiz do repo, pastas de packages) a menos que usuário pede explicitamente.
4. `.trae/` não precisa ser commitado. Se o repo já tiver `.trae/` no `.gitignore`, respeite.

---

## 🟠 TIME ÁGIL SIMULADO — ORDEM OBRIGATÓRIA DE AGENTES

> **FILOSOFIA ÁGIL BDD NO CORE (HARD RULE):**
> - SEMPRE desenvolva pequenos incrementos, guiados por testes (TDD + BDD).
> - NUNCA antecipe edge cases ou futuro não explicitamente no escopo atual.
> - Concentre-se EXATAMENTE no comportamento solicitado (BDD scenarios).
> - Entregue a menor unidade de valor que valida o comportamento pedido.
> - Se escopo for grande: QUEBRE em entregas parciais (múltiplos PRs auto-contidos) e use **gh-stack CLI** para manter hierarquia/ordem entre PRs.
> - Estrutura do código: fácil de entender, simples de evoluir, respeita SOLID, **sem quebrar comportamento existente.**
> - Code-review optimization: código limpo, não verborrágico, max 2 linhas de comentário bloco por arquivo (exceto docstrings públicas de contratos).
> - **Corpo completo destas regras + thresholds:** `engineering-contracts` SKILL §15 (Agile BDD Incremental) + §16 (Code Review Optimization)

Para QUALQUER implementação de feature / bugfix com mais de um passo:
1. **SCRUM MASTER (`harness-scrum-master`):**
   - **Preflight 0.5** — Valida se já existe PRD Approved. Se não → recomenda rodar `/harness-prd` antes.
   - **Entende escopo → valida ACs →** (se grande) **planeja gh-stack multi-PR** → monta TASK GRAPH (ou aprova lista existente) → cria TASK ENVELOPE por task.
2. **DEVELOPER (`harness-developer`):** SOMENTE chamado por SM, com ENVELOPE formal.
   - Primeiro invoca `engineering-contracts`.
   - Repo Onboarding obrigatório (Q1-Q5: lang/framework/test-stack/graphify-docs-read/Stack Match IDE skills).
   - Contract → Test → Implement (ATDD + TDD, incremento pequeno).
3. **SCOPE VALIDATION (SM + Dev):** SM compara saída do Dev com ENVELOPE.
4. **QA (`harness-qa`):** Detecta stack → Build → Lint → Typecheck → Test (affectados). Relatório estruturado. Não corrige código diretamente.
5. **COMPLIANCE LIGHT (`harness-compliance` stage=per-task):** Diff da task. Secrets/PII/SQLInjection.
6. Repete T1, T2, T3... por task.
7. **FINAL:** Compliance HEAVY (`stage=final` varre diff completo) → `manual_test_plan.md` → (se gh-stack) aplica hierarquia → `final_summary.md` → avisa o usuário.

**NUNCA pule etapas. NUNCA invoque Developer sem ENVELOPE. NUNCA invoque QA antes de SM aprovar escopo. NUNCA encerre sem Compliance final.**

---

## 🟡 BLAST RADIUS — HEURÍSTICA DE 10 ARQUIVOS

- Se uma task for modificar MAIS de 10 arquivos (novos ou editados):
  1. PARE.
  2. Adicione entrada em `decision.log.md` justificando CADA arquivo.
  3. Volte para SM que avalia se é necessário mesmo ou se deve requebrar (via gh-stack múltiplos PRs parciais).
- Adicionalmente: se uma task tocar arquivo FORA da lista "blast radius" do ENVELOPE → entrada obrigatória em `decision.log.md` + aprovação SM ANTES de seguir.

---

## 🟡 DECISIONS LOG SEMPRE

Sempre que você tomar uma decisão não trivial (trade-off, exceção a regra, arquivos não previstos, mutabilidade em hot path, RLS policy em nova tabela, escolha de criar multi-PR stack vs single PR, etc.):
1. Escreva em `<WORKTREE_ROOT>/.trae/<task-id>/decision.log.md`.
2. Formato: `[YYYY-MM-DD HH:MM] [TASK-ID] <título curto>` → depois detalhe + alternativas consideradas + porquê escolheu.

Isso previne "por que diabos isso foi feito assim?" 2 meses depois.

---

## 🟢 LOOP TIME-OUTS (UNIFICADO — TUDO AQUI)

> Esta é a seção ÚNICA sobre timeouts de loop. Antes estava duplicada em 2 lugares → agora unificada.

Em QUALQUER loop/iterações entre agentes, a regra é:

| Loop / Cenário | Limite de iterações SEM PROGRESSO CLARO | Quando parar? | O que fazer quando parar? |
|---|---|---|---|
| **Geral (Dev ↔ SM, Dev ↔ QA, Dev ↔ Compliance Light)** | **2 retornos consecutivos** sem progresso | Qualquer lado repetir mesma correção/same-error 2x | **PAUSE e PERGUNTE ao usuário** direção/novo contexto. Não loopar indefinido gastando tokens. |
| **Debug harness bugfix (`/harness-fix`)** | **5 iterações** do loop Hipótese→Instrumentar→Reproduzir→Corrigir | 5 hipóteses refutadas ou nenhuma reprodução após 5 | **Pausar + relatar hipóteses já refutadas + próximos passos sugeridos** ao usuário. |
| **CI Fix harness (`/harness-ci-fix`)** | **3 planos de fix aplicados** com CI ainda falhando | 3 fixes aplicados (mesma categoria) = não resolveu | **Pause e PERGUNTE** se usuário quer nova abordagem ou mais contexto. |

---

## 🟢 IDIOMA (SÓ AQUI — NÃO DUPLICAR)

- Todo código-fonte (identificadores, comentários, strings de mensagem): **inglês**.
- Toda mensagem de commit / descrição de PR / corpo do gh-stack PR hierarchy: **inglês**, conventional commits.
- Toda resposta ao usuário, perguntas, resumos em conversa: **português do Brasil**.
- Todo documento interno do harness (task_graph, envelopes, decisions, summaries, gh_stack_plan): **inglês**.

---

## 🔴 WORKTREE SCOPED SESSION (Não negocia — 1 sessão = 1 worktree)

> **Contrato corpo completo**: `engineering-contracts` SKILL §19. Aqui só o gate de processo/enforcement do harness.

### Preflight obrigatório (ANTES de qualquer comando, leitura de arquivo, git operation, Glob/Grep):

1. **Ler Level 1 GLOBAL INDEX (resolver chicken-and-egg):** Ler `$HOME/.trae/bindings/registry.md`. Procurar ÚLTIMA entrada STATUS=BOUND com SESSION_ID=<atual>. Extrair WORKTREE_ROOT dessa entrada.
   - Se encontrar → usar WORKTREE_ROOT dele como SCOPE ABSOLUTO sessão.
   - Se NÃO encontrar → seguir regra §19.2 (ordem precedência: menção explícita user → arquivos abertos → env workdirs → AskUserQuestion com ≤2 opções. Perguntar sempre ambíguo; NUNCA chute.

2. **Escrever binding em BOTH LEVELS após primeira aprovação (atomically:**
   - **Level 1:** Append (append-only entry to `registry.md with delimiter ---`. NEVER overwrite BOUND entries (keep history).
   - **Level 2:** Inside bound worktree: mkdir `.trae/bindings/; write `session-<SESSION_ID>.md (PER SESSION_ID).
   - 2 arquivos criados. 1 por SESSION_ID.
   - Mais detalhes contract re-binding corpo está em contracts §19. Aqui só gates processo/enforcement. Aqui gate do harness.

3. **Scissor check A CADA OPERAÇÃO de arquivo / git (agente + hook 1 global (automático:**
   - Dupla verificação. 2 camadas. Alvo path começa com WORKTREE_ROOT? Se NÃO → BLOQUEAR.
   - Saídas: (a) user confirma "sim, escrever fora scope logged decision.log, ou (b) perguntar Switch worktree? A = Switch / B = Cancel operação".
   - **Nunca operar cross-worktree silenciosamente (ler ou escrever).

4. **Trocar worktree re-bind:**
   - Confirmação EXPLÍCITA do user: Sim, trocar X agora".
   - OLD Level1 BOUND entry → STATUS=RELEASED + RELEASED_AT + NEXT_WORKTREE_ROOT + append new BOUND entry NEW Level2 OLD file STATUS=RELEASED + NEXT_BINDING; NEW Level2 NEW BOUND + PREV_BINDING.
   - Anunciar troca próximo 📍 Status output.

5. **Pre-send trimmer de refs:**
   - Se draft output tem refs clickable ≥2 worktrees DIFERENTES E user NÃO pediu comparação → PARAR. Apagar refs worktree incorreto. Manter apenas refs do BOUND WORKTREE_ROOT.

> **Enforcement AUTOMÁTICO GLOBAL (§19 2-LEVEL LAYOUT):**
>   - **Level 1 (GLOBAL INDEX resolver chicken-and-egg + FLAGS per sessão):** `$HOME/.trae/bindings/registry.md` — entry por SESSION_ID, append-only, NÃO por worktree. `SESSION_ID → WORKTREE_ROOT` lookup sem precisar conhecer worktree. Field opcional `FLAGS: LANG_PT_CHECK=DISABLED` (omitido=ENABLED) para Hook3 por sessão.
>   - **Level 2 (PER-SESSION DETAIL inside worktree):** `<WORKTREE_ROOT>/.trae/bindings/session-<SESSION_ID>.md` — histórico/auditoria re-binding chain + mirror FLAGS p/ leitura humana.
>   - **Hook 1 (PreToolUse):** [pretooluse-worktree-binding.sh](file:///home/laion/.trae/hooks/pretooluse-worktree-binding.sh) em [hooks.json](file:///home/laion/.trae/hooks.json#L5) — usa SÓ Level 1 para scissor check. Zero lock contention, resolve catch22, multi-sessão paralela works.
>   - **Hook 3 (PostToolUse WARN-only):** [posttooluse-lang-pt-check.sh](file:///home/laion/.trae/hooks/posttooluse-lang-pt-check.sh) em [hooks.json](file:///home/laion/.trae/hooks.json#L22) — detecta texto PT-BR em arquivos escritos via Edit/Write (4+ stopwords PT OU 2+ linhas c/ acentos + 2 stopwords). NUNCA corrige automaticamente, NUNCA bloqueia (exit0 sempre). Decision=warn + adicionalContext instrui agente a **AskUserQuestion obrigatório**: (A) Traduzir p/ inglês, (B) Manter PT confirmado, (C) Desabilitar Hook3 nesta sessão (append flag `FLAGS: LANG_PT_CHECK=DISABLED` no Level 1 registry + Level 2 mirror).

---

## 🔴 RESPOSTAS ENXUTAS + DEEP-DIVE GATE (Não negocia)

> Corpo completo desta regra (orçamento de palavras, seções permitidas, regra de ≤2 opções) vive SÓ em `engineering-contracts` SKILL §18. Aqui só o processo/gate do harness.

**Gates obrigatórios antes de enviar QUALQUER resposta ao usuário:**

1. **Trimmer obrigatório**: depois que o agente escrever sua resposta → rodar mentalmente "cortar TUDO que não responde diretamente o que o usuário perguntou nesta mensagem?" Cortar.
   - NÃO listar 5 opções → no máximo 2 (ou escolher a melhor e pedir OK).
   - NÃO explicar background / "porquê escolhi a lib" a menos que perguntado.
   - NÃO listar 8 edge cases → no máximo 2 (P0/CRITICAL). Todo resto: "Se surgir intermediários, voltamos aqui."
   - NÃO planos gigantes → mostrar **3 passos visíveis** + 1 oferta de aprofundar se quiser os restantes.

2. **Shape canônico (4 seções OPCIONAIS, FORMATO PARA LEITURA DIAGONAL)**:
   ```markdown
   ### 📍 Status
   <1-2 frases claras: o que foi feito / estado AGORA>

   ### 🧩 Mudanças-chave (max 3 bullets)
   • **<Escopo 1 negrito>**: <1 linha, 1 pensamento>
   • **<Escopo 2 negrito>**: <1 linha>
   • **<Escopo 3 negrito>**: <1 linha>

   ### 🔗 Refs (só os 2-5 mais importantes)
   • [<NOME_ARQUIVO curto>](file:///path/absoluto#Lx-Ly)
   • ...

   ### ❓ Próximos / Aprofundar
   Quer aprofundar em **<UMA ÚNICA coisa>**?
   ```
   **Formatação não-negociável (dentro do Shape):**
   - **TODOS os bullets, SEMPRE.** 3+ frases consecutivas sem bullet = violação (pare e formate).
   - **Negrito ( `**X**` )** em todo substantivo/label chave.
   - *Itálico ( `_X_` )* só para ressalvas/nuances.
   - `<u>Sublinhado</u>` = MÁXIMO 1 por output, reservado para a CALL-TO-ACTION MAIS CRÍTICA ou consequência 🔴.
   - 1 pensamento por bullet = ≤2 linhas. Se for maior → quebre em sub-bullets.
   - **Nunca parede de texto única.** Sempre quebrar em 2-4 seções lógicas com `##` / `###`.

3. **Oferta de deep-dive = SÓ 1 tópico por vez**. NÃO montar cardápio de 5 opções de aprofundamento.

4. **PR Body (harness-ship) lean enforcement**: esta regra complementa — PR body em 3 partes (3 paras max impl + key review points + test pointers). Corpo em `harness-ship` SKILL.

---

## 🔴 GITHUB INTEGRATION / SHIP RULES (Não negocia) + gh-stack MULTI-PR

### A) Ship → Commits padrão
Para qualquer comando `/harness-ship` ou afins:
- Use SEMPRE `gh` CLI (regras do usuário: GitHub = gh CLI).
- Commits atômicos + conventional commits.
  - **Corpo completo conventional commits (tipos válidos + regex + exemplos):** `engineering-contracts` SKILL Appendix B
- Plano de commits SEMPRE é apresentado ao usuário ANTES de qualquer `git commit`.
- Esperar aprovação EXPLÍCITA do usuário antes de commitar.

### B) Push
- SEMPRE `git push --no-verify` (regras do usuário). Push normal só com aprovação explícita.
- Branch remota não existir? `--set-upstream origin <branch>` para criar.

### C) Abrir PR (Single)
- SEMPRE abrir PR no modo **DRAFT** (não-ready-for-review) por padrão. Muda para "ready" apenas quando usuário diz explicitamente.
- Branch base = default branch do repo (`main`, `master` — detectar via `gh repo view --json defaultBranchRef`).
- Atribuir a PR para `@me` (o próprio usuário).
- **NÃO fazer merge** automaticamente. Ship pára na criação de DRAFT PR.
- **NÃO usar labels inexistentes** no repo. Só adicionar labels que já existem; não criar novas.

### D) gh-stack HIERARQUIA DE PRS PARCIAIS (NOVO — obrigatório quando scope grande > 1 PR)
> **Contexto:** `gh-stack` (https://github.com/github/gh-stack) = extensão oficial do gh CLI que cria links e hierarquia entre PRs relacionadas, mantendo ordem e dependências entre branches sequenciais. Ideal para quando o Scrum Master quebra um scope grande em múltiplos PRs auto-contidos.
>
> **Corpo completo do workflow (when-to-use + commands + examples):** `engineering-contracts` SKILL Appendix C — gh-stack Workflow Reference.

**Hard rules do gh-stack no harness:**
1. **QUANDO usar o gh-stack (SM decide no planejamento TASK GRAPH):**
   - Task Graph tiver ≥3 tasks que formam unidades de PR claramente separáveis.
   - OU: Usuário explicitamente pediu "entregar em múltiplos PRs".
   - OU: Uma única task tiver blast radius > 15 arquivos e SM decidir quebrar em 2+ PRs.
2. **Planejamento (SM cria arquivo `.trae/<task-id>/gh_stack_plan.md`) ANTES do Dev começar:**
   - Lista ordenada: `PR #N`, título, base branch, head branch, tasks cobertas, ACs do PR, reviewers opcionais, ordem de stack (base → topo).
   - Exemplo de estrutura: `[PR1 (base main)] contracts types → [PR2 (base PR1 branch)] service layer → [PR3 (base PR2 branch)] API + tests`.
   - Mostrar plano ao usuário para aprovação ANTES de Dev iniciar.
3. **Durante o ship (harness-ship executa em ORDEM da stack, de BAIXO para CIMA):**
   - Aplica commits atômicos, push, abre DRAFT PR individual para CADA nível da stack.
   - Usa `gh-stack` CLI para linkar PRs com relação de dependência (body de cada PR não-base mostra "Depends on: #PR-anterior" + gh-stack mantém graph hierarchy).
   - Atualiza `gh_stack_plan.md` com URLs dos PRs reais após cada abertura.
4. **Review + Merge:**
   - Reviewers leem PRs individualmente (de baixo para cima), pois cada um é small + autocontido.
   - Se PR do meio precisar de fix: faz no branch, rebaseia o topo automaticamente via `gh-stack rebase` (se disponível).
5. **Quando NÃO usar gh-stack:**
   - Apenas 1 PR (auto-contido).
   - Worktree com histórico muito confuso ou branches divergentes (KISS: single PR é mais simples).
   - Usuário explicitamente disse: "não usar gh-stack, single PR".

### E) Nunca faça isso no GitHub / Git
- `git commit --allow-empty` sem motivo + aprovação explícita.
- `git push --force` sem aprovação explícita dupla do usuário.
- Commit em branches `main`/`master`/`develop`/default diretamente. SEMPRE feature branch → PR.
- Commitar arquivos `.env*` com valores reais. Bloquear se houver pattern de secret.
- "Resolver" um CI failure colocando `continue-on-error: true` ou `.skip` em teste falhando para fazer passar sem aprovação do usuário.

---

## 🟢 FERRAMENTAS DE ACORDO COM PREFERÊNCIAS DO USUÁRIO

Sempre use a ferramenta / integração que o usuário definiu, por meio das APIs / CLIs correspondentes:

| Sistema | Ferramenta obrigatória | Observações |
|---|---|---|
| GitHub | `gh` CLI + `gh-stack` (hierarquia multi-PR) | Sem navegador para API calls. Navegador só para UI de review visual se pedido. |
| Jira / Confluence | API REST via `DO_JIRA_*` / `DO_CONFLUENCE_*` env vars | Sempre checar presença de vars. |
| Linear | GraphQL API → `FLOCKR_LINEAR_API_KEY` env var | Sempre checar presença. |
| Figma | Figma REST API → `LAION_FIGMA_PAT` env var | Sempre checar. |
| Railway | `railway` CLI | 1º uso: checkar conta logada + perguntar ao usuário se mantém. |
| Vercel | `vercel` CLI | 1º uso: checkar conta logada + perguntar ao usuário se mantém. |
| Nx | Sempre `--tui false` para travar sem TUI interativo. | `corepack pnpm nx <cmd> --tui false` |
| CLIs em geral | Procurar flags `-y`, `--non-interactive`, `--tui false`, `--no-tty`, `--yes` | Evitar prompts interrompidos. |
| Browser integrado do IDE | Apenas para sites genéricos. Para Atlassian/Linear/Figma/etc usar APIs acima. | |

---

## 🟠 HARNESS ESPECÍFICOS POR TIPO DE TAREFA

### Feature (harness normal): `/harness-start` → SM + Dev + QA + Compliance
- TASK GRAPH obrigatório.
- TASK ENVELOPE por task obrigatório.
- Repo onboarding Q1-Q5 antes de codar (inclui stack match IDE available_skills).
- Gates explícitos por task.
- Se SM detectar scope grande → gh-stack multi-PR plan (apresenta plano ao usuário para aprovar).

### Bug Fix (harness diferente): `/harness-fix` → Debugger expert
- **Primeira regra:** REPRODUZIR antes de qualquer análise profunda. Se não reproduzir → não codar, perguntar ao usuário contexto faltante.
- Loop: Hipótese → Instrumentar → Reproduzir → Analisar → Fixar → Verificar. (Limite 5 iterações, ver timeouts).
- Aplicar MINIMAL fix. NUNCA refatorar junto com bugfix. Refatoração = PR separada (ou gh-stack PR separado).
- Ao final: DEMONSTRAR (antes vs depois) ou prover guia passo-a-passo de reprodução para o usuário checar.

### Review: `/harness-review` PR link + ticket/descrição
- **4 categorias somente:** Runtime, Security/PII, Deps/blast-radius, Scope deviation.
- **Não é para pedantismo de estilo.** NITs, format, naming → CI já resolve. Não comentar.
- **Code-review optimization (ver `engineering-contracts` §16):** só comentar BLOCKING ou HIGH. Não "gostaria de outro nome".
- 1 achado = (severidade, categoria, arquivo:linha, snippet, razão, ação corretiva sugerida + snippet opcional).
- Não subir review oficial no GitHub a menos que usuário peça explicitamente.

### PR Comments: `/harness-pr-comments` PR link
- Classificar BOT vs HUMAN primeiro.
- HUMAN: CORRECTNESS / SECURITY / SCOPE_CREEP = implementar. QUESTION/NIT/DISCUSSION = resposta.
- Respostas em INGLÊS, educadas, sem tom argumentativo: agradecer → explicar razão → oferecer alternativa / follow-up PR.
- Não postar nada em GitHub automaticamente; usuário aprova relatório → só então subir.

### CI Fail: `/harness-ci-fix` run/PR URL
- Classificar **R1 a R9** categorias (R9 novo: Test mismatch intentional behavior change).
  - Lista oficial R1-R9: ver `harness-ci-fixer` SKILL §Classification (corpo oficial com exemplos).
- R7 = INFRA/EXTERNAL (secrets, npm 5xx, outage GH). Não codar. Reportar ao usuário.
- R9 = Test mismatch due to intentional AC/spec change → fix = atualizar teste(s) para novos ACs, NÃO reverter código. Exigir confirmação do usuário que ACs realmente mudaram.
- Demais categorias: plano de fix → apresentar ao usuário → aprovação → implementar mínimo.
- Verificar localmente equivalente. Push + re-trigger opcional.
- NUNCA desabilitar um teste ou job com `continue-on-error` para "mascarar" falha sem aprovação.
- Limite 3 planos (ver timeouts).

---

## 🔴 PARALELISMO — Regras Obrigatórias (Não Negocia)

### 🚀 Quando paralelizar é seguro (TODOS devem ser true)
1. `task_graph.md` tem **pelo menos 2 tasks**.
2. **TODOS** os envelopes de task têm **lista EXPLÍCITA e ENUMERADA de arquivos permitidos** (NÃO use globs `src/**/*` nem `packages/` — só paths concretos).
3. Pelo menos 2 tasks na **mesma onda Kahn (sem dependências mútuas)** têm **interseção vazia de arquivos**.
4. Worktree está **limpa de alterações não comitadas FORA dos envelopes** (ou usuário deu approve explícito).
5. Nenhum `.trae/_locks/*.lock.json` stale com estado `HELD` de sessão abortada anterior existe (se existir, purgar com approve do usuário).

### ❌ Quando NUNCA paralelizar (FALLBACK to serial)
1. Qualquer arquivo listado em mais de 1 task do mesmo mini-batch → **quebre em mini-batches separados via conflict graph coloring**.
2. Qualquer task com glob em blast-radius → **refuse paralelismo para essa onda**.
3. O usuário passou `--serial` flag.
4. `max_parallel` pedido > 4 → **limita a 4 + warning de segurança** (contexto e tokens crescem O(n)).
5. Compliance HEAVY, QA cross-file, ou merge-audit HIGH conflict → **rodam SINGLE-THREADED**.

### 🔒 Lock files & Single-writer rules
- **Blast-radius file locks:** `.trae/_locks/<hash>-<basename>.lock.json` → adquirir ANTES de invocar Dev, liberar APÓS gates passarem + merge-audit LOW/MEDIUM-confirmed.
- **Single writers for shared artifacts:**
  - `task_graph.md` status updates = **APENAS o dispatcher escreve**. Nenhum Dev paralelo toca nesse arquivo.
  - `session.md` = dispatcher append-only + SM escreve início/fim.
  - Decision.log = dispatcher apenda conflitos, SM apenda decisões.
  - Compliance reports por task = arquivos separados `compliance_<TASK_ID>.md`.
  - `gh_stack_plan.md` (se existir) = SÓ SM + Ship atualizam.
- Se um Dev paralelo escrever em um arquivo compartilhado listado em outro envelope: **merge-audit HIGH conflito → rollback dessa task + rerun serial**.

### 🧩 Algoritmo de paralelismo (executor dispatcher)
1. **Kahn topological sort** por dependências → ondas.
2. Dentro de cada onda: **conflict graph** (arestas = interseção de arquivos).
3. **Graph coloring greedy** → cada cor = mini-batch sem conflito de arquivo.
4. **Fan-out sub-agentes parallel**: `general_purpose_task` um por task no mini-batch corrente → isolado → escreve `dev_report_<TASK_ID>.md` → NÃO toca nos artefatos compartilhados.
5. **Merge audit por mini-batch** → confirma nenhum arquivo sobreposto foi escrito.
6. **Gates por task (serial por task, não por batch)** — SM valida SCOPE / QA / Compliance light individualmente, pois o estado da worktree é compartilhado e QA de T1 não pode afetar T3 no mesmo batch (eles têm arquivos disjuntos, ok).
7. Tasks falhadas → **sair do paralelismo e voltar para serial 1-por-1**.

### ⚖️ KISS vs Parallelismo (precedência)
Se parallel adicionar overhead de lock-contention ou > 2 vezes serial-fallback por batch → SM interrompe paralelismo e avisa usuário:
> "Paralelismo com <N> tasks teve 3 conflitos de arquivo em 2 ondas. Eficiência similar a serial. Deseja continuar paralelo ou fallback para serial total p/ evitar overhead?"
KISS ganha sempre. Parallel é OTIMIZAÇÃO, não OBRIGATORIEDADE.

---

## 🟣 PRD — Regras de Geração (Análise Crítica + Questionário Iterativo)

### Regra 0 — Análise de repo ANTES de qualquer pergunta
- `/harness-prd` NÃO começa com perguntas de produto.
- PRIMEIRO: rodar análise 4 dimensões (Performance, Security+PII, Scalability+Data, Maintainability) EVIDENCE-BASED (nomes de arquivos, linhas, padrões reais do worktree).
- Apresentar resumo executivo das 4 dimensões ao usuário EM PORTUGUÊS, com severidade por área + HIGH findings, ANTES da 1ª pergunta.
- Sem análise → não começa questionário. Hard blocker.

### Regra 1 — Fluxo rígido: 4 lotes de perguntas (não despeja tudo de uma vez)
- **Batch 1 (estratégia)**: Overview + Problem + Goals + Non-Goals. Espera respostas → follow-ups clarificantes.
- **Batch 2 (usuários + FRs)**: User stories table + FRs com edge cases + Idempotency/double-click.
- **Batch 3 (qualidade + dados + sistemas)**: NFR table + Data Model (tables + RLS) + Migrations + System Interactions + Mermaid.
- **Batch 4 (dedup + normalização + AC + open Qs)**: Dedup rules + Normalisation (GBP pence integer, UTC/London, E.164, email lowercase, UK postcode) + Acceptance Criteria checklist + Open Questions P0/P1/P2.

### Regra 2 — NUNCA pula seção do template; N/A com justificativa se não aplicável
- Template de 15 seções: Overview, Problem, Goals, Non-Goals, User Stories, FRs, NFRs, Data Model, System Interactions, Dedup, Normalisation, ACs, Open Questions.
- Se seção for "não aplicável", escrever `N/A — <1 frase explicando POR QUE não aplicável>` (ex: "N/A — feature é UI-only redirect, não altera banco de dados.").

### Regra 3 — Critical Gap Auto-Check (G1-G10) ANTES de montar PRD final
Depois de colher respostas, checar OBRIGATORIAMENTE:

| Gap | O que valida | Falha = P0? |
|---|---|---|
| G1 | User stories tem persona attendente OU declarado explicitamente "admin-only" em Non-Goals | ✅ P0 se audiências mistas |
| G2 | NFR data retention: GDPR UK default 12 meses ou 6 anos contábeis | ✅ P0 risco ICO |
| G3 | Moeda = GBP Pence Integer em NFR + Data Model + Normalisation (NUNCA float) | ✅ P0 £ bug 0.01 |
| G4 | Nova tabela tem ENABLE RLS + Supabase/Postgres policies declaradas em Data Model + AC | ✅ P0 Flockr obrigatório RLS (ver também `engineering-contracts` §17 — regra global de RLS default) |
| G5 | PII raw nunca logado declarado em NFR Observability (hash + pattern) | ✅ P0 UK GDPR |
| G6 | Double click / idempotency AC existe | 🟡 P1 duplicações |
| G7 | Permission denied (403) AC existe por role | ✅ P0 segurança |
| G8 | Non-Goals tem ≥2 itens explícitos OOS | 🟡 P1 scope creep |
| G9 | Serviço externo falha = retry policy + degrade vs hard-fail | 🟡 P1 / P0 se money |
| G10 | Open Questions P0 > 3 | Se sim → fechar P0 ANTES de marcar PRD "Review" |

Qualquer P0 não resolvido = NÃO monta PRD. Loop de volta até fechar.

### Regra 4 — Ordem de execução recomendada
Fluxo de trabalho ideal (não obrigatório, mas sugerido):
```
1. /harness-prd → gera PRD Draft (com análise crítica + questionário)
2. Stakeholder review → fecha Open Questions P0
3. /harness-prd edita → move status: Draft → Review → Approved
4. (SM valida approved PRD no preflight 0.5) → /harness-start OU /harness-parallel com PRD approved → decompõe TASK GRAPH → executa
   - Se scope grande durante TASK GRAPH → SM planeja gh-stack multi-PR e salva gh_stack_plan.md p/ aprovação
5. /harness-ship → (single OU stack) commit(s) atômico(s) + push + PR(s) DRAFT(s) hierárquicos via gh-stack
6. /harness-review + /harness-pr-comments → ciclo de code review
7. /harness-ci-fix (se CI quebrar) → finaliza
```

---

## 🌍 COMMANDS & SKILLS ARCHITECTURE REFERENCE

> **A referência COMPLETA + sintaxe + exemplos dos 13 comandos está em:** `HARNESS_COMMANDS.md` (canônico). NÃO DUPLICAR aqui.
>
> Visão rápida (13 comandos total):
> - 8 **pesados (workflow)** → wrapper de validação preflight + `Skill(...)`:
>   `/harness-prd` | `/harness-start` | `/harness-parallel` | `/harness-ship` | `/harness-fix` | `/harness-review` | `/harness-pr-comments` | `/harness-ci-fix`
> - 5 **leves (operação em arquivo)**: inline, NÃO viram skill (ler/escrever markdown, KISS → não criar skill de 3 linhas):
>   `/harness-status` | `/harness-skip` | `/harness-decisions` | `/harness-summary` | `/harness-abort`
> - Corpo completo mapping command → skill + arquitetura explicada: `HARNESS_COMMANDS.md` §Architecture Commands vs Skills.

---

Fim das regras de processo e fluxo.
