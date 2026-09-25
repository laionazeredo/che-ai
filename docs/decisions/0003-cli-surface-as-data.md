# ADR-0003: The CLI surface is data (argparse is the source, MCP is derived)

- Status: Accepted
- Date: 2026-09-25
- Area: CLI surface / agent integration / discoverability

## Context

Che's interface lives in two places that cannot see each other: the argparse declarations in
`che_core/cli.py`, and the prose in `docs/cli-reference.md` plus `commands/*.md`. An agent that wants
to call `che worktree add` has to either load ~700 lines of markdown into its context, or guess a flag
and read the error. Guessing is the expensive path: a round trip that teaches nothing about the
correct form.

There is no way to ask the CLI what it can do. `che --help` prints prose for a human; the exit codes
and the failure catalogue exist as data (`che_core/diagnostics.py`) but are not reachable as data.
Meanwhile the sibling `curate` pipeline already exposes `capabilities --json` and its own AGENTS.md
instructs agents to "always call this first" — so the pattern is established in this ecosystem, and
Che is the one that lacks it.

ADR-0001 established that Che can run inside other harnesses (Paperclip). MCP-capable harnesses are
another such host, and they need the same thing in a different shape: a tool list with typed inputs.

## Decision

**The parser is the single source for the shape of the surface, and everything else is derived from
it.** `che_core/manifest.py` walks the real argparse tree and returns JSON-serialisable data; it is
served by `che capabilities --json`.

| Question | Answered by | Why not declared by hand |
|---|---|---|
| Command tree, aliases, argument names | the parser | argparse already encodes them |
| Argument type, `choices`, `default`, `required`, `nargs`, help | the parser | ditto |
| Mutually-exclusive sets | the parser | argparse already knows; a caller must not have to guess |
| What running a command *does* | `COMMAND_SEMANTICS` | argparse cannot know: `mutates`, `requires_bound_worktree`, `output` |
| Exit codes and their meaning | `EXIT_CODES` | not expressible in argparse |
| The failure catalogue | `che_core/diagnostics.ERROR_CATALOG` | already data; exported, not re-declared |

Two guards keep the halves in step, in both directions: every command in the parser must carry a
semantics entry, and every entry must match a live command. Both fail CI, not an agent's run.

`che capabilities --json` is **compact by default** — names, summaries and semantics, plus the
exit-code table. `--command <name>` adds that command's arguments and types; `--errors` adds the
failure catalogue. The reason is measured, not stylistic: the compact surface is ~13 KB and one
command is ~2 KB, while pulling in the whole failure catalogue as well is ~29 KB. The question an
agent actually has first ("what can I do?") is answered by the cheap one.

**The MCP adapter, when it lands, is generated from this same walk** — not hand-written beside it.

## Rationale

- **A hand-written manifest would be a second source of truth.** It is the obvious design, and it is
  wrong here: argparse already declares the command tree, argument names, `choices`, `type`,
  `default`, `required`, `nargs`, help strings and mutually-exclusive groups. Re-declaring those is
  several hundred lines that can drift from the thing they describe, and the drift is *silent* — the
  manifest would confidently describe a CLI that does not exist. Introspection makes that class of bug
  impossible for the shape; the completeness tests make it loud for the semantics.
- **The win is a discoverable schema, not the protocol.** MCP decomposes into four separable parts:
  a JSON-RPC transport, a tool list with input schemas, typed results, and a structured error
  channel. The last already shipped (ADR-adjacent work: `ERROR_CATALOG` + the failure envelope). The
  tool list with schemas is what kills interface guessing, and it needs no protocol. The transport's
  marginal value is "an agent calls Che without a shell" — and Che's skills *are* markdown that runs a
  shell, so that is not today's bottleneck. Deriving the schema first means the MCP adapter becomes a
  thin, optional layer instead of a prerequisite.
- **One walk, three surfaces.** argparse, `capabilities --json`, and (later) the MCP tool list all
  read the same tree. Adding a command updates all three by construction, and the only hand-written
  part — the semantics table — is the part that genuinely cannot be derived.

## Consequences

- **A dependency on private argparse state.** The walk reads `parser._actions`,
  `parser._mutually_exclusive_groups` and `group._group_actions`, which have no public equivalent and
  are what every argparse-introspecting tool reaches for. A test asserts the walk finds known commands
  with known arguments, so a CPython change fails in CI rather than returning an empty surface that
  reads as "a Che with no commands".
- **Adding a command now has a second, small obligation.** A new command needs a `COMMAND_SEMANTICS`
  entry with a summary and three decisions; without it, tests fail. That is the point: an agent that
  believes a destructive command is read-only will run it.
- **The manifest is a contract with agents, not a dump of argparse.** `summary` is written for a
  caller deciding whether this is the command they want, which is deliberately not the terse `help`
  label written for a human scanning a list. The two are allowed to differ.
- **Still to come, in its own change:** honouring the global `--json` on the success path (today it
  shapes only the failure channel, because `eval "$(che compute_paths …)"` is a contract with the
  shell), and the MCP adapter generated from this walk.
