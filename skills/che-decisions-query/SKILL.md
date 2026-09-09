---
name: "che-decisions-query"
description: "Queries, filters, summarizes, exports, and audits Che decisions.log.jsonl history for a worktree using the canonical session contracts. Use when the user asks to inspect decision history or when another Che skill needs programmatic decision lookup."
---

# che-decisions-query — Global Skill

**Use when:** User asks to see / filter / summarise / audit decisions from a worktree's `decisions.log.jsonl` (single source of truth JSONL format, v1 schema). Also use when any skill needs to query decision history programmatically.

**What it does:** Queryable wrapper around `$CHE_WORKSPACE_SHARED/decisions.log.jsonl` for a worktree. Resolves path via `che_decisions_path` contract. Runs queries via in-process python3/jq.

**Do NOT use for:** Writing new entries (use `che_append_decision_jsonl` helper instead).

---

## 0. Preconditions (MANDATORY before any query)

1. **Worktree absolute path known.** If not → ASK user; NEVER guess.
2. **Source contracts first (STORAGE BOUNDARY PREFLIGHT, MANDATORY even for read-only skill):**
   ```bash
   # 1. Canonical session contract source
   source "${CHE_HOME:-$HOME/.trae}/contracts/che_sessions_contract.sh"

   # 2. SESSION_ID (if not defined by orchestrator)
   SESSION_ID="${SESSION_ID:-$(che_current_session_id 2>/dev/null || echo "decisions-$(date -u +%Y%m%d-%H%M%S)")}"

   # 3. Canonical paths for this session
   if [[ -z "${CHE_SESSION_DIR}" ]]; then
     che_compute_paths "$WORKTREE_ROOT" "$SESSION_ID" "$(pwd)"
     che_ensure_session_dirs "$WORKTREE_ROOT"
   fi

   # 4. Double-guard: reaffirm OUTSIDE worktree
   che_assert_outside_worktree "${CHE_SESSION_DIR}"      "$WORKTREE_ROOT" "CHE_SESSION_DIR"
   che_assert_outside_worktree "${CHE_WORKSPACE_SHARED}" "$WORKTREE_ROOT" "CHE_WORKSPACE_SHARED"

   # 5. Resolve unique canonical decisions file path (single shared file OUTSIDE worktree)
   PATH_FILE=$(che_decisions_path "${WORKTREE_ROOT}")
   ```
3. **Does `decisions.log.jsonl` exist?** If not → say "No decisions registered in this worktree yet." Stop.
4. **Optional EXPORT to spreadsheet (optional output writing):**
   - If user asks to "export to CSV/TSV/JSON" → build output_file path via:
     ```bash
     EXPORT_PATH="$(che_output_path "summary" "decisions-export-${MODE}" "${EXPORT_RELATED_ID:-decisions-general}" "workspace" "${EXT:-csv}")"
     ```
     Never write exports to `./decisions-export.csv` or worktree.

**NOTE:** Skill is read-only by default; if writing temporary export/audit output → use centralised helper above.

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
- Legacy migrated entries: `event = <UPPERCASED BRACKET TEXT>` with `data.legacy_text`

---

## 2. Query modes (use smallest scope needed)

Run queries via Python CLI runner:
`python3 -m che_core.decisions_query <path> <mode> [args]`.

### MODE: `summary` (DEFAULT when user says "show decisions")

Returns in **English**, grouped by event type, newest first, ≤20 entries by default. Human-readable summary.

Output shape (console-friendly bullet list):
```
📌 Decisions Lumos__test-worktree (N=6 entries, newest → oldest)
- [30/08 19:45] PRE-1 HEAD-SNAPSHOT | commit=2e20ef8a… (SPEC-API-HEALTH-1)
- [30/08 19:45] TEST-SPEC-SMOKE APPROVED | 4 TCs, user A (SPEC-API-HEALTH-1)
...
```

### MODE: `filter` — by spec_id / event_type / date range / keyword

Args (any combination):
- `--spec SPEC-XXX` → spec_id == SPEC-XXX only
- `--event EVENT_TYPE` → case-insensitive match (e.g. `--event spec`)
- `--after YYYY-MM-DD` / `--before YYYY-MM-DD`
- `--grep "word"` → substring match inside `data.legacy_text` + `data` all values

### MODE: `export` → CSV or TSV

- `--format csv` (columns: ts, event, spec_id, session_id, data_json_str)
- `--format tsv`

### MODE: `tail` → last N entries

- `--last N` default 10

---

## 3. When to invoke this skill (decision tree)

| User asks | → which mode |
|---|---|
| "show decisions / history" | **summary** + grouped bullets |
| "what happened to SPEC-API-HEALTH-1?" | **filter --spec SPEC-API-HEALTH-1** |
| "which gh-stacks approved yesterday?" | **filter --event GH_STACK_APPROVED --after 2026-08-29** |
| "export decisions to spreadsheet / CSV" | **export --format csv** |
| "last 20 decisions" | **tail --last 20** |
| "search for 'FLO-745' in decisions" | **filter --grep FLO-745** |

---

## 4. Output language rules

1. **Summary mode:** Always respond in **ENGLISH**. Group by event type.
2. **Filter / export / tail modes:** Headers & field names in ENGLISH (technical).
3. **Never output raw JSONL to user unless explicitly asked.** Use human-friendly summary renderer.

---

## 5. Appendix A — Inline Python fallback

Copy/paste this 1-liner pattern for queries; it's what the helper does internally.

```bash
# Example: summary mode
PATH_FILE=$(che_decisions_path "$WORKTREE_ROOT")
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
