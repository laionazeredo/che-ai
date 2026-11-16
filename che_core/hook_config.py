"""Render a host's ``hooks.json``: resolve the checkout placeholder and the command form.

``hooks.json`` is a template, not a configuration: every IDE surface gets its own rendered copy
pointing at the checkout that produced it, which is why the file ships with ``__HARNESS_TARGET__``
in place of a path. POSIX hosts execute the hook script through its shebang; Windows has no
shebang, so the rendered command has to name an interpreter explicitly.

Both installers (bash and PowerShell) and the Trae adapter delegate here, so the placeholder and
the platform rule live in exactly one place.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

PLACEHOLDER = "__HARNESS_TARGET__"
PLATFORMS = ("posix", "windows")


def default_platform() -> str:
    """Return the platform name for the running interpreter."""
    return "windows" if os.name == "nt" else "posix"


def detect_python_cmd() -> str:
    """Return the interpreter command a Windows host should use to run a hook script.

    The ``py`` launcher is preferred because it survives Python upgrades; a bare ``python`` is the
    fallback, and the launcher name is returned unchanged when neither is on PATH so the rendered
    file stays diagnosable rather than silently empty.
    """
    if shutil.which("py"):
        return "py -3"
    if shutil.which("python"):
        return "python"
    return "py -3"


def render_command(template: str, harness: str, platform: str, python_cmd: str = "") -> str:
    """Resolve one hook command for ``platform``.

    Preconditions: ``platform`` is one of ``PLATFORMS``; ``harness`` is non-empty.
    Postconditions: the placeholder is gone; a Windows command is quoted and backslash-separated.
    """
    if platform not in PLATFORMS:
        raise ValueError(f"unknown platform: {platform}")
    if not harness:
        raise ValueError("harness path must not be empty")

    resolved = template.replace(PLACEHOLDER, harness)
    if platform == "posix":
        return resolved
    windows_path = resolved.replace("/", "\\")
    return f'{python_cmd or detect_python_cmd()} "{windows_path}"'


def render_config(
    config: Dict[str, Any],
    harness: str,
    platform: str,
    python_cmd: str = "",
) -> Dict[str, Any]:
    """Return ``config`` with every string ``command`` rendered for ``platform``.

    Mutates nothing: the input document is copied shallowly at the hook level, so callers can keep
    the template around for a second render (the installer renders one copy per IDE surface).
    """
    rendered: Dict[str, Any] = dict(config)
    rendered["hooks"] = {
        event: [
            {**hook, "command": render_command(hook["command"], harness, platform, python_cmd)}
            if isinstance(hook.get("command"), str)
            else dict(hook)
            for hook in hooks
        ]
        for event, hooks in config.get("hooks", {}).items()
    }
    return rendered


def render_hooks_file(
    source: Path,
    output: Path,
    harness: Path,
    platform: str,
    python_cmd: str = "",
) -> int:
    """Render ``source`` into ``output``; return the number of commands rewritten.

    Preconditions: ``source`` exists and is a JSON object. Raises ``ValueError``/``OSError`` on
    unreadable input — the caller decides whether that is fatal.
    """
    config = json.loads(Path(source).read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"{source}: expected a JSON object at the top level")
    rendered = render_config(config, str(harness), platform, python_cmd)
    Path(output).write_text(
        json.dumps(rendered, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return sum(len(hooks) for hooks in rendered["hooks"].values())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="render_hooks.py",
        description="Render hooks.json for one host (placeholder + platform command form).",
    )
    parser.add_argument("source", help="Template hooks.json (contains __HARNESS_TARGET__).")
    parser.add_argument("output", help="Where to write the rendered copy.")
    parser.add_argument("--harness", required=True, help="Absolute path of the Che checkout.")
    parser.add_argument(
        "--platform",
        choices=PLATFORMS,
        default=default_platform(),
        help="Target host platform (default: this machine).",
    )
    parser.add_argument(
        "--python-cmd",
        default="",
        help="Interpreter command for the windows platform (default: auto-detect).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point. Returns 0 on success, 2 on usage or input errors."""
    args = _build_parser().parse_args(argv)
    try:
        count = render_hooks_file(
            Path(args.source),
            Path(args.output),
            Path(args.harness),
            args.platform,
            args.python_cmd,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"rendered {count} hook command(s) for {args.platform}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
