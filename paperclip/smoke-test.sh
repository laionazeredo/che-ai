#!/usr/bin/env bash
# Verify the Che-in-Paperclip seam without any Claude/Codex credentials:
#   1. `che` CLI is installed inside the container.
#   2. memory backend detection reports `paperclip` (env-driven).
#   3. a decision append routes to the shared sink under /paperclip/che-shared.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> 1. Che CLI installed in the container"
docker compose exec -T paperclip python3 -c "import che_core; print('che_core importable')"

echo "==> 2. memory backend detection (expect env=paperclip, store=PaperclipDecisionStore)"
docker compose exec -T paperclip python3 -c \
  "from che_core import memory_store as m; print('env=', m.detect_env(), 'store=', type(m.get_decision_store()).__name__)"

echo "==> 3. append a decision and show it lands in the shared sink"
docker compose exec -T paperclip python3 -c \
  "from che_core import memory_store as m; m.append_decision('/paperclip/project', 'SPIKE_TEST', '{\"ok\": true}')"
docker compose exec -T paperclip sh -c 'cat /paperclip/che-shared/decisions.jsonl'
