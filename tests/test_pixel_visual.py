"""Contract tests for `che_core.pixel_visual` — the gate's evidence lane, pinned to `pixelmatch`.

WHY THESE NUMBERS ARE THE TEST
------------------------------
`pixelmatch` is not an absolute difference: it is a YIQ distance gated by an anti-aliasing detector,
and the detector is the part that decides whether text renders as *changed* or as *noise*. A port
that got the metric right and the detector wrong would still return a plausible number — it would
just be a different instrument wearing the same name. So nothing here asserts against a
recomputation of the algorithm: every expected value was produced by the real `pixelmatch` 7.2.0
over these exact fixtures, and the test holds the port to it.

The fixtures are built arithmetically (no font, no resampling) so that the PNG bytes are identical
on every machine and in every Pillow release — a golden that moved with a library version would be
worse than no golden at all. `aa` counts the pixels the comparator painted yellow, which is the
detector's own output rather than its effect: without it, an implementation whose detector never
fires would pass a test that only checked totals.

The reference figures in `REFERENCE` were produced once, at port time, by running the real
`pixelmatch` 7.2.0 (with `pngjs`) over the PNGs written by `_frame_cases()`. They are constants here
because CI has no Node toolchain and should not grow one: re-deriving them at test time would mean
shipping the toolchain the port exists to avoid. To re-measure after a fixture change, write
`_frame_cases()` to a directory and run the package over it — the port must then move to match, never
the reverse.

Both halves of the port are covered. `border_ring` puts every candidate pixel on the frame's border,
which is the path that runs the transcribed scalar code; the other fixtures keep their candidates
interior, where the vectorised path decides.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pytest

from che_core.pixel_visual import (
    ImageRefused,
    build_crop_report,
    compare,
    compose_sheet,
    crop,
    frame_diff,
    load_rgba,
    public_crop_report,
    render_crop_sheet,
    save_rgba,
)

CHE_CLI_CMD = [sys.executable, "-m", "che_core.cli"]
CHE_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------------------------
# Fixtures — arithmetic, not font rendering, so the bytes never depend on a library version
# --------------------------------------------------------------------------------------------


def _mix(under: Tuple[int, ...], over: Tuple[int, ...], fraction: float) -> Tuple[int, ...]:
    """`fraction` of `over` composited onto `under`, channel by channel."""
    return tuple(int(round(low + (high - low) * fraction)) for low, high in zip(under, over))


def _fill(height: int, width: int, colour: Tuple[int, int, int, int]) -> np.ndarray:
    array = np.zeros((height, width, 4), dtype=np.uint8)
    array[..., :] = colour
    return array


def _banner(
    height: int,
    width: int,
    background: Tuple[int, int, int, int],
    ink: Tuple[int, int, int, int],
    shift: int,
) -> np.ndarray:
    """A block of ink with a one-pixel coverage ramp and a translucent bar under it.

    The ramp is what a renderer leaves on an anti-aliased edge — the part of the reference that a
    naive absolute difference would report as hundreds of changed pixels.
    """
    array = _fill(height, width, background)
    top, bottom = 3, height - 5
    left, right = 7 + shift, width - 8 + shift
    array[top:bottom, left:right] = ink
    array[top:bottom, left - 1] = _mix(background, ink, 0.5)
    array[top:bottom, right] = _mix(background, ink, 0.5)
    array[top - 1, left - 1 : right + 1] = _mix(background, ink, 0.35)
    array[bottom, left - 1 : right + 1] = _mix(background, ink, 0.35)
    array[height - 3 : height - 1, 2 : width - 2] = (255, 0, 0, 90)
    return array


def _translucent_band(alpha: int, background: Tuple[int, int, int, int], ink: Tuple[int, int, int, int]) -> np.ndarray:
    """A translucent band over an opaque block, at an alpha that straddles the threshold.

    The band exists to make the checkerboard observable at all. A translucent difference far from
    the threshold is counted under both blends, and one close to it is counted under neither, so
    only this narrow middle band separates "blended against a position-dependent checkerboard" from
    "blended against plain white". The alphas here were picked by scanning that window: at 120
    against 83 the reference counts 66 pixels one way and 132 the other.
    """
    array = _fill(24, 48, background)
    array[3:18, 7:40] = ink
    array[20:23, 2:46] = (255, 0, 0, alpha)
    return array


def _ring(height: int, width: int) -> np.ndarray:
    """A frame whose only differences are its outermost pixels.

    Every candidate therefore lands on the border ring, which is the path the port does NOT
    vectorise — the reference clamps its window there, and a corner pixel has three neighbours
    rather than eight. If that path drifted, no interior-heavy fixture would notice.
    """
    array = _fill(height, width, (255, 255, 255, 255))
    array[0, :] = (12, 24, 36, 255)
    array[height - 1, :] = (12, 24, 36, 255)
    array[:, 0] = (12, 24, 36, 255)
    array[:, width - 1] = (12, 24, 36, 255)
    return array


def _frame_cases() -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    white = (255, 255, 255, 255)
    navy = (16, 32, 48, 255)
    night = (12, 12, 16, 255)
    bone = (240, 240, 235, 255)
    return {
        # The metric's fast path: identical bytes must be zero, not "nearly zero".
        "identical": (
            _banner(32, 48, white, navy, 0),
            _banner(32, 48, white, navy, 0),
        ),
        # One pixel of drift on an anti-aliased edge: the detector has to earn its keep here.
        "aa_drift": (
            _banner(32, 48, white, navy, 0),
            _banner(32, 48, white, navy, 1),
        ),
        # Dark on light, then light on dark: the sign of the delta changes which branch draws.
        "dark_on_light": (
            _banner(32, 48, white, (0, 0, 0, 255), 0),
            _banner(32, 48, white, (40, 40, 40, 255), 0),
        ),
        "light_on_dark": (
            _banner(32, 48, night, bone, 0),
            _banner(32, 48, night, (196, 196, 190, 255), 0),
        ),
        # A wholesale change: nothing is anti-aliasing, so every candidate must count.
        "inverted": (
            _banner(32, 48, white, (10, 10, 10, 255), 0),
            _banner(32, 48, (0, 0, 0, 255), (245, 245, 245, 255), 0),
        ),
        # Translucent on both sides AND near the threshold: the only shape that makes the
        # checkerboard matter to the count. Built to straddle it rather than for looks — see
        # `_translucent_band`.
        "translucent": (
            _translucent_band(120, white, navy),
            _translucent_band(83, white, navy),
        ),
        # The border ring alone, which the vectorised interior never touches.
        "border_ring": (
            _fill(11, 13, white),
            _ring(11, 13),
        ),
    }


#: Measured with the real `pixelmatch` 7.2.0 over the PNGs written by `_frame_cases()`:
#: `(differing, antialiased, differing with checkerboard=False)`.
#:
#: All three figures matter. A total that matched while the yellow count did not would mean the
#: comparison agreed by coincidence on a different set of pixels; and only `translucent` separates
#: the two blend modes, because it is the only fixture whose translucent difference sits near the
#: threshold — everywhere else the checkerboard is arithmetically invisible.
REFERENCE = {
    "identical": (0, 0, 0),
    "aa_drift": (1, 99, 1),
    "dark_on_light": (792, 0, 792),
    "light_on_dark": (792, 0, 792),
    "inverted": (1330, 70, 1330),
    "translucent": (66, 0, 132),
    "border_ring": (44, 0, 44),
}


def _write_cases(directory: Path) -> Dict[str, Tuple[Path, Path]]:
    written = {}
    for name, (design, actual) in _frame_cases().items():
        design_path, actual_path = directory / f"{name}.design.png", directory / f"{name}.actual.png"
        save_rgba(design, design_path)
        save_rgba(actual, actual_path)
        written[name] = (design_path, actual_path)
    return written


def _antialiased_count(rgba: np.ndarray) -> int:
    """The yellow pixels — the detector's own output, not its effect on the total."""
    flat = rgba.reshape(-1, 4)
    return int(((flat[:, 0] == 255) & (flat[:, 1] == 255) & (flat[:, 2] == 0)).sum())


# --------------------------------------------------------------------------------------------
# Parity with the reference
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(REFERENCE))
def test_the_comparison_matches_pixelmatch_pixel_for_pixel(name: str, tmp_path: Path) -> None:
    """Counts and anti-aliasing must both match the reference, not just the totals."""
    design_path, actual_path = _write_cases(tmp_path)[name]
    design, actual = load_rgba(design_path), load_rgba(actual_path)

    differing, output = compare(design, actual)

    expected_differing, expected_aa, _plain = REFERENCE[name]
    assert (differing, _antialiased_count(output)) == (expected_differing, expected_aa)


@pytest.mark.parametrize("name", sorted(REFERENCE))
def test_the_checksum_pattern_matches_pixelmatch(name: str, tmp_path: Path) -> None:
    """`checkerboard=False` blends translucent pixels against white instead, which is a branch."""
    design_path, actual_path = _write_cases(tmp_path)[name]
    design, actual = load_rgba(design_path), load_rgba(actual_path)

    differing, _output = compare(design, actual, checkerboard=False)

    assert differing == REFERENCE[name][2]


def test_the_checksum_choice_moves_a_verdict_rather_than_being_cosmetic() -> None:
    """The one fixture that proves the branch is reachable: without it the toggle would be untested."""
    design, actual = _frame_cases()["translucent"]

    on_checkerboard, _ = compare(design, actual, checkerboard=True)
    on_plain_white, _ = compare(design, actual, checkerboard=False)

    assert (on_checkerboard, on_plain_white) == (66, 132)


def test_an_identical_pair_paints_no_red(tmp_path: Path) -> None:
    """The reference's fast path returns before drawing anything but the grey background."""
    design_path, actual_path = _write_cases(tmp_path)["identical"]
    design, actual = load_rgba(design_path), load_rgba(actual_path)

    differing, output = compare(design, actual)

    flat = output.reshape(-1, 4)
    assert differing == 0
    assert not ((flat[:, 0] == 255) & (flat[:, 1] == 0) & (flat[:, 2] == 0)).any()


def test_a_shape_mismatch_is_refused_rather_than_scored() -> None:
    """`pixelmatch` would compare against the wrong pixels and return a confident wrong number."""
    with pytest.raises(ImageRefused, match="differ in shape"):
        compare(np.zeros((4, 4, 4), dtype=np.uint8), np.zeros((5, 4, 4), dtype=np.uint8))


# --------------------------------------------------------------------------------------------
# The evidence pictures
# --------------------------------------------------------------------------------------------


def test_the_frame_diff_refuses_two_rasters_of_different_sizes(tmp_path: Path) -> None:
    design_path, actual_path = _write_cases(tmp_path)["identical"]
    save_rgba(np.zeros((7, 9, 4), dtype=np.uint8), actual_path)

    output, differing, refusal = frame_diff(design_path, actual_path)

    assert output is None
    assert differing == 0
    assert refusal is not None
    assert "refusing" in refusal and "9x7" in refusal


def test_the_frame_diff_returns_a_picture_when_the_sizes_agree(tmp_path: Path) -> None:
    design_path, actual_path = _write_cases(tmp_path)["aa_drift"]

    output, differing, refusal = frame_diff(design_path, actual_path)

    assert refusal is None
    assert output is not None
    assert output.shape == (32, 48, 4)
    assert differing == REFERENCE["aa_drift"][0]


# --------------------------------------------------------------------------------------------
# The crop report — the four paths a manual run actually takes
# --------------------------------------------------------------------------------------------


def _crop_scenario(directory: Path) -> Dict[str, str]:
    """A design and a DOM that disagree in each of the ways `build_crop_report` distinguishes."""
    design = _fill(24, 32, (255, 255, 255, 255))
    design[4:12, 4:20] = (16, 32, 48, 255)
    design[16:20, 4:12] = (200, 200, 200, 255)
    design[16:20, 14:22] = (10, 200, 10, 255)
    dom = design.copy()
    dom[4:12, 4:20] = (16, 32, 48, 255)
    dom[4:12, 4:19] = (16, 32, 48, 255)  # one column narrower: a 1px size drift
    design_path, dom_path = directory / "design.png", directory / "dom.png"
    save_rgba(design, design_path)
    save_rgba(dom, dom_path)

    element_map = {
        "compared": {
            "selector": "#same",
            "design_node": "1:1",
            "design_box": {"x": 4, "y": 4, "width": 16, "height": 8},
        },
        "size_mismatch": {
            "selector": "#narrow",
            "design_node": "1:2",
            "design_box": {"x": 4, "y": 4, "width": 8, "height": 8},
        },
        "outside-the-image": {
            "selector": "#same",
            "design_node": "1:3",
            "design_box": {"x": 28, "y": 20, "width": 8, "height": 8},
        },
        "no-design-box": {"selector": "#same", "design_node": "1:4"},
        "selector-not-in-facts": {
            "selector": "#ghost",
            "design_node": "1:5",
            "design_box": {"x": 4, "y": 4, "width": 4, "height": 4},
        },
    }
    map_path = directory / "design-map.json"
    map_path.write_text(json.dumps(element_map), encoding="utf-8")

    dom_facts = {
        "#same": {"box_origin": {"x": 4, "y": 4}, "box_size": {"width": 16, "height": 8}},
        "#narrow": {"box_origin": {"x": 4, "y": 4}, "box_size": {"width": 6, "height": 8}},
        "#outside": {"box_origin": {"x": 30, "y": 22}, "box_size": {"width": 8, "height": 8}},
    }
    facts_path = directory / "dom-facts.json"
    facts_path.write_text(json.dumps(dom_facts), encoding="utf-8")

    return {
        "design": str(design_path),
        "dom": str(dom_path),
        "map": str(map_path),
        "facts": str(facts_path),
    }


def test_every_element_gets_exactly_one_row_whatever_happened_to_it(tmp_path: Path) -> None:
    """The regression that made this lane worth porting: a refused element used to eat its row."""
    scenario = _crop_scenario(tmp_path)

    report = build_crop_report(scenario["design"], scenario["dom"], scenario["map"], scenario["facts"])

    statuses = {element["element"]: element["status"] for element in report["elements"]}
    assert statuses == {
        "compared": "compared",
        "size_mismatch": "size_mismatch",
        "outside-the-image": "refused",
        "no-design-box": "refused",
        "selector-not-in-facts": "refused",
    }
    assert len(report["_rows"]) == len(report["elements"])
    assert report["compared"] == 1


def test_a_refusal_is_printed_as_well_as_recorded(tmp_path: Path) -> None:
    """A refusal that only reaches the JSON is a gap the operator cannot see."""
    scenario = _crop_scenario(tmp_path)
    seen = []

    build_crop_report(scenario["design"], scenario["dom"], scenario["map"], scenario["facts"], log=seen.append)

    assert sum(1 for line in seen if "refused (" in line) == 3
    assert sum(1 for line in seen if "size_mismatch" in line) == 1
    assert sum(1 for line in seen if "px differ" in line) == 1


def test_a_size_drift_shows_both_crops_without_rescaling_either(tmp_path: Path) -> None:
    """Resampling would invent the pixels it then compares and erase the drift being shown."""
    scenario = _crop_scenario(tmp_path)

    report = build_crop_report(scenario["design"], scenario["dom"], scenario["map"], scenario["facts"])
    by_name = {element["element"]: element for element in report["elements"]}
    row = report["_rows"][[element["element"] for element in report["elements"]].index("size_mismatch")]

    assert (row[0].shape[0], row[0].shape[1]) == (8, 8)
    assert (row[1].shape[0], row[1].shape[1]) == (8, 6), "the DOM crop is the narrower one, unscaled"
    assert row[2] is None, "a pixel diff of two differently sized crops is not a picture of anything"
    assert "design crop is 8x8" in by_name["size_mismatch"]["reason"]
    assert "6x8" in by_name["size_mismatch"]["reason"]


def test_a_box_that_leaves_the_image_is_refused_rather_than_clamped() -> None:
    """Clamping would silently answer a question about a different region."""
    image = np.zeros((10, 10, 4), dtype=np.uint8)

    assert crop(image, {"x": -1, "y": 0, "width": 4, "height": 4})[1] is not None
    assert crop(image, {"x": 8, "y": 0, "width": 4, "height": 4})[1] is not None
    assert crop(image, {"x": 0, "y": 0, "width": 0, "height": 4})[1] is not None
    assert crop(image, {"x": 2, "y": 2, "width": 4, "height": 4})[1] is None


def test_the_sheet_keeps_a_blank_row_where_an_element_was_refused(tmp_path: Path) -> None:
    """Otherwise the strip shifts a picture onto the wrong element and a refusal reads as a match."""
    scenario = _crop_scenario(tmp_path)

    report = build_crop_report(scenario["design"], scenario["dom"], scenario["map"], scenario["facts"])
    sheet = render_crop_sheet(report)

    assert sheet is not None
    elements = [element["element"] for element in report["elements"]]
    step = sheet.shape[0] // len(elements)
    #: `compared` sorts first; the three refusals follow it and each must still occupy its row.
    assert (sheet[step : 4 * step] == 255).all(), "a refusal must leave a blank row, not close the gap"
    assert not (sheet[:step] == 255).all(), "the compared element's row is where its picture went"


def test_a_sheet_that_could_not_be_drawn_is_not_named(tmp_path: Path) -> None:
    """A path that was requested but never written reads as evidence of a file."""
    empty = {"design_image": "d", "dom_image": "m", "pixelmatch_threshold": 0.1, "compared": 0, "elements": []}

    assert public_crop_report(empty, sheet_written=False, sheet_path=str(tmp_path / "sheet.png"))["sheet"] is None
    written = public_crop_report(empty, sheet_written=True, sheet_path=str(tmp_path / "sheet.png"))
    assert written["sheet"] == str(tmp_path / "sheet.png")
    assert "design_image" in list(written)[0]


def test_a_sheet_with_nothing_in_it_is_not_drawn() -> None:
    assert compose_sheet([[None, None, None], [None, None, None]]) is None
    assert compose_sheet([]) is None


# --------------------------------------------------------------------------------------------
# The CLI surface §4.5 names
# --------------------------------------------------------------------------------------------


def _run_cli(args, cwd: Path):
    return subprocess.run(
        [*CHE_CLI_CMD, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(CHE_ROOT), "PATH": "/usr/bin:/bin"},
    )


def test_the_diff_does_not_fail_because_a_screen_differs(tmp_path: Path) -> None:
    """Evidence only: §4.5 is explicit that the ratio is neither a threshold nor a pass mark."""
    design_path, actual_path = _write_cases(tmp_path)["inverted"]

    result = _run_cli(
        ["pixel", "diff", "--design", str(design_path), "--dom", str(actual_path), "--out", str(tmp_path / "d.png")],
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert "% of pixels differ" in result.stdout
    assert "not a threshold" in result.stdout
    assert (tmp_path / "d.png").exists()


def test_the_diff_refuses_two_rasters_of_different_sizes(tmp_path: Path) -> None:
    design_path, actual_path = _write_cases(tmp_path)["identical"]
    save_rgba(np.zeros((7, 9, 4), dtype=np.uint8), actual_path)

    result = _run_cli(
        ["pixel", "diff", "--design", str(design_path), "--dom", str(actual_path), "--out", str(tmp_path / "d.png")],
        tmp_path,
    )

    assert result.returncode == 2
    assert "refusing" in result.stderr
    assert not (tmp_path / "d.png").exists()


def test_the_crop_writes_a_report_and_exits_zero(tmp_path: Path) -> None:
    scenario = _crop_scenario(tmp_path)
    report_path, sheet_path = tmp_path / "report.json", tmp_path / "sheet.png"

    result = _run_cli(
        [
            "pixel",
            "crop",
            "--design",
            scenario["design"],
            "--dom",
            scenario["dom"],
            "--map",
            scenario["map"],
            "--dom-facts",
            scenario["facts"],
            "--out",
            str(report_path),
            "--sheet",
            str(sheet_path),
            "--json",
        ],
        tmp_path,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["compared"] == 1
    assert payload["sheet"] == str(sheet_path)
    assert len(payload["elements"]) == 5
    assert json.loads(report_path.read_text(encoding="utf-8")) == payload
    assert sheet_path.exists(), "one element was compared, so there is a row to draw"
