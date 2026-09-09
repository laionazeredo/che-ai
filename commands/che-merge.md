---
description: "Resolve Git merge conflicts with MINIMUM BLAST RADIUS, one file at a time. DEFAULT favors current worktree (ours). 3 cases: trivial auto-resolve (whitespace/newline/auto-merge), clash asks side by side, ambiguity NEVER resolved alone → asks between 2 max options + justification."
arguments:
  - name: worktree
    description: "Absolute worktree path (REQUIRED if in chat outside worktree). If omitted and SESSION has binding §19, uses bound WORKTREE_ROOT."
    required: false
  - name: strategy
    description: "DEFAULT = ours (favors current worktree, incoming loses). Optional: theirs | both-sided-by-hunk | manual-ask-all."
    required: false
  - name: path
    description: "Optional subfilter: only conflicts WITHIN path (dir or file). Useful for even smaller blast radius."
    required: false
---

IMMEDIATELY invoke **`che-merge-resolver`** Skill.

Preflight:
1. Worktree binding check §19 — `worktree` arg vs Level 1 registry: mismatch → BLOCK. Ask.
2. `cd $WT && git status --short` — must show `UU` (unmerged) files. 0 conflicts → informational msg + stop.
3. Default strategy decision: `ours = worktree wins, incoming loses`. **Only use another if the user explicitly requested it in the arg.**
4. Skill default **ONE FILE AT A TIME — PER-HUNK NEVER GLOBAL.** Processes in alphabetical order. For each hunk:
   - **Case 1 🟢 Trivial auto:** only whitespace / newlines / import order / separate non-conflicting lines → trivial merge, no ask, log + proceed.
   - **Case 2 🟡 Clash (2 different sides):** shows 2 options — A = OURS (default worktree), B = THEIRS (incoming) + each option with 5-line context preview + **short agent justification (why one might be correct based on PR/task/semantics — NEVER act alone).** Maximum 2 options per hunk. Question has NO continue-all — each hunk is independent.
   - **Case 3 🔴 Ambiguity (≥3 paths or non-obvious semantics e.g.: function rewritten two ways or side-effect order important):** NEVER decide. Shows full context + asks 2 alternatives (A=ours, B=theirs, OR C=user types manual snippet if applicable) + **explain why it is ambiguous.** Only after user response applies.
5. Each decision → log `MERGE_RESOLVE` entry in decisions.log.jsonl: hunk_hash, file, our_side, chosen_side, strategy, user_justification (if any).
6. After last conflict: `git diff --cached --stat` (only resolved unmerged files) → confirm 0 remaining `UU`. Final report saved at `$CHE_WORKSPACE_SHARED/merge-resolve_<slug>_<YYYYMMDD>.md` (header with trivial/clash/ambiguous counts per file + decisions list).

**PROHIBITED:**
- ❌ Global `git merge -X ours` / `checkout --ours/--theirs` ENTIRE FILE without passing hunk-by-hunk (this exceeds blast radius).
- ❌ Skipping ambiguities without asking. NEVER "I chose ours because it was similar" in case 3.
- ❌ Modifying files without `UU` status.
