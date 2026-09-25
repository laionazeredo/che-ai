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
    detect_installed_adapters,
    exit_code,
    find_checkout,
    relink_adapters,
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
# Host wiring — a pull moves the checkout, not the installation
# --------------------------------------------------------------------------------------------


class Relinker:
    """Records the calls instead of running the adapters."""

    def __init__(self, adapters=None, orphans=0, failed=None):
        self.calls: list[Path] = []
        self.result = {
            "adapters": list(adapters or []),
            "orphans_removed": orphans,
            "failed": list(failed or []),
        }

    def __call__(self, che_home: Path) -> dict:
        self.calls.append(che_home)
        return self.result


class FakeRunner:
    """Stands in for `subprocess.run` when an adapter is invoked."""

    def __init__(self, stdout: str = "", returncode: int = 0):
        self.stdout = stdout
        self.returncode = returncode
        self.commands: list[list[str]] = []

    def __call__(self, command, **kwargs) -> subprocess.CompletedProcess:
        self.commands.append(list(command))
        return subprocess.CompletedProcess(command, self.returncode, stdout=self.stdout, stderr="")


def _wired_home(tmp_path: Path, checkout: Path, home_name: str, *, missing_source: bool = False) -> Path:
    """A host home holding one Che symlink, pointing into `checkout`."""
    home = tmp_path / home_name
    (home / "commands").mkdir(parents=True)
    target = checkout / "commands" / "che-explain.md"
    if not missing_source:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# source\n", encoding="utf-8")
    (home / "commands" / "che-explain.md").symlink_to(target)
    return home


def _adapter_checkout(tmp_path: Path, name: str = "trae") -> Path:
    checkout = tmp_path / "che"
    (checkout / "adapters" / name).mkdir(parents=True)
    (checkout / "adapters" / name / "install.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    return checkout


def test_the_host_is_relinked_even_when_the_checkout_is_already_current(install: Install) -> None:
    """The state a pull alone leaves behind: nothing to download, and a command that never appears."""
    relinker = Relinker(adapters=["trae"], orphans=2)

    state = update(che_home=str(install.clone), relinker=relinker)

    assert state["status"] == "up-to-date"
    assert state["updated"] is False
    assert relinker.calls == [install.clone.resolve()]
    assert state["relink"]["orphans_removed"] == 2


def test_the_host_is_relinked_after_an_update_too(install: Install) -> None:
    install.publish("commands/che-new.md", "# new\n", "feat: add a command")
    relinker = Relinker(adapters=["trae", "claude"])

    state = update(che_home=str(install.clone), relinker=relinker)

    assert state["status"] == "updated"
    assert relinker.calls == [install.clone.resolve()]


def test_check_only_does_not_touch_the_host(install: Install) -> None:
    """`--check` is a question, and answering it must not rewrite the host's completion list."""
    install.publish("a.txt", "one\n", "feat: add a")
    relinker = Relinker(adapters=["trae"])

    state = update(che_home=str(install.clone), check_only=True, relinker=relinker)

    assert state["status"] == "would-update"
    assert relinker.calls == []
    assert state["relink"] is None


def test_the_summary_reports_the_orphans_it_cleaned(install: Install) -> None:
    """The line used to claim the links were "already live" — which is what hid this whole bug."""
    relinker = Relinker(adapters=["trae"], orphans=3)

    summary = summarise(update(che_home=str(install.clone), relinker=relinker))

    assert "already live" not in summary
    assert "Re-linked 1 adapter(s) (trae)" in summary
    assert "3 stale symlink(s) removed" in summary


def test_the_summary_says_so_when_no_adapter_is_wired(install: Install) -> None:
    summary = summarise(update(che_home=str(install.clone), relinker=Relinker()))

    assert "No host adapter is wired" in summary


def test_a_failed_adapter_is_reported_without_failing_the_update(install: Install) -> None:
    """The code did update; aborting because an IDE home was read-only would hide that."""
    install.publish("a.txt", "one\n", "feat: add a")
    relinker = Relinker(failed=[{"adapter": "trae", "returncode": 1}])

    state = update(che_home=str(install.clone), relinker=relinker)

    assert state["status"] == "updated"
    assert exit_code(state) == UPDATE_OK
    assert "could not be re-linked (trae)" in summarise(state)


# --------------------------------------------------------------------------------------------
# Detection — evidence, never the mere existence of a home directory
# --------------------------------------------------------------------------------------------


def test_an_adapter_is_detected_by_a_link_into_this_checkout(tmp_path: Path) -> None:
    checkout = tmp_path / "che"
    checkout.mkdir()
    home = _wired_home(tmp_path, checkout, "trae-home")

    found = detect_installed_adapters(checkout, {"HOME": str(tmp_path), "TRAE_HOME": str(home)})

    assert found == ["trae"]


def test_the_default_home_is_used_when_the_override_is_absent(tmp_path: Path) -> None:
    checkout = tmp_path / "che"
    checkout.mkdir()
    _wired_home(tmp_path, checkout, ".trae")

    found = detect_installed_adapters(checkout, {"HOME": str(tmp_path)})

    assert found == ["trae"]


def test_a_home_that_exists_but_was_never_wired_is_not_an_adapter(tmp_path: Path) -> None:
    """`~/.claude` existing means the user has Claude Code, not that Che may install itself there."""
    checkout = tmp_path / "che"
    checkout.mkdir()
    (tmp_path / ".claude" / "commands").mkdir(parents=True)

    found = detect_installed_adapters(checkout, {"HOME": str(tmp_path)})

    assert found == []


def test_a_dangling_che_link_still_proves_the_adapter_is_installed(tmp_path: Path) -> None:
    """An installation whose links are all broken is exactly the state that has to be repaired."""
    checkout = tmp_path / "che"
    checkout.mkdir()
    home = _wired_home(tmp_path, checkout, "trae-home", missing_source=True)

    found = detect_installed_adapters(checkout, {"HOME": str(tmp_path), "TRAE_HOME": str(home)})

    assert found == ["trae"]


def test_a_link_into_another_checkout_is_not_ours(tmp_path: Path) -> None:
    checkout = tmp_path / "che"
    checkout.mkdir()
    other = tmp_path / "other-che"
    other.mkdir()
    home = _wired_home(tmp_path, other, "trae-home")

    found = detect_installed_adapters(checkout, {"HOME": str(tmp_path), "TRAE_HOME": str(home)})

    assert found == []


# --------------------------------------------------------------------------------------------
# relink_adapters — what it runs, and what it does with the answer
# --------------------------------------------------------------------------------------------


def test_relink_runs_only_the_wired_adapters_and_sums_what_they_pruned(tmp_path: Path) -> None:
    checkout = _adapter_checkout(tmp_path)
    home = _wired_home(tmp_path, checkout, "trae-home")
    runner = FakeRunner(stdout="  - orphan removed: x\nCHE_PRUNE_REMOVED=2\n")

    result = relink_adapters(checkout, runner=runner, environ={"HOME": str(tmp_path), "TRAE_HOME": str(home)})

    assert result["adapters"] == ["trae"]
    assert result["orphans_removed"] == 2
    assert result["failed"] == []
    assert runner.commands == [["bash", str(checkout / "adapters" / "trae" / "install.sh")]]


def test_an_adapter_without_an_installer_is_skipped_quietly(tmp_path: Path) -> None:
    """Detection can see a wiring that a newer checkout no longer ships an installer for."""
    checkout = tmp_path / "che"
    checkout.mkdir()
    home = _wired_home(tmp_path, checkout, "trae-home")
    runner = FakeRunner()

    result = relink_adapters(checkout, runner=runner, environ={"HOME": str(tmp_path), "TRAE_HOME": str(home)})

    assert result["adapters"] == []
    assert result["failed"] == []
    assert runner.commands == []


def test_a_nonzero_adapter_exit_is_recorded_rather_than_raised(tmp_path: Path) -> None:
    checkout = _adapter_checkout(tmp_path)
    home = _wired_home(tmp_path, checkout, "trae-home")

    result = relink_adapters(
        checkout,
        runner=FakeRunner(returncode=1),
        environ={"HOME": str(tmp_path), "TRAE_HOME": str(home)},
    )

    assert result["failed"] == [{"adapter": "trae", "returncode": 1}]


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
