"""The CLI surface, spoken as a Model Context Protocol server.

WHY THIS EXISTS
---------------
``che capabilities --json`` (ADR-0003) made the surface readable; ADR-0004 made ``--json`` govern
stdout on success and on failure alike. This module spends both. It walks the same manifest and
answers it as MCP tools, so a command added to ``build_parser`` becomes a tool with no edit here, and
a flag that changes type cannot drift between the CLI and the schema a client sees.

HOW A CALL RUNS
---------------
``tools/call`` is translated back into the argv a human would have typed, and run as a child process
through the same entry point: ``python -m che_core.cli --json <command> ...``. Spawning rather than
importing is deliberate. The CLI already owns its failure rendering, its exit codes and its
``sys.exit`` calls; a subprocess inherits all three instead of a second implementation of each, and a
tool that crashes cannot take the server down with it.

``--json`` is always passed, which is what makes the child's stdout a parseable payload on success and
a parseable envelope on failure. Its exit code becomes ``isError``. Its stdout becomes the text block
and, wrapped under ``result``, the structured content — wrapped because MCP requires
``structuredContent`` to be an object and several Che commands return a list.

TRANSPORT
---------
Newline-delimited JSON-RPC 2.0 over stdin/stdout, which is what MCP calls ``stdio``. There is no port
and no daemon: the client launches ``che mcp serve`` as a child and speaks over the pipe it already
owns. When the client goes away the pipe closes and this loop ends, so there is no process to leak and
nothing to restart.
"""

from __future__ import annotations

import json
import subprocess
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from typing import Any, Dict, List, Mapping, Optional, Sequence, TextIO

from che_core.cli import build_parser
from che_core.manifest import build_manifest

#: The revisions this server can answer. ``initialize``, ``tools/list`` and ``tools/call`` are
#: identical across all of them — ``structuredContent`` arrived in 2025-06-18 and is additive, and
#: 2026-07-28 replaced the handshake outright, so it is deliberately not in this list. The client's
#: own version is echoed when it is one of these, because a client that asked for a revision it
#: supports is better served by being answered in it than by being talked down to.
SUPPORTED_PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
DEFAULT_PROTOCOL = "2025-06-18"

SERVER_NAME = "che"

#: JSON Schema type for each type name the manifest exports.
_JSON_TYPES = {"str": "string", "int": "integer", "float": "number", "boolean": "boolean"}

_PARSE_ERROR = -32700
_INVALID_REQUEST = -32600
_METHOD_NOT_FOUND = -32601
_INVALID_PARAMS = -32602
_INTERNAL_ERROR = -32603


class InvalidArguments(Exception):
    """A call this adapter cannot honour.

    Reported as JSON-RPC ``invalid params`` rather than as a tool failure: the arguments never
    reached Che, so there is no Che failure to report, and dressing it up as one would send the
    caller looking for a catalogue entry that does not exist.
    """


class UnknownMethod(Exception):
    """A JSON-RPC method this server does not implement."""


# --- the surface, as tools ------------------------------------------------------------------------


def tool_name(command_name: str) -> str:
    """`worktree add` -> `worktree_add`. MCP allows ``[A-Za-z0-9_-]``; Che's own names use both."""
    return command_name.replace(" ", "_").replace("-", "_")


def _property_name(argument: Mapping[str, Any]) -> str:
    """`--worktree-root` -> `worktree_root`. A positional keeps the name it already has.

    Keyed by the flag rather than by its ``dest``, because two flags can share one ``dest``: a
    ``--dry-run`` / ``--apply`` pair writes to the same variable, and a schema that collapsed them
    would offer a single property that cannot express both requests.
    """
    return argument["name"].lstrip("-").replace("-", "_")


def _is_on_by_default(argument: Mapping[str, Any]) -> bool:
    """A flag whose presence stores True and whose absence already leaves True — ``--dry-run``.

    Both halves matter. ``--apply`` also stores into ``dry_run`` with default True, but it stores
    *False*, so omitting it does not leave the setting on.
    """
    return argument["type"] == "boolean" and argument.get("const") is True and argument.get("default") is True


def _schema_for(argument: Mapping[str, Any]) -> Dict[str, Any]:
    """One argument, as a JSON Schema property."""
    item: Dict[str, Any] = {"type": _JSON_TYPES.get(argument["type"], "string")}
    if "choices" in argument:
        item["enum"] = list(argument["choices"])

    nargs = argument.get("nargs")
    if nargs in ("*", "+") or isinstance(nargs, int):
        schema: Dict[str, Any] = {"type": "array", "items": item}
        if nargs == "+":
            schema["minItems"] = 1
        elif isinstance(nargs, int):
            schema["minItems"] = nargs
            schema["maxItems"] = nargs
    else:
        schema = dict(item)

    if "default" in argument:
        schema["default"] = argument["default"]
    description = argument.get("help", "")
    if _is_on_by_default(argument):
        # The one place the schema has to warn: `false` here is a request the flag cannot answer.
        note = "On by default; omitting it keeps it on."
        description = f"{description} {note}".strip()
    if description:
        schema["description"] = description
    return schema


def _tool_spec(command: Mapping[str, Any]) -> Dict[str, Any]:
    """One command, as an MCP tool."""
    properties: Dict[str, Any] = {}
    required: List[str] = []
    for argument in command.get("arguments", []):
        name = _property_name(argument)
        properties[name] = _schema_for(argument)
        if argument["required"]:
            required.append(name)

    if command["stdin"]:
        # A payload with no flag to carry it. Required, because an empty write that reports success
        # is worse than a refusal.
        properties["stdin"] = {"type": "string", "description": "Written to the command on stdin."}
        required.append("stdin")

    schema: Dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required

    return {
        "name": tool_name(command["name"]),
        "description": _description(command),
        "inputSchema": schema,
        "annotations": {"readOnlyHint": not command["mutates"]},
    }


def _description(command: Mapping[str, Any]) -> str:
    """What the tool does, plus the two consequences a caller cannot infer from the schema.

    The declared output shape is deliberately *not* mentioned: every call runs with ``--json``, so
    the default shape a human would see on stdout is not the shape this caller will get.
    """
    parts = [command["summary"] or command["name"]]
    if command["mutates"]:
        parts.append("Changes state on disk.")
    if command["requires_bound_worktree"]:
        parts.append("Needs a worktree already bound with `worktree add`.")
    return " ".join(parts)


class Surface:
    """The tool list, and the argv recipe behind each tool. Built once, at startup."""

    def __init__(self) -> None:
        manifest = build_manifest(build_parser(), include_arguments=True)
        self.tools: List[Dict[str, Any]] = []
        self.commands: Dict[str, Dict[str, Any]] = {}
        for command in manifest["commands"]:
            if command["output"] == "stream":
                # A protocol that does not return is not a tool. `che mcp serve` is the only one, and
                # listing it would invite a client to call the server into itself.
                continue
            name = tool_name(command["name"])
            self.tools.append(_tool_spec(command))
            self.commands[name] = command


# --- arguments, back to argv ----------------------------------------------------------------------


def _tokens(value: Any) -> List[str]:
    """One token per value, or one per element when the argument takes a list."""
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


def _append_flag(
    argv: List[str], argument: Mapping[str, Any], value: Any, arguments: Sequence[Mapping[str, Any]]
) -> None:
    """A boolean property means "pass this flag", which stores whatever ``const`` says."""
    if value:
        argv.append(argument["name"])
        return
    if not _is_on_by_default(argument):
        # Omitting it leaves the setting where the caller asked for it.
        return
    counterpart = next(
        (
            other
            for other in arguments
            if other is not argument and other.get("dest") == argument.get("dest") and other.get("const") is False
        ),
        None,
    )
    # Refusing beats planning a dry run and reporting success: leaving the flag out keeps it on, so
    # `false` would be answered with `true`. The way to turn it off is the paired flag.
    remedy = f"Pass `{_property_name(counterpart)}` to turn it off." if counterpart else "No flag turns it off."
    raise InvalidArguments(f"`{_property_name(argument)}` is on by default, so omitting it keeps it on. {remedy}")


def _argv_for(command: Mapping[str, Any], values: Mapping[str, Any]) -> List[str]:
    """Rebuild the argv a caller would have typed, from the tool's arguments."""
    arguments = command.get("arguments", [])
    known = {_property_name(argument) for argument in arguments}
    if command["stdin"]:
        known.add("stdin")
    unknown = sorted(set(values) - known)
    if unknown:
        raise InvalidArguments(f"`{command['name']}` has no argument(s): {', '.join(unknown)}")

    argv = list(command["name"].split())
    for argument in arguments:
        value = values.get(_property_name(argument))
        if value is None:
            continue
        if argument["kind"] == "positional":
            argv.extend(_tokens(value))
        elif argument["type"] == "boolean":
            _append_flag(argv, argument, value, arguments)
        else:
            argv.append(argument["name"])
            argv.extend(_tokens(value))
    return argv


# --- running a tool -------------------------------------------------------------------------------


def _as_json(text: str) -> Optional[Any]:
    """The payload on stdout, or ``None`` when the command printed nothing parseable."""
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def _run(argv: Sequence[str], stdin: Optional[str]) -> Dict[str, Any]:
    """Run one Che command and report it the way MCP expects a tool result."""
    completed = subprocess.run(
        [sys.executable, "-m", "che_core.cli", "--json", *argv],
        # Always a pipe, never the inherited stdin: the server's own stdin is the protocol stream,
        # and a command that read from it would swallow the next request.
        input="" if stdin is None else stdin,
        capture_output=True,
        text=True,
        check=False,
    )
    result: Dict[str, Any] = {
        # A command that failed before argparse reached it — a bad `choices` value, a missing
        # positional — writes its usage to stderr and exits, leaving stdout empty. Sending an empty
        # first block would hide the only explanation the caller is going to get.
        "content": [{"type": "text", "text": text} for text in (completed.stdout, completed.stderr) if text.strip()],
        "isError": completed.returncode != 0,
    }
    if not result["content"]:
        result["content"] = [{"type": "text", "text": ""}]
    payload = _as_json(completed.stdout)
    if payload is not None:
        result["structuredContent"] = {"result": payload}
    return result


def _call(surface: Surface, params: Mapping[str, Any]) -> Dict[str, Any]:
    name = params.get("name")
    if not isinstance(name, str):
        raise InvalidArguments("`name` is required and must be a string")
    command = surface.commands.get(name)
    if command is None:
        raise InvalidArguments(f"no such tool: {name}")
    values = params.get("arguments")
    if values is None:
        values = {}
    if not isinstance(values, Mapping):
        raise InvalidArguments("`arguments` must be an object")

    argv = _argv_for(command, values)
    return _run(argv, values.get("stdin") if command["stdin"] else None)


# --- the protocol ---------------------------------------------------------------------------------


def _initialize(params: Mapping[str, Any]) -> Dict[str, Any]:
    requested = params.get("protocolVersion")
    return {
        "protocolVersion": requested if requested in SUPPORTED_PROTOCOLS else DEFAULT_PROTOCOL,
        "capabilities": {"tools": {}},
        "serverInfo": {"name": SERVER_NAME, "version": _server_version()},
    }


def _server_version() -> str:
    """Che's version, read from the installed distribution. A source checkout has no other record."""
    try:
        return package_version("che-ai")
    except PackageNotFoundError:
        return "unknown"


def _dispatch(method: str, params: Mapping[str, Any], surface: Surface) -> Any:
    if method == "initialize":
        return _initialize(params)
    if method == "tools/list":
        return {"tools": surface.tools}
    if method == "tools/call":
        return _call(surface, params)
    if method == "ping":
        return {}
    raise UnknownMethod(method)


def _error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def reply_to(line: str, surface: Surface) -> Optional[Dict[str, Any]]:
    """The reply to one line of input, or ``None`` when the line needs no reply.

    Notifications — requests with no ``id`` — must not be answered, and an unknown notification is
    not an error worth raising. A reply is always a JSON-RPC object: this server never ends a request
    with a traceback, because a client that cannot parse the stream loses the session.
    """
    try:
        request = json.loads(line)
    except json.JSONDecodeError as exc:
        return _error(None, _PARSE_ERROR, f"not JSON: {exc}")

    if not isinstance(request, dict):
        return _error(None, _INVALID_REQUEST, "a request must be a JSON object")

    request_id = request.get("id")
    is_notification = "id" not in request
    method = request.get("method")
    if not isinstance(method, str):
        if is_notification:
            return None
        return _error(request_id, _INVALID_REQUEST, "`method` is required and must be a string")

    params = request.get("params")
    if params is None:
        params = {}
    if not isinstance(params, Mapping):
        if is_notification:
            return None
        return _error(request_id, _INVALID_PARAMS, "`params` must be an object")

    try:
        result = _dispatch(method, params, surface)
    except UnknownMethod:
        if is_notification:
            return None
        return _error(request_id, _METHOD_NOT_FOUND, f"no such method: {method}")
    except InvalidArguments as exc:
        if is_notification:
            return None
        return _error(request_id, _INVALID_PARAMS, str(exc))
    except Exception as exc:  # the last resort is the whole point: the stream must stay valid
        if is_notification:
            return None
        return _error(request_id, _INTERNAL_ERROR, f"{type(exc).__name__}: {exc}")

    if is_notification:
        return None
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def serve(stdin: Optional[TextIO] = None, stdout: Optional[TextIO] = None) -> None:
    """Read requests until the pipe closes. Streams are injectable so a test need not spawn a process."""
    surface = Surface()
    reader = sys.stdin if stdin is None else stdin
    writer = sys.stdout if stdout is None else stdout
    for line in reader:
        if not line.strip():
            continue
        reply = reply_to(line, surface)
        if reply is not None:
            writer.write(json.dumps(reply, ensure_ascii=False) + "\n")
            writer.flush()
