"""Contract tests for the test freeze.

The freeze earns its place only if three things hold: a lock lives outside the repository (so it
cannot be committed by accident), it cannot be moved by re-recording (or the anti-cheat guarantee
is theatre), and moving it leaves both hashes and the user's reason behind.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from che_core.cli import main
from che_core.diagnostics import CheError
from che_core.test_lock import authorize, manifest_path, record, verify

SPEC_TEST = "it('returns 409 Conflict when refunding an already-refunded payment', () => {})\n"


def _write(root: Path, name: str, body: str = SPEC_TEST) -> str:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return name


# ---------------------------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------------------------


def test_the_manifest_lives_outside_the_repository(bound_worktree):
    repo, _paths = bound_worktree
    name = _write(repo, "src/__tests__/refund.test.ts")

    result = record(str(repo), "t1-refund", [name])

    manifest = Path(result["manifest"])
    assert result["ok"] is True
    assert result["locked"] == [name]
    assert manifest.is_file()
    assert repo not in manifest.parents, "a lock inside the repo could be committed by accident"


def test_recording_the_same_file_again_is_idempotent(bound_worktree):
    repo, _paths = bound_worktree
    name = _write(repo, "src/__tests__/refund.test.ts")
    record(str(repo), "t1-refund", [name])

    result = record(str(repo), "t1-refund", [name])

    assert result["locked"] == []
    assert result["unchanged"] == [name]
    assert result["total_locked"] == 1


def test_record_refuses_to_move_a_lock_that_changed(bound_worktree):
    """This is the whole point: a re-record must never launder a weakened assertion."""
    repo, _paths = bound_worktree
    name = _write(repo, "src/__tests__/refund.test.ts")
    record(str(repo), "t1-refund", [name])
    _write(repo, name, "it('works', () => {})\n")

    with pytest.raises(CheError) as raised:
        record(str(repo), "t1-refund", [name])

    assert raised.value.code == "TEST_LOCK_DRIFT"


def test_record_refuses_a_file_outside_the_worktree(bound_worktree, tmp_path):
    repo, _paths = bound_worktree
    outsider = tmp_path / "elsewhere.test.ts"
    outsider.write_text(SPEC_TEST, encoding="utf-8")

    with pytest.raises(CheError) as raised:
        record(str(repo), "t1-refund", [str(outsider)])

    assert raised.value.code == "TEST_LOCK_FILE_OUTSIDE_WORKTREE"


def test_record_refuses_a_missing_file(bound_worktree):
    repo, _paths = bound_worktree

    with pytest.raises(CheError) as raised:
        record(str(repo), "t1-refund", ["src/__tests__/absent.test.ts"])

    assert raised.value.code == "TEST_LOCK_FILE_MISSING"


def test_record_needs_at_least_one_file(bound_worktree):
    repo, _paths = bound_worktree

    with pytest.raises(CheError) as raised:
        record(str(repo), "t1-refund", [])

    assert raised.value.code == "TEST_LOCK_NO_FILES"


def test_an_invalid_related_id_is_refused(bound_worktree):
    repo, _paths = bound_worktree

    with pytest.raises(CheError) as raised:
        record(str(repo), "T1 Refund!", ["src/__tests__/refund.test.ts"])

    assert raised.value.code == "TEST_LOCK_INVALID_RELATED_ID"


# ---------------------------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------------------------


def test_a_task_that_locked_nothing_verifies_as_unlocked_and_writes_nothing(bound_worktree):
    repo, _paths = bound_worktree

    result = verify(str(repo), "never-locked")

    assert result["ok"] is True
    assert result["status"] == "unlocked"
    assert result["checked"] == 0
    assert not manifest_path(str(repo), "never-locked").exists()


def test_an_untouched_lock_verifies_ok(bound_worktree):
    repo, _paths = bound_worktree
    name = _write(repo, "src/__tests__/refund.test.ts")
    record(str(repo), "t1-refund", [name])

    result = verify(str(repo), "t1-refund")

    assert result["ok"] is True
    assert result["status"] == "ok"
    assert result["checked"] == 1


def test_an_edited_test_is_reported_as_drift_with_both_hashes(bound_worktree):
    repo, _paths = bound_worktree
    name = _write(repo, "src/__tests__/refund.test.ts")
    record(str(repo), "t1-refund", [name])
    _write(repo, name, "it('works', () => {})\n")

    result = verify(str(repo), "t1-refund")

    assert result["ok"] is False
    assert result["status"] == "drift"
    assert len(result["drifted"]) == 1
    assert result["drifted"][0]["expected"] != result["drifted"][0]["actual"]


def test_a_deleted_test_is_reported_as_missing(bound_worktree):
    repo, _paths = bound_worktree
    name = _write(repo, "src/__tests__/refund.test.ts")
    record(str(repo), "t1-refund", [name])
    (repo / name).unlink()

    result = verify(str(repo), "t1-refund")

    assert result["ok"] is False
    assert result["status"] == "missing"
    assert result["missing"] == [name]


# ---------------------------------------------------------------------------------------------
# authorize
# ---------------------------------------------------------------------------------------------


def test_authorising_keeps_both_hashes_and_the_reason(bound_worktree):
    repo, _paths = bound_worktree
    name = _write(repo, "src/__tests__/refund.test.ts")
    record(str(repo), "t1-refund", [name])
    _write(repo, name, "it('works', () => {})\n")

    result = authorize(str(repo), "t1-refund", name, "the API now returns 422, not 409")

    assert result["status"] == "authorised"
    assert result["old_sha256"] != result["new_sha256"]
    stored = json.loads(manifest_path(str(repo), "t1-refund").read_text(encoding="utf-8"))
    trail = stored["locks"][name]["authorisations"]
    assert trail[-1]["reason"] == "the API now returns 422, not 409"
    assert trail[-1]["old_sha256"] == result["old_sha256"]
    assert verify(str(repo), "t1-refund")["ok"] is True


def test_authorising_an_unchanged_file_is_a_no_op(bound_worktree):
    repo, _paths = bound_worktree
    name = _write(repo, "src/__tests__/refund.test.ts")
    record(str(repo), "t1-refund", [name])

    result = authorize(str(repo), "t1-refund", name, "nothing actually changed")

    assert result["status"] == "unchanged"
    stored = json.loads(manifest_path(str(repo), "t1-refund").read_text(encoding="utf-8"))
    assert stored["locks"][name]["authorisations"] == []


def test_authorising_needs_a_reason(bound_worktree):
    repo, _paths = bound_worktree
    name = _write(repo, "src/__tests__/refund.test.ts")
    record(str(repo), "t1-refund", [name])
    _write(repo, name, "it('works', () => {})\n")

    with pytest.raises(CheError) as raised:
        authorize(str(repo), "t1-refund", name, "   ")

    assert raised.value.code == "TEST_LOCK_REASON_REQUIRED"


def test_authorising_a_file_that_was_never_locked_is_refused(bound_worktree):
    repo, _paths = bound_worktree
    locked = _write(repo, "src/__tests__/refund.test.ts")
    other = _write(repo, "src/__tests__/other.test.ts")
    record(str(repo), "t1-refund", [locked])

    with pytest.raises(CheError) as raised:
        authorize(str(repo), "t1-refund", other, "wanted to add it")

    assert raised.value.code == "TEST_LOCK_NOT_LOCKED"


# ---------------------------------------------------------------------------------------------
# the CLI contract an agent depends on
# ---------------------------------------------------------------------------------------------


def test_the_cli_exits_one_when_a_locked_test_drifted(bound_worktree, capsys):
    repo, _paths = bound_worktree
    name = _write(repo, "src/__tests__/refund.test.ts")
    main(["test-lock", "record", str(repo), "--related-id", "t1-refund", "--files", name, "--json"])
    capsys.readouterr()
    _write(repo, name, "it('works', () => {})\n")

    with pytest.raises(SystemExit) as raised:
        main(["test-lock", "verify", str(repo), "--related-id", "t1-refund", "--json"])

    assert raised.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "drift"


def test_the_cli_prints_the_lock_it_just_recorded(bound_worktree, capsys):
    repo, _paths = bound_worktree
    name = _write(repo, "src/__tests__/refund.test.ts")

    main(["test-lock", "record", str(repo), "--related-id", "t1-refund", "--files", name])

    assert "locked 1 test file(s) for t1-refund" in capsys.readouterr().out
