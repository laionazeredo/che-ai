# Template · Runbook de Incidente (on-call SRE / Engineer)

Para incidentes. Checklist step-by-step de ações a tomar em T+0 / T+5m / T+15m / T+60m.

---

## 🔴 Metadata
| Campo | Valor |
|---|---|
| Runbook ID | `run-<slug>` |
| Tipo de incidente | 🚨 Outage / 💰 Financeiro / 🔒 PII Data / 🐛 Bug General / 🔄 Degradação performance |
| Serviço / sistema alvo | |
| Autor | |
| Último teste prático do runbook | DD/MM/YYYY por <nome> |
| Status | Testado · Draft · Obsoleto |

---

## 0. Contatos (on-call atual) - ATUALIZAR SEMPRE
| Posição | Nome | Telefone | Slack handle |
|---|---|---|---|
| Incident Commander (IC) primário | | | @handle |
| IC backup | | | |
| SRE on-call | | | |
| Produto POC | | | |
| Suporte ao cliente | | | |
| Comms / PR (se P1) | | | |

---

## 1. T+0 (0 a 2 minutos): Reconhecer & Comunicar
| # | Ação | Feito? |
|---|---|---|
| 1.1 | ❗ **DECLARAR INCIDENTE** no canal #incidents com mensagem padrão abaixo: | |
| | `🚨 INCIDENTE P<P1/P2/P3> DECLARADO por @<vc> às <UTC time>. Serviço: <service>. Sintoma: <1 frase>. Impacto: <usuários / £ / SLA>. Canal: #inc-<id>` | |
| 1.2 | Criar canal específico `#inc-YYYYMMDD-<N>` + convidar todos do metadata. | |
| 1.3 | Pin dashboard principal no canal: Sentry / Grafana / Datadog URLs. | |
| 1.4 | NÃO sair investigando sem communication pair: IC delega 2 roles: COMM (atualiza status) + RESOLVER (trabalha na causa). | |

---

## 2. T+2 a T+10: Avaliar impacto & Isolar (blame-free, primeiro MITIGAR, depois diagnosticar)
| # | Ação | Feito? |
|---|---|---|
| 2.1 | **Mitigar primeiro!** Opções disponíveis: | |
| | (a) Rollback deploy → `vercel rollback <id>` / `helm rollback <release> <rev>` | |
| | (b) Feature flag OFF → Liberar a rota com FF se existir | |
| | (c) Scale up → Aumentar pods/instâncias se capacity saturado | |
| | (d) Desligar batch / workers → Se vazamento de background jobs | |
| 2.2 | Responder 5 perguntas (5-Whys inicial RÁPIDO): What / Where / When / Who affected / Why suspected | |
| 2.3 | Dashboard de monitoramento: Captura 3 screenshots (antes mitigação, depois, baseline) → salva em evidências | |
| 2.4 | Comunicar status cada 5 min MESMO que sem novidades: `[T+<N>m] Status update: ainda investigando <H1>, sem mitigação ainda, sem mudança de impacto.` | |

---

## 3. T+10 a T+30: Diagnosticar & Fix
| # | Ação | Feito? |
|---|---|---|
| 3.1 | Scientific Debug 3 hipóteses top = 3 instrumentations. Log evidências. | |
| 3.2 | Se hotfix necessário → **Criar branch `hotfix/inc-<id>` direto de main, SEM PR aprovação formal** (válido 1 vez só para incidente; PR criado em paralelo para audit posterior) | |
| 3.3 | Deploy hotfix em staging primeiro → smoke teste 3 flows críticos. | |
| 3.4 | Deploy hotfix em prod → monitor 10 min. | |

---

## 4. T+30 a T+60: Resolvido? Validar & Comunicar
| # | Ação | Feito? |
|---|---|---|
| 4.1 | **Validation checklist**: 5 minutos sem erro novo, baseline métricas (latência p95, error rate, volume), usuários reportados resolvidos 100% (se N conhecido) | |
| 4.2 | Postar mensagem RESOLVIDO no canal #incidents + #geral: | |
| | `✅ INCIDENTE P<X> RESOLVIDO @ <UTC time>. Duração: T total. Impacto final: <números>. Mitigação aplicada: <o que foi feito>. Hotfix PR: <link>. Próximos passos: postmortem em 48h úteis. Agradecimentos a @lista por responder rápido.` | |
| 4.3 | Arquivar evidências em `$CHE_WORKSPACES_ROOT/<ws>/<proj>/.project/postmortems/inc-<id>/evidence/` | |
| 4.4 | Criar issue Postmortem no board com due date ≤ 2 dias úteis, atribuir ao IC. | |

---

## 5. Pós-incidente ≥ 48h
| # | Ação | Feito? |
|---|---|---|
| 5.1 | Postmortem documento preenchido + aprovado por signatários. | |
| 5.2 | Todas Action Items SMART no backlog com prazos. | |
| 5.3 | Retrospectiva 30 min com equipe: o que funcionou, o que não, melhorar runbook. | |
| 5.4 | Runbook ATUALIZADO com lições aprendidas. Próximo teste prático agendado ≤ 30 dias. | |

---

## 6. Comandos referência rápida (por serviço)
```bash
# ====== Vercel ======
vercel ls <project>
vercel rollback <deployment-url>

# ====== Kubernetes ======
kubectl get pods -n <ns> --sort-by=.metadata.creationTimestamp | tail -10
kubectl logs -f deployment/<name> --tail=200 -n <ns> | grep ERROR | tail -30
kubectl rollout undo deployment/<name> -n <ns>

# ====== Stripe / payments ======
stripe events list --limit=20
stripe refunds create --charge=ch_xxx --amount=<pence> --reason=requested_by_customer --metadata=incident=inc-YYMMDD-N
```
