---
name: "harness-decisions-query"
description: "Queries, filters, summarizes, exports, and audits Harness decisions.log.jsonl history for a worktree using the canonical session contracts. Use when the user asks to inspect decision history or when another Harness skill needs programmatic decision lookup."
---

# harness-decisions-query — Global Skill

**Use when:** User asks to see / filter / summarize / audit decisions from a worktree's `decisions.log.jsonl` (single source of truth JSONL format, v1 schema). Also use when any skill/harness skill needs to query decision history programmatically.

**What it does:** Queryable wrapper around `$HARNESS_WORKSPACE_SHARED/decisions.log.jsonl` for a given worktree. Resolves path via `harness_decisions_path` contract. Runs queries via in-process python3/jq — no new dependencies.

**Do NOT use for:** Writing new entries (use `harness_append_decision_jsonl` in contracts/ instead, it's the single writer helper with dedup + schema).

---

## 0. Preconditions (MANDATORY before any query)

1. **Worktree absolute path known.** If not → ASK user for worktree; NEVER guess.
2. **`decisions.log.jsonl` exists?** If file doesn't exist → say "Nenhuma decisão registrada nesta worktree ainda." Stop.
3. **Source contracts first** before calling the helper CLI wrapper below:
   ```bash
   source ~/.trae/contracts/harness_sessions_contract.sh
   PATH_FILE=$(harness_decisions_path "<WORKTREE_ROOT>")
   ```

---

## 1. JSONL v1 Schema (single source of truth, canonical)

Each line = one JSON object:
```json
{
  "ts": "2026-08-30T19:23:15Z",
  "event": "SPEC_APPROVED",
  "spec_id": "SPEC-API-HEALTH-1",
  "session_id": "sess-1788118136-111831",
  "worktree_root": "/abs/path",
  "data": { "...": "..." },
  "_v": 1
}
```

Common event types:
- `SPEC`, `SPEC_OVERRIDE`, `SPEC_APPROVED`
- `TASK_GRAPH`
- `GH_STACK_DRAFT`, `GH_STACK_APPROVED`, `GH_STACK_DECLINED`
- `TEST_SPEC_SMOKE_APPROVED`
- `PRE_HEAD_SNAPSHOT`
- `BLAST_RADIUS_OVER`, `OUTSIDE_BLAST_RADIUS`
- `QA_PASS`, `COMPLIANCE_PASS_LIGHT`, `COMPLIANCE_FAIL_HEAVY`
- Legacy migrated entries: `event = <uppercased bracket text>` with `data.legacy_text`

---

## 2. Query modes (use the smallest scope needed)

Run queries via the TypeScript CLI runner (zero-build, tsx executor):
`corepack pnpm --dir ~/.trae exec tsx ~/.trae/contracts/decisions-query.cli.ts <path> <mode> [args]`.

Shortcut via package.json script:
`corepack pnpm --dir ~/.trae decisions <path> <mode> [args]`.

### MODE: `summary` (DEFAULT when user says "mostra as decisões")

Returns in PORTUGUESE, grouped by event type, newest first, ≤20 entries by default. Equivalent when user wants a human-readable summary like the old `.md` file.

Output shape (console-friendly, bullet list PT-BR):
```
📌 Decisões Lumos__test-worktree (N=6 entries, newest → oldest)
- [30/08 19:45] PRE-1 HEAD-SNAPSHOT | commit=2e20ef8a… (SPEC-API-HEALTH-1)
- [30/08 19:45] TEST-SPEC-SMOKE APPROVED | 4 TCs, user A (SPEC-API-HEALTH-1)
...
```

### MODE: `filter` — por spec_id / event_type / date range / keyword

Args (any combination):
- `--spec SPEC-XXX` → only rows with spec_id == SPEC-XXX
- `--event EVENT_TYPE` → case-insensitive match (ex: `--event spec`)
- `--after YYYY-MM-DD` / `--before YYYY-MM-DD`
- `--grep "palavra"` → substring match inside `data.legacy_text` + `data` all values

### MODE: `export` → CSV ou TSV para planilhas / dashboards

- `--format csv` (columns: ts, event, spec_id, session_id, data_json_str)
- `--format tsv`

### MODE: `tail` → últimas N entries (live monitor)

- `--last N` default 10

---

## 3. When to invoke this skill (decision tree)

| User asks | → which mode |
|---|---|
| "mostra decisões / histórico" | **summary** + PT-BR grouped bullets |
| "o que aconteceu com a SPEC-API-HEALTH-1?" | **filter --spec SPEC-API-HEALTH-1** |
| "quais gh-stacks aprovados ontem?" | **filter --event GH_STACK_APPROVED --after 2026-08-29** |
| "exporta decisões pra planilha / CSV" | **export --format csv** |
| "últimas 20 decisões" | **tail --last 20** |
| "procura a palavra 'FLO-745' nas decisões" | **filter --grep FLO-745** |

---

## 4. Output language rules

1. **Summary mode:** Always respond in **PORTUGUÊS** (user preference; matches user_profile). Group by event type.
2. **Filter / export / tail modes:** Headers & field names in ENGLISH (technical); body commentary in PT-BR if needed.
3. **Never output raw JSONL to user unless they explicitly ask for raw.** Use the summary human-friendly renderer.

---

## 5. Appendix A — Inline Python fallback (run if helper .py missing)

Copy/paste this 1-liner pattern for queries; it's what the helper does internally.

```bash
# Example: summary mode
PATH_FILE=$(harness_decisions_path "$WORKTREE_ROOT")
python3 - "$PATH_FILE" summary <<'PY'
import json, sys
path, mode = sys.argv[1:3]
entries = [json.loads(l) for l in open(path) if l.strip()]
entries.sort(key=lambda e: e.get("ts",""), reverse=True)
for e in entries[:20]:
    ts = e.get("ts","")[:16].replace("T"," ")
    ev = e.get("event","").replace("_"," ")
    sid = e.get("spec_id") or ""
    data = e.get("data", {})
    legacy = data.get("legacy_text") or json.dumps(data, ensure_ascii=False)[:80]
    print(f"- [{ts}] {ev} | {legacy} {('('+sid+')') if sid else ''}")
PY
```
