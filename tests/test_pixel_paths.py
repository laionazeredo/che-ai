"""Contract tests for `che pixel paths` — where the gate's artefacts live.

The gate's recipe used undefined shell variables (`$DESIGN_MAP`, `$DOM_FACTS`,
`$DESIGN_RAW`, `$DOMAIN_GATE_REPORT`) until now, so every run invented its own paths.
That is not a cosmetic problem in either direction:

* §4.3 freezes the element map as **regression**. If its name carried a timestamp —
  which is what every other Che artefact does — the next run would not find the
  previous one, and a re-run would look like a new map rather than the same one measured
  again. The whole comparison across runs would be gone.
* §5 allows exactly **one** free retry. If attempt 2 wrote over attempt 1's report, the
  budget would be unauditable after the fact: nothing on disk would show that a retry
  happened, or what the first score was.

So these tests pin the two classes apart — and the refusal that keeps a mistyped
sub-product from creating a second design root no skill owns.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

CHE_CLI_CMD = [sys.executable, "-m", "che_core.cli"]
#: `che_core` is importable from the Che checkout, not from the worktree under test, so
#: every call that runs with `cwd=<tmp repo>` has to carry the checkout on PYTHONPATH.
CHE_ROOT = Path(__file__).resolve().parent.parent

#: Every line the resolver prints. A stray `print` inside the helper would break every
#: caller's `eval` — quietly, and only in the shell that consumed it.
_EXPORT_LINE = re.compile(r'^export (CHE_PIXEL_[A-Z_]+)="(.+)"$')

_KEYS = {
    "CHE_PIXEL_DIR",
    "CHE_PIXEL_MAP",
    "CHE_PIXEL_DESIGN_FACTS",
    "CHE_PIXEL_DESIGN_RAW",
    "CHE_PIXEL_DOM_FACTS",
    "CHE_PIXEL_REPORT",
    "CHE_PIXEL_DESIGN_IMAGE",
    "CHE_PIXEL_DOM_SCREENSHOT",
    "CHE_PIXEL_VISUAL_DIFF",
    "CHE_PIXEL_CROP_REPORT",
    "CHE_PIXEL_CROP_SHEET",
}

#: The §4.5 pictures. Split out of `_KEYS` because no verdict reads them — they are named here so
#: the recipe has somewhere to write, not because they are scored.
_EVIDENCE_KEYS = {
    "CHE_PIXEL_DESIGN_IMAGE",
    "CHE_PIXEL_DOM_SCREENSHOT",
    "CHE_PIXEL_VISUAL_DIFF",
    "CHE_PIXEL_CROP_SHEET",
}

#: The per-element crop's numbers. Its own set because it is the one evidence artefact that is not
#: a picture, and because it is attempt-scoped like the report: §5's retry budget is only auditable
#: afterwards if the artefacts that describe one attempt are not overwritten by the next.
_CROP_REPORT_KEY = "CHE_PIXEL_CROP_REPORT"


def _env() -> dict:
    """The caller's environment — which carries the fixture's CHE_WORKSPACES_ROOT — plus
    the checkout on PYTHONPATH, since these calls run with the worktree as cwd."""
    return {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(filter(None, [str(CHE_ROOT), os.environ.get("PYTHONPATH", "")])),
    }


def _paths(repo: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        CHE_CLI_CMD + ["pixel", "paths", str(repo), "sess-pixel", "--sub-product", "demo", *extra],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=_env(),
        check=False,
    )


def _parse(stdout: str) -> dict:
    parsed = {}
    for line in stdout.splitlines():
        match = _EXPORT_LINE.match(line)
        assert match, f"not an eval-safe export line: {line!r}"
        parsed[match.group(1)] = match.group(2)
    return parsed


def _with_design_tree(bound_worktree) -> Path:
    repo, _ = bound_worktree
    (repo / "design" / "demo" / "source").mkdir(parents=True, exist_ok=True)
    return repo


# --- The two storage classes -------------------------------------------------


def test_the_frozen_artifacts_sit_inside_the_worktree_with_stable_names(bound_worktree) -> None:
    """Two runs must resolve the same map path, or "frozen as regression" is a fiction."""
    repo = _with_design_tree(bound_worktree)

    first = _parse(_paths(repo, "--breakpoint", "lg", "--backend", "figma").stdout)
    second = _parse(_paths(repo, "--breakpoint", "lg", "--backend", "figma").stdout)

    assert first["CHE_PIXEL_MAP"] == second["CHE_PIXEL_MAP"]
    assert first["CHE_PIXEL_DESIGN_FACTS"] == second["CHE_PIXEL_DESIGN_FACTS"]
    for key in ("CHE_PIXEL_MAP", "CHE_PIXEL_DESIGN_FACTS", "CHE_PIXEL_DIR"):
        assert first[key].startswith(str(repo) + "/"), f"{key} must be committed: {first[key]}"


def test_each_breakpoint_gets_its_own_frozen_artifacts(bound_worktree) -> None:
    """A 375 map and a 1440 map are two references, not one that drifted."""
    repo = _with_design_tree(bound_worktree)

    lg = _parse(_paths(repo, "--breakpoint", "lg", "--backend", "figma").stdout)
    sm = _parse(_paths(repo, "--breakpoint", "sm", "--backend", "figma").stdout)

    assert lg["CHE_PIXEL_MAP"] != sm["CHE_PIXEL_MAP"]
    assert lg["CHE_PIXEL_DIR"] == sm["CHE_PIXEL_DIR"]


def test_the_measurements_land_in_the_session_and_name_the_attempt(bound_worktree) -> None:
    """§5 gives one free retry, so attempt 1 must survive attempt 2."""
    repo = _with_design_tree(bound_worktree)

    one = _parse(_paths(repo, "--breakpoint", "lg", "--backend", "figma", "--attempt", "1").stdout)
    two = _parse(_paths(repo, "--breakpoint", "lg", "--backend", "figma", "--attempt", "2").stdout)

    for run, attempt in ((one, "1"), (two, "2")):
        assert f"-attempt{attempt}.json" in run["CHE_PIXEL_REPORT"]
        assert not run["CHE_PIXEL_DOM_FACTS"].startswith(str(repo) + "/"), "a measurement is never committed"
    assert one["CHE_PIXEL_REPORT"] != two["CHE_PIXEL_REPORT"]


def test_the_session_artifacts_are_grouped_by_related_id(bound_worktree) -> None:
    repo = _with_design_tree(bound_worktree)

    tagged = _parse(_paths(repo, "--breakpoint", "lg", "--backend", "figma", "--related-id", "FLO-7").stdout)

    assert "/FLO-7/" in tagged["CHE_PIXEL_REPORT"]
    assert "/FLO-7/" in tagged["CHE_PIXEL_DOM_FACTS"]


def test_every_key_of_the_set_is_resolved(bound_worktree) -> None:
    """The recipe substitutes all of them; a missing one would be an empty `--out` or `--map`."""
    repo = _with_design_tree(bound_worktree)

    assert set(_parse(_paths(repo, "--breakpoint", "lg", "--backend", "figma").stdout)) == _KEYS


# --- §4.5 evidence: named, session-side, and never the verdict ---------------


def test_the_evidence_pictures_have_somewhere_to_go(bound_worktree) -> None:
    """§4.5 and §6.1 both tell the reviewer to look at the diff, so every input and the
    composites must resolve to a real path — an instruction pointing at no file is the
    defect this whole convention exists to remove."""
    repo = _with_design_tree(bound_worktree)

    run = _parse(_paths(repo, "--breakpoint", "lg", "--backend", "figma").stdout)

    assert _EVIDENCE_KEYS <= set(run)
    assert len({run[key] for key in _EVIDENCE_KEYS}) == 4, "each picture is its own file"
    for key in _EVIDENCE_KEYS:
        assert run[key].endswith(".png")
        assert not run[key].startswith(str(repo) + "/"), f"{key} is evidence, not a committed reference"


def test_the_crop_report_is_attempt_scoped_like_the_measurements(bound_worktree) -> None:
    """§5's budget is only auditable afterwards if attempt 1 survives attempt 2.

    The per-element crop describes one attempt, exactly as the report does, so both carry the
    number and neither is written over. The pictures cannot: `pixelmatch` produces one composite
    per run, and it is regenerable from the flagged attempt's inputs.
    """
    repo = _with_design_tree(bound_worktree)

    first = _parse(_paths(repo, "--breakpoint", "lg", "--backend", "figma").stdout)
    second = _parse(_paths(repo, "--breakpoint", "lg", "--backend", "figma", "--attempt", "2").stdout)

    assert first[_CROP_REPORT_KEY].endswith(".json")
    assert "attempt1" in first[_CROP_REPORT_KEY]
    assert first[_CROP_REPORT_KEY] != second[_CROP_REPORT_KEY]
    assert "attempt2" in second[_CROP_REPORT_KEY]


def test_the_evidence_does_not_collide_with_the_report(bound_worktree) -> None:
    """A composite written over the report would lose the verdict it is supposed to support."""
    repo = _with_design_tree(bound_worktree)

    run = _parse(_paths(repo, "--breakpoint", "lg", "--backend", "figma").stdout)
    json_and_png = {"CHE_PIXEL_REPORT", "CHE_PIXEL_DOM_FACTS"} | _EVIDENCE_KEYS

    assert len({run[key] for key in json_and_png}) == len(json_and_png)


# --- The backend decides what the raw artefact even is -----------------------


def test_figma_dumps_its_capture_beside_the_map(bound_worktree) -> None:
    """`get_figma_data` returns text with no home of its own, so the capture is committed:
    the scored numbers must stay re-derivable from the reference they were read from."""
    repo = _with_design_tree(bound_worktree)

    raw = _parse(_paths(repo, "--breakpoint", "lg", "--backend", "figma").stdout)["CHE_PIXEL_DESIGN_RAW"]

    assert raw == str(repo / "design" / "demo" / "pixel-check" / "lg.design-raw.txt")


def test_openpencil_points_at_the_committed_op_source(bound_worktree) -> None:
    """`.op` is already the committed source of truth, so a second copy would be a fork."""
    repo = _with_design_tree(bound_worktree)

    raw = _parse(_paths(repo, "--breakpoint", "lg", "--backend", "openpencil").stdout)["CHE_PIXEL_DESIGN_RAW"]

    assert raw == str(repo / "design" / "demo" / "source" / "home.op")


# --- Refusals -----------------------------------------------------------------


def test_a_sub_product_without_a_design_tree_is_refused(bound_worktree) -> None:
    """Fail-closed: an unowned slug must not silently become a second design root."""
    repo, _ = bound_worktree

    proc = _paths(repo, "--breakpoint", "lg", "--backend", "figma")

    assert proc.returncode == 2
    assert "no design tree" in proc.stderr
    assert "che designer init" in proc.stderr
    assert not (repo / "design" / "demo").exists(), "a refused run writes nothing"


@pytest.mark.parametrize("attempt", ["0", "-1"])
def test_an_attempt_below_one_is_refused(bound_worktree, attempt: str) -> None:
    repo = _with_design_tree(bound_worktree)

    proc = _paths(repo, "--breakpoint", "lg", "--backend", "figma", "--attempt", attempt)

    assert proc.returncode == 2
    assert "--attempt must be >= 1" in proc.stderr


@pytest.mark.parametrize("breakpoint", ["", "  ", "../lg", "a/b"])
def test_a_breakpoint_that_cannot_name_a_file_is_refused(bound_worktree, breakpoint: str) -> None:
    repo = _with_design_tree(bound_worktree)

    proc = _paths(repo, "--breakpoint", breakpoint, "--backend", "figma")

    assert proc.returncode == 2
    assert "not a usable breakpoint label" in proc.stderr


def test_a_backend_with_no_capture_convention_is_refused(bound_worktree) -> None:
    """This flag picks a filename convention, so a backend no session was ever recorded from
    has none to pick.

    Penpot is declared first-class by the UX domain, which is exactly why the refusal cannot
    be left to the argument parser: `invalid choice` reads as a typo the caller did not make,
    and it is answered before anything that knows why.
    """
    repo = _with_design_tree(bound_worktree)

    proc = _paths(repo, "--breakpoint", "lg", "--backend", "penpot")

    assert proc.returncode == 2
    assert "no capture convention" in proc.stderr
    assert "invalid choice" not in proc.stderr
    assert proc.stdout == "", "a refused run resolves no paths at all"


def test_a_missing_worktree_is_refused(tmp_path: Path) -> None:
    proc = subprocess.run(
        CHE_CLI_CMD
        + [
            "pixel",
            "paths",
            str(tmp_path / "nope"),
            "sess-pixel",
            "--sub-product",
            "demo",
            "--breakpoint",
            "lg",
            "--backend",
            "figma",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 2
    assert "not a valid worktree directory" in proc.stderr


# --- The output is meant to be eval'd ----------------------------------------


def test_the_output_is_a_valid_shell_eval(bound_worktree) -> None:
    """The recipe is `eval "$(che pixel paths …)"`, so shell quoting is part of the contract."""
    repo = _with_design_tree(bound_worktree)

    proc = subprocess.run(
        [
            "bash",
            "-c",
            'eval "$(python3 -m che_core.cli pixel paths "$1" sess-pixel --sub-product demo '
            '--breakpoint lg --backend figma)" && printf "%s\\n" "$CHE_PIXEL_MAP" "$CHE_PIXEL_REPORT"',
            "bash",
            str(repo),
        ],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=_env(),
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    map_path, report_path = proc.stdout.splitlines()
    assert map_path.endswith("lg.map.json")
    assert "attempt1" in report_path
