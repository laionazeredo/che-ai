"""Contract tests for the hooks.json renderer shared by the POSIX and Windows installers.

The renderer exists because the same ten lines of JSON rewriting were duplicated in two bash
installers, and because Windows cannot execute a ``.py`` hook through its shebang. What is under
test is therefore narrow and worth pinning: the POSIX output must stay byte-identical to the
algorithm it replaced (otherwise every existing installation sees a spurious diff on upgrade), and
the Windows output must be a single quoted command whose interpreter is named explicitly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from che_core.hook_config import (
    PLACEHOLDER,
    main,
    render_command,
    render_config,
    render_hooks_file,
)

CHE_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = CHE_ROOT / "hooks.json"


def _legacy_render(source: Path, harness: str) -> str:
    """The inline algorithm both bash installers carried before this module existed."""
    config = json.loads(source.read_text())
    for event_hooks in config.get("hooks", {}).values():
        for hook in event_hooks:
            command = hook.get("command")
            if isinstance(command, str):
                hook["command"] = command.replace(PLACEHOLDER, harness)
    return json.dumps(config, ensure_ascii=False, indent=2) + "\n"


def test_posix_output_is_byte_identical_to_the_replaced_inline_algorithm(tmp_path: Path) -> None:
    harness = str(CHE_ROOT)
    output = tmp_path / "hooks.json"

    count = render_hooks_file(TEMPLATE, output, Path(harness), "posix")

    assert count == 4
    assert output.read_text() == _legacy_render(TEMPLATE, harness)


def test_posix_command_keeps_the_shebang_form() -> None:
    command = render_command(
        f"{PLACEHOLDER}/hooks/pretooluse-worktree-binding.py",
        "/home/ana/.che-ai",
        "posix",
    )

    assert command == "/home/ana/.che-ai/hooks/pretooluse-worktree-binding.py"


def test_windows_command_names_an_interpreter_and_quotes_the_path() -> None:
    command = render_command(
        f"{PLACEHOLDER}/hooks/pretooluse-worktree-binding.py",
        "C:\\Users\\ana\\.che-ai",
        "windows",
        python_cmd="py -3",
    )

    assert command == 'py -3 "C:\\Users\\ana\\.che-ai\\hooks\\pretooluse-worktree-binding.py"'


def test_windows_command_converts_posix_separators() -> None:
    command = render_command(
        f"{PLACEHOLDER}/hooks/posttooluse-lang-pt-check.py",
        "/home/ana/.che-ai",
        "windows",
        python_cmd="python",
    )

    assert command == 'python "\\home\\ana\\.che-ai\\hooks\\posttooluse-lang-pt-check.py"'


def test_placeholder_never_survives_a_render(tmp_path: Path) -> None:
    output = tmp_path / "hooks.json"

    for platform in ("posix", "windows"):
        render_hooks_file(TEMPLATE, output, Path("C:/che"), platform, python_cmd="py -3")
        assert PLACEHOLDER not in output.read_text()


def test_render_config_leaves_non_string_commands_untouched() -> None:
    config = {"hooks": {"PreToolUse": [{"command": 42, "name": "numeric"}, {"name": "no-command"}]}}

    rendered = render_config(config, "/che", "posix")

    assert rendered["hooks"]["PreToolUse"][0] == {"command": 42, "name": "numeric"}
    assert rendered["hooks"]["PreToolUse"][1] == {"name": "no-command"}


def test_render_config_does_not_mutate_the_template() -> None:
    config = json.loads(TEMPLATE.read_text())

    render_config(config, "/che", "windows", python_cmd="py -3")

    assert config["hooks"]["PreToolUse"][0]["command"] == f"{PLACEHOLDER}/hooks/pretooluse-worktree-binding.py"


@pytest.mark.parametrize("platform", ["darwin", "linux", ""])
def test_unknown_platform_is_rejected(platform: str) -> None:
    with pytest.raises(ValueError):
        render_command(f"{PLACEHOLDER}/hooks/x.py", "/che", platform)


def test_empty_harness_is_rejected() -> None:
    with pytest.raises(ValueError):
        render_command(f"{PLACEHOLDER}/hooks/x.py", "", "posix")


def test_main_reports_missing_source(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([str(tmp_path / "absent.json"), str(tmp_path / "out.json"), "--harness", "/che"])

    assert exit_code == 2
    assert "ERROR:" in capsys.readouterr().err


def test_main_reports_invalid_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    broken = tmp_path / "hooks.json"
    broken.write_text("{not json")

    exit_code = main([str(broken), str(tmp_path / "out.json"), "--harness", "/che"])

    assert exit_code == 2
    assert "ERROR:" in capsys.readouterr().err


def test_main_writes_a_rendered_file(tmp_path: Path) -> None:
    output = tmp_path / "hooks.json"

    exit_code = main(
        [str(TEMPLATE), str(output), "--harness", "/che", "--platform", "windows", "--python-cmd", "py -3"]
    )

    assert exit_code == 0
    rendered = json.loads(output.read_text())
    assert all(
        hook["command"].startswith('py -3 "\\che\\hooks\\') for hooks in rendered["hooks"].values() for hook in hooks
    )
    assert output.read_text().endswith("\n")
