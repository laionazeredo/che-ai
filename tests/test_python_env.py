"""The Python gates must survive an LD_LIBRARY_PATH that shadows libsqlite3.

An IDE terminal can export a loader path whose ``libsqlite3.so.0`` is older than the one the
interpreter was built against, which breaks ``import sqlite3`` and every SQLite-backed test
module at collection. These assertions pin the sanitiser and the hooks that use it.
"""

import os
import subprocess
from pathlib import Path

CHE_ROOT = Path(__file__).resolve().parent.parent
PY_ENV_LIB = CHE_ROOT / "scripts" / "lib" / "python-env.sh"


def _run(script: str, ld_library_path: str) -> str:
    """Source the library, run ``script`` in bash, return stripped stdout."""
    env = {**os.environ, "LD_LIBRARY_PATH": ld_library_path}
    completed = subprocess.run(
        ["bash", "-c", f'source "{PY_ENV_LIB}"; {script}'],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return completed.stdout.strip()


def test_shadowing_entry_is_dropped(tmp_path):
    shadow = tmp_path / "ide-bundle"
    shadow.mkdir()
    (shadow / "libsqlite3.so.0").write_bytes(b"")
    kept = tmp_path / "other"
    kept.mkdir()

    assert _run("che_ld_library_path_without_sqlite_shadow", f"{shadow}:{kept}") == str(kept)


def test_clean_path_is_preserved(tmp_path):
    kept = tmp_path / "other"
    kept.mkdir()

    assert _run("che_ld_library_path_without_sqlite_shadow", str(kept)) == str(kept)


def test_shadow_entries_are_reported(tmp_path):
    shadow = tmp_path / "ide-bundle"
    shadow.mkdir()
    (shadow / "libsqlite3.so.0").write_bytes(b"")

    assert _run("che_sqlite_shadow_entries", f"{shadow}:{tmp_path}") == str(shadow)


def test_python_runs_with_the_sanitised_loader_path(tmp_path):
    shadow = tmp_path / "ide-bundle"
    shadow.mkdir()
    (shadow / "libsqlite3.so.0").write_bytes(b"")

    assert _run("che_python -c 'import sqlite3; print(sqlite3.sqlite_version)'", str(shadow))


def test_git_hooks_run_pytest_through_the_sanitised_python():
    for hook in ("pre-commit", "pre-push"):
        text = (CHE_ROOT / "scripts" / "git-hooks" / hook).read_text(encoding="utf-8")
        assert "che_python -m pytest" in text, f"{hook} bypasses the sanitiser"


def test_dev_dependency_check_reports_the_shadow():
    text = (CHE_ROOT / "scripts" / "check-dev-dependencies.sh").read_text(encoding="utf-8")

    assert "che_sqlite_shadow_entries" in text
    assert "sqlite3 stdlib module" in text
