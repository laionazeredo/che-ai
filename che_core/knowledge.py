"""Project knowledge — the durable, agent-maintained record of how a project works.

Two artifact families live under the project folder (never the user worktree):
``glossary.md`` (vocabulary) and ``<domain>/conventions.md`` (observed practice).
This module owns the canonical topic taxonomy, the Markdown (de)serialisation, the
scaffold/read verbs and the change-set engine behind ``che knowledge apply``.
"""

from __future__ import annotations

import difflib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from che_core.diagnostics import fail
from che_core.paths import assert_outside_worktree, write_file_atomic
from che_core.project_layout import (
    DOMAIN_SLUGS,
    get_domain_dir,
    get_project_dir,
    normalise_domain,
    validate_slug,
)

CONVENTIONS_FILENAME = "conventions.md"
GLOSSARY_FILENAME = "glossary.md"

# Canonical section skeleton, identical for every domain. Single source of truth: the
# scaffolder writes exactly these headings and the reader keys on them.
UNIVERSAL_SECTIONS: Tuple[str, ...] = (
    "Scope & Precedence",
    "Vocabulary",
    "Artifacts & Deliverables",
    "Naming & Structure",
    "Authoring Rules",
    "Quality Bar & Definition of Done",
    "Review & Feedback",
    "Change & Approval",
    "Tooling & Automation",
    "Evidence & Sources",
    "Gaps & Open Questions",
)

# Domain-specific §5 sub-topics. The extension point: a new domain is one new key here.
CONVENTION_TOPICS: Dict[str, Tuple[str, ...]] = {
    "engineering": (
        "Code Style",
        "Language & Typing",
        "Comments & Documentation",
        "Testing",
        "Error Handling & Logging",
        "Architecture & Layering",
        "Dependencies & Build",
        "Commits & Pull Requests",
        "Branching & Merge",
        "CI Gates",
        "Security & Secrets",
        "Observability",
    ),
    "devops": (
        "Environments & Promotion",
        "Infrastructure as Code",
        "Containers & Orchestration",
        "Pipelines & Required Checks",
        "Deploy & Rollback",
        "Secrets Management",
        "Observability & Alerting",
        "Incident Response & Runbooks",
        "Cost & Tagging",
    ),
    "product": (
        "Requirement Format",
        "Ticket Conventions",
        "Prioritisation",
        "Definition of Ready & Done",
        "Metrics & Instrumentation",
        "Release & Communication",
    ),
    "business": (
        "Pricing & Commercial Rules",
        "Compliance & Regulatory",
        "Contracts & SLAs",
        "Financial Reporting",
        "Vendor & Partner",
    ),
    "design": (
        "Design System & Tokens",
        "Component & Token Naming",
        "Accessibility",
        "Layout & Spacing",
        "Typography & Colour",
        "Iconography & Assets",
        "Motion & Interaction",
        "Handoff Contract",
        "Localisation",
    ),
    "copywriting": (
        "Tone of Voice",
        "Register & Spelling",
        "Microcopy Patterns",
        "SEO & Length Constraints",
        "Legal & Disclaimer Wording",
    ),
    "social": (
        "Channels & Cadence",
        "Post Formats",
        "Brand Voice per Channel",
        "Hashtags & Mentions",
    ),
    "seo-analytics": (
        "Measurement Plan",
        "Event Taxonomy",
        "URL & Slug Conventions",
        "Metadata Conventions",
        "KPI Definitions",
    ),
}

GLOSSARY_COLUMNS: Tuple[str, ...] = ("Term", "Definition", "Aliases", "Domain", "Source", "Updated")

_SECTION_RE = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", re.M)
_TOPIC_RE = re.compile(r"^###\s+5\.\d+\s+(.+?)\s*$", re.M)
_CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")


def _escape_cell(value: str) -> str:
    """One Markdown table cell: whitespace collapsed, `|` escaped so the row round-trips."""
    return " ".join(str(value).split()).replace("|", "\\|")


def _unescape_cell(value: str) -> str:
    return value.replace("\\|", "|")


def normalise_key(text: str) -> str:
    """Case-insensitive identity used for terms and topic titles."""
    return " ".join(text.split()).casefold()


def _require_project(project_slug: str) -> Path:
    """Precondition: a valid, existing project slug. Returns its project folder."""
    try:
        validate_slug(project_slug, label="project_slug")
    except ValueError as exc:
        fail("INVALID_SLUG", exc=str(exc))
    project_dir = get_project_dir(project_slug)
    if not project_dir.is_dir():
        fail("UNKNOWN_PROJECT", project_slug=project_slug)
    return project_dir


def _require_domain(domain: str) -> str:
    """Precondition: a canonical domain slug. Aliases are normalised; unknown ones fail."""
    try:
        return normalise_domain(domain)
    except ValueError as exc:
        fail("INVALID_DOMAIN", exc=str(exc))


def _display(domain: str) -> str:
    return domain.replace("-", " ").title()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def conventions_path(project_slug: str, domain: str) -> Path:
    """``<project>/<domain>/conventions.md`` — always outside the user worktree."""
    _require_project(project_slug)
    return get_domain_dir(project_slug, _require_domain(domain)) / CONVENTIONS_FILENAME


def glossary_path(project_slug: str) -> Path:
    """``<project>/glossary.md`` — always outside the user worktree."""
    return _require_project(project_slug) / GLOSSARY_FILENAME


# --- conventions document --------------------------------------------------------


def parse_sections(text: str) -> Dict[str, str]:
    """Map ``N. Title`` -> body. A duplicate heading is impossible in correct code → crash."""
    sections: Dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(text))
    for index, match in enumerate(matches):
        key = f"{match.group(1)}. {match.group(2).strip()}"
        if key in sections:
            raise AssertionError(f"duplicate section heading {key!r} in knowledge document")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[key] = text[match.end() : end].strip()
    return sections


def parse_topics(body: str) -> List[Tuple[str, str]]:
    """Ordered ``(title, body)`` pairs for the ``### 5.N Title`` headings inside §5."""
    matches = list(_TOPIC_RE.finditer(body))
    topics: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        key = normalise_key(title)
        if key in seen:
            raise AssertionError(f"duplicate topic {title!r} in knowledge document")
        seen.add(key)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        topics.append((title, body[match.end() : end].strip()))
    return topics


def render_topics(topics: Sequence[Tuple[str, str]]) -> str:
    """Render the §5 sub-topics, renumbering sequentially in the given order."""
    blocks = []
    for index, (title, body) in enumerate(topics, start=1):
        heading = f"### 5.{index} {title}"
        blocks.append(f"{heading}\n\n{body.strip()}" if body.strip() else heading)
    return "\n\n".join(blocks)


def render_conventions(project_slug: str, domain: str, sections: Dict[str, str]) -> str:
    """Render a full conventions document from its section map (deterministic bytes)."""
    canonical = _require_domain(domain)
    lines: List[str] = [
        f"# {_display(canonical)} Conventions — {project_slug}",
        "",
        "> Maintained by /che-knowledge. Do not edit by hand; use `che knowledge apply`.",
        "> Evidence-based; when the host repo's own rules differ, the repo wins.",
        "",
    ]
    for index, title in enumerate(UNIVERSAL_SECTIONS, start=1):
        body = sections.get(f"{index}. {title}", "").strip()
        lines += [f"## {index}. {title}", ""]
        if body:
            lines += [body, ""]
    return "\n".join(lines).rstrip("\n") + "\n"


def render_conventions_skeleton(project_slug: str, domain: str) -> str:
    """The canonical empty document for one domain: 11 sections, §5 pre-seeded with topics."""
    canonical = _require_domain(domain)
    sections = {f"{index}. {title}": "" for index, title in enumerate(UNIVERSAL_SECTIONS, start=1)}
    sections["5. Authoring Rules"] = render_topics([(topic, "") for topic in CONVENTION_TOPICS[canonical]])
    return render_conventions(project_slug, canonical, sections)


# --- glossary document -----------------------------------------------------------


def parse_glossary(text: str) -> Dict[str, Dict[str, str]]:
    """Map normalised term -> row. A duplicate term is impossible in correct code → crash."""
    terms: Dict[str, Dict[str, str]] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [_unescape_cell(cell.strip()) for cell in _CELL_SPLIT_RE.split(stripped)[1:-1]]
        if not any(cells) or cells[0] == GLOSSARY_COLUMNS[0]:
            continue
        if set("".join(cells)) <= {"-", ":"}:
            continue
        if len(cells) != len(GLOSSARY_COLUMNS):
            fail(
                "KNOWLEDGE_INPUT_INVALID",
                detail=f"glossary row has {len(cells)} cells, expected {len(GLOSSARY_COLUMNS)}: {stripped!r}",
            )
        term = cells[0]
        key = normalise_key(term)
        if key in terms:
            raise AssertionError(f"duplicate glossary term {term!r}")
        terms[key] = dict(zip(GLOSSARY_COLUMNS, cells))
    return terms


def render_glossary(project_slug: str, terms: Dict[str, Dict[str, str]]) -> str:
    """Render the glossary, terms sorted by normalised key (deterministic bytes)."""
    lines = [
        f"# Glossary — {project_slug}",
        "",
        "> Maintained by /che-knowledge. Do not edit by hand; use `che knowledge apply`.",
        "",
        "| " + " | ".join(GLOSSARY_COLUMNS) + " |",
        "|" + "|".join("---" for _ in GLOSSARY_COLUMNS) + "|",
    ]
    for key in sorted(terms):
        row = terms[key]
        lines.append("| " + " | ".join(_escape_cell(row.get(column, "")) for column in GLOSSARY_COLUMNS) + " |")
    return "\n".join(lines) + "\n"


# --- verbs -----------------------------------------------------------------------


def scaffold_conventions(project_slug: str, domain: str) -> Dict[str, object]:
    """Create ``<domain>/conventions.md`` from the skeleton. Idempotent — no rewrite."""
    path = conventions_path(project_slug, domain)
    created = not path.is_file()
    if created:
        assert_outside_worktree(str(path), os.environ.get("WORKTREE_ROOT", ""), "knowledge conventions")
        write_file_atomic(str(path), render_conventions_skeleton(project_slug, domain).encode("utf-8"))
    return {
        "path": str(path),
        "domain": _require_domain(domain),
        "created": created,
        "sections": len(UNIVERSAL_SECTIONS),
    }


def show_knowledge(project_slug: str, domain: Optional[str] = None) -> Dict[str, object]:
    """Read the project's knowledge. Absent files degrade to empty; no file is created."""
    _require_project(project_slug)
    if domain is not None:
        canonical = _require_domain(domain)
        path = get_domain_dir(project_slug, canonical) / CONVENTIONS_FILENAME
        text = _read(path)
        return {
            "project": project_slug,
            "domain": canonical,
            "path": str(path),
            "exists": path.is_file(),
            "content": text,
            "sections": parse_sections(text),
        }
    glossary = _read(glossary_path(project_slug))
    domains = [
        {"domain": slug, "path": str(get_domain_dir(project_slug, slug) / CONVENTIONS_FILENAME)}
        for slug in DOMAIN_SLUGS
        if (get_domain_dir(project_slug, slug) / CONVENTIONS_FILENAME).is_file()
    ]
    return {"project": project_slug, "domains": domains, "glossary": parse_glossary(glossary)}


def render_diff(label: str, old: str, new: str) -> str:
    """Unified diff of a previewed change. Empty when the change set is a no-op."""
    if old == new:
        return ""
    return (
        "\n".join(
            difflib.unified_diff(
                old.splitlines(),
                new.splitlines(),
                fromfile=f"a/{label}",
                tofile=f"b/{label}",
                lineterm="",
            )
        )
        + "\n"
    )


def _require_str(op: Dict[str, object], field: str) -> str:
    value = op.get(field)
    if not isinstance(value, str) or not value.strip():
        fail("KNOWLEDGE_INPUT_INVALID", detail=f"operation field {field!r} must be a non-empty string")
    return value.strip()


def _aliases(op: Dict[str, object]) -> str:
    value = op.get("aliases", [])
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, list):
        fail("KNOWLEDGE_INPUT_INVALID", detail="'aliases' must be a list of strings or a string")
    return ", ".join(str(item).strip() for item in value if str(item).strip())


def _apply_glossary_op(terms: Dict[str, Dict[str, str]], op: object) -> None:
    if not isinstance(op, dict):
        fail("KNOWLEDGE_INPUT_INVALID", detail="each glossary operation must be an object")
    kind = op.get("op")
    term = _require_str(op, "term")
    key = normalise_key(term)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if kind == "insert":
        if key in terms:
            fail("KNOWLEDGE_CONFLICT", detail=f"term {term!r} already exists; use 'update'")
        terms[key] = {
            "Term": term,
            "Definition": _require_str(op, "definition"),
            "Aliases": _aliases(op),
            "Domain": str(op.get("domain", "")).strip(),
            "Source": str(op.get("source", "")).strip(),
            "Updated": today,
        }
    elif kind == "update":
        if key not in terms:
            fail("KNOWLEDGE_CONFLICT", detail=f"term {term!r} does not exist; use 'insert'")
        row = terms[key]
        row["Definition"] = str(op.get("definition", row["Definition"])).strip() or row["Definition"]
        if "aliases" in op:
            row["Aliases"] = _aliases(op)
        for column in ("Domain", "Source"):
            if column.lower() in op:
                row[column] = str(op[column.lower()]).strip()
        row["Updated"] = today
    elif kind == "delete":
        if key not in terms:
            fail("KNOWLEDGE_CONFLICT", detail=f"term {term!r} does not exist; nothing to delete")
        del terms[key]
    else:
        fail("KNOWLEDGE_INPUT_INVALID", detail=f"unknown glossary op {kind!r}")


def _apply_conventions_op(sections: Dict[str, str], op: object) -> None:
    if not isinstance(op, dict):
        fail("KNOWLEDGE_INPUT_INVALID", detail="each conventions operation must be an object")
    kind = op.get("op")
    topic = _require_str(op, "topic")
    body = _require_str(op, "body")
    key = normalise_key(topic)
    topics = parse_topics(sections.get("5. Authoring Rules", ""))
    index = next((i for i, (title, _) in enumerate(topics) if normalise_key(title) == key), None)
    if kind == "update_topic":
        if index is None:
            fail("KNOWLEDGE_CONFLICT", detail=f"topic {topic!r} not found in this domain's conventions")
        topics[index] = (topics[index][0], body)
    elif kind == "insert_topic":
        if index is not None:
            fail("KNOWLEDGE_CONFLICT", detail=f"topic {topic!r} already exists; use 'update_topic'")
        topics.append((topic, body))
    else:
        fail("KNOWLEDGE_INPUT_INVALID", detail=f"unknown conventions op {kind!r}")
    sections["5. Authoring Rules"] = render_topics(topics)


def apply_ops(project_slug: str, ops: object, *, dry_run: bool = True) -> Dict[str, object]:
    """Validate a change set, then preview (dry-run) or write it. Fails closed: nothing is
    written unless every operation validates against the current documents."""
    _require_project(project_slug)
    if not isinstance(ops, dict):
        fail("KNOWLEDGE_INPUT_INVALID", detail="ops must be a JSON object")
    glossary_ops = ops.get("glossary", [])
    conventions_ops = ops.get("conventions", [])
    if not isinstance(glossary_ops, list) or not isinstance(conventions_ops, list):
        fail("KNOWLEDGE_INPUT_INVALID", detail="'glossary' and 'conventions' must each be a list")
    if not glossary_ops and not conventions_ops:
        fail("KNOWLEDGE_INPUT_INVALID", detail="the change set is empty")

    pending: List[Tuple[Path, str, str, str]] = []

    if glossary_ops:
        path = glossary_path(project_slug)
        old = _read(path) or render_glossary(project_slug, {})
        terms = parse_glossary(old)
        for op in glossary_ops:
            _apply_glossary_op(terms, op)
        pending.append((path, "glossary.md", old, render_glossary(project_slug, terms)))

    domains: List[str] = []
    for op in conventions_ops:
        if not isinstance(op, dict):
            fail("KNOWLEDGE_INPUT_INVALID", detail="each conventions operation must be an object")
        canonical = _require_domain(str(op.get("domain", "")))
        if canonical not in domains:
            domains.append(canonical)
    for domain in domains:
        path = conventions_path(project_slug, domain)
        if not path.is_file():
            fail(
                "KNOWLEDGE_CONFLICT",
                detail=f"no conventions document for domain {domain!r}; run `che knowledge scaffold` first",
            )
        old = _read(path)
        sections = parse_sections(old)
        for op in conventions_ops:
            if _require_domain(str(op.get("domain", ""))) == domain:
                _apply_conventions_op(sections, op)
        pending.append((path, f"{domain}/conventions.md", old, render_conventions(project_slug, domain, sections)))

    changes = [
        {"target": label, "path": str(path), "diff": render_diff(label, old, new)}
        for path, label, old, new in pending
        if old != new
    ]
    if not changes:
        fail("KNOWLEDGE_INPUT_INVALID", detail="the change set would not modify any document")

    if not dry_run:
        for path, _label, _old, new in pending:
            assert_outside_worktree(str(path), os.environ.get("WORKTREE_ROOT", ""), "knowledge apply")
            write_file_atomic(str(path), new.encode("utf-8"))

    return {"applied": not dry_run, "dry_run": dry_run, "changes": changes}
