---
domain: "copywriting"
playbook_version: "0.1"
gate_files_required:
  - "gates/first-gate-template.md"
  - "gates/second-gate-template.md"
---

# Playbook — copywriting

## 0. Preconditions (run before anything in this domain)
- [ ] Session has **domain:** field set correctly in SPEC frontmatter or Scrum Master flag.
- [ ] Domain `profile.md` loaded successfully by Scrum Master Step 0.3.
- [ ] All required connectors in `connectors/` directory have config present (if used).
- [ ] **Provider Pointer Pattern (G vs E NON-NEGOTIABLE)**: Copy workflow HERE. Brand voice + tone + system guidelines → delegate.
  - (a) `skills/brand-designer/SKILL.md` → brand guidelines section (voice / tone / value prop elevator pitch).
  - (b) Scoring quality → `CHE_RULES §X Sxx "per Sxx"`. NEVER invent score numbers here.
  - PII: Do NOT write raw recipient email addresses or email body anywhere (per engineering-contracts §19 PII rule — also applies to copy deliverables with personalization).

---

## 1. Phase 1 — Brief / Discovery / Intake (Copy skeletal)
0.1 **Copy brief — THE 6 MANDATORY INPUTS:**
  1. **Product/service being sold**: 1 line, no jargon.
  2. **Target audience persona**: Who is this for? (1 paragraph, no stereotypes — pain points NOT demographics alone)
  3. **Primary CTA (ONE only)**: What should reader do NEXT? (Click / Signup / Buy / Reply / Download…)
  4. **Channel / Format**: Email (onboarding · lifecycle · sales) · Landing page · Ad copy (Meta/X/LinkedIn) · Blog · Product UI microcopy · Press release · Sms/Transactional.
  5. **TONE from brand system pointer** (see brand-designer skill): Formal 🎩 / Warm 🌞 / Playful 🎉 / Technical 🔧. Always match existing tone (S14 LEAN penalty if tone mismatch).
  6. **North Star Copy Metric (S09 CHE_RULES companion)**: One number. Example = "Open rate 28% → 37%" / "CTR 1.1 → 2.2" / "Signup CVR 4.2 → 6.5".
0.2 **Word count / Character budget hard limits**:
  | Format | Hard max | Failure (if exceeded) |
  |---|---|---|
  | Email subject | ≤ 50 chars / ≤ 9 words | Rewrite — GMail Mobile truncates > 50ch |
  | SMS / Transactional | ≤ 160 chars / 1 segment | Rewrite — 2× SMS = cost × 2 |
  | Meta / X primary text | ≤ 125 chars | Rewrite |
  | Landing H1 | ≤ 60 chars | Rewrite |
  | Landing meta description | 120-160 chars | Rewrite |
  | Blog H2 | ≤ 55 chars (SEO pointer seo-analytics) | Rewrite |
0.3 **Approved gate**: 6 inputs + word budget sent → "Copy Brief Approved" literal required.

### Output:
- `docs/copy/<slug>-01-brief.md`

---

## 2. Phase 2 — Design / Draft / Implementation
0.1 **A/B variants MINIMUM for EVERY marketing deliverable (not required transactional)**: Variant A = Direct, data-driven. Variant B = Emotional, story-led. MAX 2 variants — 3+ variants = analysis paralysis (LEAN penalty S14 +2).
0.2 **Copy formula by format (template defaults)**:
  - Email: Preheader (≥ 1 hook sentence) · Subject (pain or curiosity) · Hero H1 (≤ 9 words) · Sub (1 paragraph) · Bullets (3 benefit) · Social proof (1 testimonial) · CTA button (1 primary, 1 text link) · PS (repeat CTA + urgency/scarcity).
  - Landing page: H1 → H2 sub → 3 feature cards (Icon + Title + 1 paragraph benefit) → Social proof logo row → Testimonial → Pricing → FAQ 5 → Final CTA → Footer.
  - Blog post: Hook (1 paragraph question) → TL;DR summary bullets → 3 H2 sections → Conclusion → CTA.
0.3 **Brand system compliance**: Every piece of copy MUST use the OFFICIAL brand name exactly. No misspellings, no abbreviations not in brand guidelines (per brand-designer pointer). No emoji in B2B product UI copy (Formal/Warm tone = no emoji).
0.4 **Copy checklists: 8 items before submission** = (1) 1 CTA max? (2) Tone matches? (3) Word limit ok? (4) No jargon? (5) PII clean / no raw email addresses? (6) Spelling US/GB correct (per LANG_DOCS config)? (7) Active voice 80% +? (8) Benefit led (what reader GAINS) not feature led.

### Output:
- `docs/copy/<slug>-02-copy.md` with variants A + B + trackable UTM pointer

---

## 3. Phase 3 — Quality Gates (run EVERY gate in gates/ folder)
**Gates CONSUME CHE_RULES §X canonical scores via Sxx refs — no numbers duplicated.**
| Gate | Threshold to PASS | CHE_RULES §X ref | Auto-retry |
|---|---|---|---|
| `gates/first-gate-template.md` | Score ≥ 7.0 / 10 | per S11 + per S13 (Scope × LEAN geomean ≥ 7.0) | 1 |
| `gates/second-gate-template.md` | 0 CRITICAL items (typo in brand name · broken CTA link · PII raw email · tone mismatch 2+ words) | per S14 quality compliance | 1 |
| **[G-COPY-1] Format word-budget embedded gate** | ALL format limits within §1.2 table. 0 items over budget. | per S14 (LEAN quality check) | 1 |

Gate failure process (same for every domain, non-negotiable):
1. First fail → ONE free auto-retriable apply recommendations of gate.
2. Second fail → STOP. Ask human (domain owner) before proceeding further.
3. Never skip a gate or lower threshold without decision.log entry + user VERBATIM.

---

## 4. Phase 4 — Delivery / Handoff / Ship integration
After ALL gates PASS:
- Variant A/B with winner recommendation + rationale (1 paragraph).
- Export Markdown + Google Docs link (for non-technical collaborators review).
- Call /che-ship if code/artifacts go to git repo.
- If pure docs-only or creative-only deliverable: write final report + save in `$CHE_SESSION_DIR/reports/` for audit.

---

## Provider Pointer Pattern summary
| General (HERE, agnostic) | Specific implementation (delegated skill location) |
|---|---|
| Workflow 6 inputs · Word budget · Formulas A/B · Tone matrix | Brand guidelines voice/tone/naming = `skills/brand-designer/SKILL.md` |
| SEO blog word limits + meta description length rules | `skills/seo-analytics` connector pointer §1.2 / seo skill |
| UTM link consistency + tagging | `domains/social/playbook.md` §4 standard `utm_source=..` pattern |
| Pass/fail quality numeric | CHE_RULES §X S01-S15 canonical — NEVER duplicated |
