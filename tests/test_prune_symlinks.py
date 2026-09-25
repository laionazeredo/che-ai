"""The pruner is the half of the adapter contract that a rename depends on.

The adapters link each command and skill one at a time, walking whatever exists at install time.
That is what makes a pull live with no reinstall — and it is also why a rename leaves a dangling
symlink behind and creates no new one. The pruner is the only thing that removes those, so the
interesting cases are about what it must NOT touch: a symlink the user made, a real file, and a Che
link that still resolves.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

PRUNER = Path(__file__).resolve().parent.parent / "scripts" / "prune-che-symlinks.sh"


def _run(repo: Path, *dirs: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(PRUNER), str(repo), *[str(item) for item in dirs]],
        capture_output=True,
        text=True,
        check=False,
    )


def _pruned(result: subprocess.CompletedProcess) -> int:
    for line in result.stdout.splitlines():
        if line.startswith("CHE_PRUNE_REMOVED="):
            return int(line.split("=", 1)[1])
    raise AssertionError(f"no CHE_PRUNE_REMOVED marker in stdout: {result.stdout!r}")


class Host:
    """A checkout with two collections, and a host home wired to it."""

    def __init__(self, tmp_path: Path):
        self.repo = tmp_path / "che"
        (self.repo / "commands").mkdir(parents=True)
        (self.repo / "skills").mkdir()

        self.home = tmp_path / "home"
        self.commands = self.home / "commands"
        self.skills = self.home / "skills"
        self.commands.mkdir(parents=True)
        self.skills.mkdir()

    def source(self, relative: str) -> Path:
        """Create a file inside the checkout, as an adapter's link target would be."""
        target = self.repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# source\n", encoding="utf-8")
        return target

    def link(self, directory: Path, name: str, target: str) -> Path:
        entry = directory / name
        entry.symlink_to(target)
        return entry

    def prune(self) -> subprocess.CompletedProcess:
        return _run(self.repo, self.commands, self.skills)


def test_a_link_whose_source_was_renamed_away_is_removed(tmp_path: Path) -> None:
    """The case that started this: `/che-diff` became `/che-explain`, and the old link stayed."""
    host = Host(tmp_path)
    source = host.source("commands/che-old.md")
    orphan = host.link(host.commands, "che-old.md", str(source))
    source.unlink()

    result = host.prune()

    assert result.returncode == 0
    assert not orphan.exists()
    assert not orphan.is_symlink()
    assert _pruned(result) == 1


def test_a_link_that_still_resolves_is_a_live_injection_point(tmp_path: Path) -> None:
    host = Host(tmp_path)
    source = host.source("commands/che-live.md")
    live = host.link(host.commands, "che-live.md", str(source))

    result = host.prune()

    assert live.is_symlink()
    assert live.resolve() == source.resolve()
    assert _pruned(result) == 0


def test_a_dangling_link_pointing_outside_the_checkout_is_left_alone(tmp_path: Path) -> None:
    """A broken link is not automatically ours — the user may own it, and we do not tidy their home."""
    host = Host(tmp_path)
    foreign = host.link(host.commands, "mine.md", str(tmp_path / "somewhere-else.md"))

    result = host.prune()

    assert foreign.is_symlink()
    assert _pruned(result) == 0


def test_a_real_file_is_never_removed_however_it_is_named(tmp_path: Path) -> None:
    host = Host(tmp_path)
    real = host.commands / "che-old.md"
    real.write_text("not a symlink\n", encoding="utf-8")

    result = host.prune()

    assert real.is_file()
    assert not real.is_symlink()
    assert _pruned(result) == 0


def test_a_relative_link_into_the_checkout_is_recognised(tmp_path: Path) -> None:
    """Adapters write absolute link text, but a hand-made relative link must not slip through."""
    host = Host(tmp_path)
    orphan = host.link(host.commands, "che-old.md", "../../che/commands/che-old.md")

    result = host.prune()

    assert not orphan.is_symlink()
    assert _pruned(result) == 1


def test_the_total_counts_orphans_across_every_collection(tmp_path: Path) -> None:
    host = Host(tmp_path)
    host.link(host.commands, "che-old.md", str(host.repo / "commands" / "che-old.md"))
    host.link(host.skills, "che-gone", str(host.repo / "skills" / "che-gone"))

    result = host.prune()

    assert _pruned(result) == 2


def test_a_collection_that_does_not_exist_is_not_an_error(tmp_path: Path) -> None:
    """Adapters pass every target they know about, whether or not the host ever created it."""
    host = Host(tmp_path)
    result = _run(host.repo, host.commands, tmp_path / "never-created")

    assert result.returncode == 0
    assert _pruned(result) == 0


def test_calling_it_without_a_collection_is_a_usage_error(tmp_path: Path) -> None:
    result = _run(tmp_path / "che")

    assert result.returncode == 2
    assert "usage:" in result.stderr
