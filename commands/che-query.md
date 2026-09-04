---
description: "Run parameterized SQL against the Che state store (che_state.sqlite). Restricted to SELECT/EXPLAIN/PRAGMA by default. Use --force explicitly for writes. Automatically invokes rebuild-index if the DB doesn't exist yet."
arguments:
  - name: sql
    description: "SQL statement with ? placeholders. Wrap in quotes. Example: \"SELECT id, title, status, domain FROM tasks WHERE domain = ? AND status != ?\""
    required: true
  - name: bind
    description: "Optional positional values for the ? placeholders, in textual order. Example: ux DONE → binds [ux, DONE]."
    required: false
  - name: worktree
    description: "Absolute worktree path to resolve the state DB (most queries need this). If session already has a BOUND binding → uses that by default."
    required: false
  - name: json
    description: "Optional flag --json to return a JSON object {sql, binds, rowcount, rows[{}]} instead of ASCII table."
    required: false
---

Executes **read-only, parameterized SQL queries** against the project-level state store (`che_state.sqlite` inside `CHE_PROJECT_DIR`). Intended for advanced exploration of tasks, decisions, specs and bindings data that the `che-search` BM25 FTS5 wrapper doesn't cover (joins, filters on structured fields, aggregates).

**Preflight:**
1. Resolve worktree (binding or user-provided).
2. Run once: `python3 -m che_core.cli state rebuild-index "$WORKTREE_ROOT"` if the DB file doesn't exist yet (idempotent; cheap to re-run).
3. **Safety gate BEFORE any SQL execution:** Tokenize first word of `sql`. If it's NOT in `{SELECT, EXPLAIN, PRAGMA}` → STOP and show the user the restriction notice; only proceed if user passed `--force` explicitly.
4. Invoke:
   ```
   python3 -m che_core.cli state query \
     --sql "$SQL" \
     [--bind BIND_VAL_1 BIND_VAL_2 ...] \
     [--worktree-root "$WORKTREE_ROOT"] \
     [--json]
   ```

**Tabelas / colunas disponíveis (para montar a query):**
```
tasks(id, title, status, domain, depends_on JSON, envelope_path, envelope_body, expert_skills JSON, handoff_output JSON, done_criteria, updated_at)
task_dependencies(child_id, parent_id)
decisions(id, ts, event, worktree_root, task_id, spec_id, session_id, payload JSON)
specs(spec_id, status, domain, frontmatter_json, body, path, updated_at)
bindings(session_id, ts, status, worktree_root, flags_json, data_json, session_dir)
```

**Exemplos de uso comum:**
- Listar tasks do domínio ux que ainda não estão DONE:
  ```sql
  SELECT id, status, title FROM tasks WHERE domain='ux' AND status!='DONE' ORDER BY id
  ```
- Agrupar decisions por evento nos últimos 7 dias:
  ```sql
  SELECT event, COUNT(*) AS c FROM decisions
  WHERE ts > date('now','-7 day') GROUP BY event ORDER BY c DESC
  ```
- Join tasks → dependências → parent statuses:
  ```sql
  SELECT c.id AS child, c.status AS c_status, p.id AS parent, p.status AS p_status
  FROM task_dependencies d
  JOIN tasks c ON c.id=d.child_id
  JOIN tasks p ON p.id=d.parent_id
  WHERE c.status='TODO' ORDER BY c.id
  ```
