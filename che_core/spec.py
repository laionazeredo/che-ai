"""Deterministic structural checks for Che SPEC files — the V-gates as code.

WHY THIS EXISTS
---------------
The V1-V25 checks in ``skills/che-spec/SKILL.md`` used to be prose. An agent had to
read them and *choose* to comply: CI could not run them, a template edit could
silently invalidate them, and two runs on the same draft could disagree. That
contradicts the harness's own rule (``AGENTS.md`` §2 — procedural logic belongs in
``che_core/`` behind the CLI).

This module implements the checks that are purely structural: frontmatter keys,
table row counts, ratios, regexes and section presence. The semantic checks (is
this anti-behaviour actually dangerous? is that DONE criterion truthful?) stay with
the agent, because no regex can answer them.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It never rewrites the SPEC it validates — a validator that edits its input cannot
be trusted to report on it. Failures come back as data and the caller decides.

TIERING
-------
Not every task deserves nine tables. ``spec_tier`` scales the gate: ``lite`` for a
low-risk change to a handful of files, ``standard`` for the default case, ``full``
for high risk or a wide blast radius. The tier is declared in the frontmatter when
the author wants control, and otherwise inferred from ``risk_level`` and
``estimated_files_max``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from che_core.diagnostics import fail
from che_core.paths import write_file_atomic
from che_core.project_layout import get_domain_dir, normalise_domain

TIERS = ("lite", "standard", "full")

#: Frontmatter keys the rest of the harness reads. Missing one of these means a
#: downstream skill will silently take a default, which is worse than a red gate.
REQUIRED_FRONTMATTER = (
    "spec_id",
    "worktree_root",
    "change_class",
    "domain",
    "risk_level",
    "status",
    "estimated_files_max",
    "readiness",
    "readiness_report",
    "open_assumptions",
)

_SELECTOR_RE = re.compile(r"^[a-z0-9][a-z0-9-]*__[a-z0-9][a-z0-9-]*__[a-z0-9][a-z0-9-]*(--[a-z0-9][a-z0-9-]*)?$")
_B_ROW_RE = re.compile(r"^\*{0,2}(B-\d+)\*{0,2}$")
_AB_ROW_RE = re.compile(r"^\*{0,2}(AB-\d+)\*{0,2}$")
_A_ROW_RE = re.compile(r"^\*{0,2}(A-\d+)\*{0,2}$")
_WEASEL_RE = re.compile(r"\b(correctly|as expected|properly|works|ok)\b", re.IGNORECASE)
_SEPARATOR_RE = re.compile(r"^:?-{2,}:?$")
_TEST_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"}
_SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "vendor", "__pycache__", ".venv", "venv"}


# --- Parsing -----------------------------------------------------------------


def parse_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """Split a SPEC into its YAML-ish frontmatter and its body.

    The parser is deliberately small: flat ``key: value`` pairs plus inline lists
    (``[a, b]``). Che SPECs use nothing else, and pulling in a YAML dependency for
    six syntax forms would violate the two-dependency budget.

    Postcondition: returns ``({}, text)`` when there is no frontmatter block, so a
    caller can always treat the result as a mapping plus a body.
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = index
            break
    if end is None:
        return {}, text

    frontmatter: Dict[str, Any] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        value = raw.strip()
        if value and value[0] not in "\"'[" and " #" in value:
            value = value.split(" #", 1)[0].strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            frontmatter[key] = [item.strip().strip("\"'") for item in inner.split(",") if item.strip()]
        else:
            frontmatter[key] = value.strip("\"'")
    return frontmatter, "\n".join(lines[end + 1 :])


def _cells(line: str) -> List[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator(cells: List[str]) -> bool:
    return bool(cells) and all(_SEPARATOR_RE.match(cell) for cell in cells if cell)


def _rows_after(lines: List[str], marker: str) -> List[List[str]]:
    """Table rows of the first block that follows ``marker``.

    Stops at the next heading, so a table can never leak rows from the section
    below it — the failure mode that made the prose version easy to satisfy with
    the wrong table.
    """
    start = None
    for index, line in enumerate(lines):
        if line.strip().startswith(marker):
            start = index + 1
            break
    if start is None:
        return []

    rows: List[List[str]] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("#"):
            break
        if not stripped:
            if rows:
                break
            continue
        if not stripped.startswith("|"):
            if rows:
                break
            continue
        cells = _cells(stripped)
        if _is_separator(cells):
            continue
        rows.append(cells)
    return rows


def _id_rows(rows: List[List[str]], pattern: "re.Pattern[str]") -> List[Tuple[str, List[str]]]:
    found = []
    for row in rows:
        if not row:
            continue
        match = pattern.match(row[0])
        if match:
            found.append((match.group(1), row))
    return found


def _cell(row: List[str], index: int) -> str:
    return row[index] if len(row) > index else ""


def _section(lines: List[str], start_marker: str, stop_markers: Tuple[str, ...]) -> List[str]:
    start = None
    for index, line in enumerate(lines):
        if line.strip().startswith(start_marker):
            start = index
            break
    if start is None:
        return []
    body = []
    for line in lines[start + 1 :]:
        if any(line.strip().startswith(marker) for marker in stop_markers):
            break
        body.append(line)
    return body


# --- Tier --------------------------------------------------------------------


def infer_tier(frontmatter: Dict[str, Any]) -> str:
    """Declared ``spec_tier`` wins; otherwise derive it from risk and blast radius."""
    declared = str(frontmatter.get("spec_tier") or "").strip().lower()
    if declared in TIERS:
        return declared
    risk = str(frontmatter.get("risk_level") or "low").strip().lower()
    try:
        files = int(str(frontmatter.get("estimated_files_max") or 15))
    except ValueError:
        files = 15
    if risk == "high" or files >= 10:
        return "full"
    if risk == "low" and files <= 5:
        return "lite"
    return "standard"


# --- Validation --------------------------------------------------------------


def _check(checks: List[Dict[str, str]], check_id: str, status: str, detail: str = "") -> None:
    checks.append({"id": check_id, "status": status, "detail": detail})


def _layer_count(cell: str) -> int:
    """Distinct architectural layers named in a vertical-slice row.

    Prefers path prefixes (``pages/x`` and ``app/api/y`` are two layers); falls
    back to counting the ``·``-separated tokens when the row names layers instead
    of paths.
    """
    tokens = [token.strip() for token in cell.split("·") if token.strip()]
    prefixes = {token.split("/")[0].strip("`* ") for token in tokens if "/" in token}
    return max(len(prefixes), len(tokens))


def validate_spec(path: str, tier: Optional[str] = None) -> Dict[str, Any]:
    """Run the structural V-checks on one SPEC file.

    Preconditions: ``path`` points at a readable file; ``tier`` (when given) is one
    of :data:`TIERS`.
    Postcondition: returns a report with one entry per applicable check, never
    raising for a failed check — the caller renders and exits.
    """
    if tier is not None and tier not in TIERS:
        fail("INVALID_SPEC_TIER", tier=tier)

    spec_path = Path(path).expanduser()
    try:
        text = spec_path.read_text(encoding="utf-8")
    except OSError as exc:
        fail("UNREADABLE_INPUT", path=str(spec_path), detail=str(exc))

    frontmatter, body = parse_frontmatter(text)
    lines = body.splitlines()
    effective_tier = tier or infer_tier(frontmatter)
    checks: List[Dict[str, str]] = []

    b_rows = _id_rows(_rows_after(lines, "### §4.2"), _B_ROW_RE)
    ab_rows = _id_rows(_rows_after(lines, "### §4.3"), _AB_ROW_RE)
    b_count, ab_count = len(b_rows), len(ab_rows)

    # V1 — frontmatter completeness.
    missing = [key for key in REQUIRED_FRONTMATTER if not str(frontmatter.get(key, "")).strip()]
    if not frontmatter:
        _check(checks, "V1", "fail", "no YAML frontmatter block")
    elif missing:
        _check(checks, "V1", "fail", f"missing frontmatter keys: {', '.join(missing)}")
    else:
        _check(checks, "V1", "pass")

    # V2 — blast-radius ceiling.
    try:
        files = int(str(frontmatter.get("estimated_files_max") or 0))
    except ValueError:
        files = 0
    if files <= 0:
        _check(checks, "V2", "fail", "estimated_files_max must be a positive integer")
    elif files > 20:
        _check(checks, "V2", "fail", f"estimated_files_max={files} exceeds the 20-file ceiling")
    else:
        _check(checks, "V2", "pass")

    # V9 — at most ten positive behaviours.
    if b_count == 0:
        _check(checks, "V9", "fail", "no B-ID rows found under ### §4.2")
    elif b_count > 10:
        _check(checks, "V9", "fail", f"B_COUNT={b_count} exceeds the maximum of 10")
    else:
        _check(checks, "V9", "pass", f"B_COUNT={b_count}")

    # V10 — anti-behaviour ratio.
    expected_ab = -(-b_count // 3) if b_count else 0
    if b_count and ab_count < expected_ab:
        _check(checks, "V10", "fail", f"AB_COUNT={ab_count} < ceil({b_count}/3)={expected_ab}")
    elif b_count:
        _check(checks, "V10", "pass", f"AB_COUNT={ab_count} >= {expected_ab}")
    else:
        _check(checks, "V10", "skip", "no B-IDs to ratio against")

    # V11 — every positive behaviour names at least one test layer.
    without_layer = [b_id for b_id, row in b_rows if "✅" not in _cell(row, 4)]
    if not b_rows:
        _check(checks, "V11", "skip", "no B-ID rows")
    elif without_layer:
        _check(checks, "V11", "fail", f"no ✅ test layer on: {', '.join(without_layer)}")
    else:
        _check(checks, "V11", "pass")

    # V12 — UI selector contract (standard and above).
    if effective_tier == "lite":
        _check(checks, "V12", "skip", "tier=lite")
    else:
        bad_selectors = []
        for b_id, row in b_rows:
            if "Playwright" not in _cell(row, 4):
                continue
            selectors = re.findall(r"`([^`]+)`", _cell(row, 5))
            if not selectors:
                bad_selectors.append(f"{b_id} (none)")
                continue
            for selector in selectors:
                if not _SELECTOR_RE.match(selector):
                    bad_selectors.append(f"{b_id}={selector}")
        if bad_selectors:
            _check(checks, "V12", "fail", f"selector contract violated: {', '.join(bad_selectors)}")
        else:
            _check(checks, "V12", "pass")

    # V16 / V17 — vertical slices (standard and above).
    slice_rows = _rows_after(lines, "### §4.5")
    slices = []
    for row in slice_rows:
        slice_id = row[0].strip("* ").upper() if row else ""
        if re.match(r"^F\d+$", slice_id):
            slices.append((slice_id, row))

    if effective_tier == "lite":
        _check(checks, "V16", "skip", "tier=lite")
        _check(checks, "V17", "skip", "tier=lite")
    else:
        f0 = next((row for slice_id, row in slices if slice_id == "F0"), None)
        if f0 is None:
            _check(checks, "V16", "fail", "no F0 tracer row under ### §4.5")
        else:
            problems = []
            if _layer_count(_cell(f0, 3)) < 2:
                problems.append("F0 touches fewer than 2 architectural layers")
            if not re.search(r"\b(?:AB-)?B-\d+\b", _cell(f0, 2)):
                problems.append("F0 covers no B-ID")
            done = _cell(f0, 5)
            if not done:
                problems.append("F0 DONE criterion is empty")
            elif _WEASEL_RE.search(done):
                problems.append("F0 DONE criterion uses weasel words")
            if problems:
                _check(checks, "V16", "fail", "; ".join(problems))
            else:
                _check(checks, "V16", "pass", "F0 tracer is vertical")

        consecutive = 0
        horizontal = False
        for _slice_id, row in slices:
            consecutive = consecutive + 1 if _layer_count(_cell(row, 3)) == 1 else 0
            if consecutive >= 3:
                horizontal = True
                break
        if horizontal:
            _check(checks, "V17", "fail", "three or more consecutive single-layer slices")
        else:
            _check(checks, "V17", "pass")

    # V23 — simplicity bias: explicit deferral plus alternatives and a kill switch.
    why = "\n".join(_section(lines, "## §1", ("## §2", "## §3", "## §4", "## §5", "## §6", "## §7")))
    if "non-goals" not in why.lower():
        _check(checks, "V23", "fail", "§1 WHY has no Non-goals (deferred by design) bullet")
    elif effective_tier != "lite" and "alternatives considered" not in why.lower():
        _check(checks, "V23", "fail", "§1 WHY has no Alternatives considered bullet")
    elif effective_tier != "lite" and "kill criterion" not in why.lower():
        _check(checks, "V23", "fail", "§1 WHY has no Kill criterion bullet")
    else:
        _check(checks, "V23", "pass")

    # V24 — readiness gate recorded.
    readiness = str(frontmatter.get("readiness", "")).strip().lower()
    if readiness == "blocked":
        _check(checks, "V24", "fail", "readiness=blocked: no draft may exist")
    elif readiness not in ("passed", "assumptions"):
        _check(checks, "V24", "fail", f"readiness={readiness!r} must be passed|assumptions|blocked")
    elif not str(frontmatter.get("readiness_report", "")).strip():
        _check(checks, "V24", "fail", "readiness_report is empty")
    else:
        _check(checks, "V24", "pass", f"readiness={readiness}")

    # V25 — the executive summary is present, capped and decision-bearing.
    summary_start = next((i for i, line in enumerate(lines) if line.strip().startswith("## §0")), None)
    why_start = next((i for i, line in enumerate(lines) if line.strip().startswith("## §1")), None)
    if summary_start is None:
        _check(checks, "V25", "fail", "no ## §0 EXECUTIVE SUMMARY")
    elif why_start is not None and summary_start > why_start:
        _check(checks, "V25", "fail", "§0 appears after §1")
    else:
        end = why_start if why_start is not None else len(lines)
        summary = [line for line in lines[summary_start + 1 : end] if line.strip()]
        decisions = next((line for line in summary if line.lower().lstrip("| ").startswith("decisions needed")), "")
        if len(summary) > 15:
            _check(checks, "V25", "fail", f"§0 has {len(summary)} non-empty lines (cap 15)")
        elif not decisions or not decisions.strip("| ").split("|")[-1].strip():
            _check(checks, "V25", "fail", "§0 has no Decisions needed row")
        else:
            _check(checks, "V25", "pass")

    # V19-V22 — full tier only: the design-quality tables.
    if effective_tier != "full":
        for check_id in ("V19", "V20", "V21", "V22"):
            _check(checks, check_id, "skip", f"tier={effective_tier}")
    else:
        missing_tables = [marker for marker in ("§4.6.1", "§4.6.2", "§4.6.3") if marker not in body]
        _check(
            checks,
            "V19",
            "fail" if missing_tables else "pass",
            f"missing: {', '.join(missing_tables)}" if missing_tables else "",
        )

        a_rows = _id_rows(_rows_after(lines, "§4.7"), _A_ROW_RE)
        expected_a = -(-b_count // 3) if b_count else 0
        if "§4.7" not in body:
            _check(checks, "V20", "fail", "§4.7 assertive-programming table missing")
        elif len(a_rows) < expected_a:
            _check(checks, "V20", "fail", f"A_COUNT={len(a_rows)} < ceil({b_count}/3)={expected_a}")
        elif any("CRASH" not in _cell(row, 3).upper() for _row_id, row in a_rows):
            _check(checks, "V20", "fail", "an assertion row is not marked CRASH")
        else:
            _check(checks, "V20", "pass")

        if b_count >= 5 and "§4.8" not in body:
            _check(checks, "V21", "fail", "§4.8 DRY single-source table missing (B_COUNT>=5)")
        else:
            _check(checks, "V21", "pass")

        if len(_can_touch_prefixes(lines)) >= 3 and "§4.9" not in body:
            _check(checks, "V22", "fail", "§4.9 orthogonality map missing (>=3 top-level packages)")
        else:
            _check(checks, "V22", "pass")

    failures = [f"{entry['id']}: {entry['detail']}" for entry in checks if entry["status"] == "fail"]
    return {
        "ok": not failures,
        "path": str(spec_path),
        "tier": effective_tier,
        "counts": {"b": b_count, "ab": ab_count},
        "checks": checks,
        "failures": failures,
    }


def _can_touch_prefixes(lines: List[str]) -> List[str]:
    """Top-level path prefixes named in §2 CAN TOUCH — the orthogonality trigger."""
    section = _section(lines, "## §2", ("## §3", "## §4", "## §5", "## §6", "## §7"))
    inside = False
    prefixes = set()
    for line in section:
        stripped = line.strip()
        if stripped.startswith("###"):
            inside = "CAN TOUCH" in stripped.upper() and "CREATE" not in stripped.upper()
            continue
        if not inside or not stripped.startswith("-"):
            continue
        for token in re.findall(r"`([^`]+)`", stripped):
            prefixes.add(token.split("/")[0])
    return sorted(prefixes)


# --- Coverage ----------------------------------------------------------------


def _behaviour_ids(body: str) -> List[Dict[str, str]]:
    lines = body.splitlines()
    ids: List[Dict[str, str]] = []
    for anchor, row in _id_rows(_rows_after(lines, "### §4.2"), _B_ROW_RE):
        ids.append({"anchor": anchor, "then": _cell(row, 3)})
    for anchor, row in _id_rows(_rows_after(lines, "### §4.3"), _AB_ROW_RE):
        ids.append({"anchor": anchor, "then": _cell(row, 3)})
    return ids


def _iter_test_files(root: Path) -> List[Path]:
    found: List[Path] = []
    for candidate in root.rglob("*"):
        if len(found) >= 5000:
            break
        if not candidate.is_file() or candidate.suffix not in _TEST_SUFFIXES:
            continue
        if any(part in _SKIP_DIRS for part in candidate.parts):
            continue
        name = candidate.name.lower()
        if "test" in name or "spec" in name:
            found.append(candidate)
    return found


def coverage(spec_path: str, worktree: Optional[str] = None) -> Dict[str, Any]:
    """Bilateral check: every B-ID/AB-ID in the SPEC is named by at least one test.

    This is the executable half of the ``§5 VERIFICATION MATRIX``. The matrix says
    "Planned/Written"; this command says which anchors no test mentions at all,
    which is the question a human cannot answer by eye after ten commits.

    Preconditions: the SPEC parses; a worktree is given either as an argument or in
    the frontmatter.
    Postcondition: one row per anchor with the files that mention it, never a guess.
    """
    path = Path(spec_path).expanduser()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        fail("UNREADABLE_INPUT", path=str(path), detail=str(exc))

    frontmatter, body = parse_frontmatter(text)
    root_value = worktree or str(frontmatter.get("worktree_root") or "")
    if not root_value:
        fail("MISSING_SPEC_ARGUMENT", detail="pass --worktree or set worktree_root in the frontmatter")
    root = Path(root_value).expanduser()
    if not root.is_dir():
        fail("NOT_A_DIRECTORY", path=root)

    anchors = _behaviour_ids(body)
    files = _iter_test_files(root)
    contents = []
    for file_path in files:
        try:
            contents.append((str(file_path), file_path.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue

    rows = []
    for anchor in anchors:
        pattern = re.compile(r"(?<![A-Za-z0-9-])" + re.escape(anchor["anchor"]) + r"(?![0-9])")
        hits = [file_name for file_name, content in contents if pattern.search(content)]
        rows.append(
            {
                "anchor": anchor["anchor"],
                "status": "covered" if hits else "missing",
                "files": hits[:5],
            }
        )

    missing = [row["anchor"] for row in rows if row["status"] == "missing"]
    return {
        "ok": not missing,
        "path": str(path),
        "worktree": str(root),
        "scanned_files": len(files),
        "rows": rows,
        "summary": {"total": len(rows), "covered": len(rows) - len(missing), "missing": missing},
    }


# --- As-built merge ----------------------------------------------------------


_AS_BUILT_HEADER = "## Current behaviours"


def _existing_rows(target: Path) -> Dict[str, List[str]]:
    if not target.is_file():
        return {}
    _frontmatter, body = parse_frontmatter(target.read_text(encoding="utf-8"))
    rows = _id_rows(_rows_after(body.splitlines(), _AS_BUILT_HEADER), _B_ROW_RE)
    return {b_id: row for b_id, row in rows}


def _render_as_built(
    domain: str,
    spec_id: str,
    spec_path: str,
    merged: Dict[str, List[str]],
    added: List[str],
    modified: List[str],
    timestamp: str,
) -> str:
    def cell(value: str) -> str:
        return value.replace("|", "\\|")

    lines = [
        f"# As-built specification — {domain}",
        "",
        '> Maintained by `che spec merge`. This is the durable answer to "what does the',
        '> system do today?"; a SPEC describes one change, this file accumulates them.',
        f"> Last merge: {timestamp} from `{spec_id}` (`{spec_path}`).",
        "",
        _AS_BUILT_HEADER,
        "",
        "| B-ID | Given | When | Then | Source |",
        "|---|---|---|---|---|",
    ]
    for b_id, row in merged.items():
        lines.append(f"| {b_id} | {cell(_cell(row, 1))} | {cell(_cell(row, 2))} | {cell(_cell(row, 3))} | {spec_id} |")
    lines += ["", f"## Delta — {spec_id} ({timestamp})", "", "### ADDED"]
    lines += [f"- {b_id}" for b_id in added] or ["- none"]
    lines += ["", "### MODIFIED"]
    lines += [f"- {b_id}" for b_id in modified] or ["- none"]
    lines += [
        "",
        "### REMOVED",
        "- none detected — removals must be declared explicitly; this command never drops a behaviour",
        "",
    ]
    return "\n".join(lines)


def merge_as_built(spec_path: str, project: str, domain: str = "engineering", dry_run: bool = True) -> Dict[str, Any]:
    """Fold an Approved SPEC's positive behaviours into the project's as-built spec.

    Without this, Che's SPEC is an execution artifact that dies with the session and
    the next agent has no description of the system — the gap OpenSpec closes with
    delta specs and archiving.

    Preconditions: the SPEC parses and has at least one B-ID.
    Postcondition: with ``dry_run=False`` the target exists and contains every
    previously known behaviour plus the new ones; no behaviour is ever deleted.
    """
    path = Path(spec_path).expanduser()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        fail("UNREADABLE_INPUT", path=str(path), detail=str(exc))

    frontmatter, body = parse_frontmatter(text)
    spec_id = str(frontmatter.get("spec_id") or path.stem)
    domain_slug = normalise_domain(domain)
    target = get_domain_dir(project, domain_slug) / "spec.md"

    new_rows = dict(_id_rows(_rows_after(body.splitlines(), "### §4.2"), _B_ROW_RE))
    if not new_rows:
        fail("SPEC_HAS_NO_BEHAVIOURS")

    existing = _existing_rows(target)
    merged: Dict[str, List[str]] = dict(existing)
    added: List[str] = []
    modified: List[str] = []
    for b_id, row in new_rows.items():
        if b_id not in merged:
            added.append(b_id)
        elif _cell(merged[b_id], 3) != _cell(row, 3):
            modified.append(b_id)
        merged[b_id] = row

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    content = _render_as_built(domain_slug, spec_id, str(path), merged, added, modified, timestamp)
    if not dry_run:
        write_file_atomic(
            str(target), content.encode("utf-8"), worktree_root=str(frontmatter.get("worktree_root") or "")
        )

    return {
        "dry_run": dry_run,
        "target": str(target),
        "spec_id": spec_id,
        "domain": domain_slug,
        "added": added,
        "modified": modified,
        "total_behaviours": len(merged),
        "note": "removals are never inferred; declare them explicitly",
    }
