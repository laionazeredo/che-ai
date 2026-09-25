"""The CLI surface, as data — so an agent can read it instead of guessing it.

WHY THIS EXISTS
---------------
Che's interface lived in two places that could not see each other: the argparse declarations in
``cli.py``, and the prose in ``docs/cli-reference.md``. An agent that wanted to call ``che worktree
add`` had to load 700 lines of markdown into context, or guess and read the error. Guessing is the
expensive path: a wrong flag costs a round trip and teaches nothing about the right one.

:func:`build_manifest` walks the real parser and returns the surface as JSON-serialisable data —
every command, its arguments and their types, which are required, which are mutually exclusive, what
the command does to the world, the exit codes it can return, and the whole failure catalogue. It is
served by ``che capabilities --json``.

WHY THE PARSER, AND NOT A HAND-WRITTEN MANIFEST
-----------------------------------------------
The obvious design is a declared manifest that argparse, the JSON schema and (later) the MCP adapter
all read. It is the wrong one here. argparse already encodes the command tree, argument names,
``choices``, ``type``, ``default``, ``required``, ``nargs``, the help strings and the
mutually-exclusive groups; re-declaring those by hand is several hundred lines that can drift from
the thing they describe, and the drift would be silent — the manifest would confidently describe a
CLI that does not exist.

So the parser is the single source for the *shape*, and this module adds the two things it cannot
know: what running a command does (:data:`COMMAND_SEMANTICS`) and which exit codes exist
(:data:`EXIT_CODES`). Both are guarded by tests that fail when a command is added without a semantics
entry, and when a semantics entry outlives its command.

DEPENDENCY ON PRIVATE ARGPARSE STATE
------------------------------------
The walk reads ``parser._actions``, ``parser._mutually_exclusive_groups`` and ``group._group_actions``.
Those are private and have no public equivalent — every argparse-introspecting tool reaches for them.
That is a real dependency on a CPython internal, so ``tests/test_manifest.py`` asserts the walk finds
known commands with known arguments: a future Python that changes the representation fails in CI
rather than returning an empty surface that reads as a Che with no commands.
"""

from __future__ import annotations

import argparse
import importlib
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from che_core.diagnostics import (
    ERROR_CATALOG,
    EXIT_BOUNDARY,
    EXIT_NOT_FOUND,
    EXIT_OK,
    EXIT_UNEXPECTED,
    EXIT_USAGE,
)
from che_core.selfupdate import UPDATE_FETCH_FAILED, UPDATE_REINSTALL_FAILED

#: The skills' guard (`command -v che >/dev/null 2>&1 || exit 98`). Not raised by ``che_core``, but
#: an agent will meet it, so it belongs in the table an agent reads.
EXIT_MISSING_DEPENDENCY = 98

#: The documented exit-code contract, as data. `che update` keeps its own numbers because it reports a
#: different kind of outcome: not "the command failed" but "the update did not happen".
EXIT_CODES: Tuple[Dict[str, Any], ...] = (
    {"code": EXIT_OK, "name": "OK", "meaning": "Success."},
    {
        "code": EXIT_UNEXPECTED,
        "name": "UNEXPECTED",
        "meaning": "A Che bug, not a mistake in the caller's input. Re-run to confirm, then report it.",
    },
    {
        "code": EXIT_USAGE,
        "name": "USAGE",
        "meaning": "Bad argument, missing input, or a destructive operation applied without --confirm.",
    },
    {
        "code": EXIT_NOT_FOUND,
        "name": "NOT_FOUND",
        "meaning": (
            "The named entity exists in no registry. Deliberately overloaded: the pixel gate also "
            "exits 3 for INCONCLUSIVE, so branch on the failure `code`, never on the number."
        ),
    },
    {
        "code": UPDATE_FETCH_FAILED,
        "name": "UPDATE_FETCH_FAILED",
        "meaning": "`che update`: the remote could not be reached. Nothing was changed.",
    },
    {
        "code": UPDATE_REINSTALL_FAILED,
        "name": "UPDATE_REINSTALL_FAILED",
        "meaning": "`che update`: the code moved but the CLI could not be reinstalled, so deps may be stale.",
    },
    {
        "code": EXIT_MISSING_DEPENDENCY,
        "name": "MISSING_DEPENDENCY",
        "meaning": "The `che` CLI is not on PATH. Raised by the skills' guard before any write.",
    },
    {
        "code": EXIT_BOUNDARY,
        "name": "STORAGE_BOUNDARY",
        "meaning": "A Che artifact would land inside the user's repository.",
    },
)

#: The values ``output`` may take — what lands on stdout, so a caller knows what it is parsing.
OUTPUT_SHAPES = ("json", "shell", "kv", "text", "prose", "none")

#: What argparse cannot know: the consequence of running a command.
#:
#: Keyed by the space-joined command path, exactly as argparse names it. **Every** command must appear,
#: because a wrong answer here is worse than no answer — an agent that believes a destructive command
#: is read-only will run it. ``tests/test_manifest.py`` asserts completeness in both directions.
#:
#: * ``summary`` — one sentence, written for a caller deciding whether this is the command they want.
#:   Deliberately not argparse's ``help``: that is a terse label for a human scanning a list, this is
#:   the sentence an agent reads instead of the whole CLI reference.
#: * ``mutates`` — does it change state on disk, in a registry or in a database?
#: * ``requires_bound_worktree`` — does it need a path already bound via ``che worktree add``?
#: * ``output`` — what lands on stdout, so a caller knows what it is parsing:
#:   ``json`` (a JSON value) · ``shell`` (`export K="v"` lines, for `eval`) · ``kv`` (`K=v` lines) ·
#:   ``text`` (one bare value) · ``prose`` (human text, not for parsing) · ``none`` (nothing).
COMMAND_SEMANTICS: Dict[str, Dict[str, Any]] = {
    # --- plumbing ---------------------------------------------------------------
    "compute_paths": {
        "summary": "Resolve every Che storage path for a bound worktree, as eval-able export lines.",
        "mutates": False,
        "requires_bound_worktree": True,
        "output": "shell",
    },
    "ensure_dirs": {
        "summary": "Materialise the project skeleton, worktree folder and session folder.",
        "mutates": True,
        "requires_bound_worktree": True,
        "output": "none",
    },
    "output_path": {
        "summary": "Resolve the canonical path for a Che artifact outside the worktree, creating its parent.",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "text",
    },
    "write_file_atomic": {
        "summary": "Write stdin to a target path atomically, refusing targets inside the worktree.",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "none",
    },
    "assert_outside_worktree": {
        "summary": "Hard-stop guard: fail if a candidate path falls inside the user worktree.",
        "mutates": False,
        "requires_bound_worktree": False,
        "output": "none",
    },
    "registry_append": {
        "summary": "Append one row to the session registry (session, status, worktree, payload).",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "none",
    },
    "registry_lookup": {
        "summary": "Read the last registry row for a session, or fail with NO_REGISTRY_ENTRY.",
        "mutates": False,
        "requires_bound_worktree": False,
        "output": "json",
    },
    "decision_append": {
        "summary": "Append one decision record to the worktree's decisions.log.jsonl.",
        "mutates": True,
        "requires_bound_worktree": True,
        "output": "none",
    },
    "config": {
        "summary": "Set the session flags (languages, PT check) that skills read before writing.",
        "mutates": True,
        "requires_bound_worktree": True,
        "output": "prose",
    },
    "capabilities": {
        "summary": "Describe the whole CLI surface as data: commands, arguments, exit codes, failures.",
        "mutates": False,
        "requires_bound_worktree": False,
        "output": "json",
    },
    # --- portability ------------------------------------------------------------
    "export": {
        "summary": "Archive a project (docs, worktrees, optional databases) into a portable tarball.",
        "mutates": True,
        "requires_bound_worktree": True,
        "output": "prose",
    },
    "import": {
        "summary": "Restore a portable tarball, recreating the project and its worktrees.",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "json",
    },
    # --- task graph -------------------------------------------------------------
    "task list": {
        "summary": "List tasks in a worktree's task graph, filtered by status, domain or readiness.",
        "mutates": False,
        "requires_bound_worktree": True,
        "output": "json",
    },
    "task show": {
        "summary": "Show one task: its envelope, dependencies and recorded status.",
        "mutates": False,
        "requires_bound_worktree": True,
        "output": "json",
    },
    "task resume": {
        "summary": "Resume a stopped task and record the session that picked it up.",
        "mutates": True,
        "requires_bound_worktree": True,
        "output": "json",
    },
    "task set-status": {
        "summary": "Move a task to a new status, optionally with a reason.",
        "mutates": True,
        "requires_bound_worktree": True,
        "output": "json",
    },
    "task graph-summary": {
        "summary": "Summarise the task graph: topological order, critical path, ready set.",
        "mutates": False,
        "requires_bound_worktree": True,
        "output": "json",
    },
    # --- state store ------------------------------------------------------------
    "state rebuild-index": {
        "summary": "Rebuild the SQLite FTS5 index over the worktree's files (the files stay the truth).",
        "mutates": True,
        "requires_bound_worktree": True,
        "output": "json",
    },
    "state query": {
        "summary": "Run parameterised SQL against the state store. Read-only unless --force is given.",
        "mutates": True,
        "requires_bound_worktree": True,
        "output": "json",
    },
    "state sanitize": {
        "summary": "Purge state-store records past the age or count limits. Supports --dry-run.",
        "mutates": True,
        "requires_bound_worktree": True,
        "output": "json",
    },
    "state search": {
        "summary": "Full-text search over tasks, specs, decisions and envelopes.",
        "mutates": False,
        "requires_bound_worktree": True,
        "output": "json",
    },
    # --- rag --------------------------------------------------------------------
    "rag build-index": {
        "summary": "Chunk and embed the worktree's text for hybrid search. Runs fully locally.",
        "mutates": True,
        "requires_bound_worktree": True,
        "output": "json",
    },
    "rag search": {
        "summary": "Hybrid BM25 + vector search over the RAG index.",
        "mutates": False,
        "requires_bound_worktree": True,
        "output": "json",
    },
    # --- projects ---------------------------------------------------------------
    "project create": {
        "summary": "Create or refresh the flat project folder that tracks a git checkout.",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "json",
    },
    "project list": {
        "summary": "List projects with their docs, worktrees and database files.",
        "mutates": False,
        "requires_bound_worktree": False,
        "output": "json",
    },
    "project remove": {
        "summary": "Move a project to .trash/ (never deleted). Dry-run by default; needs --confirm to apply.",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "json",
    },
    "project restore": {
        "summary": "Move a trashed project back to its recorded original path.",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "json",
    },
    "project trash-list": {
        "summary": "List the trash entries with their manifests, so a restore slug can be read off.",
        "mutates": False,
        "requires_bound_worktree": False,
        "output": "json",
    },
    # --- worktrees --------------------------------------------------------------
    "worktree add": {
        "summary": "Bind a git checkout to a project. Idempotent: re-running reuses the existing tree.",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "json",
    },
    "worktree list": {
        "summary": "List the worktrees bound to a project.",
        "mutates": False,
        "requires_bound_worktree": False,
        "output": "json",
    },
    "worktree show": {
        "summary": "Show one worktree binding: its repo, branch, origin and bound path.",
        "mutates": False,
        "requires_bound_worktree": False,
        "output": "json",
    },
    "worktree remove": {
        "summary": "Move a worktree folder to .trash/ (never the repo). Dry-run by default; needs --confirm.",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "json",
    },
    # --- update / eject ---------------------------------------------------------
    "update": {
        "summary": "Fast-forward this Che checkout to the latest main and re-link the host adapters.",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "json",
    },
    "eject plan": {
        "summary": "Plan a safe uninstall: what moves to trash, what stays. Dry-run by default.",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "json",
    },
    "eject trash-list": {
        "summary": "List previous ejects sitting in trash, with their manifests.",
        "mutates": False,
        "requires_bound_worktree": False,
        "output": "json",
    },
    "eject restore": {
        "summary": "Restore a previous eject from trash and re-run the adapter setup.",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "json",
    },
    # --- pixel gate -------------------------------------------------------------
    "pixel check": {
        "summary": "Score a design against a live DOM. Exit 0=PASS, 1=FAIL, 3=INCONCLUSIVE, 2=bad input.",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "prose",
    },
    "pixel paths": {
        "summary": "Resolve the gate's artifact set as eval-able export lines; the design tree must exist.",
        "mutates": False,
        "requires_bound_worktree": True,
        "output": "shell",
    },
    "pixel diff": {
        "summary": "Write the §4.5 whole-frame diff PNG. Evidence only: it never exits non-zero on a difference.",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "prose",
    },
    "pixel crop": {
        "summary": "Write the §4.5 per-element crop report and strip. Evidence only, never a verdict.",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "prose",
    },
    # --- design domain (delegated to che_core.designer) -------------------------
    "designer bootstrap": {
        "summary": "Create the session-side design folder a design gate writes into.",
        "mutates": True,
        "requires_bound_worktree": True,
        "output": "kv",
    },
    "designer init": {
        "summary": "Write the git-native design tree (DESIGN.md + tokens.json) inside the worktree.",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "kv",
    },
    "designer validate": {
        "summary": "Validate a DESIGN.md against the canonical section spec. Exit 1 when it is invalid.",
        "mutates": False,
        "requires_bound_worktree": False,
        "output": "prose",
    },
    "designer tokens render": {
        "summary": "Re-render DESIGN.md frontmatter and tokens.styles.css from tokens.json (single source).",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "kv",
    },
    "designer stock add": {
        "summary": "Copy a downloaded asset into design/assets/ and record its provenance in CREDITS.md.",
        "mutates": True,
        "requires_bound_worktree": False,
        "output": "kv",
    },
}

#: Commands whose real argument surface lives in a different parser, because `cli.py` forwards them
#: verbatim before argparse runs (argparse cannot forward leading optionals through a subparser —
#: bpo-17050). Without this the manifest would describe `designer` as taking no arguments at all,
#: which is worse than not describing it.
DELEGATED_PARSERS: Dict[str, str] = {"designer": "che_core.designer"}


# --- walking the parser --------------------------------------------------------------------------


def _subparser_action(parser: argparse.ArgumentParser) -> Optional[argparse.Action]:
    for action in parser._actions:  # noqa: SLF001 — no public equivalent, see module docstring
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _delegated(parser_path: Sequence[str]) -> Optional[argparse.ArgumentParser]:
    module_name = DELEGATED_PARSERS.get(" ".join(parser_path))
    if not module_name:
        return None
    return importlib.import_module(module_name).build_parser()


def _walk(
    parser: argparse.ArgumentParser,
    path: Tuple[str, ...] = (),
    aliases: Tuple[str, ...] = (),
) -> Iterator[Tuple[Tuple[str, ...], Tuple[str, ...], argparse.ArgumentParser]]:
    """Yield ``(path, aliases, parser)`` for every command in the tree, depth-first.

    A command with no subparsers is a leaf and is yielded. A command that delegates its surface to
    another parser is walked through it, so its real arguments are described under the same path.
    """
    action = _subparser_action(parser)
    if action is None:
        delegated = _delegated(path)
        if delegated is not None:
            yield from _walk(delegated, path, aliases)
            return
        yield path, aliases, parser
        return

    # argparse registers aliases as extra keys pointing at the same parser object; the first key is
    # the canonical name and the rest are aliases, which is the order a caller should read them in.
    names_by_parser: Dict[int, List[str]] = {}
    for name, child in action.choices.items():
        names_by_parser.setdefault(id(child), []).append(name)

    for name, child in action.choices.items():
        names = names_by_parser[id(child)]
        if name != names[0]:
            continue
        yield from _walk(child, (*path, names[0]), tuple(names[1:]))


# --- describing one command ----------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return str(value)


def _type_name(argument: argparse.Action) -> str:
    # `store_true` / `store_false` set nargs=0. Checked before `type`, which is None for both and for
    # plain string arguments alike.
    if argument.nargs == 0:
        return "boolean"
    if argument.type is not None:
        return getattr(argument.type, "__name__", str(argument.type))
    return "str"


def _is_required(argument: argparse.Action) -> bool:
    if argument.option_strings:
        return bool(argument.required)
    # argparse leaves `required` False for positionals even when they must be supplied: a positional
    # that neither takes a variable count nor has a default is required, and saying otherwise would
    # send a caller into a usage error the manifest told them not to expect.
    if argument.nargs in ("?", "*"):
        return False
    return argument.default is None


def _describe_argument(argument: argparse.Action) -> Dict[str, Any]:
    option_strings = list(argument.option_strings)
    if option_strings:
        # The longest form is the name a caller should use; the rest are aliases.
        name = max(option_strings, key=len)
        described: Dict[str, Any] = {
            "name": name,
            "dest": argument.dest,
            "kind": "option",
            "type": _type_name(argument),
            "required": _is_required(argument),
        }
        aliases = sorted(option for option in option_strings if option != name)
        if aliases:
            described["aliases"] = aliases
    else:
        described = {
            "name": argument.dest,
            "dest": argument.dest,
            "kind": "positional",
            "type": _type_name(argument),
            "required": _is_required(argument),
        }

    if argument.choices is not None:
        described["choices"] = [str(choice) for choice in argument.choices]
    if isinstance(argument.nargs, int) and argument.nargs > 0:
        described["nargs"] = argument.nargs
    if argument.default is not argparse.SUPPRESS and argument.default is not None:
        described["default"] = _jsonable(argument.default)
    if argument.help:
        described["help"] = " ".join(argument.help.split())
    return described


def _describe_arguments(parser: argparse.ArgumentParser) -> List[Dict[str, Any]]:
    described = []
    for argument in parser._actions:  # noqa: SLF001 — see module docstring
        if isinstance(argument, (argparse._SubParsersAction, argparse._HelpAction)):
            continue
        described.append(_describe_argument(argument))
    return described


def _describe_groups(parser: argparse.ArgumentParser) -> List[Dict[str, Any]]:
    """The mutually-exclusive sets, which argparse knows and a caller must not have to guess."""
    described = []
    for group in parser._mutually_exclusive_groups:  # noqa: SLF001 — see module docstring
        names = sorted(
            max(action.option_strings, key=len)
            for action in group._group_actions  # noqa: SLF001 — see module docstring
            if action.option_strings
        )
        if names:
            described.append({"required": bool(group.required), "one_of": names})
    return described


def _describe_command(
    path: Sequence[str],
    aliases: Sequence[str],
    parser: argparse.ArgumentParser,
    *,
    include_arguments: bool,
) -> Dict[str, Any]:
    name = " ".join(path)
    semantics = COMMAND_SEMANTICS.get(name, {})
    described: Dict[str, Any] = {
        "name": name,
        "aliases": list(aliases),
        "summary": semantics.get("summary", ""),
        "mutates": semantics.get("mutates"),
        "requires_bound_worktree": semantics.get("requires_bound_worktree"),
        "output": semantics.get("output"),
    }
    if include_arguments:
        described["arguments"] = _describe_arguments(parser)
        groups = _describe_groups(parser)
        if groups:
            described["mutually_exclusive"] = groups
    return described


# --- the manifest ---------------------------------------------------------------------------------


def _describe_errors() -> List[Dict[str, Any]]:
    """The failure catalogue, so a caller that received a code can look up what it means.

    ``message`` and ``hint`` are exported as the ``str.format`` templates they are: they name the
    values the failure will carry, which is how a caller learns what to expect in ``details``.
    """
    return [
        {
            "code": spec.code,
            "stage": spec.stage,
            "exit_code": spec.exit_code,
            "message": spec.message,
            "hint": spec.hint,
            "next_actions": list(spec.next_actions),
            "retryable": spec.retryable,
        }
        for spec in sorted(ERROR_CATALOG.values(), key=lambda spec: spec.code)
    ]


def build_manifest(
    parser: argparse.ArgumentParser,
    *,
    include_arguments: bool = False,
    include_errors: bool = False,
) -> Dict[str, Any]:
    """Describe ``parser`` as data. The one place a Che surface is enumerated.

    **Compact by default, on purpose.** An agent's first question is "what can I do?", and answering
    it with every argument of every command costs more context than it saves — the arguments are the
    bulk of the payload and are needed for exactly one command at a time. So ``arguments`` appear only
    when they are asked for, and the failure catalogue is opt-in for the same reason: a caller that
    just received a failure already has its rendered message and remedy in the envelope.
    """
    commands = [
        _describe_command(path, aliases, command_parser, include_arguments=include_arguments)
        for path, aliases, command_parser in _walk(parser)
    ]
    manifest: Dict[str, Any] = {
        "global_options": _describe_arguments(parser),
        "exit_codes": [dict(entry) for entry in EXIT_CODES],
        "commands": commands,
    }
    if include_errors:
        manifest["errors"] = _describe_errors()
    return manifest


def find_command(manifest: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    """The command whose name or alias matches ``name``, so `--command` accepts either spelling."""
    wanted = " ".join(name.split())
    for command in manifest["commands"]:
        if command["name"] == wanted or wanted in command["aliases"]:
            return command
    return None
