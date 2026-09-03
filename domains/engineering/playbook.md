# Domain: `engineering` · Playbook obrigatório (não pula etapas)

Pipeline de desenvolvimento de features e bugfixes. **NÃO PULA ETAPAS.** Sempre completo = ship sem dor.

---

## Etapa 0: Spec Approved & Bounded Context (SM gates 0→1.5)
Entrada obrigatória: SPEC aprovado com YAML frontmatter (domain = engineering por default).
Sub-etapas (todas feitas pelo Scrum Master §0→1.5, NÃO pelo dev):
- 0.1 Binding 2-level aprovado (workspace + worktree).
- 0.2 ADR se `change_class ∈ {arch, platform, large-migration}`.
- 0.3 Task graph topológico com envelopes atômicos + file locks (onde aplicável paralelismo Kahn).
- 0.4 QA stack detectada + compliance light plan.
- 0.5 **GATE Approved**: SPEC carimbado Approved. Se não, volta loop.

Saída desta etapa: `task_graph.md` + `tasks/<TASK_ID>/envelope.md` para cada task.

---

## Etapa 1: TDD Loop (por task)
Fluxo canônico por task atômica.

| Passo | Ação | Artefato esperado | Fail condition |
|---|---|---|---|
| 1.1 | **Escreve teste FALHANDO** que representa 1 AC. | `*.{test,spec}.{ts,rs,py}` ou Playwright spec | Teste não falha = teste ruim, escreve de novo. |
| 1.2 | **Implementa** MENOR quantidade de código possível para o teste passar. | Código em `src/` | Teste ainda falha → volta 1.2. |
| 1.3 | **Refatora** agora que teste verde: renomeia variáveis, extrai função, melhora tipos. **NÃO muda comportamento.** | Código limpo. | Teste deixa de ficar verde → refactor ruim, desfaz. |
| 1.4 | **Repete** para próximo AC. | — | Todas ACs da task cobertas por teste. |

### Regras hard fail etapa 1
- ❌ Implementou antes do teste quebrando = falhou etapa. Volta.
- ❌ Teste vazio (mock everything, assertion vazio `expect(true).toBe(true)`) = fail.
- ❌ Só testa happy path. Teste obrigatoriamente cobre 1 caminho erro por AC.

---

## Etapa 2: Gates Quality (G-ENG-1 + G-ENG-2 obrigatórios)
**Rodado automaticamente pelo ship §0.9.5 DOMAIN GATES** antes de abrir PR Draft.

| Gate ID | Nome | Threshold OBRIGATÓRIO numérico | Retry automático | Human required após |
|---|---|---|---|---|
| G-ENG-1 | **Lint · Typecheck · Test Pass Rate** | `lint_errors=0`, `typecheck_errors=0`, `test_pass_rate=100%` (0 testes podem FAIL). Warnings permitidos se `--exact=false`. | 1 retry automático se for flaky detectado (mesmo seed 2x runs iguais) | 2nd falha |
| G-ENG-2 | **Coverage Gate** | `lines_coverage ≥ 70%` GERAL + `novo_código ≥ 80%` + `branch_coverage ≥ 65%`. Exclui `**/*.test.*`, `**/migrations/**`, `**/*.config.*`. | 1 retry automático re-run coverage report. | 2nd falha (só cai threshold com EXPLICIT_OVERRIDE do user logado). |

### Override rules (IGUAL padrão ship §0.9.5):
- 1st FAIL em qualquer gate → agente aplica retry 1 grátis com sugestões top3 desvios.
- 2nd FAIL → HARD STOP. 3 opções: (A) corrigir manual (B) EXPLICIT_OVERRIDE user VERBATIM log decisions.log entry format `[EXPLICIT_OVERRIDE] GATE=<id> threshold=<original> reason="<user literal verboatim>"` (C) cancelar ship.
- **Threshold NUNCA É ABAIXADO PELO AGENTE.** Mesmo que "pareça ok".

---

## Etapa 3: Dev Handoff para Code Review
Checklist 100% preenchido ANTES de abrir o PR.

| # | Item | Confirmado? |
|---|---|---|
| 1 | Commit mensagem conventional commit `feat|fix|refactor|chore|docs|perf|ops(scope): <description>` en | |
| 2 | ACs no SPEC todas marcadas DELIVERED + evidência (link teste verde ou screenshot Playwright) | |
| 3 | Migrations: adicionado R DOWN correspondente se reversível, senão justificado em comentário | |
| 4 | Novas ENV vars: todas declaradas em `.env.example` + parser zod no pacote `@flockr/config` ou equivalente | |
| 5 | Gates G-ENG-1 e G-ENG-2 PASSADOS + artifacts de report anexados ao PR description | |
| 6 | Secrets / PATs / keys: `git diff --cached` confirma NENHUM secret trackeado | |
| 7 | Comando local `typecheck` + `lint` passa 100% clean antes do push | |
| 8 | Logging PII redacted + trace_id propagado corretamente através de cross-calls | |
| 9 | Decisions.log atualizado com decisões arquiteturais não triviais da task | |
| 10 | PR Description contém: O que mudou? Por que? Como testar? Risks? Rollback? | |

---

## Etapa 4: Post-deploy (quando aplicável) — §20 FIRE DRILL
| Ação | Prazo | Artefato |
|---|---|---|
| 4.1 SLO baseline check (latência / error rate p50, p95, p99) | 5 min após deploy visível | Captura screenshot ou métrica logada |
| 4.2 Rollback capability: confirma comando rollback documentado e testado (staging). | Antes do deploy em prod | runbook rollback |
| 4.3 Sentry / provider observabilidade: erros novos? (não = ok. sim = rollback ou hotfix). | 10 min após deploy | alert check |
| 4.4 decisions.log POST_DEPLOY_CHECK entry: `timestamp + commit + env + who + result = {ok,warn,rollback}` | Imediatamente | decisions.log |

---

## Log de decisões OBRIGATÓRIO por etapa
Cada etapa não trivial → 1 linha em `decisions.log.jsonl` (helper oficial):
```
[0-ETAPA-APPROVED] spec=<slug> approved domain=engineering
[1-TDD-LOOP-DONE] task=<TASK_ID> ac_count=N test_count=N pass_rate=100%
[2-GATES] gate=G-ENG-1 pass=yes gate=G-ENG-2 pass=yes
[3-HANDOFF-READY] pr_url=<draft> checklist_completed=10/10
[4-POST-DEPLOY-CHECK] env=production result=ok
```
