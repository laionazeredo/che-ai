# Codex Adapter

Makes the shared Engineering Che available to Codex without duplicating skills.

## Install

Run:

    ./adapters/codex/install.sh

The installer:

- links `adapters/codex/AGENTS.md` to `~/.codex/AGENTS.md`;
- links valid Che skills to `~/.agents/skills/`;
- preserves existing non-symlink user configuration;
- validates `SKILL.md` frontmatter before installation.

## Development checkout

Run:

    export CHE_HOME=/absolute/path/to/che-ai
    export CHE_SESSION_ID="codex-$(date +%s)"
    codex

Example explicit skill invocation:

    $che-spec
    $che-scrum-master
    $che-qa
    $che-code-review
    $che-ship

## Uninstall

Run:

    ./adapters/codex/uninstall.sh

The uninstaller removes only symlinks owned by this Che installation.
