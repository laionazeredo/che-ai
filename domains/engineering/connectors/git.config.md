# Engineering Connector 1: Git + GitHub CLI (gh)

§18 engineering contracts + §21 External Connectors GENERALISED.
Order of precedence: **P1 official gh CLI / P2 native git CLI (fallback)**. PROHIBITED: hardcoded PAT, raw API curl/fetch, manual octokit SDK.

---

## P1 · GitHub CLI (`gh`) — Canonical for GitHub operations
**Official installer**: `(type -p wget >/dev/null && sudo wget https://github.com/cli/cli/releases/download/v2.59.0/gh_2.59.0_linux_amd64.tar.gz -O- | tar xz --strip-components=1 -C /usr/local) || (type -p curl >/dev/null && curl -sL https://github.com/cli/cli/releases/download/v2.59.0/gh_2.59.0_linux_amd64.tar.gz | tar xz --strip-components=1 -C /usr/local)`

### Auth pattern (XDG path, NOT text PAT)
```bash
# Credential saved in XDG. Prohibited from printing in logs.
gh auth status --show-token 2>&1 | grep -c "Logged in to github.com" >/dev/null
# If it fails → request user via: gh auth login --git-protocol ssh --web --scopes repo,workflow,read:org
```

### Mapped operations (use nothing outside this table in code)
| Operation | Canonical gh CLI command | Notes |
|---|---|---|
| Create branch | `git checkout -b <slug>` → no gh needed (uses P2) | Always sanitise branch-slug: lowercase, `-` separator, no special chars |
| Commit | `git add` + `git commit -m "conventional: ..."` | Native P2 |
| Push | `git push --set-upstream origin <branch>` | Native P2 |
| List open PRs | `gh pr list --state open --json number,title,url,headRefName,statusCheckRollup` | `--json` whenever possible (parseable) |
| Create DRAFT PR | `gh pr create --draft --title "..." --body "..." --base main --head <branch>` | ALWAYS create DRAFT first (ship §0.9 post-gates) |
| Mark PR ready | `gh pr ready <number>` | Only after G1-G5 all pass |
| Check CI status | `gh pr checks <number> --watch` | If CI is red → che-ci-fix skill |
| PR comments triage | `gh pr view <number> --json comments,reviews` | see che-pr-comments skill |
| Merge PR | `gh pr merge <number> --squash --delete-branch --admin` | ALWAYS --squash + delete branch |
| Label | `gh pr edit <n> --add-label "🟢 scope-approved"` | Project-specific label convention |
| Check PR diff vs target branch | `gh pr diff <n>` | |
| Run manual CI workflow | `gh workflow run <yml> -f branch=<x>` | |

### Anti-patterns HARD FAIL (§18):
1. ❌ `git clone https://x-access-token:<PAT>@github.com/...` (PAT leak)
2. ❌ `curl -H "Authorization: Bearer $PAT" https://api.github.com/...` (raw HTTP)
3. ❌ Use of `@octokit/rest` TS SDK without ADR justification (greater complexity than CLI)
4. ❌ Commits without conventional format
5. ❌ Local merge commits. Always `git pull --ff-only` or rebase.

---

## P2 · Native Git CLI (fallback — only when gh does not cover)
Accepted basic commands:
- `git status --short`
- `git add` / `git commit` / `git push` / `git pull --ff-only`
- `git checkout -b`, `git switch`
- `git diff`, `git diff --cached`
- `git log --oneline -n <N>`
- `git stash`, `git stash pop`
- `git branch`, `git worktree`

### Permitted worktree operations (Flockr standard)
```bash
# Create new worktree = isolation per PR / feature (avoids dirty checkout):
git worktree add -b feat/<slug> ../<repo>.worktrees/feat-<slug> dev
# List active worktrees
git worktree list
# Remove when PR is merged
git worktree remove ../<repo>.worktrees/feat-<slug> --force
```

### Anti-patterns:
- ❌ `git push --force` without `--force-with-lease`
- ❌ `git reset --hard` on shared branches (local private only)
- ❌ `git add .` without `git diff --cached` review (risk of accidental secrets)
