# Template · Incident Runbook (on-call SRE / Engineer)

For incidents. Step-by-step checklist of actions to take at T+0 / T+5m / T+15m / T+60m.

---

## 0. 🔴 Metadata
| Field | Value |
|---|---|
| Runbook ID | `run-<slug>` |
| Incident Type | 🚨 Outage / 💰 Financial / 🔒 PII Data / 🐛 General Bug / 🔄 Performance Degradation |
| Target Service / System | |
| Author | |
| Last Practical Test of Runbook | DD/MM/YYYY by <name> |
| Status | Tested · Draft · Obsolete |

---

## 1. Contacts (Current on-call) - ALWAYS UPDATE
| Position | Name | Phone | Slack Handle |
|---|---|---|---|
| Primary Incident Commander (IC) | | | @handle |
| Backup IC | | | |
| On-call SRE | | | |
| Product POC | | | |
| Customer Support | | | |
| Comms / PR (if P1) | | | |

---

## 2. T+0 (0 to 2 minutes): Acknowledge & Communicate
| # | Action | Done? |
|---|---|---|
| 1.1 | ❗ **DECLARE INCIDENT** in #incidents channel with the standard message below: | |
| | `🚨 P<P1/P2/P3> INCIDENT DECLARED by @<you> at <UTC time>. Service: <service>. Symptom: <1 sentence>. Impact: <users / £ / SLA>. Channel: #inc-<id>` | |
| 1.2 | Create specific channel `#inc-YYYYMMDD-<N>` + invite everyone from metadata. | |
| 1.3 | Pin main dashboard in the channel: Sentry / Grafana / Datadog URLs. | |
| 1.4 | DO NOT investigate alone without a communication pair: IC delegates 2 roles: COMM (updates status) + RESOLVER (works on root cause). | |

---

## 3. T+2 to T+10: Assess Impact & Isolate (blame-free, MITIGATE first, then diagnose)
| # | Action | Done? |
|---|---|---|
| 2.1 | **Mitigate first!** Available options: | |
| | (a) Rollback deploy → `vercel rollback <id>` / `helm rollback <release> <rev>` | |
| | (b) Feature flag OFF → Disable the route with FF if it exists | |
| | (c) Scale up → Increase pods/instances if capacity is saturated | |
| | (d) Disable batch / workers → If background jobs leak is suspected | |
| 2.2 | Answer 5 questions (initial QUICK 5-Whys): What / Where / When / Who affected / Why suspected | |
| 2.3 | Monitoring Dashboard: Capture 3 screenshots (before mitigation, after, baseline) → save in evidence | |
| 2.4 | Communicate status every 5 min EVEN IF no news: `[T+<N>m] Status update: still investigating <H1>, no mitigation yet, no change in impact.` | |

---

## 4. T+10 to T+30: Diagnose & Fix
| # | Action | Done? |
|---|---|---|
| 3.1 | Scientific Debug: 3 top hypotheses = 3 instrumentations. Log evidence. | |
| 3.2 | If hotfix needed → **Create `hotfix/inc-<id>` branch directly from main, WITHOUT formal PR approval** (valid only once for incident; PR created in parallel for later audit) | |
| 3.3 | Deploy hotfix to staging first → smoke test 3 critical flows. | |
| 3.4 | Deploy hotfix to prod → monitor for 10 min. | |

---

## 5. T+30 to T+60: Resolved? Validate & Communicate
| # | Action | Done? |
|---|---|---|
| 4.1 | **Validation checklist**: 5 minutes without new errors, baseline metrics (p95 latency, error rate, volume), reported users 100% resolved (if N known) | |
| 4.2 | Post RESOLVED message in #incidents + #general: | |
| | `✅ P<X> INCIDENT RESOLVED @ <UTC time>. Duration: T total. Final impact: <numbers>. Mitigation applied: <what was done>. Hotfix PR: <link>. Next steps: postmortem in 48 business hours. Thanks to @list for responding quickly.` | |
| 4.3 | Archive evidence in `$CHE_WORKSPACES_ROOT/<ws>/<proj>/project/postmortems/inc-<id>/evidence/` | |
| 4.4 | Create Postmortem issue on board with due date ≤ 2 business days, assign to IC. | |

---

## 6. Post-incident ≥ 48h
| # | Action | Done? |
|---|---|---|
| 5.1 | Postmortem document filled out + approved by signatories. | |
| 5.2 | All SMART Action Items in backlog with deadlines. | |
| 5.3 | 30 min Retrospective with team: what worked, what didn't, improve runbook. | |
| 5.4 | Runbook UPDATED with lessons learned. Next practical test scheduled ≤ 30 days. | |

---

## 7. Quick Reference Commands (per service)
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
