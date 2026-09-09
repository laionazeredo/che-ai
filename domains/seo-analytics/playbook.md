---
domain: "seo-analytics"
playbook_version: "0.1"
gate_files_required:
  - "gates/first-gate-template.md"
  - "gates/second-gate-template.md"
---

# Playbook — seo-analytics

## 0. Preconditions (run before anything in this domain)
- [ ] Session has **domain:** field set correctly in SPEC frontmatter or Scrum Master flag.
- [ ] Domain `profile.md` loaded successfully by Scrum Master Step 0.3.
- [ ] All required connectors in `connectors/` directory have config present (if used).
- [ ] **Provider Pointer Pattern (G vs E)**: SEO structural workflow lives HERE. Technical SEO rules + audit methodology → delegates to 2 skills WITHOUT duplicating numbers:
  - (a) `skills/audit-website/SKILL.md` — 230+ rules, 15 categories. Scoring: "per CHE_RULES §X Sxx". NEVER redefine rule weights here.
  - (b) `skills/programmatic-seo/SKILL.md` — template pages at scale patterns (keyword+city, integration, comparison templates).
  - Numbers/thresholds → CHE_RULES §X S01-S15.

---

## 1. Phase 1 — Brief / Discovery / Intake (SEO skeletal)
0.1 **Keyword universe**: 3 buckets = Branded (≥ 30% traffic floor) · Commercial (💰) · Informational (📚). Minimum 20 keywords ≥ 100/mo search volume.
0.2 **Competitor SERP gap analysis (top 3 rivals)**: Extract 20 keywords they rank #1-10 and we don't.
0.3 **Technical SEO baseline scan**: Run audit-website skill FIRST before writing any content. Attach baseline health score (S14 companion).
0.4 **North Star SEO KPI (S09 CHE_RULES companion)**: Example = "Organic impressions 130k → 260k in 90 days" OR "Top3 keywords 6 → 18". Measurable number ONLY.
0.5 **Approved gate**: Brief + KPI + Gap + Baseline sent → "SEO Brief Approved" literal.

### Output:
- `docs/seo/<slug>-01-brief.md`

---

## 2. Phase 2 — Design / Draft / Implementation
0.1 **Content calendar 30-60-90**: 30 day = quick wins (easy keywords). 60 day = mid-tail clusters. 90 day = pillar pages.
0.2 **Programmatic SEO module spec** IF ≥ 100 template pages required (per programmatic-seo skill): Template schema + data source + 1:1 URL/keyword.
0.3 **On-page SEO checklist per page**: 10 items (title < 60ch · meta desc 120-160ch · H1 unique · alt text images · canonical · noindex non-canonical · OG tags 1200×630 · Schema.org JSON-LD · internal links ≥ 4 · load-time LCP < 2.5s per core-web-vitals skill pointer).

### Output:
- `docs/seo/<slug>-02-content-plan.md`
- Content files written / programmatic template code written

---

## 3. Phase 3 — Quality Gates (run EVERY gate in gates/ folder)
**Gates REFERENCE CHE_RULES §X canonical thresholds.** Required gates for seo-analytics:
| Gate file / ID | Threshold to PASS | CHE_RULES §X ref | Auto-retry allowed (max N) |
|---|---|---|---|
| `gates/first-gate-template.md` | Score ≥ 7.0 / 10 (Health Score companion S14) | per S14 Engineering + per S13 Geomean | 1 |
| `gates/second-gate-template.md` | 0 CRITICAL items (broken links / missing H1 / 404 canonical / no HTTPS) | per S02 + per S12 data freshness | 1 |
| **[G-SEO-1] Technical + CWV embedded** | LCP < 2.5s · INP < 200ms · CLS < 0.1 (per core-web-vitals skill pointer) · organic CTR ≥ 2% | per S14 (quality) + per S09 (KPI) | 1 |

Gate failure process (same for every domain, non-negotiable):
1. First fail → ONE free auto-retriable apply recommendations of gate.
2. Second fail → STOP. Ask human (domain owner) before proceeding further.
3. Never skip a gate or lower threshold without decision.log entry + user VERBATIM.

---

## 4. Phase 4 — Delivery / Handoff / Ship integration
After ALL gates PASS:
- Attach before/after health score screenshot to PR.
- Write GSC (Google Search Console) tracking plan: Keywords tracked + weekly delta report cadence.
- Call /che-ship if code/artifacts go to git repo.
- If pure docs-only or creative-only deliverable: write final report + save in `$CHE_SESSION_DIR/reports/` for audit.

---

## Provider Pointer Pattern summary
| General pattern (HERE, agnostic) | Specific implementation (delegated to skill) |
|---|---|
| Audit pass/fail 230+ rules overall methodology | `skills/audit-website/SKILL.md` |
| Template generation for keyword + location pages at scale | `skills/programmatic-seo/SKILL.md` |
| CWV LCP / INP / CLS thresholds numeric | `skills/core-web-vitals/SKILL.md` |
| Score numeric | CHE_RULES §X S01-S15 — NEVER duplicated |
