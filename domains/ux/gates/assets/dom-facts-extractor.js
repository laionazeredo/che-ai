/**
 * che pixel check — implementation-side fact extractor (gate §2.3 + §4.2).
 *
 * WHY THIS FILE IS JAVASCRIPT AND NOT PYTHON
 * -----------------------------------------
 * `che_core/pixel.py` is a pure comparator and never touches a browser. Measuring a
 * rendered element can only be done from inside the page, so the extraction lives
 * here, as the single function the agent hands to `mcp_Chrome_DevTools_MCP.evaluate_script`
 * *verbatim*. Before this file existed the recipe was prose in the gate, and every run
 * re-improvised it — which is how the units drifted (`line-height` in px instead of a
 * ratio) and how a forgotten property turned into a silent gap.
 *
 * HOW TO CALL IT
 * --------------
 * 1. `navigate_page` with `initScript` setting the two globals below, so the preconditions
 *    are asserted by the page rather than declared by the caller:
 *
 *        window.__CHE_PIXEL_MAP__ = { "<css selector>": "<kind>" };
 *        window.__CHE_PIXEL_VIEWPORT__ = 1440;   // the width the design was captured at
 *
 * 2. `resize_page` to that same width, then `evaluate_script` with THIS FILE'S CONTENT
 *    as the `function` argument. It returns the `dom-facts.json` bag directly: keyed by
 *    selector, ready for `che pixel check --dom`.
 *
 * WHAT IT REFUSES, AND WHY THAT IS THE POINT
 * ------------------------------------------
 * A measurement taken under the wrong conditions is worse than no measurement, because
 * it looks like evidence. So this function throws instead of returning numbers when:
 *   - the map is missing (nothing to measure),
 *   - `devicePixelRatio !== 1` (CSS px would not be the px the design states),
 *   - the page width disagrees with `__CHE_PIXEL_VIEWPORT__` (the design and the DOM
 *     would have been captured at different sizes).
 * Animations and transitions are neutralised with a stylesheet rather than left to an
 * emulated media feature, and each element is only read once two consecutive frames
 * report the same rect. A rect that is still moving is not a measurement.
 */

async () => {
  const map = window.__CHE_PIXEL_MAP__;
  const expectedWidth = window.__CHE_PIXEL_VIEWPORT__;

  if (!map || typeof map !== "object" || Array.isArray(map)) {
    throw new Error(
      "che: window.__CHE_PIXEL_MAP__ is not set — inject {\"<selector>\": \"<kind>\"} via initScript before navigating",
    );
  }
  if (window.devicePixelRatio !== 1) {
    throw new Error(
      `che: devicePixelRatio is ${window.devicePixelRatio} — CSS pixels are only comparable to the design at 1`,
    );
  }
  if (expectedWidth && window.innerWidth !== expectedWidth) {
    throw new Error(
      `che: the page is ${window.innerWidth}px wide but __CHE_PIXEL_VIEWPORT__ declares ${expectedWidth}px — ` +
        "the design and the DOM would have been captured at different sizes",
    );
  }

  const overrides = document.createElement("style");
  overrides.textContent =
    "*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}";
  document.head.appendChild(overrides);

  await document.fonts.ready;

  const num = (value) => {
    const parsed = parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const round = (value) => (value === null ? null : Math.round(value * 100) / 100);

  /** Split on commas that are not inside parentheses — a colour function has its own. */
  const splitTopLevel = (value) => {
    const parts = [];
    let depth = 0;
    let current = "";
    for (const char of value) {
      if (char === "(") depth += 1;
      else if (char === ")") depth -= 1;
      if (char === "," && depth === 0) {
        parts.push(current.trim());
        current = "";
        continue;
      }
      current += char;
    }
    parts.push(current.trim());
    return parts.filter((part) => part.length > 0);
  };

  /** The first shadow, in the five axes the gate's §1 #12 compares. */
  const firstShadow = (value) => {
    if (!value || value === "none" || value.includes("inset")) return null;
    const first = splitTopLevel(value)[0];
    if (!first) return null;
    const lengths = (first.match(/-?\d+(?:\.\d+)?px/g) || []).map(parseFloat);
    if (lengths.length < 2) return null;
    let alpha = 1;
    const rgba = first.match(/rgba?\(([^)]*)\)/);
    if (rgba) {
      const channels = rgba[1].split(",").map((channel) => channel.trim());
      if (channels.length === 4) {
        const parsed = parseFloat(channels[3]);
        if (Number.isFinite(parsed)) alpha = parsed;
      }
    }
    return {
      x: lengths[0],
      y: lengths[1],
      blur: lengths[2] === undefined ? 0 : lengths[2],
      spread: lengths[3] === undefined ? 0 : lengths[3],
      alpha,
    };
  };

  /** Line boxes of a leaf's own text: equal computed styles can still wrap differently. */
  const lineCount = (element) => {
    if (element.children.length > 0) return null;
    const range = document.createRange();
    range.selectNodeContents(element);
    const tops = new Set(Array.from(range.getClientRects()).map((rect) => Math.round(rect.top)));
    return tops.size === 0 ? null : tops.size;
  };

  /** Two consecutive identical rects, or the last reading after 30 frames. */
  const settle = async (element) => {
    let previous = null;
    for (let frame = 0; frame < 30; frame += 1) {
      const rect = element.getBoundingClientRect();
      const key = `${rect.x},${rect.y},${rect.width},${rect.height}`;
      if (key === previous) return rect;
      previous = key;
      await new Promise((resolve) => requestAnimationFrame(resolve));
    }
    return element.getBoundingClientRect();
  };

  const facts = {};
  for (const selector of Object.keys(map)) {
    const element = document.querySelector(selector);
    // Absent from the DOM is a *finding*, not an error: the comparator reports it as
    // `missing_from_dom` and fails the run. Swallowing it here would hide a designed
    // element that never shipped.
    if (!element) continue;

    const rect = await settle(element);
    const computed = getComputedStyle(element);
    const fontSize = num(computed.fontSize);
    const lineHeightPx = num(computed.lineHeight);
    const spacingPx = num(computed.letterSpacing);
    const rowGap = num(computed.rowGap);
    const columnGap = num(computed.columnGap);

    const record = {
      kind: map[selector],
      coord_frame: "viewport",
      box_size: { width: round(rect.width), height: round(rect.height) },
      box_origin: { x: round(rect.x), y: round(rect.y) },
      padding: [
        num(computed.paddingTop),
        num(computed.paddingRight),
        num(computed.paddingBottom),
        num(computed.paddingLeft),
      ],
      margin: [
        num(computed.marginTop),
        num(computed.marginRight),
        num(computed.marginBottom),
        num(computed.marginLeft),
      ],
      radius: [
        num(computed.borderTopLeftRadius),
        num(computed.borderTopRightRadius),
        num(computed.borderBottomRightRadius),
        num(computed.borderBottomLeftRadius),
      ],
      border_width: num(computed.borderTopWidth),
      border_color: computed.borderTopColor,
      fg: computed.color,
      font_size: fontSize,
      font_weight: num(computed.fontWeight),
      font_family: computed.fontFamily,
      opacity: num(computed.opacity),
      // The design states a multiplier and a browser reports pixels, so both sides are
      // normalised to a ratio here — the unit §1 #8's tolerance is written in.
      line_height: fontSize !== null && lineHeightPx !== null ? round(lineHeightPx / fontSize) : null,
      letter_spacing: fontSize !== null && spacingPx !== null ? round(spacingPx / fontSize) : null,
    };

    if (rowGap !== null && columnGap !== null) {
      record.gap = [round(rowGap), round(columnGap)];
    }

    const lines = lineCount(element);
    if (lines !== null) record.line_count = lines;

    const shadow = firstShadow(computed.boxShadow);
    if (shadow !== null) record.shadow = shadow;

    // §1 #11 compares the whole paint stack, bottom-to-top — the direction the design side states
    // natively (Figma's `fills[0]` is the bottom layer). CSS names its layers the other way round
    // in `background-image` and paints `background-color` underneath every one of them, so this
    // re-orders rather than passes values through: that reversal is what makes the two sides
    // comparable at all, and it is why a stack is emitted instead of the single paint used before.
    //
    // A layer that is not a comparable paint — `url(...)` is an image — omits the whole property
    // rather than being skipped. Skipping would shift every layer after it, pairing design layer
    // *n* with this side's layer *n-1* and reporting a deviation between two unrelated paints.
    // Omitting leaves the category unverified, which is the honest reading of "this stack cannot
    // be compared". The top-most layer is the one that used to be compared alone, so a node whose
    // design has an overlay over a base colour no longer matches on the base and passes.
    const imageLayers = computed.backgroundImage === "none" ? [] : splitTopLevel(computed.backgroundImage);
    const colour = computed.backgroundColor;
    const colourPaints = colour !== "transparent" && !/^rgba?\(0, 0, 0, 0\)$/.test(colour);
    if (imageLayers.every((layer) => /gradient\(/.test(layer))) {
      const stack = [...imageLayers].reverse();
      if (colourPaints) stack.unshift(colour);
      if (stack.length > 0) record.bg = stack;
    }

    facts[selector] = record;
  }

  return facts;
}
