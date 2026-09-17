---
gate_id: "ux-pixel-check-gate"
domain: "ux"
version: "0.6.0"
executable: true
inspired_by_reference_skill: "Flockr official /figma-pixel-check skill (see domains/ux/profile.md cross-references) — NOTE: that skill is a NUMERIC token diff, not an image diff. Adopt its method: compare design properties against rendered properties, never screenshot against screenshot."
threshold_pass: "score_0_to_10 ≥ 8.0  AND  pct_elements_within_4px_tolerance ≥ 95%  AND  no critical deviation > 8px"
threshold_single_critical_fail: "Any single critical element (CTA button, hero heading) with deviation > 8px, and ANY mismatch on a critical category that carries no tolerance (font-weight, font-family) → FAIL, regardless of overall score."
tool_official: "§2 Execution runner: `che pixel check` (che_core/pixel.py). Design side: mcp_Figma_AI_Bridge.get_figma_data (Figma) or mcp_open-pencil.get_jsx/node_bounds/analyze_spacing/analyze_typography/analyze_colors (OpenPencil). Implementation side: mcp_Chrome_DevTools_MCP.evaluate_script (getBoundingClientRect + getComputedStyle)."
tool_evidence_only: "Image diff (export_image + playwright_screenshot + pixelmatch) — attaches a human-readable artefact to the PR. NEVER the PASS/FAIL signal: whole-frame pixel deltas are dominated by text antialiasing/DPR/font-loading noise while being near-blind to a 2px radius error, which inverts the signal-to-noise ratio for exactly the deviations this gate exists to catch."
retry_policy: "1 free automatic retry (fixes top 3 deviations / padding / radius / font-size). 2nd failure → HUMAN REQUIRED hard stop ship."
log_format_decisions: "[DOMAIN-GATE-EXECUTED] domain=ux gate=pixel-check-gate status={PASS|FAIL|INCONCLUSIVE} score={x.y} within_4px_pct={0.xx} deviation_max_px={n} elements={n} coverage={0.xx} attempt={n} viewport={ok|undeclared} backend={name} override='{verbatim reason}' unverified={cat,cat} unreachable={cat} duration_ms={ms} traceId=... (the last three blocks are emitted only when non-empty; `unreachable` is the §2.6 held-back set, never merged into `unverified`)"
---

# Executable Gate — UX · Pixel Perfect (based on `/figma-pixel-check`)

> **Philosophy: Absolute measures per element (padding, radius, font size, EXACT hex color, X/Y position) are NUMERICAL — not a matter of taste. We don't evaluate "beauty" — we evaluate the absolute deviation of N pixels between the Figma/PenPot reference and the code implementation. 100% mathematical. 0% subjective.**

---

## 0. Prerequisites

- Valid design reference: a Figma `node_id` or an OpenPencil `.op` node id. NOT "any image".
- Code implementation running locally (Next.js build or dev server).
- Design-side MCP: `mcp_Figma_AI_Bridge` (`figma`) or `mcp_open-pencil` (`openpencil`).
- Implementation-side MCP: `mcp_Chrome_DevTools_MCP`.
- A `$CHE_PIXEL_MAP` (§2.4) plus matching `data-design-node` attributes in the JSX (§4.3).
- Evidence only, never the verdict: `che pixel diff` + `che pixel crop` (§4.5). The pixelmatch port is
  the only code in Che outside the standard library; `Pillow` and `numpy` come with the CLI install.

---

## 1. Comparison Methodology (18 elements per analyzed frame)

For each unique node/frame = a page / screen / component, we measure these absolute values and compare reference vs implementation:

| # | Measurement Category | How we measure | Allowed tolerance (pass) |
|---|---|---|---|
| 1 | **Width / Height box model** | `node.width`, `node.height` (Figma) vs `getBoundingClientRect()` (implementation) | ≤ 4px on each axis |
| 2 | **Internal Padding-top / right / bottom / left** | 4 individual values | ≤ 4px each (all 4 must pass) |
| 3 | **External Margin to near siblings** | Space between previous and next element | ≤ 4px |
| 4 | **Border-radius (all 4 corners top-left…bottom-right individually)** | Exact profile token value: xs=2/sm=4/md=8/lg=16/xl=24/full=9999 | ≤ 2px (radius is highly sensitive; 3px deviation is visually perceptible) |
| 5 | **Border-width / Border-color hex** | `getComputedStyle` vs Figma stroke | Width ≤1px · Color delta E ≤ 5 CIE76 |
| 6 | **Typography font-size (px point-by-point)** | Computed vs Figma font size | ≤ 2px (visually very sensitive) |
| 7 | **Typography font-weight (400/500/600/700)** | Exact. No tolerance. | EXACT match (no "almost 600"). |
| 8 | **Typography line-height (leading)** | Exact value (1.5, 1.2, 1.4 profile) | ≤ 0.05 leading |
| 9 | **Typography letter-spacing** | 0.01em default, exact tokens | ≤ 0.01em |
| 10 | **Foreground color hex / RGB (text)** | Delta E 1976 CIE76 | ≤ 5 (human eye doesn't see difference) |
| 11 | **Background paint stack — every layer, bottom-to-top** (surface) | Flat: `getComputedStyle` vs design fill. Gradient: same stop count, each stop within ΔE, stop positions within 2pp, axis within 2°. **A gradient against a flat colour is a mismatch, not an absence.** A design with two fills is compared *layer by layer*; a stack whose length differs is a mismatch on the layer that has no counterpart. | ≤ 5 ΔE per layer |
| 12 | **Box-shadow parameters (x/y/blur/spread/color alpha)** | 5 values per individual shadow | x,y ≤ 2px · blur,spread ≤ 4px · alpha ≤ 0.04 |
| 13 | **Absolute X / Y position in SM/MD/LG/XL viewport** (12-column grid alignment) | Figma x,y vs screenshot | ≤ 8px per breakpoint |
| 14 | **Auto-layout gap (row / column)** | `layout.gap` (design) vs computed `row-gap` / `column-gap` (implementation) — the form #3 takes in every auto-layout frame | ≤ 4px per axis |
| 15 | **Typography font-family** | `fontFamily` (design) vs the *first* family of computed `font-family` (implementation) | EXACT match (no "looks similar") |
| 16 | **Opacity** | `node.opacity` (design; omitted means 1) vs computed `opacity` (implementation) | ≤ 0.04 |
| 17 | **Asset identity** (images, SVGs, icons) | `asset_sha256` declared on the map entry vs the digest of what the implementation actually serves | EXACT — **opt-in**: checked only where a map entry declares one |
| 18 | **Text line count** (reflow) | Design: stated only where the box hugs its content, then `1 + explicit line breaks`. Implementation: client rects of the text leaf's `Range`. **Where the box can wrap, the design states nothing and the category is unverified** — not a pass. | EXACT — an extra line is a wrap the design did not have |

---

## 2. Execution (the standard recipe)

`che-ship §0.9.5` runs these steps verbatim. The comparator is code, never a model — see §4.4.

### 2.1 Bring the implementation up

Serve the app on a fixed origin and keep it up for the whole run. A production build is preferred
over a dev server: dev overlays inject DOM nodes the design does not have.

```bash
corepack pnpm --filter <app> dev   # or build + start
```

### 2.2 Capture the design side

`mcp_Figma_AI_Bridge.get_figma_data(fileKey, nodeId)` for `figma`, or `mcp_open-pencil.get_jsx` /
`node_bounds` / `analyze_*` for `openpencil` — the backend frozen in `$CHE_PIXEL_MAP`, never both.

Save the **raw** response to `$CHE_PIXEL_DESIGN_RAW` (§2.4) — the `get_figma_data` text, or the `.op`
document, which is that path already. Write it with the ordinary file tooling, **not**
`che write_file_atomic`: that helper refuses any target inside the worktree, and this file is inside it
on purpose. It is committed because the runner re-parses it on every run: the reference is then the bytes
the numbers were read from, never a hand-copied transcription that drifts from its source.

### 2.3 Measure the DOM side

`mcp_Chrome_DevTools_MCP`: `navigate_page` → `resize_page`(breakpoint) → `evaluate_script`
returning `getBoundingClientRect()` + `getComputedStyle()` per selector. Apply §4.2's determinism
rules **before** reading anything — typography rows are meaningless if a fallback font was measured.

Write the bag to `$CHE_PIXEL_DOM_FACTS` (§2.4), keyed by selector:
`{"[data-design-node='12:345']": { ... }}`. It is a session artefact, so it goes through the canonical
writer rather than a relative path:

```bash
che write_file_atomic "$CHE_PIXEL_DOM_FACTS" <<'JSON'
{ ... the object evaluate_script returned ... }
JSON
```

**Do not hand-write the extraction.** `assets/dom-facts-extractor.js` is the committed extractor: it
carries §4.2's determinism rules as code, refuses to run under conditions that would make its numbers
meaningless, and returns the bag in exactly this shape. Inject the map and the captured width as page
globals, then pass the file's content to `evaluate_script` (§2.3 below has the recipe).

`coord_frame` is **mandatory on every element**, because without it the comparator cannot tell a real
match from a coincidence. `getBoundingClientRect()` is **viewport**-relative while the design is
**parent**-relative, so declaring `viewport` against a `parent` reference is not a layout mismatch, it
is two different origins subtracted. The engine refuses to compare positions unless both sides declare
the same frame (§4.4).

`kind` is recorded **provenance** — what the extractor was told the element is — and a bag may omit it.
The applicability rule that keeps a frame's missing font from escalating reads the **design** node's
kind (§4.1), not this one, so requiring it here would add a precondition that changes no comparison.

The bag is validated before the run is scored (`che_core/pixel_dom.py`): a wrong unit — `line_height` in
px where §1 #8 compares the multiplier — is reported as a usage error instead of being scored as an
enormous deviation, and a selector the map names but the bag lacks is refused rather than turned into a
false `missing_from_dom` failure.

### 2.4 Run the comparator

Resolve the artifact set first. **Do not type these paths by hand** — `che pixel paths` is the single
source of truth for where they live (§2.3, §4.1–§4.3), and a hand-typed name is a name the next run
cannot find:

```bash
eval "$(che pixel paths "$WORKTREE_ROOT" "$SESSION_ID" \
  --sub-product <sub_product> --breakpoint lg --backend figma \
  --related-id "$RELATED_ID" --attempt 1)"
# → CHE_PIXEL_DIR · CHE_PIXEL_MAP · CHE_PIXEL_DESIGN_FACTS · CHE_PIXEL_DESIGN_RAW
#   CHE_PIXEL_DOM_FACTS · CHE_PIXEL_REPORT
#   CHE_PIXEL_DESIGN_IMAGE · CHE_PIXEL_DOM_SCREENSHOT · CHE_PIXEL_VISUAL_DIFF (§4.5)
#   CHE_PIXEL_CROP_REPORT · CHE_PIXEL_CROP_SHEET (§4.5, per element)
```

```bash
che pixel check \
  --map "$CHE_PIXEL_MAP" \
  --dom "$CHE_PIXEL_DOM_FACTS" \
  --design-source "$CHE_PIXEL_DESIGN_RAW" --design-backend figma \
  --design-facts-out "$CHE_PIXEL_DESIGN_FACTS" \
  --design-viewport "$DESIGN_WIDTH" --dom-viewport "$DOM_WIDTH" \
  --breakpoint lg --attempt 1 \
  --out "${DOMAIN_GATE_REPORT:-$CHE_PIXEL_REPORT}"
```

`$DOMAIN_GATE_REPORT` is the generic report slot `che-ship §0.9.5` sets for every gate it runs; the typed
name is the standalone default. They are the same artefact, so exactly one of them is written — the gate
never produces a report the caller does not know about.

The resolved set is split by lifetime, and the split is load-bearing:

| Artifact | Lives | Why there |
|---|---|---|
| `CHE_PIXEL_MAP` (§4.3) | inside the worktree, `design/<sub_product>/pixel-check/<breakpoint>.map.json` | human-approved and **frozen as regression**: a stable name is what lets the next run prove it measured the same reference, and the PR diff is where a reviewer approves it |
| `CHE_PIXEL_DESIGN_FACTS` (§4.1) | beside the map | the per-element record a reviewer reads instead of the raw capture |
| `CHE_PIXEL_DESIGN_RAW` (§4.1) | beside the map (`figma`), or `design/<sub_product>/source/home.op` (`openpencil`) | the artefact the numbers were read from, so a re-run derives them from the same bytes |
| `CHE_PIXEL_DOM_FACTS` (§4.2) | session, `design/<related_id>/<timestamp>-<sub_product>-<breakpoint>-dom-facts.json` | a measurement of one attempt, never committed |
| `CHE_PIXEL_REPORT` | session, `…-check-attempt<N>.json` | §5 allows **one** retry, so the attempt number is in the name: attempt 2 must not erase attempt 1, or the budget is unauditable after the fact |
| `CHE_PIXEL_DESIGN_IMAGE` · `CHE_PIXEL_DOM_SCREENSHOT` · `CHE_PIXEL_VISUAL_DIFF` (§4.5) | session, `…-design.png` · `…-dom.png` · `…-visual-diff.png` | evidence, so the same rule as any other measurement: nothing scores it, therefore nothing commits it. `$CHE_PIXEL_DIR` holds only what a reviewer *approves*; a rendering of a layout still being fixed would go stale in the diff |
| `CHE_PIXEL_CROP_REPORT` · `CHE_PIXEL_CROP_SHEET` (§4.5, per element) | session, `…-crop-report-attempt<N>.json` · `…-crop-sheet-attempt<N>.png` | the same, except that the report carries `--attempt` like the measurement it describes: it is the artefact that says *which* element a difference is in, so attempt 1's must survive attempt 2 |

`che pixel paths` refuses (exit `2`) a sub-product whose design tree does not exist yet — `che designer
init` creates it — so a mistyped slug cannot silently become a second design root that no skill owns.

`--attempt` is the pass number: `1` for the first measurement, `2` for §5's single free retry. The runner
**refuses `> 2`** (exit `2`) unless `--override-reason "<verbatim user text>"` is also given, so the loop
cannot run past its budget by accident. Resolve the paths again with the same `--attempt` value before a
retry, so the second report lands under its own name.

`--design-viewport` and `--dom-viewport` are the widths each side was captured at. When both are given
and disagree the command **refuses** (exit `2`) rather than scoring: 375 compared against 1440 does not
make the numbers slightly wrong, it makes every one of them meaningless. When either is omitted the
report records `viewport=undeclared`, and a PASS from such a run is weaker evidence — it must say so in
the PR.

`CHE_PIXEL_MAP` (§4.3) is the only join between the two sides and is human-approved and frozen. An
element missing from it is silent scope reduction: that element is simply never compared.

Branch on the exit code; do not parse the text.

| Exit | Verdict | Meaning |
|---|---|---|
| `0` | `PASS` | The three §3 conditions held. |
| `1` | `FAIL` | A §3 condition broke, **or** a designed element is absent from the DOM. |
| `3` | `INCONCLUSIVE` | Could not be decided honestly — see §2.5. |
| `2` | usage | Unreadable artefact, incomplete map entry, unknown backend, or a **viewport mismatch**. |

### 2.5 INCONCLUSIVE is never a pass

It means "could not verify", and `§0.9.5` MUST treat it as a hard stop rather than a skip-to-green:

- a critical (×2) category was measured on **no** element, and inapplicability does not explain why.
  Which side stayed silent is deliberately irrelevant: the design source not exposing `padding` and the
  caller not collecting `font-family` from the DOM leave the gate equally blind, so the second must not
  become a way to opt out of the escalation by simply not measuring;
- a declared element has **no** design reference — usually a stale `design_node` or the wrong backend;
- nothing at all was measurable, so the two artefacts share no comparable property.

A category missing from *one* element is **not** a gap: a text node has no explicit padding row and a
frame has no font, so those report `not_applicable` instead of escalating.

### 2.6 `coverage` — what a PASS did not look at

The score is computed over the rows that were **verified**, so a high score cannot mean "this page is
visually identical". It means "among the properties that could be measured, the weighted match was
high". `coverage` is the fraction of §1's own surface that the run actually reached
(`verified categories / 18`); `unverified` names the remainder.

The denominator is 18, not 19, and the report names what was held back: `unreachable_categories`
carries `margin`. #5 splits into two engine categories (`border_width` and `border_color`) and is the
only row that does — so §1's 18 rows and the engine's 19 categories differ by exactly that split.
`margin` (#3) is *unreachable*: the DOM extractor measures all four computed sides, but neither design
backend has a code path that emits one, because neither authoring tool models a margin any more —
auto-layout replaced it with `gap` (#14). Every run in this gate's history would therefore report it
`absent_from_design` and pay a permanent loss for a comparison that was never on offer. That is a
different thing from `unverified`, which names rows *this* run did not reach and which more mapping or
a richer fact set can close. Keeping it in the denominator made the ceiling unreachable by
construction; dropping it silently would have hidden a hole in the gate. So it leaves the fraction,
stays in §1 and in the category numbering, and is printed by name — disclosed, not discounted.

Both are on the summary line, together with `unreachable` when the held-back set is non-empty. A `PASS`
**MUST** be quoted together with them in the PR description —
`status=PASS score=9.5 coverage=0.21 unverified=padding,radius,position unreachable=margin` is an honest
statement, and `status=PASS score=9.5` alone is not.

Coverage is deliberately **not** a PASS condition. The numerator moves with things that are nobody's
fault (`.op` has no coordinates at all; the Figma bridge emits no `letterSpacing`), so a fixed floor
would either never bind or block honest work — inventing a threshold for it would be exactly the
unprincipled number this gate exists to avoid. Treat a low coverage as a prompt to widen the mapping
or the fact set, not as a failure.

Known unverified-by-default categories, all visible in `unverified`: `position` (never from `.op`,
and only when both sides declare the same frame), `letter_spacing` (never from Figma), `opacity` (never
from `.op`) and `asset` (opt-in: a map entry that declares no digest has not asked for the check).
Raising any of them is a mapping or fact-set change, not a code change. `margin` is deliberately **not**
in this list — it is unreachable rather than unverified, and so is reported separately.

> `executable: true` does not promise a verdict for every input. It promises a mechanism that runs —
> and that says "I could not measure this" instead of inventing a PASS.

---

## 3. Final Score 0–10 (weighted average by importance)

Each element above has a different WEIGHT for the score (more important = higher penalty if wrong):

| Weight | Categories |
|---|---|
| **×2 (Double weight · Critical Element)** | #2 Internal padding, #6 Font-size, #7 Font-weight, #10 Foreground color, #15 Font-family, #17 Asset identity |
| **×1.5 (Medium weight)** | #3 Margin, #4 Radius, #13 X/Y Position, #14 Auto-layout gap |
| **×1 (Standard weight)** | All other remaining categories |

### Calculation
```
raw_score_per_element = max(0, 1.0 - (measured_deviation / allowed_tolerance))
weighted_score = Σ (raw_score_per_element × WEIGHT) / Σ WEIGHTS
final_score_0_10 = round(weighted_score × 10, 1)
```

### PASS Condition (all 3 must be TRUE simultaneously)
1. `final_score_0_10 ≥ 8.0`
2. `(total_passed_measurements / total_measurements) ≥ 0.95` (95% of individual values within tolerance)
3. **No ×2 WEIGHT (critical) category is wrong.** Concretely: no critical measurement exceeds its 8px budget, **and** no critical category that carries *no tolerance* (#7 font-weight, #15 font-family) is mismatched at all — there is no such thing as "3px of the wrong typeface", so an 8px budget does not describe them and their deviation is a flag rather than a length. A CTA button with 8px of wrong padding, or the wrong font, fails the run even when the overall score is 9.0.

---

## 4. Mechanism — the artifact contracts

> **Superseded (do not use):** earlier versions of this file declared the primary tool as
> `mcp_open-pencil.diff_jsx(file_id, node_id, actual_dom_screenshot)`. That signature does not exist.
> The real `diff_jsx(from, to, document_id?, page_id?)` is a *structural* diff between two nodes of the
> same document — it reports added/removed children and changed props, never measurements, and it
> cannot see the DOM at all. The `figma-cli` fallback was equally fictional: Figma ships no official
> CLI, and the official integration is the MCP bridge. Kept as a warning: a plausible-looking tool
> signature that nothing can execute is how this gate came to be declared "executable" while being
> impossible to run.

The gate compares **numbers, not pictures**. §1's 17 categories are properties; both sides must be
reduced to the same property schema before any comparison happens.

### 4.1 Reference side → `$CHE_PIXEL_DESIGN_FACTS`

| Backend | Tools | Output |
|---|---|---|
| `figma` | `mcp_Figma_AI_Bridge.get_figma_data(fileKey, nodeId)` for properties; `download_figma_images` for assets | one record per element |
| `openpencil` | `mcp_open-pencil.get_jsx(node)` + `node_bounds` + `analyze_spacing` / `analyze_typography` / `analyze_colors`; `export_svg` / `export_image` for assets | one record per element |
| `penpot` | **not implemented.** The official `@penpot/mcp` server exposes `execute_code` (JS against the Plugin API) and no fact-export tool, so a bag has to be produced by a script, **recorded from a real session and pinned by a fixture** before a run can be trusted. Until then `--design-backend penpot` is refused (`2`, `no extractor`); a hand-built bag goes in through `--design` with `penpot` as provenance. `domains/ux/connectors/penpot.config.md` → "Wiring status" | — |

Per `DESIGN_BACKEND_CONTRACT.md`, the backend is resolved fail-closed and never converted between
engines. A backend the domain declares but no extractor reads is refused **by name**, separately from a
misspelling: the connector tells a designer Penpot is supported, so a refusal shaped like a typo would
send them to check a spelling they got right. `che pixel check --design-facts-out "$CHE_PIXEL_DESIGN_FACTS"` writes the record from the same
extraction it scores, so the file cannot be a hand-copied transcription that drifts from the numbers:

```jsonc
{ "cta-button": {
    "design_node": "12:345",
    "selector": "[data-design-node='12:345']",
    "breakpoint": "lg",
    "facts": { "kind": "instance", "coord_frame": "parent",
               "box_size": { "width": 320, "height": 52 },
               "box_origin": { "x": 480, "y": 220 },
               "padding": [12, 24, 12, 24],
               "gap": [16, 16],
               "radius": [8, 8, 8, 8],
               "border_width": 1, "border_color": "#E4E4E7",
               "font_size": 18, "font_weight": 600, "font_family": "Poppins",
               "line_height": 1.2, "letter_spacing": 0,
               "fg": "#18181B", "bg": ["#FFFFFF"],
               "shadow": { "x": 0, "y": 2, "blur": 8, "spread": 0, "alpha": 0.08 } } } }
```

`bg` is a **list** even when it holds one paint (§1 #11 compares the whole stack, bottom-to-top), and
`line_count` appears only on text whose box hugs its content (§1 #18).

Text and git-diffable on purpose: it is the artefact a PR reviewer can actually check, and it is written
to `$CHE_PIXEL_DESIGN_FACTS` **inside the worktree** (§2.4) so the diff carries it. `breakpoint` is a
scalar rather than a map of breakpoints because the file is one per breakpoint — advertising a shape the
resolver never produces is how a reader learns to distrust the schema.

The vocabulary is deliberately the **flat** one, not a nested presentation (`w`/`h`,
`border: {width, color}`, `font: {size, …}`). Those are the same numbers in a second schema, which would
have to be kept in sync by hand and could then disagree with what was scored — the failure this gate
exists to remove, one level down. So there is one vocabulary, and the record and the comparison are the
same values:

| Shape | Where | Consumed by |
|---|---|---|
| **Per-element record** (the JSON above: the flat facts, keyed by element) | `$CHE_PIXEL_DESIGN_FACTS`, for humans | the reviewer; the PR description |
| **Flat per-node facts** (`{"<design_node>": {"kind": "frame", "coord_frame": "parent", "padding": [...], …}}`) | in memory | `che pixel check` — `--design-source` extracts it from `$CHE_PIXEL_DESIGN_RAW`, or `--design` reads it pre-extracted |

An element whose `design_node` the extractor could not read keeps an entry with an empty `facts` object
rather than being omitted: "this node was unreadable" and "this element was never mapped" are different
findings, and §2.6 depends on the difference being visible.

**An omitted zero is a value, not a gap.** The rule is per property, and it is what decides whether an
absence becomes a measurement or stays unverified:

| Property | Exists on | Omitted means | On anything else |
|---|---|---|---|
| `padding` | auto-layout containers only | `[0,0,0,0]` | no value emitted → unverified |
| `radius` | boxes (frame, rectangle, instance, component, group) | `[0,0,0,0]` | no value emitted → unverified |
| `opacity` | any Figma node | `1.0` | `.op` cannot express it → unverified |
| `bg` | any node carrying fills | one paint is a one-element stack; a stack is read whole | a layer that is not a comparable paint (an image) → the whole stack is omitted → unverified |
| `fg` | any node carrying fills | the **top-most** paint, which is the visible ink | same rule |
| `line_count` | text whose box hugs its content (§1 #18) | — (nothing is defaulted) | a `.op` `fixed-width` box, or a Figma `fill`/`fixed` box, wraps at a width the source never states → omitted → unverified |

Reading the first case as "the source withheld it" made a ×2 critical category unmeasurable on every
auto-layout screen, so such a page returned INCONCLUSIVE even when everything else was comparable.

The runner deliberately does not read the per-element record: it re-parses the raw `get_figma_data`
/ `.op` artefact on every run (§2.2), so the numbers it scores can never drift from the design file
they came from. `--design` exists for the case where the extraction already happened; it expects the
flat, node-keyed form, not the nested one.

### 4.2 Implementation side → `$CHE_PIXEL_DOM_FACTS`

Measure the live DOM — **never photograph it** — with the committed extractor.
`assets/dom-facts-extractor.js` is the only sanctioned producer of this bag: inject the map and the
captured width as page globals, then hand the file's content to
`mcp_Chrome_DevTools_MCP.evaluate_script`. It returns the bag directly, and it throws rather
than returning numbers when `devicePixelRatio !== 1`, when the page width disagrees with the declared
one, or when its globals are absent — because a measurement taken under the wrong conditions looks like
evidence and is not.

Every record carries `coord_frame`, which position depends on (§2.3). The rules below are why this is a
script and not a paragraph: prose cannot enforce a determinism rule, and each of these was ignored at
least once while the recipe was prose.

For #14 the record needs the computed `row-gap` / `column-gap`. An element that is not a flex or grid
container reports `normal`, which is **omitted** rather than coerced to 0: `normal` is not a
measurement, and a fabricated zero would fail the element against a design that never asked for one.

`bg` is the whole paint stack, **bottom-to-top**, and the extractor re-orders to get there: CSS names
`background-image` top-first and paints `background-color` underneath every one of them, while the design
side states `fills` bottom-to-top. That reversal *is* the comparison, and it is why a stack can now be
compared at all — the single top paint is what a design with a tint over a base used to be scored
against. One non-comparable layer (`url(...)` is an image) omits the whole property rather than being
skipped, because skipping would shift every layer after it and pair the design's layer *n* with this
side's layer *n-1*. A single paint is still emitted as a one-element list, so the property has one shape.

`line_count` — the number of client rects a text leaf's `Range` produces — is now §1 #18 and is scored
where the design can state it, which is only where wrapping is impossible (§4.1).

Determinism rules — without these the gate measures noise and the score is meaningless:

- fixed viewport per breakpoint, `deviceScaleFactor: 1`, one run each
- `await document.fonts.ready` **before** reading (otherwise you measure fallback-font metrics)
- animations / transitions / caret disabled; `prefers-reduced-motion` emulated
- element scrolled into view, then wait for two consecutive identical rects
- browser version and font files pinned — a font substitution invalidates every typography row
- non-deterministic subtrees excluded via the map (avatars, timestamps, maps, ads, user content)

### 4.3 Element map → `$CHE_PIXEL_MAP`

Design node → DOM element cannot be inferred reliably, so it is declared once, approved by a human,
and frozen as regression. It is committed at
`design/<sub_product>/pixel-check/<breakpoint>.map.json` (§2.4) — one map per breakpoint, because a 375
layout and a 1440 layout are two references, not one that drifted. Add `data-design-node="12:345"` in
the JSX so the map is self-documenting in the code.

```jsonc
{ "cta-button": { "design_node": "12:345", "selector": "[data-design-node='12:345']" },
  "hero-icon":  { "design_node": "12:400", "selector": "[data-design-node='12:400']",
                  "asset_sha256": "<64 lowercase hex>" } }
```

`asset_sha256` is **optional** and opts that element into §1 #17: it is the digest of the bytes the
implementation must serve — `sha256sum` of the committed file (or of the response body). It is declared
in the map because the design source carries an opaque vendor reference (`imageRef`), never the digest of
what will be served, so only the human freezing the map can state it. An element without it is reported
`not_applicable` for #17, not unverified: no check was asked for.

`design_box` is **optional** and read only by §4.5's per-element crop — nothing scored looks at it:

```jsonc
{ "cta-button": { "design_node": "12:345", "selector": "[data-design-node='12:345']",
                  "design_box": { "x": 480, "y": 220, "width": 320, "height": 52 } } }
```

It is the node's box in the **design image's own pixels**, which neither fact set carries — the design
side states a parent-relative origin and the DOM side a viewport-relative one, and a raster has a third
frame. Inferring it by summing ancestor origins is not attempted: the facts carry no parent links, and a
wrong crop is a confident picture of the wrong region. An element without it is refused by the crop tool
and simply absent from the sheet; it changes nothing in the verdict.

### 4.4 Comparator → pure function, no LLM

Implemented in `che_core/pixel.py` and invoked as `che pixel check` (§2.4). The functional core is
pure: it takes the two fact maps and the map, and returns deviations plus a score, applying §1's
tolerances and §3's weights and PASS conditions verbatim. All I/O — fetching the design, measuring
the browser, writing the report — happens in the caller, which is what makes the comparator testable
offline against frozen artefacts.

It is code and not a judgement call on purpose: a model deciding whether 3px is "close enough" to 4px
is exactly the subjectivity this gate forbids.

Two refusals are built into it, both of which exist because a confident wrong number is worse than a
missing one:

- **Positions are only compared inside a matching declared frame.** The design side is parent-relative
  and `getBoundingClientRect()` is viewport-relative; differencing them measures the distance between
  two origins. An undeclared or disagreeing `coord_frame` leaves `position` unverified instead —
  which is why a run against an `.op` document always reports `position` unverified, since an
  auto-layout tree has no coordinates to give.
- **A viewport mismatch is refused outright**, not scored and footnoted (§2.4).

### 4.5 Image diff (evidence only — never the verdict)

This is the instrument §6.1 falls back on for what no per-element property can see: `object-fit`, crop,
`<svg>` path data, reflow, paint order. `che pixel check` does not produce it and no verdict reads it —
the comparison is numeric, and a whole-frame delta is deliberately not a PASS/FAIL signal
(`tool_evidence_only`, §6.1). The step is **manual**, and a manual step that nobody records is a step
nobody takes, so the PR must name `$CHE_PIXEL_VISUAL_DIFF` when it exists — and say so when it does not.

Both sides are rasterised at the same declared width (§2.3), and their sizes must agree: a comparison
across two sizes returns a number computed against the wrong pixels rather than an error, which is the
one way this evidence can lie. `che pixel diff` refuses that case (exit 2) rather than producing it.

| Side | Tool | Target |
|---|---|---|
| design | `mcp_open-pencil.export_image` (scale 2) or `mcp_Figma_AI_Bridge.download_figma_images` | `$CHE_PIXEL_DESIGN_IMAGE` |
| implementation | `mcp_Chrome_DevTools_MCP.take_screenshot` at the §2.3 viewport | `$CHE_PIXEL_DOM_SCREENSHOT` |

```bash
che pixel diff \
  --design "$CHE_PIXEL_DESIGN_IMAGE" --dom "$CHE_PIXEL_DOM_SCREENSHOT" \
  --out "$CHE_PIXEL_VISUAL_DIFF"
```

The comparison is `pixelmatch` 7.2.0's: a YIQ colour distance (Kotsarenko & Ramos) gated by an
anti-aliasing detector (Vysniauskas, 2009). `che_core/pixel_visual.py` is a port of it, and
`tests/test_pixel_visual.py` holds that port to the package's own counts — so the picture is the one the
npm tool drew, without a Node toolchain in the harness and without adding a dev dependency to the
repository being judged.

Differing sizes are the only non-zero exit. A screen that differs is the finding, not a failure to run:
nothing reads this file.

The percentage is **not** a threshold and must never be quoted as one: dominant causes are text
antialiasing, DPR and font-loading, while a 2px radius error barely moves it. The file is for the
reviewer's eye, and the number is for context.

#### Per element — `che pixel crop`

The frame delta above answers "did this screen change". It cannot answer "which element", because its
percentage is dominated by the noise of everything that is not the element you are asking about. The
crop is the same instrument narrowed to one box, and it is what makes the residue §6.1 lists —
`object-fit`, crop, `<svg>` path data, reflow, paint order — readable at all.

It is still **evidence**: nothing scores it, it never exits non-zero on a difference, and its ratio is
not a pass mark.

```bash
che pixel crop \
  --design "$CHE_PIXEL_DESIGN_IMAGE" --dom "$CHE_PIXEL_DOM_SCREENSHOT" \
  --map "$CHE_PIXEL_MAP" --dom-facts "$CHE_PIXEL_DOM_FACTS" \
  --out "$CHE_PIXEL_CROP_REPORT" --sheet "$CHE_PIXEL_CROP_SHEET"
```

Two things it needs that no other step does, both stated rather than inferred:

- **`design_box` on the map entry** — `{ "x": 480, "y": 220, "width": 320, "height": 52 }` in the
  **design image's own pixels**. Neither fact set carries image coordinates: the design side is
  parent-relative (§4.2) and the DOM side is viewport-relative. Only the caller who exported the frame
  knows where a node sits inside it, and summing ancestor origins is not possible from the facts. The
  DOM side needs nothing extra — at `devicePixelRatio === 1` a viewport screenshot's origin *is* the
  viewport origin, which is what `coord_frame: "viewport"` asserts.
- **Boxes of the same size.** A mismatch is recorded as `size_mismatch` and the two crops are shown
  side by side; the tool deliberately does **not** scale one to the other, because resampling would
  invent the pixels it then compares and would erase the size drift, which is itself the finding.

Rows in the sheet follow the JSON's `elements` order — that is the legend, since drawing labels would
mean shipping a font to a tool that draws pixels, not type. Every element keeps its row: an element
that was refused renders blank and its reason is in the JSON, so the strip never shifts a picture onto
the wrong element and "could not measure" never looks like "matched".

---

## 5. Retry Policy (same as A11y gate)

**Why this is bounded — the anti-loop rule.** A pixel gate is a *measure → edit → measure* loop, and the
one thing an agent cannot supply is the decision to stop. So the bound is a mechanism, not a promise:

- The runner takes `--attempt N` and **refuses to execute when `N > 2`** (exit `2`) unless the caller
  also passes `--override-reason "<verbatim user text>"`, which is recorded in the report and shown on
  the summary line. Two attempts is the entire budget: one measurement plus the one free retry below.
- Every report carries `attempt`, `design_map_sha256` and `design_source_sha256`. A re-run whose hashes
  changed is **not a retry** — it is a *new baseline*, and comparing its score to the previous one is
  meaningless. Widening the map until the gate speaks is moving the goalposts; the hashes are what make
  that visible instead of deniable.
- The loop terminates on a verdict, and only **FAIL** creates work. PASS ends it. INCONCLUSIVE ends it
  too: its causes are almost never in the implementation (see the third row), so re-running the same
  check cannot resolve it.

| Failure # | Action |
|---|---|
| **1st failure** | **FREE AUTOMATIC Retry**: Take the 3 measurements with HIGHEST deviation (top 3 — `che pixel check` prints them as `fix:` lines, worst first) and apply the obvious fix (padding: 12→16, radius: 4→8, color: #...). Re-run the gate ONE more time, declaring `--attempt 2`. |
| **2nd failure** (after automatic retry) | **HARD STOP ship §0.9.5 DOMAIN GATES.** Do not open PR. Message: "GATE G-UX-2 PIXEL FAIL after retry. Current score = {s} ≥8.0? N. Top 3 deviations: [...]. Manual fix or EXPLICIT_OVERRIDE VERBATIM user logged in decisions.log." |
| **INCONCLUSIVE** (exit `3`) | **HARD STOP, and never a loop.** The gate could not measure, so there is no score to retry against. Classify §2.5's `reason` before acting: a *procedural* cause (wrong `--design-backend`, stale `design_node`, renamed selector, viewport mismatch, or a DOM fact bag that never collected the property) is repairable **once**; a *structural* cause (a category the source does not expose, an element the map omits) is **not repairable by re-running** — widening the map until the gate speaks is moving the goalposts, and the report's digests record that it happened. For a structural cause, disclose the blind spot from §6.1 in the PR and stop. Never override to PASS: the override exists for a *measured* disagreement, not for a missing measurement. |
| **EXPLICIT_OVERRIDE (ONLY user VERBATIM)** | `[EXPLICIT_OVERRIDE] domain=ux gate=pixel-check-gate old=8.0 new={x.y} reason="..."` |

---

## 6. What this gate DOES NOT do (delimited purpose, KISS)
- ❌ Does not evaluate "visual beauty" / personal taste → only numerical deviation.
- ❌ Does not validate animations / motion → motion stays in `domains/ux/gates/motion-gate.md` (future phase 2, not created today).
- ❌ Does not validate textual content copy → separate copywriting domain copy gate (future phase 2).
- ❌ Does not replace A11y validation → run A11y Gate BEFORE this one. Correct layout with inaccessible content = Fail.

### 6.1 It does not answer "is it identical to the Figma?"

This is the most important limitation to read before quoting a PASS. §1 measures **geometry and text
metrics on the elements you mapped**. That is a useful, strictly numeric subset — and it is not visual
equivalence. A page can score 10.0 while being visibly wrong, because each of the following is outside
§1, or only partly inside it. All of them were found by inspection, none of them is hypothetical:

| Not measured | Consequence |
|---|---|
| **Images, SVGs, icons** | **Closed for identity — now §1 #17** (exact digest, ×2, opt-in via the map). Still outside §1: `object-fit`, crop and an `<svg>`'s path data — identity catches "the wrong asset", not "the right asset, mis-cropped". |
| **Font *family*** | **Closed — now §1 #15** (exact match, ×2). The gap it closes was the worst shape a hole can take: a different typeface with matching metrics scored 100 %. |
| **Gradient and multi-fill** | **Closed for a stack, up to the layer order a source states.** §1 #11 now compares the whole paint stack (`layer[0]`…), not the first paint: a design with a tint over a base scored against the base alone used to pass, which is a confident match rather than a gap. Figma states `fills` bottom-to-top and the DOM side re-orders CSS into that direction; a `.op` stack is omitted, because that format documents no direction and guessing it inverts the comparison. Outside §1 still: a gradient whose axis is stated in a non-numeric form on one side (`to right` vs `90deg`), where the axis is not compared. |
| **Element visibility** | **Partly closed — now §1 #16** (`opacity`, ≤ 0.04). Still outside §1: `display`, `visibility`, clipping and occlusion. An element hidden by any of those, at full opacity, still passes every row. |
| **Paint order / z-index** | **Accepted limit, not a pending task.** Figma states no `z-index`, and the failure is two elements *swapping* while each keeps its own box — so no per-element property can see it. It would need a run-level comparison of the design tree's sibling order against the DOM's document order for the mapped elements, and neither order is collected. Deliberately not built: it is a second, differently-shaped comparison inside a gate whose contract is per-element absolute measures, and every property in §1 would keep its own meaning while this one alone needed a structural one. §4.5's per-element crop is where a swap is visible to a human eye, which is the instrument that already exists for it. |
| **Alignment to the grid** | **Closed by §1 #13 as far as it can be measured.** A misaligned element is a displaced one, which #13 measures — **when both sides declare the same frame** (the implementation side emits `box_origin` relative to its mapped parent with `coord_frame: "parent"`). Deriving a column index from the parent's `gridTemplateColumns` would be inference rather than measurement, so it is not attempted; a grid *tool* is a different instrument from a numeric deviation gate. |
| **Text reflow** | **Closed — §1 #18.** The design side states a line count only where wrapping is impossible: `sizing.horizontal: "hug"` (Figma) or `textGrowth: "auto"` (`.op`) says the box took the text's own size, so the rendered lines are the text's own breaks. A fixed/filled box wraps at a width the source never reports and the property is omitted — unverified, not a pass. This is what catches text that fits the design and wraps in the browser. |
| **Sub-tolerance drift** | 3px of padding everywhere, or a uniform 5px position shift, is inside tolerance on every row and invisible in the aggregate. Accepted: the tolerances are the product decision, and `coverage` is what discloses how much of §1 they covered. |
| **Margin** | **Permanently unreachable — §1 #3.** This one is inverted: the *implementation* side measures it (all four computed margins), and no design backend emits one — neither authoring tool models a margin any more, because auto-layout replaced it with `gap`. So the comparator can only ever report `absent_from_design`, and §2.6 holds it out of `coverage` under `unreachable_categories` rather than pretending it was checked. The mechanism modern frames actually use to space children is `gap`, which **is** measured (#14). |

The image diff (§4.5) remains the instrument for the rendering-level residue — `object-fit`, crop, path
data, paint order — and it is deliberately **not** the PASS/FAIL signal (see `tool_evidence_only`). So
the two methods have complementary blind spots and this gate machine-checks only one of them. When
"identical to the design" is the actual requirement, the numeric gate is necessary and not sufficient:
the reviewer still has to look at `$CHE_PIXEL_VISUAL_DIFF` — and at `$CHE_PIXEL_CROP_REPORT`, which
narrows the same instrument to one element's box, because a whole-frame percentage is dominated by
everything that is *not* the element in question. Reflow is no longer on this list: §1 #18 scores it
where the design can state a line count.

`coverage` (§2.6) is the honest summary of how much of the surface above was reached — not a substitute
for it.
