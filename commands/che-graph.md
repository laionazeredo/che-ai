---
description: "Graph & Knowledge wrapper around graphify CLI (pipx graphifyy package, local AST only — no network). 4 canonical subcommands: refresh | query <NL question> | path <A> <B> | stats. Always idempotently adds graphify-out/ to .gitignore. Falls back to grep-based heuristics if graphify CLI not installed."
arguments:
  - name: worktree
    description: "Absolute worktree path. If missing and no binding exists → ASK first."
    required: false
  - name: subcommand
    description: "Required positional: refresh | query \"your question\" | path SymbolA SymbolB | stats. Example: /che-graph query \"how does QR ticket validation reach the DB\""
    required: true
---

IMMEDIATELY invoke the **`che-graph`** Skill.

Preflight:
1. If binding Level1 exists → use WORKTREE_ROOT from it.
2. If no binding AND no worktree → ASK first; create binding (§19 2-LEVEL).
3. Subcommand dispatch inside che-graph:
   - `refresh` → (re)builds graphify-out/ with GRAPH_REPORT.md + graph.html + graph.json; incremental if already present.
   - `query "<text>"` → natural-language ask over the graph; each returned symbol MUST include absolute path:line-range (not just filename).
   - `path A B` → returns shortest call/dependency chain between two symbols; BFS fallback on grep if graph missing.
   - `stats` → prints 10-line stable snapshot: nodes count by type, top-5 hub files, LOC by language, biggest class/module.
