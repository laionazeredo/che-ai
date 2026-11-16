"""The executable contract for manual test plans — scaffold, migrate, validate.

WHY THIS EXISTS
---------------
``manual_test_plan.md`` is the only artifact that reaches the person who verifies an increment, and
it feeds three consumers: the human (``che-manual-verification``), the agent
(``che-manual-test-executor``) and the PR body (``che-ship``). It used to be free prose, so the
executor had to infer intent from sentences and a missing locator only surfaced mid-run.

This module gives every acceptance criterion a machine-readable contract inside the same Markdown
file: the human reads the prose, the agent reads the block. ``sync`` scaffolds or migrates a plan,
``validate`` is the gate that keeps it executable.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It never writes contract *content*. No step, locator or assertion is inferred: ``sync`` inserts a
TODO skeleton and reports what is missing, so the gate stays honest instead of rubber-stamping.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from che_core.diagnostics import fail
from che_core.paths import compute_paths, output_path, write_file_atomic

DRIVERS = ("ui", "api", "db", "manual")
LANES = ("local", "preview", "remote")
SEVERITIES = ("BLOCKER", "HIGH", "MEDIUM", "LOW")
EVIDENCE_KINDS = ("screenshot", "video", "console_log", "network_log", "api_response", "log_file")
ACTIONS = ("goto", "click", "fill", "press", "wait", "assert", "api", "manual")

CONTRACT_KEYS = ("id", "driver", "lane", "base_url", "evidence", "severity", "steps", "notes")
STEP_KEYS = (
    "action",
    "url",
    "role",
    "name",
    "label",
    "text",
    "value",
    "key",
    "ms",
    "for_text",
    "expect_visible",
    "expect_hidden",
    "expect_url",
    "expect_api",
    "expect_status",
    "method",
    "path",
    "body",
    "instruction",
)
LOCATOR_KEYS = ("role", "name", "label", "text")
#: CSS and XPath are the habit this contract replaces: the executor resolves elements from the
#: accessibility tree, and a CSS path is both unreadable for the tester and brittle.
FORBIDDEN_LOCATOR_KEYS = ("css", "selector", "xpath")

PLACEHOLDER = "todo"
_WEASEL = re.compile(r"\b(correctly|as expected|properly|works|ok)\b", re.IGNORECASE)
_AC_HEADING = re.compile(r"^###\s+(AC-\d+)\s*:\s*(.*)$")
_CONTRACT_MARKER = re.compile(r"^#\s*---\s*executable contract\s*\((AC-\d+)\)\s*---\s*$")
_HEADING = re.compile(r"^#{1,3}\s")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


# --- Parsing -----------------------------------------------------------------


def blank_comments(text: str) -> str:
    """Replace HTML comments with blank space, preserving the line count.

    Commented-out examples must not count as acceptance criteria, and every index computed from
    the blanked text has to keep pointing at the same line of the original.
    """
    return _COMMENT.sub(lambda match: "\n" * match.group(0).count("\n"), text)


def _strip_comment(line: str) -> str:
    """Drop a trailing ``# comment`` that is not inside a quoted scalar."""
    quote: Optional[str] = None
    for index, char in enumerate(line):
        if quote is not None:
            if char == quote:
                quote = None
            continue
        if char in "\"'":
            quote = char
        elif char == "#" and (index == 0 or line[index - 1] in " \t"):
            return line[:index]
    return line


def _scalar(raw: str) -> Any:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [item.strip().strip("\"'") for item in inner.split(",") if item.strip()]
    return value


def parse_contract(block: str) -> Tuple[Dict[str, Any], List[str]]:
    """Parse the restricted YAML subset a contract block uses.

    Supported: ``key: value`` at column 0, ``steps:`` followed by ``- key: value`` items with
    ``  key: value`` continuation lines, quoted scalars, inline ``[a, b]`` lists and ``#`` comments.
    Deliberately not a YAML parser — the two-dependency budget does not buy one, and a strict
    subset with a precise error beats a permissive parser that accepts what the executor cannot run.

    Postcondition: returns ``(contract, problems)``; a malformed block never raises.
    """
    contract: Dict[str, Any] = {}
    problems: List[str] = []
    steps: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    in_steps = False

    for number, raw in enumerate(block.splitlines(), start=1):
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        stripped = line.strip()

        if stripped.startswith("- "):
            if not in_steps:
                problems.append(f"line {number}: a list item is only valid under `steps:`")
                continue
            key, separator, value = stripped[2:].partition(":")
            if not separator:
                problems.append(f"line {number}: step item needs `key: value`")
                current = None
                continue
            current = {key.strip(): _scalar(value)}
            steps.append(current)
            continue

        if line[:1] in (" ", "\t"):
            if current is None:
                problems.append(f"line {number}: indented key outside a step item")
                continue
            key, separator, value = stripped.partition(":")
            if not separator:
                problems.append(f"line {number}: step key needs `key: value`")
                continue
            current[key.strip()] = _scalar(value)
            continue

        key, separator, value = stripped.partition(":")
        if not separator:
            problems.append(f"line {number}: expected `key: value`")
            continue
        if key.strip() == "steps":
            in_steps = True
            current = None
            continue
        in_steps = False
        current = None
        contract[key.strip()] = _scalar(value)

    if steps:
        contract["steps"] = steps
    return contract, problems


def _fence_mask(lines: Sequence[str]) -> List[bool]:
    """True for every line inside a ``` fence, including the fence lines themselves.

    The contract marker starts with ``#``, which a heading scan would read as an H1 and use to end
    the AC section one line too early — hiding the very block it introduces.
    """
    mask: List[bool] = []
    inside = False
    for line in lines:
        if line.strip().startswith("```"):
            mask.append(True)
            inside = not inside
            continue
        mask.append(inside)
    return mask


def _ac_sections(lines: Sequence[str]) -> List[Dict[str, Any]]:
    """Every ``### AC-N:`` heading with its body span, in document order."""
    sections: List[Dict[str, Any]] = []
    mask = _fence_mask(lines)
    starts = [index for index, line in enumerate(lines) if not mask[index] and _AC_HEADING.match(line)]
    for start in starts:
        stop = len(lines)
        for index in range(start + 1, len(lines)):
            if not mask[index] and _HEADING.match(lines[index]):
                stop = index
                break
        match = _AC_HEADING.match(lines[start])
        sections.append(
            {
                "id": match.group(1),
                "title": match.group(2).strip(),
                "start": start,
                "stop": stop,
                "body": list(lines[start + 1 : stop]),
            }
        )
    return sections


def contract_blocks(body: Sequence[str]) -> List[List[str]]:
    """Inner lines of every fenced ``yaml`` block that opens with the contract marker."""
    blocks: List[List[str]] = []
    index = 0
    while index < len(body):
        if body[index].strip() != "```yaml":
            index += 1
            continue
        end = next((position for position in range(index + 1, len(body)) if body[position].strip() == "```"), None)
        if end is None:
            break
        inner = list(body[index + 1 : end])
        first = next((line.strip() for line in inner if line.strip()), "")
        if _CONTRACT_MARKER.match(first):
            blocks.append(inner)
        index = end + 1
    return blocks


# --- Validation --------------------------------------------------------------


def _check(checks: List[Dict[str, str]], check_id: str, status: str, detail: str = "") -> None:
    checks.append({"id": check_id, "status": status, "detail": detail})


def _is_placeholder(value: Any) -> bool:
    return isinstance(value, str) and PLACEHOLDER in value.lower()


def _locators(step: Dict[str, Any]) -> List[str]:
    return [key for key in LOCATOR_KEYS if str(step.get(key, "")).strip()]


def _step_problems(number: int, step: Any) -> List[str]:
    if not isinstance(step, dict):
        return [f"step {number}: not a mapping"]

    problems: List[str] = []
    unknown = sorted(set(step) - set(STEP_KEYS))
    if unknown:
        problems.append(f"step {number}: unknown key(s) {', '.join(unknown)}")

    action = str(step.get("action", "")).strip().lower()
    if not action or _is_placeholder(action):
        return problems + [f"step {number}: `action` is missing or TODO"]
    if action not in ACTIONS:
        return problems + [f"step {number}: action must be one of {', '.join(ACTIONS)}"]

    for key, value in step.items():
        if key != "action" and _is_placeholder(value):
            problems.append(f"step {number}: `{key}` is still TODO")

    forbidden = [key for key in FORBIDDEN_LOCATOR_KEYS if key in step]
    if forbidden:
        problems.append(
            f"step {number}: CSS/XPath locators are not allowed ({', '.join(forbidden)}) — use role+name, label or text"
        )

    if action in ("click", "fill") and not _locators(step):
        problems.append(f"step {number}: {action} needs role+name, label or text")
    if action == "fill" and not str(step.get("value", "")).strip():
        problems.append(f"step {number}: fill needs `value`")
    if action == "goto" and not str(step.get("url", "")).strip():
        problems.append(f"step {number}: goto needs `url`")
    if action == "press" and not str(step.get("key", "")).strip():
        problems.append(f"step {number}: press needs `key`")
    if action == "wait" and not (step.get("for_text") or step.get("ms")):
        problems.append(f"step {number}: wait needs `for_text` or `ms`")
    if action == "api":
        for key in ("method", "path", "expect_status"):
            if not str(step.get(key, "")).strip():
                problems.append(f"step {number}: api needs `{key}`")
    if action == "manual" and not str(step.get("instruction", "")).strip():
        problems.append(f"step {number}: manual needs `instruction`")
    if action == "assert":
        expected = [
            key
            for key in ("expect_visible", "expect_hidden", "expect_url", "expect_api")
            if str(step.get(key, "")).strip()
        ]
        if not expected:
            problems.append(f"step {number}: assert needs at least one expect_* key")
        for key in expected:
            if _WEASEL.search(str(step[key])):
                problems.append(f"step {number}: `{key}` uses a weasel word — write the literal text")

    return problems


def _contract_problems(ac_id: str, contract: Dict[str, Any]) -> List[str]:
    problems: List[str] = []

    unknown = sorted(set(contract) - set(CONTRACT_KEYS))
    if unknown:
        problems.append(f"unknown key(s): {', '.join(unknown)}")

    for key in ("id", "driver", "lane", "evidence", "severity", "steps"):
        if key not in contract:
            problems.append(f"missing `{key}`")

    if str(contract.get("id", "")).strip() and contract["id"] != ac_id:
        problems.append(f"`id: {contract['id']}` does not match the heading {ac_id}")

    driver = str(contract.get("driver", "")).strip().lower()
    if driver and driver != PLACEHOLDER and driver not in DRIVERS:
        problems.append(f"driver must be one of {', '.join(DRIVERS)}")
    lane = str(contract.get("lane", "")).strip().lower()
    if lane and lane != PLACEHOLDER and lane not in LANES:
        problems.append(f"lane must be one of {', '.join(LANES)}")
    severity = str(contract.get("severity", "")).strip().upper()
    if severity and severity != PLACEHOLDER.upper() and severity not in SEVERITIES:
        problems.append(f"severity must be one of {', '.join(SEVERITIES)}")

    evidence = contract.get("evidence")
    if isinstance(evidence, str):
        evidence = [evidence] if evidence.strip() else []
    if not _is_placeholder(contract.get("evidence")):
        for kind in evidence or []:
            if str(kind).strip().lower() not in EVIDENCE_KINDS:
                problems.append(f"evidence `{kind}` is not one of {', '.join(EVIDENCE_KINDS)}")

    for key, value in contract.items():
        if key != "steps" and _is_placeholder(value):
            problems.append(f"`{key}` is still TODO")

    if driver == "ui" and not str(contract.get("base_url", "")).strip():
        problems.append("`base_url` is required for driver=ui")

    steps = contract.get("steps")
    if not isinstance(steps, list) or not steps:
        return problems + ["`steps` needs at least one item"]

    for number, step in enumerate(steps, start=1):
        problems.extend(_step_problems(number, step))

    actions = [str(step.get("action", "")).strip().lower() for step in steps if isinstance(step, dict)]
    browser_actions = {"goto", "click", "fill", "press", "wait", "assert"}
    if driver == "manual" and any(action != "manual" for action in actions):
        problems.append("driver=manual requires every step to be `action: manual`")
    if driver == "api" and "api" not in actions:
        problems.append("driver=api requires at least one `action: api` step")
    if driver == "ui" and not any(action in browser_actions for action in actions):
        problems.append("driver=ui requires at least one browser step")

    return problems


def validate_plan(path: str) -> Dict[str, Any]:
    """Run the MP-checks on one manual test plan.

    Preconditions: ``path`` points at a readable Markdown file.
    Postcondition: one entry per AC plus the document-level checks; a failed check never raises.
    """
    plan_path = Path(path).expanduser()
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError as exc:
        fail("UNREADABLE_INPUT", path=str(plan_path), detail=str(exc))

    lines = blank_comments(text).splitlines()
    sections = _ac_sections(lines)
    checks: List[Dict[str, str]] = []

    if not sections:
        _check(checks, "MP1", "fail", "no `### AC-<N>:` headings")
    else:
        _check(checks, "MP1", "pass", f"{len(sections)} AC(s)")

    seen: Dict[str, int] = {}
    for section in sections:
        ac_id = section["id"]
        seen[ac_id] = seen.get(ac_id, 0) + 1
        if seen[ac_id] > 1:
            _check(checks, "MP2", "fail", f"{ac_id} is declared more than once")
            continue
        if not section["title"] or _is_placeholder(section["title"]):
            _check(checks, "MP2", "fail", f"{ac_id}: heading title is empty or a placeholder")

        blocks = contract_blocks(section["body"])
        if not blocks:
            _check(checks, "MP3", "fail", f"{ac_id}: no ```yaml executable contract block")
            continue
        if len(blocks) > 1:
            _check(checks, "MP3", "fail", f"{ac_id}: {len(blocks)} contract blocks, expected exactly 1")
            continue

        contract, problems = parse_contract("\n".join(blocks[0]))
        if problems:
            _check(checks, "MP4", "fail", f"{ac_id}: {'; '.join(problems)}")
            continue

        problems = _contract_problems(ac_id, contract)
        if problems:
            _check(checks, "MP5", "fail", f"{ac_id}: {'; '.join(problems)}")
        else:
            _check(checks, "MP5", "pass", f"{ac_id}: {contract['driver']}/{contract['lane']}")

    failures = [f"{entry['id']}: {entry['detail']}" for entry in checks if entry["status"] == "fail"]
    return {
        "ok": not failures,
        "path": str(plan_path),
        "acs": len(sections),
        "checks": checks,
        "failures": failures,
    }


# --- Scaffolding -------------------------------------------------------------


def _skeleton_lines(ac_id: str) -> List[str]:
    return [
        "```yaml",
        f"# --- executable contract ({ac_id}) ---",
        f"id: {ac_id}",
        "driver: TODO          # ui | api | db | manual",
        "lane: TODO            # local | preview | remote",
        "base_url: TODO        # absolute URL; required for driver=ui",
        "evidence: TODO        # screenshot | video | console_log | network_log | api_response | log_file",
        "severity: TODO        # BLOCKER | HIGH | MEDIUM | LOW",
        "steps:",
        "  - action: TODO      # goto | click | fill | press | wait | assert | api | manual",
        "```",
    ]


def _new_plan_lines(worktree_root: str) -> List[str]:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return [
        "# Manual Test Plan — TODO: task or feature slug",
        "",
        "> Written by `che manual-plan sync`. The prose is for the human; each ```yaml block is the",
        "> executable contract read by `che-manual-test-executor` and rendered by",
        "> `che-manual-verification`. Run `che manual-plan validate <path>` before shipping.",
        "",
        f"- **Created:** {stamp}",
        f"- **Worktree:** `{worktree_root}`",
        "- **Branch / PR:** TODO",
        "- **Requires access to:** TODO",
        "",
        "## 0. Environment Setup — Preconditions",
        "",
        "```bash",
        "# TODO: exact commands, in order. Environment variables by NAME only — never values.",
        "```",
        "",
        "### Test accounts / test data",
        "",
        "- TODO: role or persona — never the password",
        "",
        "## 1. Per Acceptance Criterion — Scenario Test Cases",
        "",
        "### AC-1: TODO — the user-visible behaviour",
        "",
        "**GIVEN:** TODO",
        "**WHEN:** TODO",
        "**THEN:** TODO — the exact text or state the tester must observe",
        "",
        "#### Manual Steps",
        "",
        "1. TODO",
        "",
        *_skeleton_lines("AC-1"),
        "",
        "#### Severity if FAILS",
        "",
        "- TODO: BLOCKER / HIGH / MEDIUM / LOW",
        "",
        "## 2. Smoke Test Checklist",
        "",
        "| # | Area | Check | Expected | PASS / FAIL | Notes |",
        "|---|---|---|---|---|---|",
        "| S1 | Build | `TODO` | 0 errors | | |",
        "| S2 | Login | TODO | lands on the dashboard | | |",
        "| S3 | Navigation | TODO | no 500 / blank page | | |",
        "| S4 | Logs | TODO | no CRITICAL / ERROR | | |",
        "",
        "## 3. Rollback Plan",
        "",
        "TODO: how to undo what this verification created.",
        "",
    ]


def _candidate_plans(workspace: Path) -> List[Path]:
    found: List[Path] = []
    for root in (workspace / "qa", workspace):
        if not root.is_dir():
            continue
        for path in root.rglob("*.md"):
            name = path.name.lower().replace("_", "-")
            if "manual-test-plan" in name or "manual-plan" in name:
                found.append(path)
    return found


def resolve_plan_path(
    worktree_root: str,
    session_id: str,
    explicit_path: Optional[str] = None,
    slug: str = "manual-plan",
) -> Tuple[Path, bool]:
    """The plan to update: explicit path, else the newest known plan, else a fresh canonical path.

    Postcondition: returns ``(path, exists)``; ``exists`` is False only when the path was just
    resolved for creation (nothing has been written yet).
    """
    if explicit_path:
        path = Path(explicit_path).expanduser()
        return path, path.is_file()

    paths = compute_paths(worktree_root, session_id)
    workspace = Path(paths["CHE_WORKSPACE_SHARED"])
    candidates = _candidate_plans(workspace)
    if candidates:
        newest = max(candidates, key=lambda candidate: candidate.stat().st_mtime)
        return newest, True

    target = output_path(
        "qa",
        "manual-test-plan",
        slug,
        "workspace",
        "md",
        worktree_root=worktree_root,
        root=paths["CHE_WORKSPACE_SHARED"],
    )
    return Path(target), False


def sync_plan(
    worktree_root: str,
    session_id: str,
    explicit_path: Optional[str] = None,
    slug: str = "manual-plan",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Create the plan if absent, or insert the missing contract skeletons if present.

    Preconditions: ``worktree_root`` is a bound worktree (a fresh path needs its storage roots).
    Postcondition: existing prose is preserved byte-for-byte; only TODO skeletons are added, and
    a second run on the same file reports ``changed: false``.
    """
    path, exists = resolve_plan_path(worktree_root, session_id, explicit_path, slug)

    if not exists:
        content = "\n".join(_new_plan_lines(worktree_root))
        if not dry_run:
            write_file_atomic(str(path), content.encode("utf-8"), worktree_root=worktree_root)
        return {"path": str(path), "created": True, "inserted": ["AC-1"], "acs": 1, "changed": True, "dry_run": dry_run}

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        fail("UNREADABLE_INPUT", path=str(path), detail=str(exc))

    lines = text.splitlines()
    sections = _ac_sections(blank_comments(text).splitlines())
    missing = {section["start"]: section["id"] for section in sections if not contract_blocks(section["body"])}

    output: List[str] = []
    for index, line in enumerate(lines):
        output.append(line)
        if index in missing:
            output.append("")
            output.extend(_skeleton_lines(missing[index]))
            output.append("")

    changed = bool(missing)
    if changed and not dry_run:
        write_file_atomic(str(path), "\n".join(output).encode("utf-8"), worktree_root=worktree_root)

    return {
        "path": str(path),
        "created": False,
        "inserted": list(missing.values()),
        "acs": len(sections),
        "changed": changed,
        "dry_run": dry_run,
    }
