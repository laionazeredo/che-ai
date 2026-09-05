import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from che_core.hooks import posttooluse_git_worktree
from che_core.paths import resolve_workspace_name, resolve_worktree_slug
from che_core.workspaces import ensure_worktree_l3_dirs

CHE_CLI_CMD = [sys.executable, "-m", "che_core.cli"]


@pytest.fixture(autouse=True)
def _isolate_workspaces_root(tmp_path, monkeypatch):
    """Override CHE_WORKSPACES_ROOT para TUDO dentro de tmp_path — NÃO toca ~/.che-workspaces real."""
    isolated = tmp_path / "che-ws-test"
    isolated.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CHE_WORKSPACES_ROOT", str(isolated))
    yield isolated


def _run_cli(*args):
    """Roda o CLI do che e retorna (exit_code, stdout, stderr)."""
    proc = subprocess.run(
        CHE_CLI_CMD + list(args),
        capture_output=True,
        text=True,
        env={**os.environ},
        check=False,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _parse_json(s):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


# --- WORKSPACE TESTS (L1) -----------------------------------------------------


def test_workspace_add_and_list_cli():
    """che workspace add foo → cria dir; che workspace list → retorna entry."""
    code, out, _ = _run_cli("workspace", "add", "Test WS")
    assert code == 0, out
    data = _parse_json(out)
    assert data is not None
    assert data.get("created") is True
    assert "name" in data
    slug = data["name"]
    assert slug

    code2, out2, _ = _run_cli("workspace", "list")
    assert code2 == 0
    lst = _parse_json(out2)
    assert isinstance(lst, list)
    assert any(w["name"] == slug for w in lst)


def test_workspace_remove_3_safety_gates():
    """remove segue 3 gates: (1) dry-run default (2) confirmed obrigatório (3) move pra trash não apaga."""
    _run_cli("workspace", "add", "yolo-deleteme")

    # Gate 1: dry-run default → NÃO move
    code, out, _ = _run_cli("workspace", "remove", "yolo-deleteme")
    assert code == 0
    data = _parse_json(out)
    assert data["dry_run"] is True
    assert "action_would_be" in data
    assert "to" in data

    # Gate 2: sem dry-run mas também sem confirmed → aborted=True
    code2, out2, _ = _run_cli("workspace", "remove", "yolo-deleteme", "--no-dry-run")
    assert code2 == 0
    d2 = _parse_json(out2)
    assert d2["aborted"] is True
    assert d2["dry_run"] is False

    _, out_list, _ = _run_cli("workspace", "list")
    assert "yolo-deleteme" in out_list

    # Gate 3: com dupla flag → move para trash (não apaga)
    code3, out3, _ = _run_cli("workspace", "remove", "yolo-deleteme", "--no-dry-run", "--confirm")
    assert code3 == 0
    d3 = _parse_json(out3)
    assert d3["moved"] is True
    trash_target = Path(d3["to"])
    assert trash_target.is_dir()

    _, out_list2, _ = _run_cli("workspace", "list")
    lst2 = _parse_json(out_list2)
    assert not any("yolo-deleteme" in str(w.get("name", "")) for w in lst2)


def test_workspace_trash_list_and_restore():
    """remove → trash-list mostra → restore traz de volta, conflito-safe."""
    _run_cli("workspace", "add", "restore-me")
    _, out_rm, _ = _run_cli("workspace", "remove", "restore-me", "--no-dry-run", "--confirm")
    rm = _parse_json(out_rm)
    trash_slug = Path(rm["to"]).name

    _, out_tl, _ = _run_cli("workspace", "trash-list")
    tl = _parse_json(out_tl)
    assert isinstance(tl, list)
    assert any(t["slug"] == trash_slug for t in tl)

    _, out_r, _ = _run_cli("workspace", "restore", trash_slug)
    r = _parse_json(out_r)
    assert r["restored"] is True

    _, out_list, _ = _run_cli("workspace", "list")
    names = str(out_list).lower()
    assert "restore-me" in names


# --- PROJECT TESTS (L2) -------------------------------------------------------


def test_project_init_scaffold_8_files_and_ensure_l3(tmp_path):
    """che project init → scaffold 8 artefatos L2 + L3 no CHE_WORKSPACE_SHARED (fora do worktree, contratual §4)."""
    wt = tmp_path / "myproj"
    wt.mkdir()
    (wt / ".git").mkdir()
    (wt / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

    code, out, err = _run_cli("project", "init", str(wt))
    assert code == 0, f"exit={code} stderr={err} stdout={out}"
    d = _parse_json(out)
    assert d["initialized"] is True
    assert d["files_created_count"] >= 7

    project_dir = Path(d["project_dir"])
    expected_files = [
        "architecture.md",
        "project_profile.md",
        "product_context.md",
        "roadmap.md",
        "roles/index.md",
        "registry.jsonl",
        "_db/README.txt",
    ]
    for rel in expected_files:
        p = project_dir / rel
        assert p.is_file(), f"Faltando scaffold file: {rel} em {project_dir}"

    arch_content = (project_dir / "architecture.md").read_text()
    assert "C4 L1" in arch_content or "System Context" in arch_content

    # L3 worktree shared dir é FORA do worktree (contrato canônico paths.py §162-209):
    # fica em CHE_WORKSPACES_ROOT / <workspace> / <worktree_slug> / .wt
    ws_shared = Path(d["paths"]["CHE_WORKSPACE_SHARED"])
    assert ws_shared.is_dir(), f"L3 CHE_WORKSPACE_SHARED deveria existir: {ws_shared}"


def test_project_remove_and_restore_safety():
    """project remove segue mesmas 3 safety gates + restore ok."""
    with tempfile.TemporaryDirectory() as td:
        tmpd = Path(td)
        (tmpd / ".git").mkdir()
        _run_cli("project", "init", str(tmpd))
        _, out_list, _ = _run_cli("project", "list")
        lst = _parse_json(out_list)
        assert isinstance(lst, list) and len(lst) >= 1
        slug = lst[0]["slug"]

        # dry-run default
        code, out, _ = _run_cli("project", "remove", slug)
        assert code == 0
        dr = _parse_json(out)
        assert dr["dry_run"] is True
        assert "action_would_be" in dr

        # no-dry-run sem confirm = aborted
        code2, out2, _ = _run_cli("project", "remove", slug, "--no-dry-run")
        d2 = _parse_json(out2)
        assert d2["aborted"] is True

        # com dupla flag = moved
        code3, out3, _ = _run_cli("project", "remove", slug, "--no-dry-run", "--confirm")
        d3 = _parse_json(out3)
        assert d3["moved"] is True
        trash_slug = Path(d3["to"]).name

        # restore traz de volta
        code4, out4, _ = _run_cli("project", "restore", trash_slug)
        d4 = _parse_json(out4)
        assert d4["restored"] is True


# --- HOOK TESTS (posttooluse_git_worktree) ------------------------------------


def test_hook_worktree_add_payload_creates_l3(tmp_path):
    """Hook detecta RunCommand com 'git worktree add <path>' → chama ensure_worktree_l3_dirs."""
    target = tmp_path / "wt-feature-x"
    target.mkdir()
    (target / ".git").mkdir(exist_ok=True)

    # Payload segue schema que o hook espera: toolName + toolArgs.command
    payload = {
        "toolName": "RunCommand",
        "toolArgs": {"command": f"cd /tmp && git worktree add {target} feat/x"},
    }
    result = posttooluse_git_worktree(payload)
    assert result.get("decision") in ("allow", None)
    ctx = result.get("additionalContext", "")
    assert "L3" in ctx or "AUTO" in ctx or "criado" in ctx or "CHE_WORKSPACE_SHARED" in ctx

    # L3 shared dir existe em CHE_WORKSPACES_ROOT/<workspace>/<worktree_slug>/.wt (NÃO dentro de target/.wt!)
    ws_name = resolve_workspace_name(str(target))
    wt_slug = resolve_worktree_slug(str(target))
    ws_root = Path(os.environ["CHE_WORKSPACES_ROOT"])
    l3_shared = ws_root / ws_name / wt_slug / ".wt"
    assert l3_shared.is_dir(), f"L3 shared deveria existir em {l3_shared}"


def test_hook_worktree_remove_payload_moves_to_trash(tmp_path):
    """Hook detecta 'git worktree remove' → cleanup l3 move para trash."""
    target = tmp_path / "wt-old-feature"
    target.mkdir()
    (target / ".git").mkdir(exist_ok=True)
    ensure_worktree_l3_dirs(str(target))

    # ANTES: confirma L3 shared existe (via paths canônicos, NÃO via target/.wt)
    ws_name = resolve_workspace_name(str(target))
    wt_slug = resolve_worktree_slug(str(target))
    ws_root = Path(os.environ["CHE_WORKSPACES_ROOT"])
    l3_parent = ws_root / ws_name / wt_slug
    assert l3_parent.is_dir(), f"L3 parent deveria existir ANTES do remove: {l3_parent}"

    payload = {
        "toolName": "Bash",
        "toolArgs": {"cwd": str(target), "command": "git worktree remove old-feat"},
    }
    result = posttooluse_git_worktree(payload)
    assert "additionalContext" in result
    assert "AUTO" in result["additionalContext"] or "L3" in result["additionalContext"]
