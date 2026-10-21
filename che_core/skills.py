"""Deterministic skill discovery across the three Che scopes.

Resolution order is fixed — **project > repository > global** — and the same
skill name in more than one scope is reported once, with the closest scope marked
effective and the others listed as ``shadowed``. An agent therefore never has to
guess precedence: it asks the CLI and reads the answer.

Nothing here infers a project from the current working directory. The project is
either named explicitly or resolved through the worktree binding registry; an
unbound checkout simply has no project scope.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from che_core.diagnostics import fail
from che_core.project_layout import get_project_dir, get_workspaces_root, project_exists, validate_slug
from che_core.worktrees import find_worktree_by_path

SKILL_FILENAME = "SKILL.md"

#: Canonical precedence. The list order is the contract, not a presentation detail.
SCOPE_ORDER = ("project", "repository", "global")

_REPOSITORY_SKILL_DIRS = (".claude/skills", ".trae/skills")
_GLOBAL_SKILL_DIRS = (".claude/skills", ".trae/skills")


def parse_frontmatter(text: str) -> Dict[str, str]:
    """Read the leading YAML block as flat ``key: value`` pairs.

    Che only needs ``name`` and ``description``, so the parser deliberately stops
    there instead of growing a YAML dependency. A folded or literal scalar
    (``>`` / ``|``) is joined into one line, which is how the descriptions in the
    skill corpus are written.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    fields: Dict[str, str] = {}
    key: Optional[str] = None
    for raw in lines[1:]:
        if raw.strip() == "---":
            break
        if raw[:1] in (" ", "\t"):
            if key and raw.strip():
                fields[key] = f"{fields[key]} {raw.strip()}".strip()
            continue
        if ":" not in raw:
            continue
        name, _, value = raw.partition(":")
        key = name.strip()
        value = value.strip()
        if value in (">", "|", ">-", "|-"):
            value = ""
        fields[key] = value.strip("\"'")
    return fields


def _global_skill_dirs() -> Tuple[Path, ...]:
    """User-scope skill folders. Resolved per call so ``HOME`` stays testable."""
    home = Path.home()
    return tuple(home / rel for rel in _GLOBAL_SKILL_DIRS)


def _scope_dirs(project_slug: Optional[str], repo_root: Path) -> List[Tuple[str, Path]]:
    """Every directory to scan, already ordered by precedence."""
    dirs: List[Tuple[str, Path]] = []
    if project_slug:
        dirs.append(("project", get_project_dir(project_slug) / "skills"))
    dirs.extend(("repository", repo_root / rel) for rel in _REPOSITORY_SKILL_DIRS)
    dirs.extend(("global", path) for path in _global_skill_dirs())
    return dirs


def _read_skills(directory: Path, scope: str) -> List[Dict[str, Any]]:
    """Skills declared by ``<directory>/<name>/SKILL.md``, sorted by folder name."""
    if not directory.is_dir():
        return []

    skills: List[Dict[str, Any]] = []
    for child in sorted(directory.iterdir()):
        skill_file = child / SKILL_FILENAME
        if not child.is_dir() or not skill_file.is_file():
            continue
        try:
            text = skill_file.read_text(encoding="utf-8")
        except OSError:
            continue
        meta = parse_frontmatter(text)
        skills.append(
            {
                "name": meta.get("name") or child.name,
                "description": meta.get("description", ""),
                "scope": scope,
                "path": str(skill_file),
            }
        )
    return skills


def _project_from_init_registry(repo_root: str) -> List[str]:
    """Projects whose ``PROJECT_INIT`` record names ``repo_root``.

    The fallback exists for a project that has no worktree bound yet: its skills
    are already worth discovering, and the checkout it tracks is recorded data —
    not a guess from the current directory.
    """
    root = get_workspaces_root()
    if not root.is_dir():
        return []

    matches: List[str] = []
    for project_dir in sorted(root.iterdir()):
        registry = project_dir / "registry.jsonl"
        if not project_dir.is_dir() or project_dir.name.startswith(".") or not registry.is_file():
            continue
        try:
            validate_slug(project_dir.name)
        except ValueError:
            continue
        for line in registry.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("repo_root") == repo_root:
                matches.append(project_dir.name)
                break
    return matches


def resolve_project_slug(repo_root: str) -> Optional[str]:
    """Project bound to ``repo_root``, or ``None`` when the checkout is unknown.

    Two projects resolving to the same checkout is an ambiguous answer, and Che
    never resolves ambiguity by picking one: the caller must name the project.
    """
    projects = sorted({m["project"] for m in find_worktree_by_path(repo_root) if m.get("project")})
    if not projects:
        projects = sorted(set(_project_from_init_registry(repo_root)))
    if len(projects) > 1:
        fail("AMBIGUOUS_PROJECT_BINDING", path=repo_root, projects=", ".join(projects))
    return projects[0] if projects else None


def list_skills(*, project: Optional[str] = None, repo: Optional[str] = None) -> Dict[str, Any]:
    """Resolve every skill visible to this session, closest scope first.

    Preconditions: ``project``, when given, is an existing project slug.
    Postcondition: ``skills`` holds one entry per name — the effective one — and
    ``shadowed`` holds the entries the winner overrides.
    """
    repo_root = Path(repo).expanduser().resolve() if repo else Path.cwd().resolve()

    project_slug = project
    if project_slug is None:
        project_slug = resolve_project_slug(str(repo_root))
    elif not project_exists(project_slug):
        fail("UNKNOWN_PROJECT", project_slug=project_slug)

    scanned: List[Dict[str, Any]] = []
    collected: List[Dict[str, Any]] = []
    for scope, directory in _scope_dirs(project_slug, repo_root):
        found = _read_skills(directory, scope)
        scanned.append(
            {
                "scope": scope,
                "path": str(directory),
                "exists": directory.is_dir(),
                "count": len(found),
            }
        )
        collected.extend(found)

    winners: Dict[str, str] = {}
    effective: List[Dict[str, Any]] = []
    shadowed: List[Dict[str, Any]] = []
    for skill in collected:
        winner = winners.get(skill["name"])
        if winner is None:
            winners[skill["name"]] = skill["scope"]
            effective.append(skill)
        else:
            shadowed.append({**skill, "shadowed_by": winner})

    return {
        "project_slug": project_slug,
        "repo_root": str(repo_root),
        "scope_order": list(SCOPE_ORDER),
        "scanned": scanned,
        "skills": effective,
        "shadowed": shadowed,
    }
