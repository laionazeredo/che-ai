"""Contract tests for the MCP adapter.

The adapter is generated from the manifest (ADR-0003), so there are only two things to hold it to:
the generation is faithful — every tool the client sees is a command that exists, with the schema the
parser actually declares — and the protocol answers every request with valid JSON-RPC, including the
ones it refuses. What each command *does* is not this module's business; the CLI's own tests cover it.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Mapping

import pytest

from che_core.cli import build_parser
from che_core.manifest import build_manifest
from che_core.mcp_server import (
    DEFAULT_PROTOCOL,
    SUPPORTED_PROTOCOLS,
    InvalidArguments,
    Surface,
    _argv_for,
    _call,
    reply_to,
    serve,
    tool_name,
)

CHE_ROOT = Path(__file__).resolve().parent.parent

#: The character set MCP allows in a tool name, and its length ceiling.
TOOL_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@pytest.fixture(scope="module")
def surface() -> Surface:
    return Surface()


def _tools(surface: Surface) -> Dict[str, Dict[str, Any]]:
    return {tool["name"]: tool for tool in surface.tools}


def _schema(surface: Surface, name: str) -> Dict[str, Any]:
    return _tools(surface)[name]["inputSchema"]


def _commands() -> Dict[str, Dict[str, Any]]:
    return {command["name"]: command for command in build_manifest(build_parser())["commands"]}


def _reply(surface: Surface, payload: Mapping[str, Any]) -> Dict[str, Any]:
    return reply_to(json.dumps(payload), surface)


def _argv(surface: Surface, name: str, values: Mapping[str, Any]) -> list:
    return _argv_for(surface.commands[name], values)


# ---------------------------------------------------------------------------------------------
# The tools are the commands
# ---------------------------------------------------------------------------------------------


def test_the_tools_are_the_commands_the_cli_has(surface: Surface) -> None:
    """Generated, not declared: a command added to the parser appears here with no edit to this module."""
    expected = {tool_name(name) for name, command in _commands().items() if command["output"] != "stream"}

    assert set(_tools(surface)) == expected
    assert len(expected) > 40


def test_the_server_does_not_offer_itself_as_a_tool(surface: Surface) -> None:
    """`che mcp serve` never returns, so a client that called it would be talking to itself."""
    assert _commands()["mcp serve"]["output"] == "stream"
    assert tool_name("mcp serve") not in _tools(surface)


def test_every_tool_name_is_unique_and_one_the_protocol_accepts(surface: Surface) -> None:
    """A collision would silently drop a command: the tool list is indexed by name."""
    names = [tool["name"] for tool in surface.tools]

    assert len(names) == len(set(names))
    assert all(TOOL_NAME.match(name) for name in names), names


def test_every_tool_carries_a_description_and_an_object_schema(surface: Surface) -> None:
    for tool in surface.tools:
        assert tool["description"].strip(), tool["name"]
        assert tool["inputSchema"]["type"] == "object", tool["name"]


# ---------------------------------------------------------------------------------------------
# The schema is the parser
# ---------------------------------------------------------------------------------------------


def test_a_mandatory_argument_is_mandatory_in_the_schema(surface: Surface) -> None:
    """`worktree add` needs a repo path and two options; a schema that let them slide is a broken call."""
    schema = _schema(surface, "worktree_add")

    assert schema["required"] == ["repo_path", "project", "name"]
    assert schema["additionalProperties"] is False


def test_a_command_with_no_arguments_still_has_a_schema(surface: Surface) -> None:
    assert _schema(surface, "project_list") == {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }


def test_a_list_argument_becomes_an_array(surface: Surface) -> None:
    """`--bind` is `nargs='*'`; calling it a string would send one token where many belong."""
    bind = _schema(surface, "state_query")["properties"]["bind"]

    assert bind["type"] == "array"
    assert bind["items"] == {"type": "string"}


def test_a_choice_is_carried_into_the_schema(surface: Surface) -> None:
    scope = _schema(surface, "output_path")["properties"]["scope"]

    assert scope["enum"] == ["session", "workspace"]


def test_a_flag_is_a_boolean_with_its_default(surface: Surface) -> None:
    force = _schema(surface, "worktree_add")["properties"]["force"]

    assert force["type"] == "boolean"
    assert force["default"] is False


def test_a_flag_that_is_on_by_default_says_so(surface: Surface) -> None:
    """`--dry-run` cannot be turned off by passing `false`, so the schema must warn before the call."""
    dry_run = _schema(surface, "worktree_remove")["properties"]["dry_run"]

    assert "On by default" in dry_run["description"]


def test_the_worktree_requirement_reaches_the_description(surface: Surface) -> None:
    """Nothing in the schema says a path must already be bound, and the CLI fails without one."""
    assert "bound" in _tools(surface)["task_list"]["description"]


def test_a_mutating_tool_is_not_annotated_read_only(surface: Surface) -> None:
    tools = _tools(surface)

    assert tools["task_list"]["annotations"]["readOnlyHint"] is True
    assert tools["worktree_add"]["annotations"]["readOnlyHint"] is False


def test_a_command_that_reads_stdin_gets_a_required_stdin_property(surface: Surface) -> None:
    """Without it the tool would write an empty file and report success."""
    schema = _schema(surface, "write_file_atomic")

    assert schema["properties"]["stdin"]["type"] == "string"
    assert "stdin" in schema["required"]


# ---------------------------------------------------------------------------------------------
# Arguments, back to argv
# ---------------------------------------------------------------------------------------------


def test_positionals_keep_the_order_the_parser_declares(surface: Surface) -> None:
    """argparse assigns positionals by position, so a rebuilt argv has to preserve it."""
    argv = _argv(
        surface,
        "output_path",
        {"type": "spec", "slug": "s", "related_id": "r", "scope": "session", "ext": "md"},
    )

    assert argv == ["output_path", "spec", "s", "r", "session", "md"]


def test_an_option_travels_with_its_value(surface: Surface) -> None:
    argv = _argv(surface, "worktree_add", {"repo_path": "/tmp/x", "project": "p", "name": "n", "force": True})

    assert argv == ["worktree", "add", "/tmp/x", "--project", "p", "--name", "n", "--force"]


def test_a_list_argument_becomes_several_tokens(surface: Surface) -> None:
    argv = _argv(surface, "state_query", {"sql": "SELECT 1", "bind": ["a", "b"]})

    assert argv == ["state", "query", "--sql", "SELECT 1", "--bind", "a", "b"]


def test_a_flag_is_left_out_when_it_is_not_asked_for(surface: Surface) -> None:
    argv = _argv(surface, "worktree_add", {"repo_path": "/tmp/x", "project": "p", "name": "n", "force": False})

    assert "--force" not in argv


def test_an_argument_the_command_does_not_have_is_refused(surface: Surface) -> None:
    """Dropping it silently would run a different command than the caller asked for."""
    with pytest.raises(InvalidArguments, match="no argument"):
        _call(surface, {"name": "capabilities", "arguments": {"verbose": True}})


def test_a_flag_that_is_on_by_default_cannot_be_turned_off_by_asking_for_false(surface: Surface) -> None:
    """Leaving the flag out keeps it on, so `false` would be answered with `true`."""
    with pytest.raises(InvalidArguments) as caught:
        _call(
            surface,
            {
                "name": "worktree_remove",
                "arguments": {"project_slug": "p", "worktree_name": "w", "dry_run": False},
            },
        )

    assert "no_dry_run" in str(caught.value), "the refusal must name the flag that can turn it off"


def test_an_unknown_tool_is_invalid_params(surface: Surface) -> None:
    with pytest.raises(InvalidArguments, match="no such tool"):
        _call(surface, {"name": "worktree_destroy", "arguments": {}})


# ---------------------------------------------------------------------------------------------
# The protocol
# ---------------------------------------------------------------------------------------------


def test_initialize_echoes_a_protocol_the_server_can_speak(surface: Surface) -> None:
    reply = _reply(
        surface,
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
    )

    assert reply["result"]["protocolVersion"] == "2025-06-18"
    assert reply["result"]["serverInfo"]["name"] == "che"
    assert reply["result"]["serverInfo"]["version"]


def test_an_unsupported_protocol_falls_back_to_one_it_does_speak(surface: Surface) -> None:
    reply = _reply(
        surface,
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}},
    )

    assert reply["result"]["protocolVersion"] == DEFAULT_PROTOCOL
    assert DEFAULT_PROTOCOL in SUPPORTED_PROTOCOLS


def test_a_notification_is_not_answered(surface: Surface) -> None:
    """JSON-RPC forbids replying to a request with no id, and `notifications/initialized` is one."""
    assert _reply(surface, {"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_an_unknown_method_is_method_not_found(surface: Surface) -> None:
    reply = _reply(surface, {"jsonrpc": "2.0", "id": 7, "method": "tools/destroy"})

    assert reply["error"]["code"] == -32601


def test_a_line_that_is_not_json_is_a_parse_error_with_a_null_id(surface: Surface) -> None:
    """There is no request to attribute it to, and the loop has to survive to read the next line."""
    reply = reply_to("{not json", surface)

    assert reply["error"]["code"] == -32700
    assert reply["id"] is None


def test_a_request_that_is_not_an_object_is_refused(surface: Surface) -> None:
    assert reply_to("[1, 2]", surface)["error"]["code"] == -32600


def test_a_blank_line_is_skipped_and_one_request_is_one_reply() -> None:
    """A stray print anywhere in the server would corrupt the stream, so the output is counted."""
    stdin = StringIO('\n{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n\n')
    stdout = StringIO()

    serve(stdin, stdout)

    lines = [line for line in stdout.getvalue().splitlines() if line.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["id"] == 1


# ---------------------------------------------------------------------------------------------
# A call runs the CLI
# ---------------------------------------------------------------------------------------------


def test_a_call_returns_the_payload_the_cli_printed(surface: Surface) -> None:
    """`output_path` prints a bare path by default; the object here proves `--json` was passed."""
    result = _call(
        surface,
        {
            "name": "output_path",
            "arguments": {"type": "spec", "slug": "probe", "related_id": "mcp", "scope": "session", "ext": "md"},
        },
    )

    assert result["isError"] is False
    assert result["structuredContent"]["result"]["path"].endswith(".md")


def test_a_che_failure_is_an_error_that_still_parses(surface: Surface) -> None:
    """The envelope is the point of `--json` on the failure path (ADR-0004): keep it structured."""
    result = _call(surface, {"name": "registry_lookup", "arguments": {"session_id": "no-such-session"}})

    assert result["isError"] is True
    assert result["structuredContent"]["result"]["code"] == "NO_REGISTRY_ENTRY"


def test_a_usage_error_reaches_the_caller_as_text(surface: Surface) -> None:
    """argparse exits before any envelope exists, so its usage line is all there is to forward."""
    result = _call(
        surface,
        {
            "name": "output_path",
            "arguments": {"type": "spec", "slug": "s", "related_id": "r", "scope": "nonsense", "ext": "md"},
        },
    )

    assert result["isError"] is True
    assert "usage: che" in result["content"][0]["text"]


def test_stdin_reaches_the_command(surface: Surface, tmp_path: Path) -> None:
    target = tmp_path / "written.txt"

    result = _call(
        surface,
        {"name": "write_file_atomic", "arguments": {"target": str(target), "stdin": "payload\n"}},
    )

    assert result["isError"] is False, result["content"]
    assert target.read_text(encoding="utf-8") == "payload\n"


def test_the_server_answers_over_a_real_pipe() -> None:
    """The transport is stdio, so what is worth proving is that it works and ends when the pipe closes."""
    requests = (
        "\n".join(
            [
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
                json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
            ]
        )
        + "\n"
    )

    completed = subprocess.run(
        [sys.executable, "-m", "che_core.cli", "mcp", "serve"],
        input=requests,
        capture_output=True,
        text=True,
        check=False,
        cwd=str(CHE_ROOT),
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    replies = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    assert [reply["id"] for reply in replies] == [1, 2]
    assert len(replies[1]["result"]["tools"]) > 40
