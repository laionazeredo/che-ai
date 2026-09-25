"""Contract tests for the machine-readable CLI surface.

`che capabilities --json` is only useful if it is *true*. Three things keep it so: the walk must
reach every command (it reads private argparse state, so a CPython change could silently empty it),
every command must carry a declared meaning (argparse cannot know what running a command does), and
the two must not drift apart in either direction. The first is asserted against known commands and
known arguments; the second and third against the parser itself.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

from che_core.cli import build_parser
from che_core.diagnostics import ERROR_CATALOG
from che_core.manifest import (
    COMMAND_SEMANTICS,
    DELEGATED_PARSERS,
    EXIT_CODES,
    OUTPUT_SHAPES,
    _describe_arguments,
    build_manifest,
    find_command,
)

CHE_ROOT = Path(__file__).resolve().parent.parent

#: The four keys every entry must carry. Asserted exhaustively so a new one cannot be added to some
#: entries and forgotten in others — a half-populated contract reads as "no answer" rather than
#: "wrong answer", which is worse for a caller that trusts it.
SEMANTICS_KEYS = {"summary", "mutates", "requires_bound_worktree", "output"}


def _commands() -> dict:
    return {command["name"]: command for command in build_manifest(build_parser())["commands"]}


def _arguments(command: dict) -> dict:
    return {argument["name"]: argument for argument in command["arguments"]}


def _detailed(name: str) -> dict:
    manifest = build_manifest(build_parser(), include_arguments=True)
    return find_command(manifest, name)


# ---------------------------------------------------------------------------------------------
# The walk reaches the surface
# ---------------------------------------------------------------------------------------------


def test_the_walk_finds_the_commands_the_cli_documents() -> None:
    """A guard on the private argparse state the walk depends on.

    If a future CPython changes how actions or subparsers are stored, the walk could return nothing —
    and an empty surface looks exactly like a Che with no commands. Naming the commands here turns
    that into a CI failure with a diff.
    """
    names = set(_commands())

    assert len(names) > 40, f"the walk found only {len(names)} commands; it is not reaching the tree"
    assert {"compute_paths", "worktree add", "project remove", "state query", "pixel check"} <= names


def test_the_walk_reaches_through_a_delegated_parser() -> None:
    """`che designer …` is forwarded before argparse, so its arguments live in another parser.

    Describing it as taking no arguments would be worse than not describing it: a caller would read
    the empty argument list as "this command needs nothing".
    """
    assert "designer" in DELEGATED_PARSERS

    init = _arguments(_detailed("designer init"))

    assert init["worktree_root"]["kind"] == "positional"
    assert init["--sub-product"]["required"] is True


# ---------------------------------------------------------------------------------------------
# The declared meaning is complete, and matches the parser
# ---------------------------------------------------------------------------------------------


def test_every_command_carries_a_declared_meaning() -> None:
    """Adding a command without saying what it does must fail here, not in an agent's run."""
    undeclared = sorted(set(_commands()) - set(COMMAND_SEMANTICS))

    assert not undeclared, f"commands with no COMMAND_SEMANTICS entry: {undeclared}"


def test_no_declared_meaning_outlives_its_command() -> None:
    """A stale entry is a description of a command that no longer exists — silently wrong."""
    stale = sorted(set(COMMAND_SEMANTICS) - set(_commands()))

    assert not stale, f"COMMAND_SEMANTICS entries with no command: {stale}"


@pytest.mark.parametrize("name", sorted(COMMAND_SEMANTICS))
def test_every_entry_is_fully_populated(name: str) -> None:
    entry = COMMAND_SEMANTICS[name]

    assert set(entry) == SEMANTICS_KEYS, f"{name} declares {sorted(entry)}"
    assert entry["summary"].strip(), f"{name} has an empty summary"
    assert entry["summary"].endswith("."), f"{name}: the summary is a sentence"
    assert isinstance(entry["mutates"], bool), f"{name}: mutates must be decided, not defaulted"
    assert isinstance(entry["requires_bound_worktree"], bool)
    assert entry["output"] in OUTPUT_SHAPES, f"{name}: unknown output shape {entry['output']!r}"


def test_a_command_that_cannot_change_anything_is_a_minority_worth_naming() -> None:
    """The `mutates` flag only earns its place if both answers occur — otherwise it is decoration."""
    answers = {entry["mutates"] for entry in COMMAND_SEMANTICS.values()}

    assert answers == {True, False}


# ---------------------------------------------------------------------------------------------
# Arguments, as argparse describes them
# ---------------------------------------------------------------------------------------------


def test_a_positional_that_must_be_supplied_is_reported_required() -> None:
    """argparse leaves `required` False for positionals, so reporting it raw would mislead."""
    arguments = _arguments(_detailed("worktree add"))

    assert arguments["repo_path"] == {
        "name": "repo_path",
        "dest": "repo_path",
        "kind": "positional",
        "type": "str",
        "required": True,
        "help": "Absolute path to the git checkout.",
    }


def test_a_positional_with_a_default_is_not_required() -> None:
    """`che output_path … [suffix]` takes an optional trailing value; it must not read as mandatory."""
    arguments = _arguments(_detailed("output_path"))

    assert arguments["suffix"]["kind"] == "positional"
    assert arguments["suffix"]["required"] is False


def test_a_flag_is_a_boolean_with_its_default_stated() -> None:
    arguments = _arguments(_detailed("worktree add"))

    assert arguments["--force"]["type"] == "boolean"
    assert arguments["--force"]["default"] is False
    assert arguments["--force"]["required"] is False


def test_a_required_option_is_reported_required() -> None:
    arguments = _arguments(_detailed("worktree add"))

    assert arguments["--project"]["kind"] == "option"
    assert arguments["--project"]["required"] is True


def test_a_choice_is_exported_so_a_caller_does_not_guess() -> None:
    arguments = _arguments(_detailed("output_path"))

    assert arguments["scope"]["choices"] == ["session", "workspace"]


def test_the_long_form_names_the_option_and_the_short_one_is_an_alias() -> None:
    """No Che command declares a short option today, so the rule is asserted on a parser that does.

    `-h`/`--help` is deliberately not the example: it is filtered out of the argument list, because
    listing it as an argument of all 44 commands would be noise dressed as information.
    """
    probe = argparse.ArgumentParser(prog="probe")
    probe.add_argument("-o", "--output", help="where to write")

    described = _describe_arguments(probe)

    assert described[0]["name"] == "--output"
    assert described[0]["aliases"] == ["-o"]


def test_a_mutually_exclusive_set_is_exported_because_a_caller_must_pick_one() -> None:
    """`pixel check` needs exactly one of `--design` / `--design-source`; argparse knows, callers do not."""
    check = _detailed("pixel check")

    assert check["mutually_exclusive"] == [{"required": True, "one_of": ["--design", "--design-source"]}]


def test_an_alias_is_reported_against_its_canonical_name() -> None:
    """argparse registers aliases as extra keys; a caller should see one command with two other names."""
    commands = _commands()

    assert commands["project create"]["aliases"] == ["add", "init"]
    assert commands["update"]["aliases"] == ["self-update", "upgrade"]
    assert "add" not in commands, "an alias must not appear as a command of its own"


# ---------------------------------------------------------------------------------------------
# Compact by default, detailed on request
# ---------------------------------------------------------------------------------------------


def test_the_default_omits_arguments_and_errors() -> None:
    """The default answers "what can I do?"; the arguments are needed one command at a time."""
    manifest = build_manifest(build_parser())

    assert "errors" not in manifest
    assert all("arguments" not in command for command in manifest["commands"])


def test_asking_for_a_command_adds_its_arguments_and_the_failure_catalogue_is_opt_in() -> None:
    manifest = build_manifest(build_parser(), include_arguments=True, include_errors=True)

    assert all("arguments" in command for command in manifest["commands"])
    assert len(manifest["errors"]) == len(ERROR_CATALOG)


def test_the_failure_catalogue_is_the_one_the_runner_uses() -> None:
    """Exported, not re-declared: a code the CLI can raise must be a code the manifest names."""
    errors = {entry["code"] for entry in build_manifest(build_parser(), include_errors=True)["errors"]}

    assert errors == set(ERROR_CATALOG)


def test_the_exit_code_table_names_every_code_the_cli_uses() -> None:
    codes = {entry["code"] for entry in EXIT_CODES}

    assert {0, 1, 2, 3, 99} <= codes, "the codes raised by che_core itself must all be named"
    assert all(entry["meaning"].strip() for entry in EXIT_CODES)


def test_find_command_accepts_a_name_or_an_alias() -> None:
    manifest = build_manifest(build_parser())

    assert find_command(manifest, "worktree add")["name"] == "worktree add"
    assert find_command(manifest, "add")["name"] == "project create"
    assert find_command(manifest, "nope") is None


# ---------------------------------------------------------------------------------------------
# The CLI surface itself
# ---------------------------------------------------------------------------------------------


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "che_core.cli", *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(CHE_ROOT),
    )


def test_the_command_is_reachable_and_prints_json_on_request() -> None:
    result = _cli("capabilities", "--json")

    assert result.returncode == 0, result.stderr
    manifest = json.loads(result.stdout)
    assert {"global_options", "exit_codes", "commands"} <= set(manifest)


def test_narrowing_to_one_command_keeps_the_shape() -> None:
    """`--command` filters; it does not return a different kind of document."""
    result = _cli("capabilities", "--json", "--command", "worktree add")

    assert result.returncode == 0, result.stderr
    manifest = json.loads(result.stdout)
    assert [command["name"] for command in manifest["commands"]] == ["worktree add"]
    assert "exit_codes" in manifest


def test_an_unknown_command_is_a_catalogued_failure() -> None:
    result = _cli("--json", "capabilities", "--command", "worktree destroy")

    assert result.returncode == 2
    assert json.loads(result.stdout)["code"] == "UNKNOWN_COMMAND"


def test_the_human_list_names_every_command_with_its_summary() -> None:
    result = _cli("capabilities")

    assert result.returncode == 0, result.stderr
    assert "worktree add" in result.stdout
    assert "Bind a git checkout to a project" in result.stdout
