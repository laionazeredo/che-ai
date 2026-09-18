#!/usr/bin/env bash
# One-command Paperclip + Che bootstrap. Idempotent: re-running never duplicates
# the company, the agents or the skills.
#
#   ./bootstrap.sh                 # build, import, then serve the UI on :3210
#   ./bootstrap.sh --headless      # build + import only (no host port, no auth)
#   PORT=4000 ./bootstrap.sh       # serve the UI on another port
#
# Why it works in two phases:
#   Phase 1 boots `local_trusted` on loopback, where requests are implicitly
#   trusted, so a board API key can be minted without any credentials and the
#   package can be imported unattended. Phase 2 switches the same container to
#   `authenticated` and publishes the UI port; the minted key and the imported
#   data live in the shared volume, so nothing has to be redone.
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"

PORT="${PORT:-3210}"
MODE="ui"
[[ "${1:-}" == "--headless" ]] && MODE="headless"

# Docker Desktop / WSL do not bind-mount the build context with BuildKit.
export DOCKER_BUILDKIT=0

BASE_ARGS=(-f docker-compose.yml)
UI_ARGS=(-f docker-compose.yml -f docker-compose.ui.yml)
export CHE_UI_PORT="$PORT"

# Persist the auth secret: rotating it would invalidate existing sessions and
# anything Paperclip encrypted with it (stored provider API keys).
SECRET_FILE=".better-auth-secret"
if [[ -z "${BETTER_AUTH_SECRET:-}" ]]; then
  [[ -f "$SECRET_FILE" ]] || (umask 077 && openssl rand -hex 32 > "$SECRET_FILE")
  BETTER_AUTH_SECRET="$(cat "$SECRET_FILE")"
fi
export BETTER_AUTH_SECRET

echo "==> 1/5 regenerate package/ (seed + skills) and build image"
python3 build-package.py
docker compose "${BASE_ARGS[@]}" build

echo "==> 2/5 boot local_trusted (loopback, no published port)"
docker compose "${BASE_ARGS[@]}" up -d --force-recreate

echo "==> 3/5 wait for the API"
ready=""
for _ in $(seq 1 60); do
  if docker compose "${BASE_ARGS[@]}" exec -T paperclip \
       curl -sf -o /dev/null http://127.0.0.1:3100/api/health 2>/dev/null; then
    ready="yes"
    break
  fi
  sleep 2
done

if [[ -z "$ready" ]]; then
  echo "==> the API never came up. Last container logs:" >&2
  docker compose "${BASE_ARGS[@]}" logs --tail 20 paperclip >&2 || true
  cat >&2 <<'HINT'

If the log says "Refusing to reuse PostgreSQL: its data directory belongs to
another instance", the embedded Postgres was killed uncleanly and left a stale
pid file that now matches an unrelated live pid. Clear it and retry:

  docker run --rm -v che-paperclip_paperclip-data:/paperclip alpine \
    rm -f /paperclip/instances/default/db/postmaster.pid
HINT
  exit 1
fi

echo "==> 4/5 mint board key + import package (idempotent)"
docker compose "${BASE_ARGS[@]}" exec -T paperclip \
  python3 /opt/che-ai/paperclip/bootstrap.py

if [[ "$MODE" == "headless" ]]; then
  echo "==> done (headless). Imported into the local_trusted instance."
  exit 0
fi

echo "==> 5/5 switch to authenticated + publish UI on :$PORT"
docker compose "${UI_ARGS[@]}" up -d

for _ in $(seq 1 60); do
  if curl -sf -o /dev/null "http://localhost:$PORT/api/health"; then
    echo "==> done. Open http://localhost:$PORT"
    exit 0
  fi
  sleep 2
done

echo "==> UI did not answer on :$PORT; check: docker compose ${UI_ARGS[*]} logs paperclip" >&2
exit 1
