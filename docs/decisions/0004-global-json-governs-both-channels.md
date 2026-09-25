# ADR-0004: the global `--json` governs stdout on both channels

- Status: Accepted
- Date: 2026-09-25
- Area: CLI surface / agent integration
- Follows: ADR-0003 (the CLI surface is data)

## Context

ADR-0003 made the surface readable: `che capabilities --json` describes every command and the shape
each one emits. This ADR is the second of the three steps that decision set out.

Today the global `--json` shapes the **failure** channel only. On success, stdout carries whichever of
six shapes the command happens to use — the manifest's `output` field enumerates them: a JSON object,
`export K="v"` lines, `K=v` lines, prose, a bare path, or nothing. So the flag is silently ignored on
the success path:

```bash
che --json capabilities      # prints the human list — the flag did nothing
che --json output_path …     # prints a bare path
```

The first of those is the command that exists to make the surface discoverable, which makes the gap
hard to argue for. The reference documented the omission as deliberate: making the global flag select
JSON on success "has to keep the `eval` recipes working".

**That premise was checked and is false.** No recipe passes `--json`. Every occurrence of
`eval "$(che compute_paths …)"` and `eval "$(che pixel paths …)"` omits the flag — around thirty of
them across `skills/`, `commands/` and `contracts/`. The earlier caution described a design that
changes the **default** output; an opt-in flag changes nothing for a caller that does not pass it.

## Decision

**`che --json <command>` means: stdout carries no prose and no shell. It carries one JSON value, or
nothing at all.**

1. The global `--json` and a command's own `--json` are the same question — *did this caller ask for
   machine-readable output?* — and they get one answer, resolved once (`_wants_json`).
2. `output` in the manifest keeps describing the **default**, flag-less shape. It is what a caller
   gets without asking, which is what a caller choosing whether to ask needs to know.
3. Defaults do not move. `compute_paths` and `pixel paths` still print `export K="v"`, because that is
   a contract with the shell, not a rendering choice.
4. A command with no result (`output: "none"`) stays silent under `--json`. Exit 0 is the answer;
   inventing `{"status": "ok"}` for `write_file_atomic` would be a payload nobody reads, and it would
   not match the domain payloads the always-JSON commands already return.

## Rationale

- **The guarantee an agent needs is about the channel, not the schema.** "Always JSON" is impossible
  without re-shaping 27 existing payloads, and those payloads are consumed today. "Never prose on
  stdout when I asked for machine output" is the property that lets an agent write one parse path
  instead of six, and it costs no breaking change.
- **One decision, one place.** A mapping rendered as `export K="v"` or as JSON is the same mapping, so
  the choice belongs in a single module rather than repeated at sixteen call sites. The dialects did
  not drift because anyone chose them; they drifted because each command made the decision locally.
- **`che designer …` answers the same question.** It is forwarded to a domain sub-CLI before argparse
  runs, so the flag has to travel with it. A caller should not have to learn which of Che's commands
  are forwarded in order to know whether `--json` applies.

## Consequences

- **A latent bug was found and fixed on the way.** `main()` stripped `--json` from `argv` before
  calling `parse_args`, so `args.json_global` was **always** `False`: the flag reached argparse never,
  and worked only because `diagnosed` does a literal membership test on the original argv. That is why
  the success path could not have honoured the flag even if a handler had asked. The flag now stays in
  `argv` for argparse to parse, and only the designer dispatch looks through it — which is the one
  place that runs before argparse.
- **The `eval` recipes are unaffected** — verified by searching for the flag next to every recipe, not
  assumed from the fact that they work today.
- **A new module, `che_core/output.py`,** owns the mapping → shape decision. It is the sibling of
  `che_core/diagnostics.py`: one failure, one description; one payload, one shape. `_print_json` moves
  there, so the forty existing JSON call sites keep working unchanged.
- **`che designer …` no longer strips the flag** when forwarding. That forwarding code exists because
  argparse cannot pass a leading optional through `REMAINDER` (bpo-17050); the flag now travels in the
  same argv rather than being dropped.
- **Three modules stay outside the contract** because they are not `che` commands: `ship.py`,
  `xray.py` and `decisions_query.py` are invoked as `python3 -m che_core.<module>`, so a `che` flag can
  never reach them. They keep their output and their own entrypoints. Naming the boundary is part of
  the decision: "every command honours `--json`" would be false without it.
- **No new manifest field.** If the rule under `--json` is uniform, `output` needs no companion flag
  saying whether `--json` applies — a second field would be a second thing to keep true.
- **Still to come:** the MCP adapter generated from the same walk (ADR-0003).
