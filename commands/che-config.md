---
description: "Set session configuration flags (e.g., chat language, documentation language, PT detection)."
arguments:
  - name: lang-chat
    description: "Language for agent chat dialogue (en | pt-BR)."
    required: false
  - name: lang-docs
    description: "Language for documentation, PRs and commits (en | pt-BR)."
    required: false
  - name: lang-report
    description: "Language for generated reports (en | pt-BR)."
    required: false
  - name: pt-check
    description: "Enable/disable Portuguese text detection hook (ENABLED | DISABLED)."
    required: false
---

1. Resolve `WORKTREE_ROOT` and `SESSION_ID`.
2. Execute: `python3 -m che_core.cli config "$SESSION_ID" "$WORKTREE_ROOT" ${lang_chat:+--lang-chat "$lang_chat"} ${lang_docs:+--lang-docs "$lang_docs"} ${lang_report:+--lang-report "$lang_report"} ${pt_check:+--pt-check "$pt_check"}`.
3. Report success to the user.
