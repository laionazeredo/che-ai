# Derived Paperclip image with the Che CLI installed (Mode B: executable harness).
#
# The official image already ships `claude` and `codex` (see the upstream
# Dockerfile's `npm install -g @anthropic-ai/claude-code @openai/codex`), so we
# only add the Che stdlib Python package so `che` is on PATH inside Paperclip.
FROM ghcr.io/paperclipai/paperclip:latest

RUN apt-get update \
  && apt-get install -y --no-install-recommends python3-pip python3-venv \
  && rm -rf /var/lib/apt/lists/*

# Bake the whole che-ai repo and install the `che` console script.
COPY . /opt/che-ai
RUN python3 -m pip install --break-system-packages --no-cache-dir /opt/che-ai

# The upstream entrypoint (tini -> docker-entrypoint.sh) is preserved.
