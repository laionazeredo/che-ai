import json
import os
import subprocess
import sys
from pathlib import Path

from che_core.eject import (
    GITIGNORE_MARKER_BEGIN,
    GITIGNORE_MARKER_END,
    eject_apply,
    eject_plan,
    eject_restore,
    eject_trash_list,
)

CHE_CLI_CMD = [sys.executable, "-m", "che_core.cli"]


def _run_cli(*args):
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


def _fake_che_home(root: Path, kind: str = "copy-install") -> Path:
    che = root / "dot-trae"
    che.mkdir(parents=True, exist_ok=True)
    (che / "CHE_RULES.md").write_text("rules\n", encoding="utf-8")
    (che / "CHE_COMMANDS.md").write_text("commands\n", encoding="utf-8")
    (che / "README.md").write_text("readme\n", encoding="utf-8")
    (che / "che_core").mkdir()
    (che / "che_core" / "__init__.py").write_text("", encoding="utf-8")
    (che / "che_core" / "eject.py").write_text("pass\n", encoding="utf-8")
    (che / "skills").mkdir()
    (che / "skills" / "engineering-contracts").mkdir()
    (che / "skills" / "engineering-contracts" / "SKILL.md").write_text("x\n", encoding="utf-8")
    (che / "commands").mkdir()
    (che / "commands" / "che-eject.md").write_text("y\n", encoding="utf-8")
    (che / "scripts").mkdir()
    (che / "scripts" / "setup-adapters.sh").write_text("#!/bin/sh\necho adapters\n", encoding="utf-8")
    # BLACKLIST ABSOLUTA
    (che / "user_rules").mkdir()
    (che / "user_rules" / "my-rules.md").write_text("keep\n", encoding="utf-8")
    bindings = che / "bindings"
    bindings.mkdir()
    (bindings / "registry.jsonl").write_text('{"k":"v"}\n', encoding="utf-8")
    (che / "memory").mkdir()
    (che / "memory" / "state.sqlite").write_bytes(b"\x00\x01")
    (che / "node_modules").mkdir()
    (che / "node_modules" / "dep").mkdir()
    if kind == "git-clone":
        (che / ".git").mkdir()
        (che / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    return che


def _fake_client_repo(root: Path, with_snippet: bool = True) -> Path:
    client = root / "client-project"
    client.mkdir(parents=True, exist_ok=True)
    lines = [".env", "node_modules/"]
    if with_snippet:
        lines += [
            GITIGNORE_MARKER_BEGIN,
            ".che-workspaces/",
            ".che-export-*.tar.gz",
            GITIGNORE_MARKER_END,
        ]
    lines += ["dist/", "*.log"]
    (client / ".gitignore").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return client


def _first_step_of_kind(res, kind):
    for s in res.get("steps", []):
        if s.get("kind") == kind:
            return s
    return None


# ── 1. install_kind detect + blacklist info no plano ────────────────────────


def test_install_kind_detect_and_plan_fields(tmp_path):
    che_copy = _fake_che_home(tmp_path / "a", kind="copy-install")
    che_git = _fake_che_home(tmp_path / "b", kind="git-clone")
    trash = tmp_path / "trash"

    plan_copy = eject_plan(che_home=che_copy, trash_root=trash)
    plan_git = eject_plan(che_home=che_git, trash_root=trash)

    assert plan_copy["install_kind"] == "copy-install"
    assert plan_git["install_kind"] == "git-clone"
    assert plan_git["keep_git_repo_user_choice"] is True
    bl = plan_copy["destructive_blacklist_never_touches"]
    assert "user_rules" in bl["dirs_inside_che_home"]
    assert ".git" in bl["dirs_inside_che_home"]
    assert "bindings/registry.jsonl" in bl["files_inside_che_home"]
    assert isinstance(plan_copy["what_will_happen"], list) and len(plan_copy["what_will_happen"]) >= 2


# ── 2. 3 safety gates BLOQUEIAM sem as flags ────────────────────────────────


def test_eject_apply_safety_gates_block(tmp_path):
    che = _fake_che_home(tmp_path, "copy-install")
    plan = eject_plan(che_home=che, trash_root=tmp_path / "tr")

    # Caso A: dry_run=True (default) → status dry-run
    res_a = eject_apply(plan, dry_run=True, confirmed=False, i_know_what_im_doing=False)
    assert res_a["status"] == "dry-run" or res_a["status"] == "blocked-safety-gates"
    assert (che / "CHE_RULES.md").exists()

    # Caso B: --apply mas sem confirmed → blocked
    res_b = eject_apply(plan, dry_run=False, confirmed=False, i_know_what_im_doing=True)
    assert res_b["status"] == "blocked-safety-gates"
    assert (che / "CHE_RULES.md").exists()

    # Caso C: --apply + confirmed mas SEM --i-know-what-im-doing → blocked
    res_c = eject_apply(plan, dry_run=False, confirmed=True, i_know_what_im_doing=False)
    assert res_c["status"] == "blocked-safety-gates"
    assert (che / "CHE_RULES.md").exists()

    # Caso D: tudo False + dry_run=False → blocked
    res_d = eject_apply(plan, dry_run=False, confirmed=False, i_know_what_im_doing=False)
    assert res_d["status"] == "blocked-safety-gates"


# ── 3. copy-install — whitelist movida · blacklist intacta ──────────────────


def test_copy_install_moves_whitelist_preserves_blacklist(tmp_path):
    che = _fake_che_home(tmp_path, "copy-install")
    trash_root = tmp_path / "trash"
    plan = eject_plan(che_home=che, trash_root=trash_root)
    res = eject_apply(plan, dry_run=False, confirmed=True, i_know_what_im_doing=True)

    assert res["status"] == "applied"
    step_move = _first_step_of_kind(res, "che-home-moved-to-trash")
    assert step_move is not None
    trash_dir = Path(step_move["trash_dir"])
    assert trash_dir.is_dir()
    assert step_move["moved_count"] >= 7  # CHE_RULES.md, CHE_COMMANDS, README, che_core, skills, commands, scripts
    assert step_move["kept_blacklist_count"] >= 4  # user_rules, bindings, memory, node_modules (copy-install não tem .git)

    # Whitelist FORA de che_home / DENTRO da trash
    assert not (che / "CHE_RULES.md").exists()
    assert not (che / "che_core").is_dir()
    assert not (che / "skills").is_dir()
    assert (trash_dir / "CHE_RULES.md").exists()
    assert (trash_dir / "che_core" / "eject.py").exists()

    # BLACKLIST continua em che_home
    assert (che / "user_rules" / "my-rules.md").is_file()
    assert (che / "bindings" / "registry.jsonl").is_file()
    assert (che / "memory" / "state.sqlite").is_file()
    assert (che / "node_modules" / "dep").is_dir()


# ── 4. git-clone keep-git default — NÃO move nada ───────────────────────────


def test_git_clone_keep_git_default_does_not_move(tmp_path):
    che = _fake_che_home(tmp_path, "git-clone")
    trash_root = tmp_path / "trash"
    plan = eject_plan(che_home=che, trash_root=trash_root, keep_git_repo=True)
    res = eject_apply(plan, dry_run=False, confirmed=True, i_know_what_im_doing=True)

    assert res["status"] == "applied"
    step_keep = _first_step_of_kind(res, "che-home-kept")
    assert step_keep is not None
    # Whitelist CONTINUA em che_home
    assert (che / "CHE_RULES.md").is_file()
    assert (che / "che_core" / "eject.py").is_file()
    assert (che / ".git" / "HEAD").is_file()
    # Nenhum item whitelist foi movido
    assert (che / "skills").is_dir()
    assert (che / "README.md").is_file()


# ── 5. snippet .gitignore markers BEGIN/END só removidos ────────────────────


def test_remove_client_gitignore_snippet_only(tmp_path):
    clientA = _fake_client_repo(tmp_path / "a", with_snippet=True)
    clientB = _fake_client_repo(tmp_path / "b", with_snippet=False)

    che = _fake_che_home(tmp_path / "che", "copy-install")
    plan = eject_plan(
        che_home=che,
        trash_root=tmp_path / "tr",
        scan_client_repos=[clientA, clientB],
    )
    res = eject_apply(plan, dry_run=False, confirmed=True, i_know_what_im_doing=True)

    contentA = (clientA / ".gitignore").read_text(encoding="utf-8").splitlines()
    contentB = (clientB / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert GITIGNORE_MARKER_BEGIN not in contentA
    assert GITIGNORE_MARKER_END not in contentA
    assert ".che-workspaces/" not in contentA
    assert ".env" in contentA and "node_modules/" in contentA
    assert "dist/" in contentA and "*.log" in contentA
    assert ".env" in contentB and "dist/" in contentB

    step_snip = _first_step_of_kind(res, "client-gitignore-snippets-removed")
    assert step_snip is not None
    assert step_snip.get("count", 0) >= 1


# ── 6. trash-list retorna manifests JSON válidos ─────────────────────────────


def test_eject_trash_list_returns_manifests(tmp_path):
    che = _fake_che_home(tmp_path, "copy-install")
    trash_root = tmp_path / "my-trash"
    plan = eject_plan(che_home=che, trash_root=trash_root)
    eject_apply(plan, dry_run=False, confirmed=True, i_know_what_im_doing=True)

    entries = eject_trash_list(trash_root=trash_root)
    assert isinstance(entries, list) and len(entries) >= 1
    entry = entries[0]
    assert "trash_slug" in entry
    assert "trash_dir" in entry
    assert entry["manifest_exists"] is True
    manifest = entry["manifest"]
    assert manifest is not None
    assert manifest["install_kind"] == "copy-install"
    assert manifest["che_home"].endswith("dot-trae")
    assert "items_moved_count" in manifest
    assert manifest["items_moved_count"] > 0


# ── 7. restore — move de volta · conflito = skipped · não sobrescreve ────────


def test_restore_moves_back_refuses_conflict_then_succeeds(tmp_path):
    che = _fake_che_home(tmp_path / "root", "copy-install")
    trash_root = tmp_path / "tr"

    plan = eject_plan(che_home=che, trash_root=trash_root)
    res_eject = eject_apply(plan, dry_run=False, confirmed=True, i_know_what_im_doing=True)
    assert res_eject["status"] == "applied"
    assert not (che / "CHE_RULES.md").exists()

    # Pega o slug via trash_list
    entries = eject_trash_list(trash_root=trash_root)
    assert len(entries) == 1
    slug = entries[0]["trash_slug"]
    assert slug.startswith("che-eject--")

    # Block: confirmed missing
    res_block = eject_restore(slug, trash_root=trash_root, dry_run=False, confirmed=False)
    assert res_block["status"] == "blocked-missing-confirmed"

    # Cria arquivo conflituoso e roda restore confirmed
    (che / "CHE_RULES.md").write_text("CONFLITO\n", encoding="utf-8")
    res_conflict = eject_restore(slug, trash_root=trash_root, dry_run=False, confirmed=True)
    # Detecta conflito via skipped_count > 0, NÃO aborta global
    assert res_conflict["status"] == "applied"
    assert res_conflict["skipped_count"] >= 1
    # Conflito NÃO sobrescrito
    assert (che / "CHE_RULES.md").read_text(encoding="utf-8") == "CONFLITO\n"

    # Remove conflito → restore deve mover tudo de volta
    (che / "CHE_RULES.md").unlink()
    res_ok = eject_restore(slug, trash_root=trash_root, dry_run=False, confirmed=True)
    assert res_ok["status"] == "applied"
    assert res_ok["moved_back_count"] >= 1
    assert (che / "CHE_RULES.md").is_file()
    assert (che / "che_core" / "eject.py").is_file()
    assert (che / "skills").is_dir()
    # Blacklist intacta
    assert (che / "user_rules" / "my-rules.md").is_file()
    assert (che / "bindings" / "registry.jsonl").is_file()
    assert (che / "memory" / "state.sqlite").is_file()
