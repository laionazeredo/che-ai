---
description: "Read and summarize entries from worktree decisions.log.jsonl (Portuguese summary). Use Skill che-decisions-query for filters/export."
arguments:
  - name: worktree
    description: "Worktree absolute path. If missing → ASK."
    required: false
  - name: mode
    description: "One of: summary (default), filter, tail, export-csv, export-tsv."
    required: false
  - name: spec
    description: "Filter mode only: specific SPEC_ID."
    required: false
  - name: event
    description: "Filter mode only: event type substring (case-insensitive)."
    required: false
  - name: last
    description: "Limit entries count (default 20 for summary / 10 for tail)."
    required: false
---

Lightweight inline command. Resolve path via contracts helper. Use Skill `che-decisions-query` for advanced queries (date ranges, export options, grep keyword, csv full).

Flow:

1. **If worktree arg missing → ASK user.** Never guess path.
2. Source contracts + resolve path:
   ```bash
   source ~/.trae/contracts/che_sessions_contract.sh
   JSONL=$(che_decisions_path "<WORKTREE_ROOT>")
   ```
3. **File not exists?** "Nenhuma decisão registrada nesta worktree ainda." → STOP.
4. Default mode = summary. Run CLI helper TypeScript:
   ```bash
   corepack pnpm --dir ~/.trae exec tsx ~/.trae/contracts/decisions-query.cli.ts "$JSONL" summary --last "${LAST:-20}" --lang pt
   ```
5. If mode=filter/event/spec → invoke Skill `che-decisions-query` to do the filtering.
6. If mode=export-csv → run `export --format csv --out ~/Desktop/decisions_<slug>.csv` and tell user file path.
