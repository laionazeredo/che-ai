# Template · Postmortem (Incidente 5-Whys + Action Items)

Preenchimento OBRIGATÓRIO para qualquer incidente P1/P2 (downtime prod, data breach, perda financeira > £100, leak PII). Baseado no template Google SRE + 5 Whys.

---

## 🔴 Metadata
| Campo | Valor |
|---|---|
| ID incidente | `inc-YYYYMMDD-<N>` |
| Nome curto memorável | Ex: "FLO-513 refund duplicate em race condition" |
| Severidade real | P1 (global outage, >1h downtime, PII leak, £ loss) · P2 (intermitente, partial) · P3 (interno, 0 user impact) |
| Domínio impactado | engineering · product · devops |
| Ambiente | Prod | Staging | Dev |
| Início (UTC) | `YYYY-MM-DD HH:MM UTC` |
| Duração total | `XXm` (detectado `+Ym` + mitigado `+Zm`) |
| Deteção por | User report · Alert Sentry/Datadog · Monitoramento · QA · Outro |
| Autor postmortem | |
| Participantes timeline | |

---

## 2. Resumo Executivo (3 frases MAX, recomendado CEO-read level)
1. O que aconteceu, em linguagem simples:
2. Impacto para usuários e negócio:
3. Lição #1 mais crítica aprendida:

---

## 3. Timeline detalhada (UTC, minuto-a-minuto, eventos de DEBUG)
| Horário UTC | Horário BR (GMT-3) | Ação / evento | Ator | Link evidência |
|---|---|---|---|---|
| 14:02 | 11:02 | 1º customer abre ticket: "não consigo pedir refund 2x no mesmo pedido" | Suporte N2 | Ticket #4821 |
| 14:05 | 11:05 | Sentry alert dispara 500 /api/refunds spike 50x baseline | Sentry | Sentry URL |
| ... | | | | |

---

## 4. Impacto Quantificado
| Métrica | Valor | Nota |
|---|---|---|
| Usuários afetados | N = | Estimativa ex: 32 pedidos, 89 tickets |
| Perda financeira | £ XX,YY | Refunds duplicated já estornados = +N para devolver stripe |
| SLA quebrado? | Sim / Não | Se sim, quanto % excedeu |
| PII / dados leak | NÃO / SIM (quais campos) | |

---

## 5. 5 Whys (root cause chain)
```
Why 1: Por que clientes receberam refund duplicate?
  → Porque API /refunds aceitou 2 requests simultâneos MESMO idempotency key (não checado no middleware).
Why 2: Por que idempotency key NÃO foi validada?
  → Por que validação estava comentada "// TODO: enable when db index criado".
Why 3: Por que comentaram sem ADR / data alvo?
  → Porque PR #182 não foi scope-checked, passou G1 scope sem evidência do TODO resolvido.
Why 4: Por que scope checker não detectou?
  → Gate G1 não varre comentários TODO com data expirada.
Why 5 (ROOT CAUSE):
  → Falta regra no scope-checker (G1 LEAN category 4 ENV-VAR/MIGRATION) para: "TODOS comentários TODO/FIXME/HACK que REFEREM migration OU db constraint → deve ter data alvo ≤ hoje e ADR correspondente."
```

---

## 6. Action Items (SMART: Specific Measurable Assignable Realistic Timed)
Cada ação tem DONO + DATA LIMITE + TIPO (HARDEN / MONITOR / DOC / TEST / PROCESS)

| # | Ação | Tipo | Dono | Prazo | Status |
|---|---|---|---|---|---|
| 1 | Criar unique index no DB (refunds.idempotency_key) + migration reversible | HARDEN | DB team | 05/09 | |
| 2 | Uncomment idempotency middleware validação + teste unitário race condition 2 requests simultâneos | TEST | | | |
| 3 | Adicionar regra G1 scope-checker: TODO/FIXME/HACK com date ≥ commit data → warning HIGH | PROCESS | Scrum Master skill maintainer | 10/09 | |
| 4 | Alert Sentry: rate /refunds > 10x baseline page owner Slack #incidents automaticamente | MONITOR | DevOps | 07/09 | |
| 5 | Atualizar runbook refund com: como detectar duplicate, como estornar em Stripe + DB | DOC | | 12/09 | |

---

## 7. O que funcionou bem (Blameless, 3 pontos)
1.
2.
3.

---

## 8. O que pode melhorar (3 pontos prioritários)
1.
2.
3.

---

## 9. Assinaturas de aprovação
| Cargo | Nome | Data | Aprovado? |
|---|---|---|---|
| Incident Commander | | DD/MM/YYYY | ✅ / ❌ |
| Tech Lead área impactada | | DD/MM/YYYY | ✅ / ❌ |
| Produto Owner | | DD/MM/YYYY | ✅ / ❌ |
| Head of Engineering (apenas P1/P2 £loss) | | DD/MM/YYYY | ✅ / ❌ |

---

### Link permanente (salvo em projeto .project/postmortems/)
- `$CHE_WORKSPACES_ROOT/<workspace>/<project>/.project/postmortems/inc-YYYYMMDD-<N>.md`
