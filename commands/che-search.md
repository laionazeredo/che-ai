---
description: "Full-text semantic search across the Che project knowledge base using SQLite FTS5 BM25 scoring. Covers: tasks + envelopes body, decisions payload, specs documents. Optional scope filter and top-K limit. Falls back to LIKE-based search gracefully if the FTS5 virtual tables could not be created."
arguments:
  - name: query_text
    description: "Free-text search query (English or Portuguese OK). Can include multi-word phrases; FTS5 prefix-matches each token. Wrap in quotes."
    required: true
  - name: worktree
    description: "Absolute worktree path. If session has a BOUND binding → uses binding WORKTREE_ROOT by default."
    required: false
  - name: top_k
    description: "Positive integer. Default = 15. Max number of results per scope before scope cross-merge."
    required: false
  - name: scope
    description: "One of: all | tasks | specs | decisions | envelopes. Default = all. Restricts search to the chosen FTS content scope."
    required: false
---

Run the **BM25-ranked FTS5 full-text search** over the project's durable knowledge. Compared to raw `/che-query` SQL, this command is the right default for the common case where the user says "procure por X" / "search for X" without structured filters.

**Preflight:**
1. Resolve worktree.
2. If the state store DB does not exist OR older than the most recent decisions.log modification (quick stat() compare): call `che state rebuild-index $WORKTREE_ROOT` first. (Otherwise skip to keep search instant.)
3. Run:
   ```
   python3 -m che_core.cli state search "$WORKTREE_ROOT" "$QUERY_TEXT" \
     --top-k 15 \
     --scope all \
     --json
   ```

**Expected output structure (after --json):**
```
{
  "query": "...",
  "scope": "all",
  "top_k": 15,
  "fts": true,
  "results": [
    {"scope": "tasks", "id": "T3", "title": "...", "domain": "ux", "status": "TODO", "score": -1.23,
     "envelope_path": "/abs/path/to/envelope.md"},
    {"scope": "decisions", "id": 482, "ts": "...", "event": "TASK_RESUME", ...},
    {"scope": "specs", "spec_id": "spec-refunds", "status": "Approved", ...}
  ]
}
```

**Agent display rules for the user:**
- Group results by `scope` (Tasks / Decisions / Specs).
- For Tasks → include ID, Domain, Status, Title, 1-line snippet (use envelope_path+title; if not obvious, grep first 160 chars from envelope body).
- For Decisions → include event, ts, task_id if any, payload snippet (first 120 chars JSON condensed).
- For Specs → include spec_id, domain, status, abs path.
- If `results.length == 0` AND user typed a multi-word phrase → retry with a single OR-ed keyword version of the query before giving up (don't bug user for this).
