"""che pixel visual — the gate's evidence lane, in Python instead of Node.

WHY THIS FILE EXISTS
--------------------
§4.5's two pictures (the whole-frame diff and the per-element crop) used to be `.mjs` scripts that
imported `pixelmatch` + `pngjs`. That put them outside `pytest` — no test could execute them — and
they proved it: the crop shipped with two false claims in its own docstring that only surfaced when
someone finally ran it by hand. Architecture principle #6 says Che's logic is Python, "no Node in
the core", and the image tools had no excuse for an exception: unlike
`assets/dom-facts-extractor.js`, which is a payload only a browser can execute, these only ever
touched files.

So the algorithm is ported rather than reinvented. `pixelmatch` is not an absolute difference — it
is a YIQ distance with an anti-aliasing detector (Vysniauskas, 2009), and dropping either would make
the instrument *worse*: an absolute difference on text renders almost nothing but anti-aliasing
noise. The port is line-for-line against pixelmatch 7.2.0, and `tests/test_pixel_visual.py` holds it
to the real package's numbers.

THE TWO DEPENDENCIES, AND WHY THEY ARE THE MINIMUM
--------------------------------------------------
`Pillow` decodes and encodes PNG (which `zlib` + `struct` can also do, at the cost of owning a codec:
filters, colour types, interlacing). `numpy` is what makes the comparison run at a usable speed, and
that is a measured claim, not a preference. On a 1440x7500 frame pair of the shape the gate actually
meets — a design gradient against a flat implementation colour, 91.5% of pixels differing:

| stage | loop-per-pixel Python | this module |
|---|---|---|
| YIQ delta pass | 10.1 s | 0.5 s |
| anti-aliasing detector | 192 s (19.5 us per candidate pixel) | 14 s |
| whole comparison, worst case | 202 s | 15 s |
| whole comparison, screen that mostly matches | — | 0.6 s |

The reference `pixelmatch` runs the same pair in 0.8 s, so this is ~18x slower rather than 240x, and
the gap only opens on frames where almost nothing matches — where the anti-aliasing detector is
genuinely asked about every pixel. Both dependencies are declared in `pyproject.toml` and resolved by
the installer; nothing larger (scikit-image, OpenCV, imageio) earns its place for these two jobs.

FAITHFULNESS
------------
Everything the anti-aliasing detector touches is a *neighbourhood*, and a neighbourhood near the
frame edge is not the same shape: the reference clamps its window, so a corner pixel has three
neighbours rather than eight, and one of the eight clamped slots collapses onto the pixel itself.
Vectorising that directly would count a pixel as its own sibling. So the frame is split: the
**interior** (where every 3x3 window is fully inside, and the eight slots are eight distinct
neighbours) is computed with array operations, and the **border ring** — `2*(H+W)-4` pixels, 0.17%
of the frame — runs the transcribed scalar code. The two agree by construction, and the parity tests
cover both.

IT IS STILL NOT A VERDICT. Nothing in this module feeds a score. `tool_evidence_only` in the gate
frontmatter is the rule: the diff ratio is not a threshold, and the crop never exits non-zero
because two pictures differ. It exists to be looked at.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

#: YIQ weights, from "Measuring perceived color difference using YIQ NTSC transmission color space in
#: mobile applications" (Kotsarenko & Ramos). Transcribed, not derived — see the module docstring.
_LUMA = (0.29889531, 0.58662247, 0.11448223)
_CHROMA_I = (0.59597799, -0.27417610, -0.32180189)
_CHROMA_Q = (0.21147017, -0.52261711, 0.31114694)

#: The largest possible YIQ distance, which `threshold` scales into the accept/reject boundary.
_MAX_YIQ_DELTA = 35215.0

DEFAULT_THRESHOLD = 0.1
DEFAULT_ALPHA = 0.1
AA_COLOUR = (255, 255, 0)
DIFF_COLOUR = (255, 0, 0)

#: Rows per pass. The delta pass allocates ~8 float64 temporaries per pixel, so a 1440x7500 frame
#: done in one go peaks near a gigabyte. Blocking bounds that without changing a single value.
_BLOCK_ROWS = 256

#: The eight neighbours, in the order the reference's `for x: for y:` loop visits them. The order is
#: load-bearing: `delta < min` and `delta > max` are strict, so the *first* extremum in this order
#: wins a tie, and `argmin`/`argmax` only reproduce that if the axis is stacked this way.
_SLOTS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
_SLOT_DX = np.array([dx for dx, _ in _SLOTS], dtype=np.int64)
_SLOT_DY = np.array([dy for _, dy in _SLOTS], dtype=np.int64)

#: Why the PNG is read as RGBA8 and nothing else: a design export and a screenshot agree on nothing
#: else by default (palette, 16-bit, interlace, CMYK), and normalising here is what makes the byte
#: comparison meaningful. Pillow refuses what it cannot read, which is the refusal we want.
_MODE = "RGBA"


class ImageRefused(ValueError):
    """A picture this lane will not draw, because a picture of the wrong region looks like evidence."""


# --------------------------------------------------------------------------------------------
# Loading, saving, cropping
# --------------------------------------------------------------------------------------------


def load_rgba(path: str | Path) -> np.ndarray:
    """Read `path` as an `(H, W, 4)` uint8 array, whatever the file's own colour model was."""
    with Image.open(path) as image:
        return np.asarray(image.convert(_MODE), dtype=np.uint8)


def save_rgba(image: np.ndarray, path: str | Path) -> None:
    """Write an `(H, W, 4)` uint8 array as a PNG, creating the parent directory if needed."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.ascontiguousarray(image, dtype=np.uint8), mode=_MODE).save(target, format="PNG")


def crop(array: np.ndarray, box: dict) -> Tuple[Optional[np.ndarray], Optional[str]]:
    """Copy `box` out of `array`, or say why it cannot be.

    Returns `(crop, None)` or `(None, reason)`. Nothing is resampled: a box that does not fit is
    refused rather than clamped, because clamping would silently answer a different question.
    """
    height, width = array.shape[:2]
    x = int(round(float(box["x"])))
    y = int(round(float(box["y"])))
    box_width = int(round(float(box["width"])))
    box_height = int(round(float(box["height"])))
    if box_width <= 0 or box_height <= 0:
        return None, f"box is empty ({box_width}x{box_height})"
    if x < 0 or y < 0 or x + box_width > width or y + box_height > height:
        return None, f"box {x},{y} {box_width}x{box_height} leaves the {width}x{height} image"
    return array[y : y + box_height, x : x + box_width].copy(), None


# --------------------------------------------------------------------------------------------
# The comparison (a port of pixelmatch 7.2.0)
# --------------------------------------------------------------------------------------------


def _packed(array: np.ndarray) -> np.ndarray:
    """The 4 bytes of each pixel as one integer, which is how `hasManySiblings` compares them.

    Endianness is irrelevant: the value is only ever tested for equality, and both sides come
    through this same function.
    """
    contiguous = np.ascontiguousarray(array, dtype=np.uint8)
    return contiguous.view(np.uint32).reshape(contiguous.shape[0], contiguous.shape[1])


def _background_grid(index: np.ndarray, checkerboard: bool) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The colour a semi-transparent pixel is blended against, for a grid of pixel indices.

    Transcribed from the reference, including the odd-looking strides — they are applied to the
    *byte* offset `k = 4 * pixel_index`, which is why the red channel is constant. Reproducing it
    matters for parity; "fixing" it would silently move every translucent pixel's verdict.
    """
    if not checkerboard:
        white = np.full(index.shape, 255.0)
        return white, white, white
    k = 4 * index
    red = (48 + 159 * (k % 2)).astype(np.float64)
    green = (48 + 159 * (np.floor_divide(k, 1.618033988749895).astype(np.int64) % 2)).astype(np.float64)
    blue = (48 + 159 * (np.floor_divide(k, 2.618033988749895).astype(np.int64) % 2)).astype(np.float64)
    return red, green, blue


def _background(pixel_index: int, checkerboard: bool) -> Tuple[float, float, float]:
    """`_background_grid` for a single pixel, used by the scalar border path."""
    if not checkerboard:
        return 255.0, 255.0, 255.0
    k = 4 * pixel_index
    return (
        float(48 + 159 * (k % 2)),
        float(48 + 159 * (int(k / 1.618033988749895) % 2)),
        float(48 + 159 * (int(k / 2.618033988749895) % 2)),
    )


def _background_field(
    shape: Tuple[int, int], start: int, checkerboard: bool
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """`_background_grid` for a block, with `start` the block's first *global* pixel index.

    Global, not block-local: the checkerboard is a function of position in the frame, so a block
    that restarted the pattern at zero would blend the same pixel differently depending on where the
    block boundary happened to fall.
    """
    height, width = shape
    index = (start + np.arange(height * width, dtype=np.int64)).reshape(height, width)
    return _background_grid(index, checkerboard)


def _colour_delta(one: np.ndarray, two: np.ndarray, start: int, checkerboard: bool) -> np.ndarray:
    """The signed squared YIQ distance per pixel; negative where `two` is darker."""
    first = one.astype(np.float64)
    second = two.astype(np.float64)
    red_one, green_one, blue_one, alpha_one = (first[..., index] for index in range(4))
    red_two, green_two, blue_two, alpha_two = (second[..., index] for index in range(4))

    delta_red = red_one - red_two
    delta_green = green_one - green_two
    delta_blue = blue_one - blue_two
    delta_alpha = alpha_one - alpha_two

    translucent = (alpha_one < 255) | (alpha_two < 255)
    if translucent.any():
        back_red, back_green, back_blue = _background_field(one.shape[:2], start, checkerboard)
        blended_red = (red_one * alpha_one - red_two * alpha_two - back_red * delta_alpha) / 255.0
        blended_green = (green_one * alpha_one - green_two * alpha_two - back_green * delta_alpha) / 255.0
        blended_blue = (blue_one * alpha_one - blue_two * alpha_two - back_blue * delta_alpha) / 255.0
        delta_red = np.where(translucent, blended_red, delta_red)
        delta_green = np.where(translucent, blended_green, delta_green)
        delta_blue = np.where(translucent, blended_blue, delta_blue)

    luma = delta_red * _LUMA[0] + delta_green * _LUMA[1] + delta_blue * _LUMA[2]
    chroma_i = delta_red * _CHROMA_I[0] + delta_green * _CHROMA_I[1] + delta_blue * _CHROMA_I[2]
    chroma_q = delta_red * _CHROMA_Q[0] + delta_green * _CHROMA_Q[1] + delta_blue * _CHROMA_Q[2]

    magnitude = 0.5053 * luma * luma + 0.299 * chroma_i * chroma_i + 0.1957 * chroma_q * chroma_q
    return np.where(luma > 0, -magnitude, magnitude)


# --- the scalar anti-aliasing path, transcribed; used verbatim on the border ring -----------------


def _brightness_delta(
    array: np.ndarray,
    centre_index: int,
    neighbour_index: int,
    centre: Tuple[int, int, int, int],
    checkerboard: bool,
) -> float:
    """Luma-only delta between the centre pixel and one neighbour, for the anti-aliasing test."""
    red_one, green_one, blue_one, alpha_one = centre
    row, column = divmod(neighbour_index, array.shape[1])
    neighbour = array[row, column]
    red_two, green_two, blue_two, alpha_two = (int(channel) for channel in neighbour)

    delta_red = float(red_one - red_two)
    delta_green = float(green_one - green_two)
    delta_blue = float(blue_one - blue_two)
    delta_alpha = float(alpha_one - alpha_two)
    if delta_red == 0.0 and delta_green == 0.0 and delta_blue == 0.0 and delta_alpha == 0.0:
        return 0.0

    if alpha_one < 255 or alpha_two < 255:
        back_red, back_green, back_blue = _background(centre_index, checkerboard)
        delta_red = (red_one * alpha_one - red_two * alpha_two - back_red * delta_alpha) / 255.0
        delta_green = (green_one * alpha_one - green_two * alpha_two - back_green * delta_alpha) / 255.0
        delta_blue = (blue_one * alpha_one - blue_two * alpha_two - back_blue * delta_alpha) / 255.0

    return delta_red * _LUMA[0] + delta_green * _LUMA[1] + delta_blue * _LUMA[2]


def _has_many_siblings(packed: np.ndarray, x: int, y: int) -> bool:
    """True when 3+ of the neighbours carry the pixel's own packed value."""
    height, width = packed.shape
    x0, y0 = max(x - 1, 0), max(y - 1, 0)
    x2, y2 = min(x + 1, width - 1), min(y + 1, height - 1)
    value = packed[y, x]
    zeroes = 1 if (x == x0 or x == x2 or y == y0 or y == y2) else 0
    for neighbour_x in range(x0, x2 + 1):
        for neighbour_y in range(y0, y2 + 1):
            if neighbour_x == x and neighbour_y == y:
                continue
            if value == packed[neighbour_y, neighbour_x]:
                zeroes += 1
                if zeroes > 2:
                    return True
    return False


def _antialiased(array: np.ndarray, own: np.ndarray, other: np.ndarray, x: int, y: int, checkerboard: bool) -> bool:
    """The Vysniauskas slope test: is this pixel's difference only anti-aliasing?"""
    height, width = array.shape[:2]
    x0, y0 = max(x - 1, 0), max(y - 1, 0)
    x2, y2 = min(x + 1, width - 1), min(y + 1, height - 1)
    centre_index = y * width + x
    centre = tuple(int(channel) for channel in array[y, x])
    zeroes = 1 if (x == x0 or x == x2 or y == y0 or y == y2) else 0

    darkest = 0.0
    brightest = 0.0
    darkest_at = (0, 0)
    brightest_at = (0, 0)
    for neighbour_x in range(x0, x2 + 1):
        for neighbour_y in range(y0, y2 + 1):
            if neighbour_x == x and neighbour_y == y:
                continue
            delta = _brightness_delta(array, centre_index, neighbour_y * width + neighbour_x, centre, checkerboard)
            if delta == 0.0:
                zeroes += 1
                if zeroes > 2:
                    return False
            elif delta < darkest:
                darkest = delta
                darkest_at = (neighbour_x, neighbour_y)
            elif delta > brightest:
                brightest = delta
                brightest_at = (neighbour_x, neighbour_y)

    if darkest == 0.0 or brightest == 0.0:
        return False

    return (_has_many_siblings(own, *darkest_at) and _has_many_siblings(other, *darkest_at)) or (
        _has_many_siblings(own, *brightest_at) and _has_many_siblings(other, *brightest_at)
    )


# --- the vectorised anti-aliasing path, for pixels whose 3x3 window is fully inside the frame ----


def _brightness_delta_field(
    centre: np.ndarray, neighbour: np.ndarray, background: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]
) -> np.ndarray:
    """`_brightness_delta` for one neighbour slot, over a whole window of centre pixels.

    `background` is the checkerboard the caller already resolved for this window, or `None` when the
    reference would blend against plain white. It is computed once per row-block rather than once per
    slot: it is a function of the pixel's position in the frame and of nothing else, so eight
    identical recomputations per slot per image were eight times the same allocation.
    """
    first = centre.astype(np.float64)
    second = neighbour.astype(np.float64)
    delta_red = first[..., 0] - second[..., 0]
    delta_green = first[..., 1] - second[..., 1]
    delta_blue = first[..., 2] - second[..., 2]
    delta_alpha = first[..., 3] - second[..., 3]
    identical = (delta_red == 0.0) & (delta_green == 0.0) & (delta_blue == 0.0) & (delta_alpha == 0.0)

    translucent = (first[..., 3] < 255.0) | (second[..., 3] < 255.0)
    if translucent.any():
        back_red, back_green, back_blue = background if background is not None else (255.0, 255.0, 255.0)
        blended_red = (first[..., 0] * first[..., 3] - second[..., 0] * second[..., 3] - back_red * delta_alpha) / 255.0
        blended_green = (
            first[..., 1] * first[..., 3] - second[..., 1] * second[..., 3] - back_green * delta_alpha
        ) / 255.0
        blended_blue = (
            first[..., 2] * first[..., 3] - second[..., 2] * second[..., 3] - back_blue * delta_alpha
        ) / 255.0
        delta_red = np.where(translucent, blended_red, delta_red)
        delta_green = np.where(translucent, blended_green, delta_green)
        delta_blue = np.where(translucent, blended_blue, delta_blue)

    luma = delta_red * _LUMA[0] + delta_green * _LUMA[1] + delta_blue * _LUMA[2]
    #: The reference returns before the blend when the two pixels are identical; force the same zero
    #: rather than relying on the blend happening to cancel.
    return np.where(identical, 0.0, luma)


def _sibling_truth(packed: np.ndarray) -> np.ndarray:
    """`_has_many_siblings` for every pixel: vectorised inside, exact on the border ring.

    The border cannot be vectorised with the interior because the reference clamps its window, so a
    pixel at `x == 0` sees `x0 == x1 == 0` — the slot that would be its left neighbour *is* itself,
    and counting it would inflate the sibling count by one.
    """
    height, width = packed.shape
    truth = np.zeros((height, width), dtype=bool)
    if height < 3 or width < 3:
        for y in range(height):
            for x in range(width):
                truth[y, x] = _has_many_siblings(packed, x, y)
        return truth

    padded = np.pad(packed, 1, mode="edge")
    centre = packed[1:-1, 1:-1]
    count = np.zeros(centre.shape, dtype=np.uint16)
    for dx, dy in _SLOTS:
        count += padded[2 + dy : height + dy, 2 + dx : width + dx] == centre
    truth[1:-1, 1:-1] = count > 2

    for x in range(width):
        truth[0, x] = _has_many_siblings(packed, x, 0)
        truth[height - 1, x] = _has_many_siblings(packed, x, height - 1)
    for y in range(1, height - 1):
        truth[y, 0] = _has_many_siblings(packed, 0, y)
        truth[y, width - 1] = _has_many_siblings(packed, width - 1, y)
    return truth


def _sparse_antialiased(
    padded: np.ndarray,
    own_siblings: np.ndarray,
    other_siblings: np.ndarray,
    ys: np.ndarray,
    xs: np.ndarray,
    width: int,
    background: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]],
) -> np.ndarray:
    """`_antialiased` for an explicit list of pixels, none of them on the border ring.

    Sparse rather than windowed on purpose. The detector is only asked about pixels whose YIQ delta
    already broke the threshold, and on a screen that mostly matches that is a small fraction of the
    frame — a dense window would pay for all 368k pixels of a block to answer about a hundred of
    them. Worst case (nothing matches, so every pixel is a candidate) it degrades to the dense cost,
    which is bounded by the same row-blocking.

    `padded` carries one replicated row and column on each side, so a neighbour is a plain fancy
    index and the reference's clamping is reproduced by `mode="edge"`. It is padded once for the
    whole frame: the frame is tens of megabytes and a per-block pad would copy all of it thirty times.
    """
    centre = padded[ys + 1, xs + 1]
    deltas = np.stack(
        [_brightness_delta_field(centre, padded[ys + 1 + dy, xs + 1 + dx], background) for dx, dy in _SLOTS],
        axis=-1,
    )

    usable = (deltas == 0.0).sum(axis=-1) <= 2
    has_darkest = (deltas < 0.0).any(axis=-1)
    has_brightest = (deltas > 0.0).any(axis=-1)
    #: Strict comparisons, and a delta of exactly zero belongs to the `zeroes` branch rather than to
    #: either extremum — so zeros are pushed out of the running before the arg-extremum.
    darkest_slot = np.argmin(np.where(deltas < 0.0, deltas, np.inf), axis=-1)
    brightest_slot = np.argmax(np.where(deltas > 0.0, deltas, -np.inf), axis=-1)

    darkest_y, darkest_x = ys + _SLOT_DY[darkest_slot], xs + _SLOT_DX[darkest_slot]
    brightest_y, brightest_x = ys + _SLOT_DY[brightest_slot], xs + _SLOT_DX[brightest_slot]

    darkest_ok = own_siblings[darkest_y, darkest_x] & other_siblings[darkest_y, darkest_x]
    brightest_ok = own_siblings[brightest_y, brightest_x] & other_siblings[brightest_y, brightest_x]
    return usable & has_darkest & has_brightest & (darkest_ok | brightest_ok)


def _ring_mask(height: int, width: int) -> np.ndarray:
    """The pixels whose 3x3 window is clipped by the frame edge."""
    ring = np.zeros((height, width), dtype=bool)
    if height < 3 or width < 3:
        ring[:] = True
        return ring
    ring[0, :] = True
    ring[height - 1, :] = True
    ring[:, 0] = True
    ring[:, width - 1] = True
    return ring


def _candidate_mask(design: np.ndarray, actual: np.ndarray, limit: float, checkerboard: bool) -> np.ndarray:
    """Where `|delta| > maxDelta` — the only pixels the anti-aliasing detector is asked about."""
    height, width = design.shape[:2]
    candidates = np.zeros((height, width), dtype=bool)
    for top in range(0, height, _BLOCK_ROWS):
        bottom = min(top + _BLOCK_ROWS, height)
        delta = _colour_delta(design[top:bottom], actual[top:bottom], top * width, checkerboard)
        candidates[top:bottom] = np.abs(delta) > limit
    return candidates


def compare(
    design: np.ndarray,
    actual: np.ndarray,
    threshold: float = DEFAULT_THRESHOLD,
    alpha: float = DEFAULT_ALPHA,
    checkerboard: bool = True,
) -> Tuple[int, np.ndarray]:
    """Count the pixels that differ, and draw the diff the way `pixelmatch` would.

    Returns `(differing, rgba)`. Anti-aliased differences are drawn yellow and are **not** counted:
    that exclusion is the whole point of using this metric rather than an absolute difference, and it
    is what makes the number readable on text.
    """
    if design.shape != actual.shape:
        raise ImageRefused(
            f"images differ in shape: {design.shape[1]}x{design.shape[0]} vs {actual.shape[1]}x{actual.shape[0]}"
        )

    height, width = design.shape[:2]
    limit = _MAX_YIQ_DELTA * threshold * threshold

    #: The background of the diff, exactly as `drawGrayPixel` computes it: the design blended towards
    #: white. JS writes into a Uint8Array, which truncates rather than rounds.
    luma = design[..., 0] * _LUMA[0] + design[..., 1] * _LUMA[1] + design[..., 2] * _LUMA[2]
    grey = (255.0 + (luma - 255.0) * alpha * design[..., 3] / 255.0).astype(np.uint8)
    output = np.empty((height, width, 4), dtype=np.uint8)
    output[..., 0] = grey
    output[..., 1] = grey
    output[..., 2] = grey
    output[..., 3] = 255

    candidates = _candidate_mask(design, actual, limit, checkerboard)
    if not candidates.any():
        return 0, output

    packed_design, packed_actual = _packed(design), _packed(actual)
    excluded = np.zeros((height, width), dtype=bool)

    ring = _ring_mask(height, width)
    for y, x in zip(*np.nonzero(candidates & ring)):
        excluded[y, x] = _antialiased(design, packed_design, packed_actual, x, y, checkerboard) or _antialiased(
            actual, packed_actual, packed_design, x, y, checkerboard
        )

    interior = candidates & ~ring
    if interior.any():
        design_siblings, actual_siblings = _sibling_truth(packed_design), _sibling_truth(packed_actual)
        padded_design = np.pad(design, ((1, 1), (1, 1), (0, 0)), mode="edge")
        padded_actual = np.pad(actual, ((1, 1), (1, 1), (0, 0)), mode="edge")
        for top in range(0, height, _BLOCK_ROWS):
            bottom = min(top + _BLOCK_ROWS, height)
            band = interior[top:bottom]
            if not band.any():
                continue
            local_y, xs = np.nonzero(band)
            ys = local_y + top
            index = ys.astype(np.int64) * width + xs
            background = _background_grid(index, checkerboard) if checkerboard else None
            excluded[ys, xs] = _sparse_antialiased(
                padded_design, design_siblings, actual_siblings, ys, xs, width, background
            ) | _sparse_antialiased(padded_actual, actual_siblings, design_siblings, ys, xs, width, background)

    antialiased = candidates & excluded
    differing = candidates & ~excluded
    output[antialiased] = (*AA_COLOUR, 255)
    output[differing] = (*DIFF_COLOUR, 255)
    return int(differing.sum()), output


def frame_diff(
    design_path: str | Path, dom_path: str | Path, threshold: float = DEFAULT_THRESHOLD
) -> Tuple[Optional[np.ndarray], int, Optional[str]]:
    """The whole-frame picture, or the reason it would be nonsense.

    Returns `(diff, differing, refusal)`. `diff` is `None` exactly when `refusal` is set.

    Two rasters of different sizes cannot be compared: `pixelmatch` would return a number computed
    against the wrong pixels rather than an error, which is the one way this evidence can lie.
    """
    design = load_rgba(design_path)
    actual = load_rgba(dom_path)
    if design.shape != actual.shape:
        return (
            None,
            0,
            f"refusing: design is {design.shape[1]}x{design.shape[0]}, DOM is {actual.shape[1]}x{actual.shape[0]}",
        )
    differing, output = compare(design, actual, threshold)
    return output, differing, None


# --------------------------------------------------------------------------------------------
# The sheet
# --------------------------------------------------------------------------------------------


def compose_sheet(rows: Sequence[Sequence[Optional[np.ndarray]]], gap: int = 2) -> Optional[np.ndarray]:
    """Stack one row per element, design | implementation | diff, or `None` if there is nothing to draw.

    Rows keep their position even when a cell is missing: a blank row is how a refusal stays visible
    once the pictures are the only thing a reviewer looks at.
    """
    crops = [crop_image for row in rows for crop_image in row if crop_image is not None]
    if not crops:
        return None

    cell_width = max(crop_image.shape[1] for crop_image in crops)
    cell_height = max(crop_image.shape[0] for crop_image in crops)
    sheet = np.full(((cell_height + gap) * len(rows), cell_width * 3 + gap * 2, 4), 255, dtype=np.uint8)
    for index, row in enumerate(rows):
        top = index * (cell_height + gap)
        for column, crop_image in enumerate(row):
            if crop_image is None:
                continue
            left = column * (cell_width + gap)
            sheet[top : top + crop_image.shape[0], left : left + crop_image.shape[1]] = crop_image
    return sheet


# --------------------------------------------------------------------------------------------
# `che pixel crop` — the report the gate's §4.5 names
# --------------------------------------------------------------------------------------------


def _dom_box(record: Optional[dict]) -> Optional[dict]:
    """The DOM box, which the facts already state in image coordinates."""
    if not isinstance(record, dict):
        return None
    origin = record.get("box_origin")
    size = record.get("box_size")
    if not isinstance(origin, dict) or not isinstance(size, dict):
        return None
    try:
        return {
            "x": float(origin["x"]),
            "y": float(origin["y"]),
            "width": float(size["width"]),
            "height": float(size["height"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


def build_crop_report(
    design_path: str | Path,
    dom_path: str | Path,
    map_path: str | Path,
    dom_facts_path: str | Path,
    threshold: float = DEFAULT_THRESHOLD,
    log: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Crop every mapped element out of both rasters and describe what the crops show.

    Returns the report body; the caller decides where it goes. The sheet is optional and is not part
    of the return value — `render_crop_sheet` builds it from the crops, so a caller that only wants
    the numbers does not pay for the picture.
    """
    say = log or (lambda _message: None)
    design_image = load_rgba(design_path)
    dom_image = load_rgba(dom_path)
    with open(map_path, encoding="utf-8") as handle:
        element_map = json.load(handle)
    with open(dom_facts_path, encoding="utf-8") as handle:
        dom_facts = json.load(handle)

    if not isinstance(element_map, dict):
        raise ImageRefused(f"{map_path} is not an element map: a JSON object is expected")

    elements: List[Dict[str, Any]] = []
    rows: List[List[Optional[np.ndarray]]] = []

    def refuse(element: str, reason: str) -> None:
        #: Recorded *and* printed: a refusal that only reaches the JSON is a gap the operator cannot
        #: see, and the sheet would then look complete when it is not.
        elements.append({"element": element, "status": "refused", "reason": reason})
        rows.append([None, None, None])
        say(f"{element}: refused ({reason})")

    for key in sorted(element_map):
        entry = element_map[key]
        if not isinstance(entry, dict):
            refuse(key, "map entry is not an object")
            continue

        #: Declared, never inferred: the two fact sets state boxes in different frames and a raster
        #: has a third, so only the caller who exported the frame knows where a node sits inside it.
        design_box = entry.get("design_box")
        if not isinstance(design_box, dict):
            refuse(key, "no `design_box` on the map entry — pass the node's box in the design image's own pixels")
            continue

        actual_box = _dom_box(dom_facts.get(entry.get("selector")))
        if actual_box is None:
            refuse(key, f"no box for selector {entry.get('selector')} in the DOM facts")
            continue

        design_crop, design_error = crop(design_image, design_box)
        actual_crop, actual_error = crop(dom_image, actual_box)
        if design_error or actual_error:
            refuse(key, design_error or actual_error or "unknown crop failure")
            continue

        assert design_crop is not None and actual_crop is not None  # the errors above cover None
        if design_crop.shape != actual_crop.shape:
            #: Not scaled on purpose: resampling invents the pixels it would then compare, and it
            #: would erase the size drift this row exists to show.
            reason = (
                f"design crop is {design_crop.shape[1]}x{design_crop.shape[0]}, "
                f"implementation crop is {actual_crop.shape[1]}x{actual_crop.shape[0]}"
            )
            elements.append(
                {
                    "element": key,
                    "design_box": design_box,
                    "dom_box": actual_box,
                    "status": "size_mismatch",
                    "reason": reason,
                }
            )
            rows.append([design_crop, actual_crop, None])
            say(f"{key}: size_mismatch ({reason})")
            continue

        differing, diff_image = compare(design_crop, actual_crop, threshold)
        counted = int(design_crop.shape[0] * design_crop.shape[1])
        elements.append(
            {
                "element": key,
                "design_box": design_box,
                "dom_box": actual_box,
                "status": "compared",
                "pixels": counted,
                "differing_pixels": differing,
                "ratio": 0 if counted == 0 else round(differing / counted, 4),
            }
        )
        rows.append([design_crop, actual_crop, diff_image])
        ratio = 0.0 if counted == 0 else 100.0 * differing / counted
        say(f"{key}: {differing}/{counted} px differ ({ratio:.2f}%)")

    compared = sum(1 for element in elements if element["status"] == "compared")
    return {
        "design_image": str(design_path),
        "dom_image": str(dom_path),
        "pixelmatch_threshold": threshold,
        "compared": compared,
        "elements": elements,
        "_rows": rows,
    }


def render_crop_sheet(report: Dict[str, Any]) -> Optional[np.ndarray]:
    """The strip for a report built by `build_crop_report`, or `None` when there is nothing to draw."""
    rows = report.get("_rows") or []
    return compose_sheet(rows)


def public_crop_report(report: Dict[str, Any], sheet_written: bool, sheet_path: Optional[str]) -> Dict[str, Any]:
    """The report as it goes to disk: internal keys dropped, and `sheet` naming only a real file.

    A path that was requested but never written reads as evidence of a file, which is the same
    mistake as a refusal that only exists in JSON.
    """
    body = {key: value for key, value in report.items() if not key.startswith("_")}
    body["sheet"] = sheet_path if (sheet_written and sheet_path) else None
    #: Field order follows the JSON the `.mjs` wrote, so a diff of two reports stays readable.
    return {
        "design_image": body["design_image"],
        "dom_image": body["dom_image"],
        "pixelmatch_threshold": body["pixelmatch_threshold"],
        "sheet": body["sheet"],
        "compared": body["compared"],
        "elements": body["elements"],
    }
