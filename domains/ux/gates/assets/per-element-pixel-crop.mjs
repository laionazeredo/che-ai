/**
 * che pixel check — per-element pixel crop (gate §4.5, evidence lane only).
 *
 * WHY A CROP AND NOT A WHOLE-FRAME DELTA
 * --------------------------------------
 * §4.5's whole-frame diff is dominated by text antialiasing, DPR and font-loading noise, so a
 * 2px radius error barely moves its percentage while a font substitution moves it a lot. That
 * inverts the signal-to-noise ratio for exactly the deviations this gate exists to catch, which
 * is why the picture was demoted to evidence in the first place. Cropping to each mapped
 * element's own box drops the frame's background and its unrelated text out of the comparison,
 * so what is left describes the element the gate scored — and the residue §6.1 lists
 * (`object-fit`, crop, `<svg>` path data, reflow, paint order) finally has an instrument that
 * points at *one* element instead of at a whole screen.
 *
 * IT IS STILL NOT A VERDICT. This program never exits non-zero because of a difference, and no
 * verdict reads its output: `tool_evidence_only` in the gate frontmatter is the rule, and a
 * threshold here would be exactly the unprincipled number the gate refuses to invent. It exists
 * to be looked at.
 *
 * WHY IT NEEDS `design_box` ON THE MAP ENTRY
 * ------------------------------------------
 * Neither fact set carries image coordinates. The design side states `box_origin` relative to
 * its *parent* (§4.2) and the DOM side states `getBoundingClientRect()`, relative to the
 * viewport. Cropping a raster needs the box in that raster's own pixels, and only the caller who
 * exported the frame knows where a node sits inside it — so the map declares it:
 *
 *     { "cta": { "design_node": "12:345", "selector": "#cta",
 *                "design_box": { "x": 480, "y": 220, "width": 320, "height": 52 } } }
 *
 * Inferring it by summing ancestor origins is not attempted: the facts carry no parent links, so
 * a wrong crop would be a confident picture of the wrong region. The DOM side needs no such
 * declaration — at `devicePixelRatio === 1` a viewport screenshot's origin *is* the viewport
 * origin, which is what the extractor's `coord_frame: "viewport"` already asserts.
 *
 * HOW TO CALL IT
 * --------------
 * From a scratch directory that has `pngjs`/`pixelmatch`, not from Che and not from the project
 * under test: `node --input-type=module -` resolves bare specifiers from the working directory, so
 * where it runs decides what it can import — and the gate must not edit the `package.json` of the
 * repository it is judging (§4.5).
 *
 *     node --input-type=module - \
 *       --design "$CHE_PIXEL_DESIGN_IMAGE" --dom "$CHE_PIXEL_DOM_SCREENSHOT" \
 *       --map "$CHE_PIXEL_MAP" --dom-facts "$CHE_PIXEL_DOM_FACTS" \
 *       --out "$CHE_PIXEL_CROP_REPORT" --sheet "$CHE_PIXEL_CROP_SHEET" \
 *       < domains/ux/gates/assets/per-element-pixel-crop.mjs
 *
 * It prints one line per element and writes the JSON. The sheet is a stacked strip — design
 * crop, implementation crop, diff, in that order per row — whose rows follow the JSON's
 * `elements` array, since drawing labels would mean shipping a font to a tool that exists to
 * avoid dependencies.
 *
 * WHAT IT REFUSES
 * ---------------
 * A crop that cannot be trusted is not written, because a picture of the wrong region looks like
 * evidence. Refused: a mapped element with no `design_box`; an element absent from either fact
 * set; a box that leaves its image; and boxes of different sizes. The last one is deliberately
 * *not* fixed by scaling — resampling would invent the pixels it then compares and would hide the
 * size drift, which is itself the finding worth reading. Mismatches are recorded as
 * `size_mismatch` and shown side by side in the sheet.
 */

import { readFileSync, writeFileSync } from "node:fs";

import { PNG } from "pngjs";
import pixelmatch from "pixelmatch";

const args = process.argv.slice(2);
const flag = (name) => {
  const at = args.indexOf(`--${name}`);
  return at === -1 ? null : args[at + 1];
};

const designPath = flag("design");
const domPath = flag("dom");
const mapPath = flag("map");
const domFactsPath = flag("dom-facts");
const outPath = flag("out");
const sheetPath = flag("sheet");
const threshold = Number(flag("threshold") ?? 0.1);

for (const [name, value] of Object.entries({
  design: designPath,
  dom: domPath,
  map: mapPath,
  "dom-facts": domFactsPath,
  out: outPath,
})) {
  if (!value) {
    console.error(`che: --${name} is required`);
    process.exit(2);
  }
}

const readJson = (path) => JSON.parse(readFileSync(path, "utf8"));
const designImage = PNG.sync.read(readFileSync(designPath));
const domImage = PNG.sync.read(readFileSync(domPath));
const map = readJson(mapPath);
const domFacts = readJson(domFactsPath);

/** Copy `box` out of `image` as a fresh PNG, or explain why it cannot be. */
const crop = (image, box) => {
  const x = Math.round(box.x);
  const y = Math.round(box.y);
  const width = Math.round(box.width);
  const height = Math.round(box.height);
  if (width <= 0 || height <= 0) return { error: `box is empty (${width}x${height})` };
  if (x < 0 || y < 0 || x + width > image.width || y + height > image.height) {
    return { error: `box ${x},${y} ${width}x${height} leaves the ${image.width}x${image.height} image` };
  }
  const out = new PNG({ width, height });
  PNG.bitblt(image, out, x, y, width, height, 0, 0);
  return { png: out };
};

/** The DOM box, which the facts already state in image coordinates. */
const domBoxOf = (record) => {
  const origin = record?.box_origin;
  const size = record?.box_size;
  if (!origin || !size || !Number.isFinite(origin.x) || !Number.isFinite(origin.y)) return null;
  if (!Number.isFinite(size.width) || !Number.isFinite(size.height)) return null;
  return { x: origin.x, y: origin.y, width: size.width, height: size.height };
};

const elements = [];

/**
 * Recorded *and* printed. A refusal that only reaches the JSON is a gap the operator cannot
 * see, and the sheet cannot show it either — so an element this tool could not measure would
 * be indistinguishable from one that matched.
 */
const refuse = (element, reason) => {
  elements.push({ element, status: "refused", reason });
  console.log(`${element}: refused (${reason})`);
};

for (const key of Object.keys(map).sort()) {
  const entry = map[key];
  if (!entry || typeof entry !== "object") {
    refuse(key, "map entry is not an object");
    continue;
  }

  // Declared, never inferred: the two facts sets state boxes in different frames, and a raster
  // has a third. Only the caller who exported the frame can say where a node sits inside it.
  const designBox = entry.design_box;
  if (!designBox || typeof designBox !== "object") {
    refuse(key, "no `design_box` on the map entry — pass the node's box in the design image's own pixels");
    continue;
  }

  const domBox = domBoxOf(domFacts[entry.selector]);
  if (!domBox) {
    refuse(key, `no box for selector ${entry.selector} in the DOM facts`);
    continue;
  }

  const designCrop = crop(designImage, designBox);
  const domCrop = crop(domImage, domBox);
  if (designCrop.error || domCrop.error) {
    refuse(key, designCrop.error ?? domCrop.error);
    continue;
  }

  const record = { element: key, design_box: designBox, dom_box: domBox };
  if (designCrop.png.width !== domCrop.png.width || designCrop.png.height !== domCrop.png.height) {
    // Not scaled on purpose: resampling invents the pixels it would then compare, and it would
    // erase the size drift this row is here to show.
    Object.assign(record, {
      status: "size_mismatch",
      reason: `design crop is ${designCrop.png.width}x${designCrop.png.height}, implementation crop is ${domCrop.png.width}x${domCrop.png.height}`,
    });
    elements.push(record);
    elements[elements.length - 1]._crops = [designCrop.png, domCrop.png, null];
    console.log(`${key}: size_mismatch (${record.reason})`);
    continue;
  }

  const diff = new PNG({ width: designCrop.png.width, height: designCrop.png.height });
  const changed = pixelmatch(
    designCrop.png.data,
    domCrop.png.data,
    diff.data,
    designCrop.png.width,
    designCrop.png.height,
    { threshold },
  );
  const counted = designCrop.png.width * designCrop.png.height;
  Object.assign(record, {
    status: "compared",
    pixels: counted,
    differing_pixels: changed,
    ratio: counted === 0 ? 0 : Number((changed / counted).toFixed(4)),
  });
  elements.push(record);
  elements[elements.length - 1]._crops = [designCrop.png, domCrop.png, diff];
  console.log(`${key}: ${changed}/${counted} px differ (${(100 * record.ratio).toFixed(2)}%)`);
}

// The strip: one row per element, design | implementation | diff. Rows follow `elements`, so the
// JSON is the legend — which is how a tool with no font stays readable. Every element keeps its
// row, and one that was refused renders blank: filtering the refusals out made the legend false
// twice over, because the row after a refusal shifted up (pairing the picture with the wrong
// element) and an element the tool could not measure looked exactly like one that matched.
const rows = elements.map((entry) => ({ _crops: entry._crops ?? [null, null, null] }));
const crops = rows.flatMap((row) => row._crops).filter(Boolean);
if (sheetPath && crops.length > 0) {
  const gap = 2;
  const cellWidth = Math.max(...crops.map((png) => png.width));
  const cellHeight = Math.max(...crops.map((png) => png.height));
  const sheet = new PNG({ width: cellWidth * 3 + gap * 2, height: (cellHeight + gap) * rows.length });
  sheet.data.fill(255);
  rows.forEach((row, index) => {
    const top = index * (cellHeight + gap);
    row._crops.forEach((png, column) => {
      if (!png) return;
      PNG.bitblt(png, sheet, 0, 0, png.width, png.height, column * (cellWidth + gap), top);
    });
  });
  writeFileSync(sheetPath, PNG.sync.write(sheet));
}

for (const entry of elements) {
  delete entry._crops;
}

writeFileSync(
  outPath,
  `${JSON.stringify(
    {
      // Provenance, so the numbers can be reproduced: the images they came from, and the
      // pixelmatch threshold, which is a signal-to-noise choice rather than a pass mark.
      design_image: designPath,
      dom_image: domPath,
      pixelmatch_threshold: threshold,
      sheet: crops.length > 0 ? sheetPath : null,
      compared: elements.filter((entry) => entry.status === "compared").length,
      elements,
    },
    null,
    2,
  )}\n`,
);
