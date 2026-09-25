"""The one place a Che failure is described, so every surface describes it the same way.

WHY THIS EXISTS
---------------
A failure used to be whatever prose the call site happened to print, followed by a number. That
cost an agent three things, and all three are fixable in one place:

1. **No stable identity.** ``exit 3`` means "unknown project" in ``worktrees.py`` and
   "INCONCLUSIVE" in the pixel gate, so an agent cannot branch on the number and must instead
   pattern-match English. Here every failure has a ``code``, and the code is the contract — the
   exit number stays as it was, for the scripts already relying on it.
2. **Two shapes for one command.** With ``--json`` a success printed an envelope on stdout and a
   failure printed prose on stderr, so the agent had to parse two formats and guess which one it
   was looking at. ``emit()`` renders the failure in the shape the caller asked for.
3. **No remedy.** "Error: bad slug" leaves the reader to work out what to do. Every spec below
   carries a ``hint`` and, where a command fixes the problem, ``next_actions`` naming it.

The envelope deliberately mirrors the one ``curate`` already documents
(``{status, code, stage, hint, retryable, next_actions, message, exit_code}``): this is the
ecosystem's existing shape, not a new invention.

HOW TO ADD A FAILURE
--------------------
Add the spec to ``ERROR_CATALOG`` first, then ``fail("THE_CODE", ...)`` at the call site. A test
asserts every code raised in ``che_core`` is catalogued, so the order matters — the same rule the
``curate`` pipeline states for its own catalog.

NOT IN SCOPE
------------
Verdicts are not failures. The pixel gate's PASS / FAIL / INCONCLUSIVE, and the ``che update``
statuses, are *results*: they exit with a meaningful code and print a report. They do not go
through this module, and they are not in the catalog.
"""

from __future__ import annotations

import functools
import json
import string
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, NoReturn, Optional, Sequence, Tuple

#: Success.
EXIT_OK = 0
#: Uncaught failure: the caller did nothing wrong, Che did.
EXIT_UNEXPECTED = 1
#: Usage or precondition failure: bad argument, missing input, refused destructive apply.
EXIT_USAGE = 2
#: The entity named exists in no registry: unknown project, worktree, trash entry.
EXIT_NOT_FOUND = 3
#: Storage-boundary violation: a Che artifact would land inside the user's repository.
EXIT_BOUNDARY = 99


@dataclass(frozen=True)
class ErrorSpec:
    """Everything known about one failure before it happens.

    ``message`` and ``hint`` are ``str.format`` templates over the values passed to ``fail()``, so a
    spec can name the offending path without the call site building a sentence. A literal brace
    must therefore be doubled (``{{``); the tests render every entry, so a missed one fails loudly
    rather than printing a placeholder marker to a user.
    """

    code: str
    stage: str
    exit_code: int
    message: str
    hint: str = ""
    next_actions: Tuple[str, ...] = ()
    retryable: bool = False


def _spec(
    code: str,
    stage: str,
    exit_code: int,
    message: str,
    hint: str = "",
    next_actions: Sequence[str] = (),
    retryable: bool = False,
) -> Tuple[str, ErrorSpec]:
    return code, ErrorSpec(code, stage, exit_code, message, hint, tuple(next_actions), retryable)


#: code -> spec. The single source of truth: a failure that is not here cannot be raised.
#:
#: Ordered by area, not alphabetically, so a reader can see the shape of what can go wrong. The
#: exit codes reproduce the behaviour that shipped, including where two areas disagree: a string
#: code removes the ambiguity the numbers carried, and renumbering would break the scripts and the
#: documented table that already depend on them.
ERROR_CATALOG: Dict[str, ErrorSpec] = dict(
    [
        # ------------------------------------------------------------------ arguments
        _spec(
            "MISSING_WORKTREE_ROOT",
            "arguments",
            EXIT_USAGE,
            "worktree_root is required.",
            "Pass the absolute path of a bound worktree.",
            ("che worktree list",),
        ),
        _spec(
            "MISSING_REPO_PATH",
            "arguments",
            EXIT_USAGE,
            "repo_path is required.",
            "Pass the absolute path of the repository checkout.",
        ),
        _spec(
            "MISSING_SESSION_ID",
            "arguments",
            EXIT_USAGE,
            "session_id is required.",
            "Pass the session id, or let the caller resolve it from $CHE_SESSION_ID.",
        ),
        _spec(
            "MISSING_EVENT_TYPE",
            "arguments",
            EXIT_USAGE,
            "event_type is required.",
            "Name the decision event, e.g. SPEC, SKIP_GATE, REVIEW_OVERRIDE.",
        ),
        _spec(
            "MISSING_DESIGN_MD_PATH",
            "arguments",
            EXIT_USAGE,
            "design_md_path is required.",
        ),
        _spec(
            "MISSING_ASSET_PATH",
            "arguments",
            EXIT_USAGE,
            "asset_path is required.",
        ),
        _spec(
            "MISSING_ASSET_METADATA",
            "arguments",
            EXIT_USAGE,
            "{label} is required.",
            "A stock asset needs its provenance recorded: provider, license and source_url.",
        ),
        _spec(
            "MISSING_REGISTRY_FIELDS",
            "arguments",
            EXIT_USAGE,
            "session_id, status and worktree_root are required.",
            "A registry row is only meaningful with all three.",
        ),
        _spec(
            "MISSING_ARTIFACT_ARGUMENT",
            "arguments",
            EXIT_USAGE,
            "{helper}: {argument} is required.",
            "An artifact path is built from its type, slug, extension and scope; a write needs a target.",
        ),
        _spec(
            "INVALID_ARTIFACT_SCOPE",
            "arguments",
            EXIT_USAGE,
            "{helper}: scope must be 'session' or 'workspace', got {scope!r}.",
            "Session scope resolves under $CHE_SESSION_DIR, workspace scope under $CHE_WORKSPACE_SHARED.",
        ),
        _spec(
            "INVALID_SLUG",
            "arguments",
            EXIT_USAGE,
            "{exc}",
            "Slugs are lowercase, digits and dashes: ^[a-z0-9][a-z0-9-]*$, at most 63 characters.",
        ),
        _spec(
            "INVALID_DOMAIN",
            "arguments",
            EXIT_USAGE,
            "{exc}",
            "Use one of the canonical domains, or an accepted alias.",
            ("che project --help",),
        ),
        _spec(
            "INVALID_SUB_PRODUCT_SLUG",
            "arguments",
            EXIT_USAGE,
            "invalid sub-product slug {sub_product!r} — must match {pattern}",
            "The sub-product names a folder under design/, so it has to be a slug.",
        ),
        _spec(
            "INVALID_BREAKPOINT_LABEL",
            "arguments",
            EXIT_USAGE,
            "{breakpoint!r} is not a usable breakpoint label.",
            "Use a plain name without a slash, and not '.' or '..': it becomes a filename.",
        ),
        _spec(
            "INVALID_ATTEMPT",
            "arguments",
            EXIT_USAGE,
            "--attempt must be >= 1, found {attempt}.",
            "The first run of a gate is --attempt 1.",
        ),
        _spec(
            "INVALID_FLAGS_JSON",
            "arguments",
            EXIT_USAGE,
            "--flags is not valid JSON: {detail}",
            'Pass a JSON object, e.g. --flags \'{{"LANG_CHAT": "pt-BR"}}\'.',
        ),
        _spec(
            "INVALID_DESIGN_SOURCE",
            "arguments",
            EXIT_USAGE,
            "--design-source requires --design-backend ({backends}).",
            "The source names a file; the backend decides how to read it.",
        ),
        _spec(
            "NOT_A_DIRECTORY",
            "arguments",
            EXIT_USAGE,
            "{path} is not a valid directory.",
            "Check the path, and that it exists on this machine.",
        ),
        _spec(
            "PATH_UNRESOLVABLE",
            "arguments",
            EXIT_USAGE,
            "cannot resolve {path}: {detail}",
            "The path is unreadable or holds a symlink loop; resolve it by hand to see why.",
        ),
        _spec(
            "NOT_A_GIT_REPOSITORY",
            "arguments",
            EXIT_USAGE,
            "{path} is not a git repository. Che {subject} require git (contract R4); nothing was created.",
            "Run `git init` there first, or point at a checkout that already is one.",
        ),
        _spec(
            "NO_CAPTURE_CONVENTION",
            "arguments",
            EXIT_USAGE,
            "--backend {backend!r} has no capture convention yet — no session has ever been recorded "
            "from it, so the raw reference filename would be a guess.",
            "See domains/ux/connectors/penpot.config.md 'Wiring status' for what has to exist first. "
            "Implemented now: {backends}.",
        ),
        _spec(
            "REFUSED_WITHOUT_CONFIRM",
            "arguments",
            EXIT_USAGE,
            "refusing to apply without --confirm.",
            "Run the --dry-run first, review the plan, then re-run with --no-dry-run --confirm.",
        ),
        _spec(
            "REFUSED_UNMANAGED_DIRECTORY",
            "arguments",
            EXIT_USAGE,
            "{path} exists but holds no {binding}. Refusing to adopt an unmanaged directory.",
            "Pass --force to adopt it, or choose another --name.",
        ),
        # ------------------------------------------------------------------ not found
        _spec(
            "UNKNOWN_PROJECT",
            "resolve",
            EXIT_NOT_FOUND,
            "project {project_slug!r} does not exist.",
            "Projects are created explicitly; nothing is inferred from a path.",
            ("che project init <repo> --slug {project_slug}", "che project list"),
        ),
        _spec(
            "UNKNOWN_WORKTREE",
            "resolve",
            EXIT_NOT_FOUND,
            "no worktree {worktree_name!r} in project {project_slug!r}.",
            "List what the project actually has before naming one.",
            ("che worktree list",),
        ),
        _spec(
            "UNBOUND_WORKTREE",
            "resolve",
            EXIT_NOT_FOUND,
            "{path} is not bound to any Che worktree.",
            "A worktree is the only thing that binds a filesystem path; bind it once.",
            ("che worktree add {path} --project <project> --name <name>", "che project list"),
        ),
        _spec(
            "NO_REGISTRY_ENTRY",
            "resolve",
            EXIT_UNEXPECTED,
            "no registry row for session {session_id!r}.",
            "The session has not been bound yet. If it should have been, the registry may be behind.",
            ("che worktree list",),
        ),
        _spec(
            "TRASH_ENTRY_NOT_FOUND",
            "resolve",
            EXIT_NOT_FOUND,
            "trash entry {trash_slug!r} not found.",
            "Removals land in .trash/; list them before restoring.",
            ("che project trash-list",),
        ),
        _spec(
            "TRASH_MANIFEST_INCOMPLETE",
            "resolve",
            EXIT_NOT_FOUND,
            "no original_path in the manifest of {trash_slug!r}.",
            "The entry cannot be restored without knowing where it came from.",
        ),
        _spec(
            "RESTORE_TARGET_EXISTS",
            "resolve",
            EXIT_NOT_FOUND,
            "restore target {target} already exists — refusing to overwrite.",
            "Move or rename the existing path, then restore again.",
        ),
        _spec(
            "DESIGN_TREE_MISSING",
            "design",
            EXIT_USAGE,
            "no design tree at {path}.",
            "Initialise it with `che designer init <worktree_root> <session_id> --sub-product <slug>`; "
            "the tree holds the design source of truth.",
        ),
        _spec(
            "TOKENS_JSON_MISSING",
            "design",
            EXIT_USAGE,
            "tokens.json not found at {path}; cannot render (R4 single-source).",
            "Tokens are the single source of truth for the design system; render needs them.",
            ("che designer init <worktree_root> <session_id> --sub-product <slug>",),
        ),
        _spec(
            "DESIGN_MD_MISSING",
            "design",
            EXIT_USAGE,
            "DESIGN.md not found at {path}.",
            "The design document is the contract a design tree is validated against.",
            ("che designer init <worktree_root> <session_id> --sub-product <slug>",),
        ),
        _spec(
            "ASSET_FILE_MISSING",
            "design",
            EXIT_USAGE,
            "asset file not found at {path}.",
            "Record the asset only after the file is on disk.",
        ),
        _spec(
            "TEMPLATE_MISSING",
            "install",
            EXIT_USAGE,
            "{name} template missing at {path}.",
            "The Che installation is incomplete: the template ships with the checkout.",
            ("che update",),
        ),
        # ------------------------------------------------------------------ input integrity
        _spec(
            "UNREADABLE_INPUT",
            "input",
            EXIT_USAGE,
            "cannot read {path}: {detail}",
            "Check the file exists and is readable.",
        ),
        _spec(
            "INVALID_JSON",
            "input",
            EXIT_USAGE,
            "{path} is not valid JSON: {detail}",
            "Fix the JSON at the reported position; a trailing comma is the usual cause.",
        ),
        _spec(
            "TOKENS_MISSING_COLORS",
            "input",
            EXIT_USAGE,
            "A-2 — tokens.json must contain a `colors` object (single source of truth).",
            "Add the colours to tokens.json rather than to a component.",
        ),
        _spec(
            "DOM_FACTS_UNUSABLE",
            "input",
            EXIT_USAGE,
            "the DOM fact bag is not usable ({count} problem(s)):\n{problems}",
            "Re-run domains/ux/gates/assets/dom-facts-extractor.js over the whole map.",
        ),
        _spec(
            "PIXEL_INPUT_INVALID",
            "input",
            EXIT_USAGE,
            "{detail}",
            "The pixel gate compares a design raster with a DOM raster; both must be readable.",
        ),
        _spec(
            "PIXEL_SIZE_MISMATCH",
            "input",
            EXIT_USAGE,
            "{detail}",
            "Rasters of different sizes are refused rather than scored: the number would be computed "
            "against the wrong pixels.",
        ),
        _spec(
            "ASSET_NOT_AN_IMAGE",
            "input",
            EXIT_USAGE,
            "AB-4 — asset {name} is not a real image (HTML/placeholder payload); discarded.",
            "The download returned a placeholder page rather than the asset.",
        ),
        # ------------------------------------------------------------------ boundaries
        _spec(
            "STORAGE_BOUNDARY_VIOLATION",
            "boundary",
            EXIT_BOUNDARY,
            "{label} is falling INSIDE the user worktree at {path}.",
            "Never build paths from $PWD or <worktree>/.che/. Resolve them once with "
            'eval "$(che compute_paths "$WORKTREE_ROOT" "$SESSION_ID")" and write to '
            "$CHE_WORKSPACE_SHARED or $CHE_SESSION_DIR.",
        ),
        _spec(
            "DESIGN_ROOT_ESCAPES_WORKTREE",
            "boundary",
            EXIT_USAGE,
            "design root {design_root} escapes worktree {worktree_root}.",
            "The design tree must live inside the worktree it belongs to.",
        ),
        _spec(
            "PLANNING_ARTIFACTS_TRACKED",
            "boundary",
            EXIT_USAGE,
            "Che planning artifacts are tracked in the user repository: {files}",
            "These files belong outside the repository; committing them pollutes every PR.",
        ),
        # ------------------------------------------------------------------ persistence
        _spec(
            "APPEND_FAILED",
            "persist",
            EXIT_USAGE,
            "{target}: {detail}",
            "The append is atomic and refuses oversized records rather than truncating them.",
        ),
        _spec(
            "STATE_DB_MISSING",
            "persist",
            EXIT_USAGE,
            "state database not found at {path}.",
            "The state store is rebuildable from the filesystem, which is the source of truth.",
            ("che state rebuild-index",),
        ),
        _spec(
            "STATE_QUERY_NEEDS_FORCE",
            "persist",
            EXIT_USAGE,
            "refusing a write query without --force: {statement}",
            "Reads are the default; a write needs --force to be deliberate.",
        ),
        _spec(
            "PROVIDER_UNAVAILABLE",
            "persist",
            EXIT_UNEXPECTED,
            "the decision store is not reachable: {detail}",
            "Decisions were not recorded. The filesystem store is the fallback.",
            retryable=True,
        ),
        # ------------------------------------------------------------------ last resort
        _spec(
            "UNEXPECTED",
            "internal",
            EXIT_UNEXPECTED,
            "unexpected failure: {detail}",
            "This is a Che bug, not a mistake in your input. Re-run with the same arguments to "
            "confirm, then report it with the command line and the message above.",
        ),
    ]
)

#: Used when a code is raised that the catalog does not know. Rendering must never fail — a
#: missing spec is a bug in Che, and saying so is more useful than a second traceback. A test
#: asserts this never happens for any code the package actually raises.
UNCATALOGUED = ErrorSpec(
    code="UNCATALOGUED",
    stage="internal",
    exit_code=EXIT_UNEXPECTED,
    message="unlisted failure {code!r}: {detail}",
    hint="This failure has no entry in ERROR_CATALOG, which is a bug in Che.",
)


class CheError(Exception):
    """A failure with an identity, a cause and a remedy.

    Holds the resolved :class:`ErrorSpec` plus the values its templates need, so rendering is a
    pure function of the error — no call site decides the wording, and two sites raising the same
    code cannot describe it differently.
    """

    def __init__(self, code: str, **values: Any) -> None:
        self.code = code
        self.values: Dict[str, Any] = {key: value for key, value in values.items() if value is not None}
        self.spec = ERROR_CATALOG.get(code)
        super().__init__(code)

    # -- rendering ---------------------------------------------------------------------------

    def _render(self, template: str) -> str:
        values = dict(self.values)
        # `code` and `detail` are always available so the last-resort templates can use them.
        values.setdefault("code", self.code)
        values.setdefault("detail", self.code)
        try:
            return template.format(**values)
        except (KeyError, IndexError, ValueError):
            # A template missing a value must not hide the failure it was describing.
            missing = sorted(set(self._placeholders(template)) - set(values))
            return f"{template} [missing value(s): {', '.join(missing) or 'unknown'}]"

    @staticmethod
    def _placeholders(template: str) -> List[str]:
        return [name for _, name, _, _ in string.Formatter().parse(template) if name]

    @property
    def message(self) -> str:
        return self._render((self.spec or UNCATALOGUED).message)

    @property
    def hint(self) -> str:
        spec = self.spec or UNCATALOGUED
        return self._render(spec.hint) if spec.hint else ""

    @property
    def next_actions(self) -> List[str]:
        spec = self.spec or UNCATALOGUED
        return [self._render(action) for action in spec.next_actions]

    @property
    def exit_code(self) -> int:
        return (self.spec or UNCATALOGUED).exit_code

    @property
    def stage(self) -> str:
        return (self.spec or UNCATALOGUED).stage

    @property
    def retryable(self) -> bool:
        return (self.spec or UNCATALOGUED).retryable

    def human_lines(self) -> List[str]:
        """Two or three lines: what failed, why it matters, and the command that fixes it."""
        lines = [f"Error: {self.message}"]
        if self.hint:
            lines.append(f"Hint: {self.hint}")
        for action in self.next_actions:
            lines.append(f"Next: {action}")
        if self.spec is None:
            lines.append(f"Code: {self.code} (not in ERROR_CATALOG)")
        return lines

    def envelope(self) -> Dict[str, Any]:
        """The machine-readable form, mirroring the shape `curate` already documents."""
        payload: Dict[str, Any] = {
            "status": "error",
            "code": self.code,
            "stage": self.stage,
            "message": self.message,
            "hint": self.hint,
            "retryable": self.retryable,
            "next_actions": self.next_actions,
            "exit_code": self.exit_code,
        }
        if self.values:
            payload["details"] = self.values
        return payload

    def __str__(self) -> str:
        return self.message


def fail(code: str, **values: Any) -> NoReturn:
    """Raise a catalogued failure. The only sanctioned way to end a Che command with an error."""
    raise CheError(code, **values)


def unexpected(exc: BaseException, **values: Any) -> CheError:
    """Wrap an exception nobody anticipated, keeping its type visible to the reader."""
    return CheError("UNEXPECTED", detail=f"{type(exc).__name__}: {exc}", **values)


def emit(err: CheError, json_mode: bool = False) -> int:
    """Print the failure in the requested shape and return the exit code.

    JSON goes to stdout and prose to stderr, so a caller that asked for machine-readable output
    always finds it on stdout — whether the command succeeded or failed.
    """
    if json_mode:
        print(json.dumps(err.envelope(), ensure_ascii=False, indent=2, default=str), file=sys.stdout)
    else:
        for line in err.human_lines():
            print(line, file=sys.stderr)
    return err.exit_code


def json_requested(argv: Optional[Sequence[str]] = None) -> bool:
    """Did the caller ask for machine-readable output?

    A literal membership test rather than an argparse round-trip: the flag is a store_true on
    several subcommands and on the top-level parser, and the renderer must be usable before (or
    without) a successfully parsed namespace.
    """
    tokens = list(sys.argv[1:] if argv is None else argv)
    return "--json" in tokens


def diagnosed(func: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a CLI entrypoint so no failure escapes as a traceback or as an empty stream.

    Deliberately narrow: ``SystemExit`` and ``KeyboardInterrupt`` pass straight through, so the
    ``sys.exit(N)`` sites that have not been migrated keep behaving exactly as they did. Migrating
    a call site only improves what that site prints; it can never change control flow.
    """

    @functools.wraps(func)
    def wrapper(argv: Optional[Sequence[str]] = None) -> Any:
        try:
            return func(argv)
        except CheError as err:
            sys.exit(emit(err, json_mode=json_requested(argv)))
        except Exception as exc:  # the last resort is the whole point
            sys.exit(emit(unexpected(exc), json_mode=json_requested(argv)))

    return wrapper
