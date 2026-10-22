"""Review rule resolution — one deterministic answer to "which rules apply to this diff?".

WHY THIS EXISTS
---------------
A reviewer that reads every rule file it can find has no way to decide between two project rules
that contradict each other, so the verdict ends up depending on the order the files were read.
This module removes that choice from the reviewer: it discovers the sources, classifies each one
into an authority layer, drops the rules that do not speak about the changed files, and resolves
contradictions with a fixed precedence. What it cannot resolve is reported as a conflict and
capped, never silently picked.

LAYERS (HIGH -> LOW)
--------------------
0 hard-floor      Che invariants (security, storage boundary, worktree binding). Never loosened.
1 repo-explicit   AGENTS.md / CLAUDE.md / .claude|.agents|.cursor rules — the project's written law.
2 machine         eslint / biome / tsconfig / CI: already enforced by tooling, never re-flagged.
3 project-memory  project_profile / architecture / <domain>/conventions — derived, so layer 1 wins.

WHAT THIS MODULE DOES NOT DO
----------------------------
It does not read the diff, rank findings or decide a verdict. It answers one question with data,
so the same diff and the same rule set always produce the same review.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Sequence, Tuple

from che_core.diagnostics import fail
from che_core.project_layout import (
    get_domain_dir,
    get_project_doc,
    hermetic_git_env,
    normalise_domain,
    project_exists,
    validate_slug,
)

#: Authority rank. A lower number wins every contradiction.
LAYER_RANK: Dict[str, int] = {
    "hard-floor": 0,
    "repo-explicit": 1,
    "machine": 2,
    "project-memory": 3,
}

SEVERITY_RANK: Dict[str, int] = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

#: Che invariants. They exist without any project file, and no project rule may loosen them.
HARD_FLOOR: Tuple[Dict[str, str], ...] = (
    {
        "id": "hard-floor.security",
        "topic": "security",
        "title": "Security and PII",
        "statement": "Secrets, credentials, raw PII and tokens must never be logged, persisted or committed.",
    },
    {
        "id": "hard-floor.storage-boundary",
        "topic": "storage-boundary",
        "title": "Storage boundary",
        "statement": "Nothing Che writes may land inside the user's repository.",
    },
    {
        "id": "hard-floor.worktree-binding",
        "topic": "worktree-binding",
        "title": "Worktree binding",
        "statement": "A review runs against the worktree the session is bound to; a mismatch blocks.",
    },
)

DEFAULT_PARAMS: Dict[str, Any] = {
    "min_severity": "LOW",
    "blocking": ["CRITICAL", "HIGH"],
    "ignore_paths": [],
    "risk_paths": [],
    "categories": [0, 1, 2, 3, 4, 5, 6, 7, 8],
    "max_findings": 40,
    "max_rules": 120,
}

REPO_DOCS: Tuple[str, ...] = ("AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md", ".github/copilot-instructions.md")
REPO_RULE_DIRS: Tuple[str, ...] = (".claude/rules", ".agents/rules", ".cursor/rules")
MACHINE_FILES: Tuple[str, ...] = (
    "eslint.config.js",
    "eslint.config.mjs",
    "biome.json",
    "tsconfig.json",
    "ruff.toml",
    "pyproject.toml",
    ".pre-commit-config.yaml",
)

#: Closed topic vocabulary. Conflicts are only claimed inside these buckets, so a false
#: contradiction between two unrelated sections is not possible.
TOPIC_PATTERNS: Dict[str, str] = {
    "security": r"\b(security|auth|authz|permission|permissions|secret|secrets|token|tokens|pii|rls)\b",
    "layering": (
        r"\b(layer|layers|layering|router|routers|service|services|repository|repositories"
        r"|hexagonal|onion|boundary|boundaries)\b"
    ),
    "migrations": r"\b(migration|migrations|migrate|migrates|schema change|ddl)\b",
    "testing": r"\b(test|tests|testing|coverage|e2e|unit|units|spec|specs)\b",
    "logging": r"\b(log|logs|logging|observability|telemetry|metric|metrics|trace|traces)\b",
    "typing": r"\b(typescript|typing|type-safe|strict)\b",
    "errors": r"\b(error handling|errors|exception|exceptions|result type|throw|throws)\b",
    "dependencies": r"\b(dependency|dependencies|package|packages|import|imports|library|libraries)\b",
    "commits": r"\b(commit|commits|pull request|pull requests|branch|branches)\b",
    "naming": r"\b(naming|nomenclature)\b",
    "ui": r"\b(ui|component|components|react|selector|selectors|testid|css|tailwind)\b",
    "data": r"\b(database|databases|query|queries|index|indices|orm|sql)\b",
}

IGNORED_SECTIONS = frozenset(
    {"table of contents", "contents", "evidence & sources", "evidence and sources", "gaps & open questions"}
)

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{2,4})\s+(.+?)\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^[ \t]{0,3}(?:[-*+]|\d+[.)])\s+(.+)$", re.MULTILINE)
_NEGATIVE_RE = re.compile(r"\b(never|must not|mustn't|do not|don't|prohibited|forbidden|no longer)\b", re.I)
_POSITIVE_RE = re.compile(
    r"\b(must|always|required|mandatory|shall|should|avoid|minimi[sz]e|prefer|ensure|keep)\b", re.I
)
_CRITICAL_RE = re.compile(r"\b(critical|hard stop|non-negotiable)\b", re.I)
_HIGH_RE = re.compile(r"\b(must|never|mandatory|required|prohibited|forbidden)\b", re.I)
_MEDIUM_RE = re.compile(r"\b(should|prefer|preferred|recommended|avoid)\b", re.I)
_WORD_RE = re.compile(r"[a-z][a-z-]{2,}")

#: Ceiling on reported contradictions, so a pathological rule set cannot flood the report.
MAX_CONFLICTS = 50

#: A rule longer than this bundles several statements, so it is not compared as one subject.
MAX_SUBJECT_CHARS = 200

_STOPWORDS = frozenset(
    "the a an and or of to in on for with without is are be been being that this these those it its as at by "
    "from into not no must never always should avoid prefer ensure keep use used using all any each every per "
    "do does did can may will would more than then when where which who whom what how".split()
)


@dataclass(frozen=True)
class RuleCard:
    """One section of one rule file, reduced to the fields a review can act on."""

    id: str
    layer: str
    source: str
    line: int
    title: str
    statement: str
    topics: Tuple[str, ...]
    polarity: str
    severity: str
    scope: Tuple[str, ...]
    always: bool


# ---------------------------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------------------------


def resolve_review_rules(
    worktree_root: str,
    project: Optional[str] = None,
    changed: Optional[Sequence[str]] = None,
    domain: str = "engineering",
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Resolve the rules that apply to ``changed`` inside ``worktree_root``.

    Preconditions: ``worktree_root`` is an existing directory; ``project``, when given, exists;
    ``domain`` is a canonical domain or an accepted alias. ``changed`` defaults to the worktree's
    uncommitted paths, and an empty result means "review the whole repository".

    Postcondition: the returned mapping carries the applicable rules, the hard floor, every
    contradiction with its resolution, and the review parameters that produced the selection.
    """
    root = _validated_root(worktree_root)
    slug = _validated_project(project)
    domain_slug = _validated_domain(domain)
    params = _merged_params(slug, overrides)

    if changed is None:
        changed = _git_changed(root)
    changed_files = sorted({_normalise_path(item) for item in changed if item})
    scope_mode = "diff" if changed_files else "all"

    cards: List[RuleCard] = []
    ignored: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []

    for source in _discover(root, slug, domain_slug, changed_files):
        if source["kind"] == "machine-config":
            sources.append(_source_row(source, 0, True))
            continue
        applicable: List[RuleCard] = []
        for card in _cards_from_source(source):
            if scope_mode == "all" or card.always or _matches_any(changed_files, card.scope):
                applicable.append(card)
            else:
                ignored.append(
                    {"path": card.source, "title": card.title, "reason": "path-scoped: no changed file matches"}
                )
        sources.append(_source_row(source, len(applicable), bool(applicable)))
        cards.extend(applicable)

    conflicts, drift, superseded, conflicted = _resolve_conflicts(cards)

    kept: List[Dict[str, Any]] = []
    for card in cards:
        effective = _capped(card.severity) if card.id in conflicted else card.severity
        if SEVERITY_RANK[effective] < SEVERITY_RANK[params["min_severity"]]:
            ignored.append({"path": card.source, "title": card.title, "reason": "below min_severity"})
            continue
        kept.append(_card_row(card, effective, superseded.get(card.id), card.id in conflicted))

    kept.sort(
        key=lambda row: (
            LAYER_RANK[row["layer"]],
            -SEVERITY_RANK[row["effective_severity"]],
            row["source"],
            row["line"],
        )
    )
    available = len(kept)
    limit = int(params["max_rules"])
    if available > limit:
        for row in kept[limit:]:
            ignored.append({"path": row["source"], "title": row["title"], "reason": "outside budget"})
        kept = kept[:limit]

    return {
        "worktree": str(root),
        "project": slug,
        "domain": domain_slug,
        "changed_files": changed_files,
        "scope_mode": scope_mode,
        "params": params,
        "hard_floor": [_hard_floor_row(entry) for entry in HARD_FLOOR],
        "rules": kept,
        "conflicts": conflicts,
        "drift": drift,
        "sources": sources,
        "ignored": ignored,
        "budget": {
            "rules_available": available,
            "rules_returned": len(kept),
            "max_rules": limit,
            "approx_tokens": sum(len(row["title"]) + len(row["statement"]) for row in kept) // 4,
            "truncated": available > limit,
        },
    }


# ---------------------------------------------------------------------------------------------
# Validation (fail fast at the boundary)
# ---------------------------------------------------------------------------------------------


def _validated_root(worktree_root: str) -> Path:
    if not worktree_root:
        fail("MISSING_WORKTREE_ROOT")
    root = Path(worktree_root).expanduser()
    if not root.is_dir():
        fail("NOT_A_DIRECTORY", path=worktree_root)
    return root.resolve()


def _validated_project(project: Optional[str]) -> Optional[str]:
    if not project:
        return None
    try:
        validate_slug(project, label="project")
    except ValueError as exc:
        fail("INVALID_SLUG", exc=str(exc))
    if not project_exists(project):
        fail("UNKNOWN_PROJECT", project_slug=project)
    return project


def _validated_domain(domain: str) -> str:
    try:
        return normalise_domain(domain)
    except ValueError as exc:
        fail("INVALID_DOMAIN", exc=str(exc))


def _merged_params(project: Optional[str], overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    params = {key: (list(value) if isinstance(value, list) else value) for key, value in DEFAULT_PARAMS.items()}
    if project:
        params.update(_project_params(project))
    for key, value in (overrides or {}).items():
        if value is not None and key in DEFAULT_PARAMS:
            params[key] = value
    if isinstance(params["blocking"], str):
        params["blocking"] = [part.strip() for part in params["blocking"].split(",") if part.strip()]
    if params["min_severity"] not in SEVERITY_RANK:
        fail("INVALID_REVIEW_PARAMS", detail=f"min_severity={params['min_severity']!r}")
    unknown = [entry for entry in params["blocking"] if entry not in SEVERITY_RANK]
    if unknown:
        fail("INVALID_REVIEW_PARAMS", detail=f"blocking={unknown!r}")
    params["min_severity"] = str(params["min_severity"]).upper()
    params["blocking"] = [str(entry).upper() for entry in params["blocking"]]
    return params


def _project_params(project: str) -> Dict[str, Any]:
    profile = get_project_doc(project, "CHE_PROJECT_PROFILE")
    if profile is None or not profile.is_file():
        return {}
    frontmatter, _ = _parse_frontmatter(profile.read_text(encoding="utf-8", errors="replace"))
    review = frontmatter.get("review")
    if not isinstance(review, dict):
        return {}
    return {key: value for key, value in review.items() if key in DEFAULT_PARAMS}


# ---------------------------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------------------------


def _discover(root: Path, project: Optional[str], domain: str, changed: Sequence[str]) -> List[Dict[str, Any]]:
    found: Dict[str, Dict[str, Any]] = {}

    def add(path: Path, layer: str, kind: str, scope: Tuple[str, ...]) -> None:
        key = str(path)
        if key not in found:
            found[key] = {"path": path, "layer": layer, "kind": kind, "scope": scope}

    for name in REPO_DOCS:
        if (root / name).is_file():
            add(root / name, "repo-explicit", "repo-doc", ("**",))

    for dirname in REPO_RULE_DIRS:
        base = root / dirname
        if not base.is_dir():
            continue
        for pattern in ("*.md", "*.mdc"):
            for path in sorted(base.glob(pattern)):
                add(path, "repo-explicit", "repo-rules", ("**",))

    for rel_dir in _package_dirs(changed):
        for name in ("AGENTS.md", "CLAUDE.md"):
            path = root / rel_dir / name
            if path.is_file():
                add(path, "repo-explicit", "package-doc", (f"{rel_dir}/**",))

    for name in MACHINE_FILES:
        if (root / name).is_file():
            add(root / name, "machine", "machine-config", ("**",))

    if project:
        for path, kind in _project_docs(project, domain):
            if path.is_file():
                add(path, "project-memory", kind, ("**",))

    return list(found.values())


def _project_docs(project: str, domain: str) -> List[Tuple[Path, str]]:
    docs: List[Tuple[Optional[Path], str]] = [
        (get_project_doc(project, "CHE_ARCHITECTURE_DOC"), "architecture"),
        (get_project_doc(project, "CHE_PROJECT_PROFILE"), "profile"),
        (get_project_doc(project, "CHE_PRODUCT_CONTEXT"), "product-context"),
        (get_domain_dir(project, domain) / "conventions.md", "conventions"),
    ]
    return [(path, kind) for path, kind in docs if path is not None]


def _package_dirs(changed: Sequence[str]) -> List[str]:
    """Every ancestor folder of a changed file, excluding the repository root itself."""
    dirs = set()
    for entry in changed:
        parts = PurePosixPath(entry).parts[:-1]
        for depth in range(1, len(parts) + 1):
            dirs.add("/".join(parts[:depth]))
    return sorted(dirs)


# ---------------------------------------------------------------------------------------------
# Markdown -> rule cards
# ---------------------------------------------------------------------------------------------


def _cards_from_source(source: Dict[str, Any]) -> List[RuleCard]:
    path: Path = source["path"]
    text = path.read_text(encoding="utf-8", errors="replace")
    frontmatter, offset = _parse_frontmatter(text)
    body = _FRONTMATTER_RE.sub("", text, count=1) if offset else text

    scope = _as_globs(frontmatter.get("paths")) or source["scope"]
    declared = _as_severity(frontmatter.get("severity"))
    always = frontmatter.get("always") is True

    sections = _sections(body)
    if not sections:
        sections = [(0, _fallback_title(body, path), body)]

    cards: List[RuleCard] = []
    for start, title, raw in sections:
        if title.strip().lower() in IGNORED_SECTIONS:
            continue
        for relative, statement in _units(raw):
            polarity = _polarity(f"{title} {statement}")
            if polarity == "neutral":
                continue
            line = offset + body[: start + relative].count("\n") + 1
            cards.append(_card(source, path, line, title, statement, polarity, scope, declared, always))
    return cards


def _card(
    source: Dict[str, Any],
    path: Path,
    line: int,
    title: str,
    statement: str,
    polarity: str,
    scope: Tuple[str, ...],
    declared: Optional[str],
    always: bool,
) -> RuleCard:
    label = source.get("rel") or str(path)
    digest = hashlib.sha1(f"{label}:{line}:{title}".encode("utf-8")).hexdigest()[:12]
    return RuleCard(
        id=digest,
        layer=source["layer"],
        source=str(path),
        line=line,
        title=title,
        statement=statement,
        topics=_topics(title, statement),
        polarity=polarity,
        severity=declared or _infer_severity(title, statement),
        scope=scope,
        always=always,
    )


def _sections(body: str) -> List[Tuple[int, str, str]]:
    """(absolute index of the section body, heading title, raw body)."""
    matches = list(_HEADING_RE.finditer(body))
    sections: List[Tuple[int, str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections.append((match.end(), match.group(2).strip(), body[match.end() : end]))
    return sections


def _units(raw: str) -> List[Tuple[int, str]]:
    """(offset inside ``raw``, statement). A bullet is the rule unit when the section has bullets.

    Section-level granularity turns one long paragraph into a single 600-character "rule", which is
    both unreadable and impossible to contradict precisely. The bullet is the smallest unit a
    project actually writes, so it is the smallest unit a review should cite.
    """
    matches = list(_BULLET_RE.finditer(raw))
    if not matches:
        statement = _normalise(_strip_comments(raw))
        return [(len(raw) - len(raw.lstrip()), statement)] if statement else []

    units: List[Tuple[int, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        continuation = raw[match.end() : end].split("\n\n", 1)[0]
        statement = _normalise(_strip_comments(f"{match.group(1)} {continuation}"))
        if statement:
            units.append((match.start(), statement))
    return units


def _strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)


def _normalise(text: str) -> str:
    lines = [line.strip() for line in text.strip().splitlines()]
    joined = " ".join(line for line in lines if line)
    joined = re.sub(r"^[-*+]\s+", "", joined)
    return re.sub(r"\s+", " ", joined)[:600].strip()


def _fallback_title(body: str, path: Path) -> str:
    heading = re.search(r"^#\s+(.+?)\s*$", body, re.MULTILINE)
    return heading.group(1).strip() if heading else path.stem


def _topics(title: str, statement: str) -> Tuple[str, ...]:
    haystack = f"{title} {statement}".lower()
    return tuple(topic for topic, pattern in TOPIC_PATTERNS.items() if re.search(pattern, haystack))


def _polarity(text: str) -> str:
    if _NEGATIVE_RE.search(text):
        return "must-not"
    if _POSITIVE_RE.search(text):
        return "must"
    return "neutral"


def _infer_severity(title: str, statement: str) -> str:
    haystack = f"{title} {statement}"
    if _CRITICAL_RE.search(haystack):
        return "CRITICAL"
    if _HIGH_RE.search(haystack):
        return "HIGH"
    if _MEDIUM_RE.search(haystack):
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------------------------
# Precedence
# ---------------------------------------------------------------------------------------------


def _resolve_conflicts(
    cards: Sequence[RuleCard],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, str], set]:
    """Find contradictions that are close enough to be real, then rank them by authority.

    Two rules only contradict when they share a topic *and* a subject — the same section title, or
    at least two content words in common. Without the subject check, a "security" rule that says
    "must" and an unrelated "security" rule that says "never" would read as a conflict, and a
    report full of false contradictions is worse than no conflict detection at all.
    """
    by_topic: Dict[str, List[RuleCard]] = {}
    for card in cards:
        for topic in card.topics:
            by_topic.setdefault(topic, []).append(card)

    conflicts: List[Dict[str, Any]] = []
    drift: List[Dict[str, Any]] = []
    superseded: Dict[str, str] = {}
    conflicted: set = set()
    seen: set = set()

    for topic, group in sorted(by_topic.items()):
        for index, left in enumerate(group):
            for right in group[index + 1 :]:
                if left.polarity == right.polarity or not _same_subject(left, right):
                    continue
                winner, loser = (left, right) if _authority_key(left) <= _authority_key(right) else (right, left)
                if (winner.id, loser.id) in seen:
                    continue
                seen.add((winner.id, loser.id))
                resolved = LAYER_RANK[loser.layer] > LAYER_RANK[winner.layer]
                conflicts.append(
                    {
                        "topic": topic,
                        "kind": "precedence" if resolved else "unresolved",
                        "winner": winner.id,
                        "winner_source": _cite(winner),
                        "loser": loser.id,
                        "loser_source": _cite(loser),
                    }
                )
                if resolved:
                    superseded[loser.id] = winner.id
                    if loser.layer == "project-memory" and winner.layer == "repo-explicit":
                        drift.append({"topic": topic, "authority": _cite(winner), "stale": _cite(loser)})
                else:
                    conflicted.update({winner.id, loser.id})
                if len(conflicts) >= MAX_CONFLICTS:
                    return conflicts, drift, superseded, conflicted
    return conflicts, drift, superseded, conflicted


def _same_subject(left: RuleCard, right: RuleCard) -> bool:
    """A contradiction is only claimed between single-subject rules.

    A long bullet bundles several statements, so comparing it with a sibling produces a "conflict"
    that is really two different subjects disagreeing by accident. Short rules are the ones a
    project writes one idea at a time, and those are the only ones worth ranking.
    """
    if len(left.statement) > MAX_SUBJECT_CHARS or len(right.statement) > MAX_SUBJECT_CHARS:
        return False
    if _title_key(left.title) == _title_key(right.title):
        return True
    return len(_keywords(left.statement) & _keywords(right.statement)) >= 2


def _title_key(title: str) -> str:
    return re.sub(r"^[\d.\s]+", "", title.strip().lower())


def _keywords(text: str) -> set:
    return {word for word in _WORD_RE.findall(text.lower()) if word not in _STOPWORDS}


def _authority_key(card: RuleCard) -> Tuple[int, int, str, int]:
    return (LAYER_RANK[card.layer], -SEVERITY_RANK[card.severity], card.source, card.line)


def _capped(severity: str) -> str:
    """An unresolved contradiction never blocks: CRITICAL/HIGH fall back to MEDIUM."""
    return severity if SEVERITY_RANK[severity] <= SEVERITY_RANK["MEDIUM"] else "MEDIUM"


def _cite(card: RuleCard) -> str:
    return f"{card.source}:{card.line}"


# ---------------------------------------------------------------------------------------------
# Rows (the JSON contract)
# ---------------------------------------------------------------------------------------------


def _card_row(card: RuleCard, effective: str, superseded_by: Optional[str], conflicted: bool) -> Dict[str, Any]:
    row = asdict(card)
    row.update(
        {
            "effective_severity": effective,
            "superseded_by": superseded_by,
            "conflicted": conflicted,
        }
    )
    return row


def _hard_floor_row(entry: Dict[str, str]) -> Dict[str, Any]:
    return {
        "id": entry["id"],
        "layer": "hard-floor",
        "source": "che:hard-floor",
        "line": 0,
        "title": entry["title"],
        "statement": entry["statement"],
        "topics": [entry["topic"]],
        "polarity": "must-not",
        "severity": "CRITICAL",
        "effective_severity": "CRITICAL",
        "scope": ["**"],
        "always": True,
        "overridable": False,
        "superseded_by": None,
        "conflicted": False,
    }


def _source_row(source: Dict[str, Any], rules: int, applicable: bool) -> Dict[str, Any]:
    return {
        "path": str(source["path"]),
        "layer": source["layer"],
        "kind": source["kind"],
        "rules": rules,
        "applicable": applicable,
    }


# ---------------------------------------------------------------------------------------------
# Frontmatter (a deliberately small YAML subset: scalars, inline lists, block lists, one level)
# ---------------------------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> Tuple[Dict[str, Any], int]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, 0
    block = match.group(1)
    data: Dict[str, Any] = {}
    current_key: Optional[str] = None
    current_list: Optional[List[Any]] = None

    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and current_key is not None:
            if current_list is None:
                current_list = []
                data[current_key] = current_list
            current_list.append(_parse_scalar(stripped[2:]))
            continue
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        current_list = None
        if not value.strip():
            data[key] = {}
            current_key = key
            continue
        if line[:1].isspace() and isinstance(data.get(current_key), dict):
            data[current_key][key] = _parse_scalar(value)
            continue
        data[key] = _parse_scalar(value)
        current_key = None

    return data, len(block.splitlines()) + 2


def _parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return None
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [_parse_scalar(part) for part in inner.split(",")] if inner else []
    if len(value) > 1 and value[0] in "\"'" and value[-1] == value[0]:
        return value[1:-1]
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def _as_globs(value: Any) -> Optional[Tuple[str, ...]]:
    if isinstance(value, str) and value.strip():
        return (value.strip(),)
    if isinstance(value, list):
        globs = tuple(str(entry).strip() for entry in value if str(entry).strip())
        return globs or None
    return None


def _as_severity(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip().upper() in SEVERITY_RANK:
        return value.strip().upper()
    return None


# ---------------------------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------------------------


def _normalise_path(entry: str) -> str:
    path = entry.replace("\\", "/").strip()
    while path.startswith("./"):
        path = path[2:]
    return path.lstrip("/")


def _matches_any(paths: Sequence[str], patterns: Sequence[str]) -> bool:
    return any(_glob_regex(pattern).match(path) for path in paths for pattern in patterns)


@lru_cache(maxsize=512)
def _glob_regex(pattern: str) -> re.Pattern:
    """Translate a glob with `**` semantics into a whole-path regular expression."""
    source = pattern.replace("\\", "/")
    parts: List[str] = []
    index = 0
    while index < len(source):
        if source.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
        elif source.startswith("**", index):
            parts.append(".*")
            index += 2
        elif source[index] == "*":
            parts.append("[^/]*")
            index += 1
        elif source[index] == "?":
            parts.append("[^/]")
            index += 1
        else:
            parts.append(re.escape(source[index]))
            index += 1
    return re.compile("^" + "".join(parts) + "$")


def _git_changed(root: Path) -> List[str]:
    """Uncommitted paths, including untracked ones. Empty on any git failure.

    Two calls rather than `git status --untracked-files=all`: the tracked diff and the untracked
    list are both cheap and bounded, while asking status to walk every untracked directory is not.
    """
    tracked = _git_lines(root, ["diff", "--name-only", "-z", "HEAD"])
    untracked = _git_lines(root, ["ls-files", "--others", "--exclude-standard", "-z"])
    return sorted({path for path in tracked + untracked if path})


def _git_lines(root: Path, args: Sequence[str]) -> List[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
            env=hermetic_git_env(),
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0:
        return []
    return [_normalise_path(entry) for entry in completed.stdout.split("\0") if entry.strip()]
