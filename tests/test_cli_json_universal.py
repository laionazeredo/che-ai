"""The global `--json` governs stdout on both channels (ADR-0004).

The contract is narrower than "always JSON" and that is deliberate: `output` in the manifest keeps
describing the default, flag-less shape, and `--json` replaces it with a JSON value wherever the
command renders something. So the tests here come in two halves — the renderer, which is where the
choice is made, and the end-to-end routing, which is what an agent actually depends on.
"""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from che_core.cli import _wants_json, main
from che_core.output import emit_mapping, print_json


def _stdout(capsys) -> str:
    return capsys.readouterr().out


# --------------------------------------------------------------------------------------------
# One question, one answer
# --------------------------------------------------------------------------------------------


def test_the_global_flag_asks_for_machine_output():
    """`che --json <command>` is the form every command has to answer."""
    assert _wants_json(Namespace(json_global=True)) is True


def test_a_commands_own_flag_asks_the_same_question():
    """The per-command flags predate the global one; they must not be a second answer."""
    assert _wants_json(Namespace(json_global=False, json_out=True)) is True
    assert _wants_json(Namespace(json_global=False, json=True)) is True


def test_a_command_with_no_flag_of_its_own_can_still_be_asked():
    """`compute_paths` and `output_path` have no `--json` of their own, only the global one.

    The namespace is empty on purpose: reading `args.json_out` here would be an AttributeError, so
    the helper has to tolerate a command that never declared the flag.
    """
    assert _wants_json(Namespace()) is False
    assert _wants_json(Namespace(json_global=True)) is True


def test_neither_flag_means_no():
    assert _wants_json(Namespace(json_global=False, json_out=False, json=False)) is False


# --------------------------------------------------------------------------------------------
# The renderer
# --------------------------------------------------------------------------------------------


def test_a_mapping_renders_as_export_lines_by_default(capsys):
    """The `eval "$(che compute_paths …)"` contract: shell-quoted, no JSON anywhere."""
    emit_mapping({"CHE_PROJECT_SLUG": "acme"}, as_json=False, shell=True)

    assert _stdout(capsys) == 'export CHE_PROJECT_SLUG="acme"\n'


def test_a_mapping_renders_as_kv_lines_when_not_shell(capsys):
    emit_mapping({"CHE_DESIGN_DIR": "/tmp/design"}, as_json=False)

    assert _stdout(capsys) == "CHE_DESIGN_DIR=/tmp/design\n"


def test_a_mapping_renders_as_json_when_asked(capsys):
    payload = {"CHE_DESIGN_MD": "/tmp/design/DESIGN.md", "CHE_TOKENS_STYLES_CSS": "/tmp/t.css"}

    emit_mapping(payload, as_json=True, shell=True)

    # Round-tripped rather than string-compared: the contract is the value, not the indentation.
    assert json.loads(_stdout(capsys)) == payload


def test_the_json_renderer_survives_a_path(capsys):
    """A `Path` in a payload must not turn into a TypeError — every one of these is a path."""
    print_json({"path": Path("/tmp/x")})

    assert json.loads(_stdout(capsys)) == {"path": "/tmp/x"}


# --------------------------------------------------------------------------------------------
# The contract, end to end — through the real entrypoint
# --------------------------------------------------------------------------------------------


def test_the_global_flag_reaches_argparse():
    """Regression: `main` used to strip `--json` before parsing, so `args.json_global` was always
    False and the flag could only ever shape the failure channel. Nothing else in the CLI could see
    it, which is why the success shapes never honoured it."""
    from che_core.cli import build_parser

    assert build_parser().parse_args(["--json", "capabilities"]).json_global is True


def test_the_discovery_command_honours_the_global_flag(capsys):
    main(["--json", "capabilities"])

    assert "commands" in json.loads(_stdout(capsys))


def test_the_discovery_command_still_prints_prose_without_the_flag(capsys):
    """The human form is the default, and it stays the default."""
    main(["capabilities"])

    out = _stdout(capsys)
    assert out.startswith("capabilities\n")
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)


def test_a_bare_path_becomes_an_object(capsys):
    main(["--json", "output_path", "spec", "my-project", "rel-1", "session", "md"])

    payload = json.loads(_stdout(capsys))
    assert set(payload) == {"path"}
    assert payload["path"].endswith(".md")


def test_a_shell_contract_becomes_json_only_when_asked(bound_worktree, capsys):
    """The whole reason this change is safe: the default is untouched, so the ~30 recipes that do
    `eval "$(che compute_paths …)"` keep working — none of them passes `--json`."""
    repo, _paths = bound_worktree

    main(["compute_paths", str(repo), "test-session"])
    default = _stdout(capsys)
    assert default.startswith('export CHE_PROJECT_SLUG="acme"\n')

    main(["--json", "compute_paths", str(repo), "test-session"])
    as_json = json.loads(_stdout(capsys))

    # Same payload, two shapes: the keys an `eval` would have exported are the keys of the object.
    exported = {line.split("=", 1)[0].removeprefix("export ") for line in default.strip().splitlines()}
    assert set(as_json) == exported


def test_the_forwarded_sub_cli_answers_the_same_question(tmp_path, capsys):
    """`che designer …` is forwarded before argparse, so the flag has to travel with it."""
    design_md = tmp_path / "DESIGN.md"
    sections = (
        "Overview",
        "Colors",
        "Typography",
        "Layout",
        "Elevation & Depth",
        "Shapes",
        "Components",
        "Do's and Don'ts",
    )
    body = "\n".join(f"## {name}\n\nx\n" for name in sections)
    design_md.write_text(f"---\nname: x\n---\n\n{body}", encoding="utf-8")

    # `designer validate` exits with its verdict, 0 included — so both calls raise SystemExit.
    with pytest.raises(SystemExit) as first:
        main(["designer", "validate", str(design_md)])
    assert first.value.code == 0
    assert _stdout(capsys).startswith("errors=0")

    with pytest.raises(SystemExit) as second:
        main(["--json", "designer", "validate", str(design_md)])
    assert second.value.code == 0

    payload = json.loads(_stdout(capsys))
    assert payload == {"errors": 0, "issues": [], "sections": list(sections)}


def test_a_failure_still_renders_as_the_envelope(capsys):
    """The failure channel is what `--json` already did; making the success path honour the flag
    must not disturb it."""
    with pytest.raises(SystemExit) as exc:
        main(["--json", "capabilities", "--command", "worktree destroy"])

    assert exc.value.code == 2
    envelope = json.loads(_stdout(capsys))
    assert envelope["code"] == "UNKNOWN_COMMAND"
