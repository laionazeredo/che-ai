---
domain: "social"
playbook_version: "0.1"
gate_files_required:
  - "gates/first-gate-template.md"
  - "gates/second-gate-template.md"
---

# Playbook — social

## 0. Preconditions (run before anything in this domain)
- [ ] Session has **domain:** field set correctly in SPEC frontmatter or Scrum Master flag.
- [ ] Domain `profile.md` loaded successfully by Scrum Master Step 0.3.
- [ ] All required connectors in `connectors/` directory have config present (if used).
- [ ] **Provider Pointer Pattern (G vs E NON-NEGOTIABLE)**: Structural workflow HERE. Visual/creative rules → delegate WITHOUT duplicating brand numbers:
  - (a) `skills/brand-designer/SKILL.md` — logo, typography, colors, tokens.
  - (b) `skills/social-media/SKILL.md` — posting cadence, platform algorithm rules, content formats (Reels/Carousel/Short/Static).
  - (c) `skills/image/SKILL.md` — image/OG generation pipeline (marketing visuals, blog heroes, social cards).
  - (d) `skills/digital-marketing-expert/SKILL.md` — ads (Google/TagManager + platform-specific ads strategy).
  - Scoring → CHE_RULES §X "per Sxx".

---

## 1. Phase 1 — Brief / Discovery / Intake (Social skeletal)
0.1 **Audience persona 3-liner**: Who are we talking to? (1 paragraph) · What do they care about? (3 bullets) · Where are they? (platform order: IG · LinkedIn · X · TikTok · Threads).
0.2 **4 content pillars** (max 4, never more — lack of focus = diluted brand voice): Example = (1) Product updates (2) Customer stories (3) Education/Tutorials (4) Culture/Behind the scenes.
0.3 **North Star Social KPI (S09 CHE_RULES companion)**: 1 measurable number. Example = "LinkedIn CTR 1.1% → 2.0% in 60 days" OR "IG Followers 4200 → 8500". NOT "increase engagement" (prose = failure).
0.4 **Hashtag strategy (10 core + 20 rotating)**: 10 branded/community (owned) + 10 industry. NEVER more than 30/total per post (shadow-ban risk Meta/LinkedIn).
0.5 **Approved gate**: Persona + Pillars + KPI + Hashtags sent. Literal "Social Strategy Approved" required.

### Output:
- `docs/social/<slug>-01-strategy.md`

---

## 2. Phase 2 — Design / Draft / Implementation (Content Calendar)
0.1 **30-day content calendar (S09 + S14 CHE_RULES companions)**: 4 posts/week minimum = 16 posts/month. Each row = [Date · Platform · Pillar · Format (Reel/Carousel/Static/Short/Text) · Hook (≤ 70 char) · CTA · Copy doc path · Visual asset path · Hashtags set · Approval status].
0.2 **Brand identity re-use** (brand-designer pointer): All visuals pull color/typography/logo from the brand system. No new hex color introduced in a social post without new token proposal in design system first.
0.3 **A/B hooks (50% of ad posts)**: For every paid post, 2 hooks written. Winner selected automatically after 48h (90% confidence).
0.4 **Copy review + CTA**: Every post has exactly ONE primary CTA. 2 CTAs = conversion confusion.

### Output:
- `docs/social/<slug>-02-calendar.md`
- Visuals generated via image skill · Copy written · Assets exported

---

## 3. Phase 3 — Quality Gates (run EVERY gate in gates/ folder)
**Thresholds consume CHE_RULES §X canonical via Sxx refs — no numbers duplicated.**
| Gate | Threshold to PASS | CHE_RULES §X ref | Auto-retry |
|---|---|---|---|
| `gates/first-gate-template.md` | Score ≥ 7.0 / 10 | per S11 (scope) + per S13 (geomean) | 1 |
| `gates/second-gate-template.md` | 0 CRITICAL items (wrong logo color · typo in brand name · broken CTA link · wrong platform aspect ratio) | per S14 quality + brand compliance | 1 |
| **[G-SOC-1] Platform specs embedded gate** | All IG Stories 9:16 · LinkedIn posts ≤ 3 hashtags · X ≤ 280ch · Reels ≤ 90s | per S14 (quality check) | 1 |

Gate failure process (same for every domain, non-negotiable):
1. First fail → ONE free auto-retriable apply recommendations of gate.
2. Second fail → STOP. Ask human (domain owner) before proceeding further.
3. Never skip a gate or lower threshold without decision.log entry + user VERBATIM.

---

## 4. Phase 4 — Delivery / Handoff / Ship integration
After ALL gates PASS:
- Assets exported 2x pixel density for every platform (IG/LinkedIn/X/TikTok/Threads).
- UTM tags consistent: `?utm_source=ig&utm_medium=social&utm_campaign=<slug>_<YYYYMM>`, no manual typo UTMs.
- Call /che-ship if code/artifacts go to git repo.
- If pure docs-only or creative-only deliverable: write final report + save in `$CHE_SESSION_DIR/reports/` for audit.

---

## Provider Pointer summary
| General (HERE) | Specific (delegated skill) |
|---|---|
| Pillars / Persona / Calendar / KPI structure | `skills/social-media/SKILL.md` |
| Visual standards / colors / logo / tokens | `skills/brand-designer/SKILL.md` |
| Image + social cards generation | `skills/image/SKILL.md` |
| Paid ads + tracking + GTM integration | `skills/digital-marketing-expert/SKILL.md` · `skills/google-tagmanager` · `skills/google-ads-manager` |
| Numeric pass/fail | CHE_RULES §X S01-S15 |
