# Template · Postmortem (Incident 5-Whys + Action Items)

MANDATORY for any P1/P2 incident (production downtime, data breach, financial loss > £100, PII leak). Based on Google SRE + 5 Whys template.

---

## 1. 🔴 Metadata
| Field | Value |
|---|---|
| Incident ID | `inc-YYYYMMDD-<N>` |
| Memorable Short Name | E.g.: "FLO-513 duplicate refund in race condition" |
| Actual Severity | P1 (global outage, >1h downtime, PII leak, £ loss) · P2 (intermittent, partial) · P3 (internal, 0 user impact) |
| Impacted Domain | engineering · product · devops |
| Environment | Prod | Staging | Dev |
| Start (UTC) | `YYYY-MM-DD HH:MM UTC` |
| Total Duration | `XXm` (detected `+Ym` + mitigated `+Zm`) |
| Detected By | User report · Sentry/Datadog Alert · Monitoring · QA · Other |
| Postmortem Author | |
| Timeline Participants | |

---

## 2. Executive Summary (3 sentences MAX, recommended CEO-read level)
1. What happened, in simple language:
2. Impact on users and business:
3. #1 most critical lesson learned:

---

## 3. Detailed Timeline (UTC, minute-by-minute, DEBUG events)
| UTC Time | Local Time (GMT-3) | Action / Event | Actor | Evidence Link |
|---|---|---|---|---|
| 14:02 | 11:02 | 1st customer opens ticket: "cannot request refund twice on same order" | N2 Support | Ticket #4821 |
| 14:05 | 11:05 | Sentry alert triggers: 500 /api/refunds spike 50x baseline | Sentry | Sentry URL |
| ... | | | | |

---

## 4. Quantified Impact
| Metric | Value | Note |
|---|---|---|
| Affected Users | N = | Estimate e.g.: 32 orders, 89 tickets |
| Financial Loss | £ XX.YY | Duplicate refunds already reversed = +N to return to Stripe |
| SLA Broken? | Yes / No | If yes, by what % |
| PII / Data Leak | NO / YES (which fields) | |

---

## 5. 5 Whys (root cause chain)
```
Why 1: Why did customers receive duplicate refunds?
  → Because API /refunds accepted 2 simultaneous requests with SAME idempotency key (not checked in middleware).
Why 2: Why was the idempotency key NOT validated?
  → Because validation was commented out "// TODO: enable when db index created".
Why 3: Why was it commented out without an ADR / target date?
  → Because PR #182 was not scope-checked, passed G1 scope without evidence of TODO resolved.
Why 4: Why did the scope checker not detect it?
  → Gate G1 does not scan for TODO comments with expired dates.
Why 5 (ROOT CAUSE):
  → Missing rule in scope-checker (G1 LEAN category 4 ENV-VAR/MIGRATION) for: "ALL TODO/FIXME/HACK comments referencing migration or db constraints MUST have a target date ≤ today and a corresponding ADR."
```

---

## 6. Action Items (SMART: Specific Measurable Assignable Realistic Timed)
Each action has OWNER + DEADLINE + TYPE (HARDEN / MONITOR / DOC / TEST / PROCESS)

| # | Action | Type | Owner | Deadline | Status |
|---|---|---|---|---|---|
| 1 | Create unique index in DB (refunds.idempotency_key) + reversible migration | HARDEN | DB team | 05/09 | |
| 2 | Uncomment idempotency middleware validation + unit test for race condition (2 simultaneous requests) | TEST | | | |
| 3 | Add G1 scope-checker rule: TODO/FIXME/HACK with date ≥ commit date → HIGH warning | PROCESS | Scrum Master skill maintainer | 10/09 | |
| 4 | Sentry Alert: rate /refunds > 10x baseline automatically pages owner on Slack #incidents | MONITOR | DevOps | 07/09 | |
| 5 | Update refund runbook with: how to detect duplicates, how to reverse in Stripe + DB | DOC | | 12/09 | |

---

## 7. What worked well (Blameless, 3 points)
1.
2.
3.

---

## 8. What could be improved (3 priority points)
1.
2.
3.

---

## 9. Approval Signatures
| Role | Name | Date | Approved? |
|---|---|---|---|
| Incident Commander | | DD/MM/YYYY | ✅ / ❌ |
| Tech Lead of Impacted Area | | DD/MM/YYYY | ✅ / ❌ |
| Product Owner | | DD/MM/YYYY | ✅ / ❌ |
| Head of Engineering (P1/P2 £ loss only) | | DD/MM/YYYY | ✅ / ❌ |

---

### Permanent Link (saved in project project/postmortems/)
- `$CHE_WORKSPACES_ROOT/<workspace>/<project>/project/postmortems/inc-YYYYMMDD-<N>.md`
