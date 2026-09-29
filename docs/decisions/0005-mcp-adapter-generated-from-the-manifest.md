# ADR-0005: the MCP adapter is generated from the manifest, and runs the CLI as a child

- Status: Accepted
- Date: 2026-09-25
- Area: CLI surface / agent integration
- Follows: ADR-0003 (the CLI surface is data), ADR-0004 (global `--json` governs both channels)

## Context

ADR-0003 made the surface readable and ended with "the MCP adapter, when it lands, is generated from
this same walk". ADR-0004 made `--json` govern stdout on success and on failure alike, which is what
makes a tool call parseable at all. Both were prerequisites; this is the thing they were for.

One objection decides the design, so it is answered first: **does an MCP server mean Che now has a
daemon to run and keep alive?** No. MCP's `stdio` transport has no port and no listener — the client
launches `che mcp serve` as a child process and speaks over the pipe it already owns. When the client
exits, the pipe closes and the loop ends. There is nothing to supervise, nothing to restart, and no
state that outlives a session. A server that "falls over" is a child that exited, and the client
reports it the way it reports any failed tool.

## Decision

1. **The tool list is the manifest.** `Surface()` walks `build_manifest(build_parser(),
   include_arguments=True)` — the same call behind `che capabilities --json --command …` — and turns
   each command into a tool. Nothing is declared by hand, so a command added to `build_parser` is a
   tool on the next start, and a flag that changes type cannot drift between the CLI and the schema a
   client sees.
2. **`tools/call` runs the CLI as a child process**, as `python -m che_core.cli --json <command> …`.
   Not an import: the CLI already owns its failure rendering, its exit codes and its `sys.exit` sites,
   and a subprocess inherits all three instead of needing a second implementation of each. It also
   means a tool that crashes cannot take the server down with it.
3. **`--json` is always passed, and the exit code becomes `isError`.** This is why ADR-0004 had to
   land first: without it, half the commands would answer a tool call in prose.
4. **`structuredContent` is the payload, wrapped under `result`.** MCP requires
   `structuredContent` to be an object, and `task list` and `state search` return lists. One wrapper
   beats a shape that changes with the command.
5. **The schema is a projection of argparse, not a second opinion.** `type` maps to a JSON Schema
   type, `nargs` to an array, `choices` to `enum`, `required` to `required`,
   `additionalProperties: false`. Three manifest fields were added to make that projection possible
   (below).
6. **A command that does not return is not a tool.** `che mcp serve` declares `output: "stream"` and
   the adapter leaves those out — read from the manifest, so the exclusion is a consequence of the
   declaration rather than a list to maintain.

## Rationale

- **The server is a second *view*, never a second *implementation*.** Everything an MCP client can do,
  a shell can do with the same argv. That is what makes the adapter safe to add: it cannot become the
  only route to a behaviour, and removing it costs nothing.
- **A process per call is the right trade.** Calling in-process would be faster, and would also mean
  re-implementing `diagnosed`, the exit codes and the stdout discipline — three things the CLI's own
  tests already pin. The cost is a process launch per tool call, on an interface whose other end is a
  language model.
- **Refusals over guesses.** Three cases would otherwise return a *silently wrong* result, so each is
  refused with a message that names the remedy:
  - an argument the command does not have — dropping it runs a different command than the caller
    described;
  - `false` for a flag that is on by default (`--dry-run`) — leaving it out keeps it *on*, so `false`
    would be answered with `true`; the refusal names the paired flag that turns it off;
  - `write_file_atomic` with no `stdin` — an empty write reported as a success.
- **Usage text names the program, not the launcher.** The parser sets `prog="che"`, because the
  adapter reaches it as `python -m che_core.cli` and would otherwise forward `usage: cli.py …` to a
  caller who never typed that.

## Consequences

- **New module `che_core/mcp_server.py`; new command `che mcp serve`** — the first command whose
  `output` is `stream`, which is what `OUTPUT_SHAPES` gained that value for.
- **Three manifest fields are new.** `nargs` on any argument that is not a single value, `const` on
  every flag, and `stdin` on every command. The last is declared as `COMMANDS_READING_STDIN`, a
  sibling of `DELEGATED_PARSERS`, because it is the same kind of fact: something argparse cannot see.
  All three are reported by `che capabilities --json`, so a shell caller gets the same additions the
  adapter needed.
- **`const` closes an ambiguity that predates the adapter.** `--dry-run` and `--apply` share
  `dest: dry_run` and report the same `default`; without `const` the manifest described two flags as
  identical when one turns the setting on and the other off.
- **Protocol revisions are echoed, not imposed.** `initialize` answers in the client's version when it
  is one of `2025-11-25`, `2025-06-18`, `2025-03-26` or `2024-11-05` — the three methods used here are
  identical across all of them — and falls back to `2025-06-18`. The 2026-07-28 revision removed the
  `initialize` handshake outright and is deliberately not claimed.
- **Mutual exclusion is not restated in the schema.** `--design` / `--design-source` is enforced by
  argparse, whose refusal is catalogued and reaches the model as a tool error. Restating it in the
  schema would be a second place to get it right, for a smaller class of mistake.
- **Host registration is not part of this decision.** Writing an `mcpServers` entry is a decision to
  spawn a process on every session start, and only two of the four hosts have a format that can be
  written and verified from here: Claude (`~/.claude.json`) and Cursor (`~/.cursor/mcp.json`) both
  take JSON, and the Claude adapter already deep-merges `settings.json` for hooks. Codex is TOML with
  no writer in the supported Python range, and Trae's format is not a file this repo can see.
  `docs/cli-reference.md` §2.4 documents the one-line registration instead, so the feature is usable
  today and the per-host work stays visible.
- **ADR-0004's "still to come" is closed** — its closing line named this adapter as the last step.
