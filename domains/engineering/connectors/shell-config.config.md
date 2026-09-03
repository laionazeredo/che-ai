# Engineering Connector 2: Shell · Containers · Package Managers

§21 External Connectors: **P1 CLI oficial / P2 MCP quando disponível / PROIBIDO raw HTTP**.

Agrupa ferramentas de linha de comando usadas em todo pipeline de engenharia. Cada ferramenta tem seu fallback.

---

## 2.1 Package Managers (Corepack preferred)
| Tool | Pattern | Notes |
|---|---|---|
| **pnpm** via Corepack | `corepack pnpm <comando>` | Default monorepo Flockr. NÃO `npm`. NÃO `yarn`. |
| pnpm install | `corepack pnpm install --frozen-lockfile` (CI) / sem frozen lockfile local | frozen lockfile = 0 surpresas CI |
| Run target monorepo Nx | `corepack pnpm nx run <pkg>:<target> --tui false` | `--tui false` obrigatório em CI / scripts (não output TTY colorido quebra parse) |
| **cargo** Rust | `cargo build --release` / `cargo test` | — |
| **poetry** Python | `poetry install --no-root --sync` / `poetry run pytest` | lock file `poetry.lock` sempre trackeado |
| **pipx** Python tools globais | `pipx install graphifyy` / `pipx ensurepath` | Ferramentas CLI globais de Python SEM poluir global env do sistema. |

### Anti-padrões:
- ❌ `sudo pip install` (polui sistema)
- ❌ `npm install` em monorepo que usa pnpm/workspaces
- ❌ `--legacy-peer-deps` sem ADR de conflito de dependências.

---

## 2.2 Docker / Container runtime (MCP futuro, hoje CLI)
| Operação | Comando canônico | Notes |
|---|---|---|
| Build imagem | `docker build -t <org>/<name>:<tag> --progress plain .` | `--progress plain` para logs parseáveis CI |
| Run container efêmero | `docker run --rm -it <image> <cmd>` | `--rm` limpa container ao sair = NÃO acumula lixo |
| Compose up | `docker compose up -d --wait` / `docker compose logs -f` | `--wait` bloqueia até healthcheck ficar healthy (CI amigável) |
| Compose down | `docker compose down -v --remove-orphans` | `-v` remove volumes associados (limpa DB local. CUIDADO!) |
| Listar images dangling | `docker image ls -f dangling=true` + `docker image prune -f` | Limpeza regular espaço disco |

### Anti-padrões:
- ❌ `docker run -v /home:/home` (blast radius ENORME)
- ❌ `FROM latest` em Dockerfiles oficiais. Sempre pin tag digest SHA256 em prod
- ❌ Secrets no Dockerfile via ENV. Use buildx `--secret` ou runtime secrets.

---

## 2.3 Kubernetes / Helm (Quando aplicável)
P1 CLI oficiais: `kubectl` + `helm`.

| Operação | Comando | Notes |
|---|---|---|
| Trocar context | `kubectl config use-context <arn-cluster>` | NUNCA usa context default sem conferir (risco deploy em cluster errado) |
| Get pods | `kubectl get pods -n <ns>` | Sem `-A` por padrão (muito ruído). Especifica namespace. |
| Logs follow tail | `kubectl logs -f -l app=<x> --tail=50 -n <ns>` | Label selector melhor que nome individual pod. |
| Diff apply antes | `kubectl diff -f manifest.yaml` | OBRIGATÓRIO antes de qualquer `kubectl apply -f`. Mostra changes antes. |
| Helm upgrade dry-run | `helm upgrade --install --dry-run --debug <release> <chart>` | OBRIGATÓRIO dry-run antes de apply real. |

### Anti-padrões:
- ❌ `kubectl apply -f` sem `kubectl diff` ANTES.
- ❌ Deploy direto em prod sem staging / canary / blue-green.
- ❌ Namespace `default` (ruim). Todo app tem seu próprio namespace.

---

## 2.4 Shell Scripting Quality (scripts/*.sh)
Todos scripts de engenharia em shell DEVEM seguir estes defaults (shebang + flags):
```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
# Helpers obrigatórios:
log()   { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
warn()  { printf '\033[33m[%s WARN] %s\033[0m\n' "$(date +%H:%M:%S)" "$*" >&2; }
fail()  { printf '\033[31m[%s FAIL] %s\033[0m\n' "$(date +%H:%M:%S)" "$*" >&2; exit 1; }
# Sempre DRY RUN default, --apply para sobrescrever (§P6 engineering contracts)
APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1 || log "DRY-RUN (nenhuma mudança). Use --apply para real."
# Trap EXIT para limpeza /tmp
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
```

### Anti-padrões scripts shell:
- ❌ Sem `set -euo pipefail` = erros silenciosos.
- ❌ Hardcoded paths `~/.trae` em novos scripts. Usar `${CHE_HOME:-${HARNESS_HOME:-$HOME/.trae}}` (helpers em contracts).
- ❌ `rm -rf` path dentro $HOME. Apenas sobre $TMP (já no trap).
