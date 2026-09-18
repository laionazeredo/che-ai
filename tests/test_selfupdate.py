"""Contract tests for `che update` — the one command that moves the installation forward.

The command exists because updating Che by hand had two failure modes, and both are states a test
has to build for real: a *refusal* that leaves the working tree bit-for-bit where it was, and a
`pyproject.toml` that changed while the installed CLI quietly kept the old dependencies. So the
fixtures here are real repositories — a bare `origin`, a seed clone that pushes to it, and a working
clone that is behind it — because `git merge --ff-only` cannot be faked into meaning anything.

`update()` takes its reinstaller as an argument for the same reason: what is under test is the
*decision* to reinstall, not pipx. A suite that invoked a real package manager would be slow,
networked, and would mutate the machine it runs on.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from che_core.selfupdate import (
    UPDATE_OK,
    UPDATE_REFUSED,
    UPDATE_REINSTALL_FAILED,
    UPDATE_USAGE,
    UpdateRefused,
    exit_code,
    find_checkout,
    summarise,
    update,
)
from tests.conftest import GIT_ENV, isolated_git_env

CHE_CLI_CMD = [sys.executable, "-m", "che_core.cli"]
CHE_ROOT = Path(__file__).resolve().parent.parent


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *GIT_ENV, *args],
        capture_output=True,
        text=True,
        check=False,
        env=isolated_git_env(),
    )


def _init(cwd: Path, *extra: str) -> None:
    result = subprocess.run(
        ["git", "init", "-q", "--initial-branch=main", *extra, str(cwd)],
        capture_output=True,
        text=True,
        check=False,
        env=isolated_git_env(),
    )
    assert result.returncode == 0, result.stderr


def _look_like_che(path: Path) -> None:
    """The two markers `find_checkout` requires, and nothing else it might stumble over.

    ``skills/`` gets a file rather than being created empty: git does not track empty
    directories, so a bare ``mkdir`` here would make the seed push a tree without the marker and
    the clone would fail `find_checkout` for a reason that has nothing to do with the command.
    """
    path.mkdir(parents=True, exist_ok=True)
    (path / "CHE_RULES.md").write_text("# conventional rules\n", encoding="utf-8")
    (path / "skills").mkdir(exist_ok=True)
    (path / "skills" / "README.md").write_text("# skills\n", encoding="utf-8")


def _commit(checkout: Path, message: str) -> str:
    _git(checkout, "add", "-A")
    _git(checkout, "commit", "-q", "--allow-empty", "-m", message)
    return _git(checkout, "rev-parse", "HEAD").stdout.strip()


class Install:
    """A bare origin, the seed checkout that pushes to it, and a working clone that trails it."""

    def __init__(self, tmp_path: Path):
        self.origin = tmp_path / "origin.git"
        self.origin.mkdir()
        _init(self.origin, "--bare")

        self.seed = tmp_path / "seed"
        _look_like_che(self.seed)
        _init(self.seed)
        _commit(self.seed, "init")
        _git(self.seed, "remote", "add", "origin", str(self.origin))
        _git(self.seed, "push", "-q", "-u", "origin", "main")

        self.clone = tmp_path / "clone"
        subprocess.run(
            ["git", "clone", "-q", str(self.origin), str(self.clone)],
            capture_output=True,
            text=True,
            check=True,
            env=isolated_git_env(),
        )

    def publish(self, relative: str, content: str, message: str) -> str:
        """Commit a file on the seed and push it, so the clone is one commit behind."""
        target = self.seed / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        sha = _commit(self.seed, message)
        _git(self.seed, "push", "-q", "origin", "main")
        return sha

    def head(self) -> str:
        return _git(self.clone, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def install(tmp_path: Path) -> Install:
    return Install(tmp_path)


# --------------------------------------------------------------------------------------------
# The happy path
# --------------------------------------------------------------------------------------------


def test_a_clone_that_is_behind_fast_forwards_to_the_remote(install: Install) -> None:
    published = install.publish("CHE_RULES.md", "# rules, revised\n", "docs: revise the rules")

    state = update(che_home=str(install.clone))

    assert state["status"] == "updated"
    assert state["updated"] is True
    assert state["behind"] == 1
    assert install.head() == published
    assert (install.clone / "CHE_RULES.md").read_text(encoding="utf-8") == "# rules, revised\n"
    assert state["commits"] == [f"{published[:7]} docs: revise the rules"]


def test_running_it_again_is_success_and_touches_nothing(install: Install) -> None:
    """Idempotence is the property that makes one command safe to run blind."""
    install.publish("a.txt", "one\n", "feat: add a")
    first = update(che_home=str(install.clone))
    head_after_first = install.head()

    second = update(che_home=str(install.clone))

    assert first["status"] == "updated"
    assert second["status"] == "up-to-date"
    assert second["updated"] is False
    assert second["behind"] == 0
    assert install.head() == head_after_first
    assert exit_code(second) == UPDATE_OK
    assert "already at the latest" in summarise(second)


def test_the_check_never_moves_the_checkout(install: Install) -> None:
    """`--check` and the real run share `inspect`, so they cannot describe different futures."""
    install.publish("a.txt", "one\n", "feat: add a")
    before = install.head()

    state = update(che_home=str(install.clone), check_only=True)

    assert state["status"] == "would-update"
    assert state["updated"] is False
    assert state["behind"] == 1
    assert install.head() == before
    assert not (install.clone / "a.txt").exists()


# --------------------------------------------------------------------------------------------
# The refusals — every one of them leaves the working tree exactly where it was
# --------------------------------------------------------------------------------------------


def test_a_dirty_tracked_file_is_refused_and_the_checkout_does_not_move(install: Install) -> None:
    install.publish("CHE_RULES.md", "# rules, revised\n", "docs: revise the rules")
    before = install.head()
    (install.clone / "CHE_RULES.md").write_text("# my local edit\n", encoding="utf-8")

    with pytest.raises(UpdateRefused) as refused:
        update(che_home=str(install.clone))

    assert refused.value.code == UPDATE_REFUSED
    assert "CHE_RULES.md" in refused.value.reason
    assert "stash" in refused.value.reason
    assert install.head() == before
    assert (install.clone / "CHE_RULES.md").read_text(encoding="utf-8") == "# my local edit\n"


def test_gitignored_personal_state_does_not_count_as_dirty(install: Install) -> None:
    """`user_rules/` and `bindings/` must never be the reason an update is blocked."""
    install.publish(".gitignore", "user_rules/\nbindings/\n", "chore: ignore personal state")
    install.publish("a.txt", "one\n", "feat: add a")
    update(che_home=str(install.clone))

    (install.clone / "user_rules").mkdir()
    (install.clone / "user_rules" / "mine.md").write_text("personal\n", encoding="utf-8")

    state = update(che_home=str(install.clone))

    assert state["status"] == "up-to-date"


def test_a_branch_that_is_not_the_default_is_refused(install: Install) -> None:
    install.publish("a.txt", "one\n", "feat: add a")
    _git(install.clone, "switch", "-q", "-c", "my-experiment")

    with pytest.raises(UpdateRefused) as refused:
        update(che_home=str(install.clone))

    assert refused.value.code == UPDATE_REFUSED
    assert "my-experiment" in refused.value.reason and "main" in refused.value.reason
    assert install.head() != ""


def test_local_commits_the_remote_lacks_are_refused_rather_than_discarded(install: Install) -> None:
    install.publish("a.txt", "one\n", "feat: add a")
    (install.clone / "mine.txt").write_text("local work\n", encoding="utf-8")
    local = _commit(install.clone, "feat: my local work")

    with pytest.raises(UpdateRefused) as refused:
        update(che_home=str(install.clone))

    assert "discard" in refused.value.reason
    assert install.head() == local
    assert (install.clone / "mine.txt").exists()


def test_a_checkout_that_is_not_a_che_install_is_refused(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()

    with pytest.raises(UpdateRefused) as refused:
        find_checkout(str(plain))

    assert refused.value.code == UPDATE_USAGE
    assert "not a Che checkout" in refused.value.reason


def test_a_checkout_that_is_not_a_git_repo_is_refused_and_names_the_script(tmp_path: Path) -> None:
    """A zip install needs `gh` and an item-by-item merge, which this command does not pretend to do."""
    zip_install = tmp_path / "zip-install"
    _look_like_che(zip_install)

    with pytest.raises(UpdateRefused) as refused:
        update(che_home=str(zip_install))

    assert refused.value.code == UPDATE_USAGE
    assert "self-update-che.sh" in refused.value.reason


# --------------------------------------------------------------------------------------------
# The reason this command exists at all: a changed pyproject must reach the installed CLI
# --------------------------------------------------------------------------------------------


class Reinstaller:
    """Records the calls instead of running a package manager."""

    def __init__(self, ok: bool = True):
        self.ok = ok
        self.calls: list[Path] = []

    def __call__(self, che_home: Path) -> dict:
        self.calls.append(che_home)
        command = ["pipx", "install", "-e", str(che_home), "--force"]
        return {"ok": self.ok, "command": command, "output": ["ok" if self.ok else "boom"]}


def test_a_changed_pyproject_reinstalls_the_cli(install: Install) -> None:
    install.publish("pyproject.toml", "[project]\nname = 'che-ai'\n", "build: add a dependency")
    reinstaller = Reinstaller()

    state = update(che_home=str(install.clone), reinstaller=reinstaller)

    assert reinstaller.calls == [install.clone.resolve()]
    assert state["reinstall"]["ok"] is True
    assert state["status"] == "updated"
    assert exit_code(state) == UPDATE_OK


def test_a_change_that_does_not_touch_pyproject_leaves_the_cli_alone(install: Install) -> None:
    """Reinstall is not a ritual: it is a consequence, and it has to stay a consequence."""
    install.publish("docs/cli-reference.md", "# reference\n", "docs: add a reference")
    reinstaller = Reinstaller()

    state = update(che_home=str(install.clone), reinstaller=reinstaller)

    assert reinstaller.calls == []
    assert state["reinstall"] is None
    assert "left alone" in summarise(state)


def test_a_failed_reinstall_is_a_distinct_outcome_that_names_the_command(install: Install) -> None:
    """The code moved and the packages did not — actionable, and not the same as a failed update."""
    install.publish("pyproject.toml", "[project]\nname = 'che-ai'\n", "build: add a dependency")

    state = update(che_home=str(install.clone), reinstaller=Reinstaller(ok=False))

    assert state["status"] == "updated-without-reinstall"
    assert state["updated"] is True
    assert exit_code(state) == UPDATE_REINSTALL_FAILED
    assert "pipx install -e" in summarise(state)


# --------------------------------------------------------------------------------------------
# The CLI surface
# --------------------------------------------------------------------------------------------


def _run_cli(args, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*CHE_CLI_CMD, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(CHE_ROOT), "PATH": "/usr/bin:/bin", "HOME": str(Path.home())},
    )


def test_the_cli_aliases_all_reach_the_command(tmp_path: Path) -> None:
    for alias in ("update", "self-update", "upgrade"):
        result = _run_cli([alias, "--help"], tmp_path)
        assert result.returncode == 0, alias
        assert "--check" in result.stdout, alias


def test_the_cli_reports_what_an_update_would_bring(install: Install, tmp_path: Path) -> None:
    install.publish("a.txt", "one\n", "feat: add a")

    result = _run_cli(["update", "--check", "--che-home", str(install.clone)], tmp_path)

    assert result.returncode == UPDATE_OK, result.stderr
    assert "1 commit(s) available" in result.stdout
    assert "feat: add a" in result.stdout
    assert not (install.clone / "a.txt").exists(), "--check must not move the checkout"


def test_the_cli_exits_three_and_names_the_remedy_on_a_dirty_tree(install: Install, tmp_path: Path) -> None:
    install.publish("a.txt", "one\n", "feat: add a")
    (install.clone / "CHE_RULES.md").write_text("# edited\n", encoding="utf-8")

    result = _run_cli(["update", "--che-home", str(install.clone)], tmp_path)

    assert result.returncode == UPDATE_REFUSED
    assert "uncommitted changes" in result.stderr
    assert "nothing was changed" in result.stderr.lower()
    assert not (install.clone / "a.txt").exists()


def test_the_cli_prints_the_result_as_json(install: Install, tmp_path: Path) -> None:
    install.publish("a.txt", "one\n", "feat: add a")

    result = _run_cli(["update", "--che-home", str(install.clone), "--json"], tmp_path)

    assert result.returncode == UPDATE_OK, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "updated"
    assert payload["behind"] == 1
    assert payload["declares_dependencies"] is False
