# Engineering Connector 1: Git + GitHub CLI (gh)

§18 engineering contracts + §21 External Connectors GENERALIZADO.
Ordem de precedência: **P1 gh CLI oficial / P2 git CLI nativo (fallback)**. PROIBIDO: PAT hardcoded, curl/fetch API raw, SDK octokit manual.

---

## P1 · GitHub CLI (`gh`) — Canonical for GitHub operations
**Instalador oficial**: `(type -p wget >/dev/null && sudo wget https://github.com/cli/cli/releases/download/v2.59.0/gh_2.59.0_linux_amd64.tar.gz -O- | tar xz --strip-components=1 -C /usr/local) || (type -p curl >/dev/null && curl -sL https://github.com/cli/cli/releases/download/v2.59.0/gh_2.59.0_linux_amd64.tar.gz | tar xz --strip-components=1 -C /usr/local)`

### Auth pattern (XDG path, NÃO PAT texto)
```bash
# Credential salva em XDG. Proibido printar em logs.
gh auth status --show-token 2>&1 | grep -c "Logged in to github.com" >/dev/null
# Se falhar → pede user via: gh auth login --git-protocol ssh --web --scopes repo,workflow,read:org
```

### Operations mapeadas (não usa nada fora desta tabela em code)
| Operação | Comando canônico gh CLI | Notes |
|---|---|---|
| Criar branch | `git checkout -b <slug>` → não precisa gh (usa P2) | Sempre sanitiza branch-slug: lowercase, `-` separador, sem chars especiais |
| Commit | `git add` + `git commit -m "conventional: ..."` | P2 nativo |
| Push | `git push --set-upstream origin <branch>` | P2 nativo |
| Listar PRs abertas | `gh pr list --state open --json number,title,url,headRefName,statusCheckRollup` | `--json` sempre que possível (parseável) |
| Criar DRAFT PR | `gh pr create --draft --title "..." --body "..." --base main --head <branch>` | SEMPRE cria DRAFT primeiro (ship §0.9 post gates) |
| Marcar PR ready | `gh pr ready <numero>` | Só depois G1-G5 all pass |
| Check CI status | `gh pr checks <numero> --watch` | Se CI vermelho → harness-ci-fix skill |
| Comentários PR triage | `gh pr view <numero> --json comments,reviews` | ver harness-pr-comments skill |
| Merge PR | `gh pr merge <numero> --squash --delete-branch --admin` | SEMPRE --squash + delete branch |
| Label | `gh pr edit <n> --add-label "🟢 scope-approved"` | Convenção de labels por projeto |
| Check diff PR vs branch alvo | `gh pr diff <n>` | |
| Run CI workflow manual | `gh workflow run <yml> -f branch=<x>` | |

### Anti-padrões HARD FAIL (§18):
1. ❌ `git clone https://x-access-token:<PAT>@github.com/...` (PAT leak)
2. ❌ `curl -H "Authorization: Bearer $PAT" https://api.github.com/...` (raw HTTP)
3. ❌ Uso SDK `@octokit/rest` TS sem justificativa ADR (complexidade maior que CLI)
4. ❌ Commits sem conventional format
5. ❌ Merge commits locais. Sempre `git pull --ff-only` ou rebase.

---

## P2 · Git CLI nativo (fallback — só quando gh não cobre)
Comandos básicos aceitos:
- `git status --short`
- `git add` / `git commit` / `git push` / `git pull --ff-only`
- `git checkout -b`, `git switch`
- `git diff`, `git diff --cached`
- `git log --oneline -n <N>`
- `git stash`, `git stash pop`
- `git branch`, `git worktree`

### Worktree operations permitidas (padrão Flockr)
```bash
# Criar worktree nova = isolamento por PR / feature (evita checkout sujo):
git worktree add -b feat/<slug> ../<repo>.worktrees/feat-<slug> dev
# Listar worktrees ativos
git worktree list
# Remover quando PR merged
git worktree remove ../<repo>.worktrees/feat-<slug> --force
```

### Anti-padrões:
- ❌ `git push --force` sem `--force-with-lease`
- ❌ `git reset --hard` em branches compartilhadas (apenas local privado)
- ❌ `git add .` sem `git diff --cached` review (risco acidental secrets)
