# Codex Adapter

Makes the shared Engineering Harness available to Codex without duplicating skills.

## Install

Run:

    ./adapters/codex/install.sh

The installer:

- links `adapters/codex/AGENTS.md` to `~/.codex/AGENTS.md`;
- links valid Harness skills to `~/.agents/skills/`;
- preserves existing non-symlink user configuration;
- validates `SKILL.md` frontmatter before installation.

## Development checkout

Run:

    export HARNESS_HOME=/absolute/path/to/trae-config
    export HARNESS_SESSION_ID="codex-$(date +%s)"
    codex

Example explicit skill invocation:

    $harness-spec
    $harness-scrum-master
    $harness-qa
    $harness-code-review
    $harness-ship

## Uninstall

Run:

    ./adapters/codex/uninstall.sh

The uninstaller removes only symlinks owned by this Harness installation.
