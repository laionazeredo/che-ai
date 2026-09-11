# Engineering Connector 2: Shell · Containers · Package Managers

§21 External Connectors: **P1 official CLI / P2 MCP when available / PROHIBITED raw HTTP**.

Groups command-line tools used throughout the engineering pipeline. Each tool has its fallback.

---

## 2.1 Package Managers (Corepack preferred)
| Tool | Pattern | Notes |
|---|---|---|
| **pnpm** via Corepack | `corepack pnpm <command>` | Flockr monorepo default. NOT `npm`. NOT `yarn`. |
| pnpm install | `corepack pnpm install --frozen-lockfile` (CI) / no frozen lockfile local | frozen lockfile = 0 CI surprises |
| Run Nx monorepo target | `corepack pnpm nx run <pkg>:<target> --tui false` | `--tui false` mandatory in CI / scripts (non-colored TTY output breaks parsing) |
| **cargo** Rust | `cargo build --release` / `cargo test` | — |
| **poetry** Python | `poetry install --no-root --sync` / `poetry run pytest` | `poetry.lock` lock file always tracked |
| **pipx** Global Python tools | `pipx install graphifyy` / `pipx ensurepath` | Global Python CLI tools WITHOUT polluting the global system env. |

### Anti-patterns:
- ❌ `sudo pip install` (pollutes system)
- ❌ `npm install` in a monorepo that uses pnpm/workspaces
- ❌ `--legacy-peer-deps` without dependency conflict ADR.

---

## 2.2 Docker / Container runtime (future MCP, today CLI)
| Operation | Canonical command | Notes |
|---|---|---|
| Build image | `docker build -t <org>/<name>:<tag> --progress plain .` | `--progress plain` for parseable CI logs |
| Run ephemeral container | `docker run --rm -it <image> <cmd>` | `--rm` cleans up container on exit = DOES NOT accumulate junk |
| Compose up | `docker compose up -d --wait` / `docker compose logs -f` | `--wait` blocks until healthcheck is healthy (CI friendly) |
| Compose down | `docker compose down -v --remove-orphans` | `-v` removes associated volumes (cleans local DB. CAREFUL!) |
| List dangling images | `docker image ls -f dangling=true` + `docker image prune -f` | Regular disk space cleanup |

### Anti-patterns:
- ❌ `docker run -v /home:/home` (HUGE blast radius)
- ❌ `FROM latest` in official Dockerfiles. Always pin digest SHA256 tag in prod
- ❌ Secrets in Dockerfile via ENV. Use buildx `--secret` or runtime secrets.

---

## 2.3 Kubernetes / Helm (When applicable)
P1 official CLIs: `kubectl` + `helm`.

| Operation | Command | Notes |
|---|---|---|
| Switch context | `kubectl config use-context <arn-cluster>` | NEVER use default context without checking (risk of deploying to wrong cluster) |
| Get pods | `kubectl get pods -n <ns>` | No `-A` by default (too much noise). Specify namespace. |
| Logs follow tail | `kubectl logs -f -l app=<x> --tail=50 -n <ns>` | Label selector better than individual pod name. |
| Diff apply before | `kubectl diff -f manifest.yaml` | MANDATORY before any `kubectl apply -f`. Shows changes first. |
| Helm upgrade dry-run | `helm upgrade --install --dry-run --debug <release> <chart>` | MANDATORY dry-run before real apply. |

### Anti-patterns:
- ❌ `kubectl apply -f` without `kubectl diff` BEFORE.
- ❌ Direct deploy to prod without staging / canary / blue-green.
- ❌ `default` namespace (bad). Every app has its own namespace.

---

## 2.4 Shell Scripting Quality (scripts/*.sh)
All engineering shell scripts MUST follow these defaults (shebang + flags):
```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
# Mandatory helpers:
log()   { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
warn()  { printf '\033[33m[%s WARN] %s\033[0m\n' "$(date +%H:%M:%S)" "$*" >&2; }
fail()  { printf '\033[31m[%s FAIL] %s\033[0m\n' "$(date +%H:%M:%S)" "$*" >&2; exit 1; }
# Always DRY RUN default, --apply to overwrite (§P6 engineering contracts)
APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1 || log "DRY-RUN (no changes). Use --apply for real."
# Trap EXIT for /tmp cleanup
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
```

### Shell script anti-patterns:
- ❌ Without `set -euo pipefail` = silent errors.
- ❌ Hardcoded `~/.trae` paths in new scripts. Use `${CHE_HOME:-$HOME/.che-ai}` (helpers in contracts).
- ❌ `rm -rf` path inside $HOME. Only on $TMP (already in trap).
