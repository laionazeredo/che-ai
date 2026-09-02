# SHARED CHECKLIST — GitHub CLI (gh) Common Operations (CANONICAL)

> REFERÊNCIA COMPARTILHADA por: harness-ship, harness-code-review, harness-pr-comments, harness-ci-fixer, harness-scrum-master (gh-stack create).
> NÃO duplique. Invocar os passos abaixo + sempre checar auth antes.

---

## 0. Preflight — authenticate + confirm account

**Run FIRST on every skill that touches gh:**

```bash
gh auth status
```

Expected output includes:
- `Logged in to github.com as <username>`
- `Token: gho_***` (classic) OR fine-grained
- SSO present if org requires (Flockr: SSO mandatory)

If NOT logged in → STOP + tell user. Ask them to run `gh auth login` with scopes:
`repo, workflow, admin:org, read:project`

---

## 1. Harness commonly-used gh commands

### 1.1 Ship — commit + push + create PR (harness-ship)

```bash
# Listar mudanças para confirmar o que vai ser commitado
git status --short

# Commit individual atômico (conventional commits; veja engineering-contracts Appendix B)
git add -- <files>
git commit -m "feat(scope): imperative description"

# Push (cria branch remota se não existir)
git push --no-verify --set-upstream origin <head-branch>

# Criar DRAFT PR (nunca ready por default; user pede explicitamente ready depois)
gh pr create \
  --draft \
  --base <base-branch> \
  --head <head-branch> \
  --title "feat(scope): Full title" \
  --body-file <path-to-pr-description.md> \
  --assignee @me

# Após criação: assign + labels se necessário
gh pr edit <pr-url-or-number> --assignee @me
gh pr edit <pr-url-or-number> --label "area:payments,status:ready-for-review"

# Marcar ready for review após compliance heavy passed + user confirm
gh pr ready <pr-url-or-number>
```

### 1.2 Review — pull PR metadata + diff (harness-code-review)

```bash
gh pr view <pr-url-or-number> --json \
  number,title,baseRefName,headRefName,state,author,additions,deletions,changedFiles,commits,mergeable,url,body
gh pr diff <pr-url-or-number> --name-only
gh pr diff <pr-url-or-number> > /tmp/pr-<N>.diff
```

### 1.3 Comments — pull review threads (harness-pr-comments)

```bash
gh pr view <pr-url-or-number> --json comments,reviews,reviewRequests
# Postar uma reply em thread
gh pr reply <review-comment-db-id> --body "<polite non-argumentative English reply>"
```

### 1.4 Submit review official (harness-code-review; user asks "suba essa review")

```bash
gh pr review <pr-url-or-number> \
  --request-changes \
  --body-file "$(harness_output_path "review" "gh-review-body" "pr-<N>" "session" "md")"
  # flags: --approve / --comment / --request-changes
  # NÃO USE .trae/ dentro da worktree! Sempre via harness_output_path → HARNESS_SESSION_DIR/reviews/pr-<N>/...
```

### 1.5 CI fixer — pull failing run details (harness-ci-fixer)

```bash
# Listar jobs falhos
gh run view <run-id> --json jobs
# Pull logs de step específico falho
gh run view <run-id> --log-failed > /tmp/run-<id>-failed.log
```

---

## 2. gh-stack reference (hierarquia de PRs — N4 Solicitação)

Ver engineering-contracts Appendix C for full workflow + thresholds.

```bash
# Instalação 1x
gh extension install github/gh-stack

# Criar stack draft de todos os branches locais já preparados
gh-stack create --draft

# Rebasear stack quando branch do meio receber fix/commits
gh-stack rebase

# Status da stack
gh-stack status

# Após PR1 mergear → atualizar base dos restantes para main
gh-stack update --base main
```

---

## 3. Guardrails

- `--no-verify` on git push ONLY when CI runs server-side (GH Actions) and pre-commit hooks are already run as part of lint step. Do not skip verification as a habit.
- Never `git push -f` on shared branches (base, main, dev). Force push allowed ONLY on your own PR head branch, and log the reason (rebase after squash? cherry-pick fix?).
- PR SEMPRE inicia DRAFT. "Ready for review" só depois: compliance heavy passed + QA smoke ok + user explicit approval.
- PR body sempre em ENGLISH. Respostas a comentários de review: sempre ENGLISH educado, não-argumentativo. Comando / comandos do chat com o usuário: sempre PORTUGUÊS.
