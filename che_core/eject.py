from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

CHE_REPO_BLACKLIST_DIRS = ("user_rules", "memory", "node_modules", ".git", "bindings")
CHE_REPO_BLACKLIST_FILES = ("bindings/registry.jsonl",)

DEFAULT_TRASH_ROOT = Path.home() / ".che-workspaces" / ".trash" / "che-eject"
CHE_HOME_CANDIDATES = (Path.home() / ".trae",)

GITIGNORE_MARKER_BEGIN = "# >>> CHE PLANNING ARTIFACTS BLACKLIST BEGIN (NÃO EDITAR MANUALMENTE)"
GITIGNORE_MARKER_END = "# <<< CHE PLANNING ARTIFACTS BLACKLIST END"


def _utc_ts_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _is_che_home(path: Path) -> bool:
    return (path / "CHE_RULES.md").is_file() and (path / "skills").is_dir()


def _resolve_che_home(che_home: Optional[Path] = None) -> Path:
    if che_home is not None:
        che_home = Path(che_home).expanduser().resolve()
        if not _is_che_home(che_home):
            raise ValueError(f"che_home fornecido não é um diretório Che válido: {che_home}")
        return che_home
    for cand in CHE_HOME_CANDIDATES:
        cand = cand.expanduser().resolve()
        if _is_che_home(cand):
            return cand
    raise FileNotFoundError(
        "Nenhum diretório Che (~/.trae) encontrado. Use --che-home /caminho/para/.trae para fornecer explicitamente."
    )


def _detect_install_kind(che_home: Path) -> str:
    if (che_home / ".git").is_dir():
        return "git-clone"
    return "copy-install"


def _detect_adapters(che_home: Path) -> dict[str, dict]:
    """Detecta quais adapters multi-agentes (Codex/Claude/Cursor) parecem instalados.
    Verificação leve (symlinks existem, não quebra se não). Retorna status por adapter."""
    out: dict[str, dict] = {}
    # Codex
    codex_home = Path.home() / ".codex"
    agents_home = Path.home() / ".agents"
    codex_state = {
        "agents_md_is_link": (codex_home / "AGENTS.md").is_symlink(),
        "skills_count": 0,
        "commands_count": 0,
        "hooks_json_exists": (codex_home / "hooks.json").exists(),
    }
    skills_dir = agents_home / "skills"
    if skills_dir.is_dir():
        codex_state["skills_count"] = sum(
            1 for lnk in skills_dir.iterdir() if lnk.is_symlink() and _resolve_safe(lnk).is_relative_to(che_home)
        )
    cmds_dir = codex_home / "commands"
    if cmds_dir.is_dir():
        codex_state["commands_count"] = sum(
            1 for lnk in cmds_dir.iterdir() if lnk.is_symlink() and _resolve_safe(lnk).is_relative_to(che_home)
        )
    out["codex"] = {
        "installed_heuristic": (
            codex_state["agents_md_is_link"] or codex_state["skills_count"] > 0 or codex_state["commands_count"] > 0
        ),
        "details": codex_state,
        "uninstall_script": che_home / "adapters" / "codex" / "uninstall.sh",
    }
    # Claude
    claude_home = Path.home() / ".claude"
    claude_state = {
        "claude_md_is_link": (claude_home / "CLAUDE.md").is_symlink(),
        "skills_count": 0,
        "commands_count": 0,
        "settings_has_hooks": False,
    }
    skills_dir = claude_home / "skills"
    if skills_dir.is_dir():
        claude_state["skills_count"] = sum(
            1 for lnk in skills_dir.iterdir() if lnk.is_symlink() and _resolve_safe(lnk).is_relative_to(che_home)
        )
    cmds_dir = claude_home / "commands"
    if cmds_dir.is_dir():
        claude_state["commands_count"] = sum(
            1 for lnk in cmds_dir.iterdir() if lnk.is_symlink() and _resolve_safe(lnk).is_relative_to(che_home)
        )
    settings_path = claude_home / "settings.json"
    if settings_path.exists():
        try:
            s = json.loads(settings_path.read_text())
            claude_state["settings_has_hooks"] = bool(s.get("hooks"))
        except Exception:
            claude_state["settings_has_hooks"] = False
    out["claude"] = {
        "installed_heuristic": (
            claude_state["claude_md_is_link"]
            or claude_state["skills_count"] > 0
            or claude_state["commands_count"] > 0
            or claude_state["settings_has_hooks"]
        ),
        "details": claude_state,
        "uninstall_script": che_home / "adapters" / "claude" / "uninstall.sh",
    }
    # Cursor (project-based — global não tem, só informativo)
    out["cursor"] = {
        "installed_heuristic": False,
        "details": {
            "note": "Cursor adapter é project-based. Ejetar globalmente requer "
            "remoção manual de AGENTS.md e .cursor/rules/ em cada projeto cliente."
        },
        "uninstall_script": che_home / "adapters" / "cursor" / "uninstall.sh",
    }
    return out


def _resolve_safe(p: Path) -> Path:
    try:
        return p.resolve()
    except Exception:
        return p


def _trash_ensure(che_home: Path, trash_root: Optional[Path] = None) -> Path:
    if trash_root is None:
        trash_root = DEFAULT_TRASH_ROOT
    trash_root = Path(trash_root).expanduser().resolve()
    trash_root.mkdir(parents=True, exist_ok=True)
    return trash_root


def _manifest_path(trash_dir: Path) -> Path:
    return trash_dir / "eject-manifest.json"


def _run_uninstall_script(script: Path, dry_run: bool) -> tuple[int, str]:
    if not script.exists():
        return (0, f"skip: script não existe {script}")
    if dry_run:
        return (0, f"[dry-run] iria rodar: bash {script}")
    try:
        res = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return (res.returncode, (res.stdout or "") + (res.stderr or ""))
    except Exception as e:
        return (2, f"erro ao rodar {script}: {e!r}")


def _remove_client_gitignore_snippets(
    repo_roots_to_check: Optional[list[Path]] = None, dry_run: bool = True
) -> list[dict]:
    """Remove (ou simula) o snippet da blacklist injetado por install-che.sh
    nos .gitignore de projetos clientes. Só toca arquivos que contêm os markers.
    Se repo_roots_to_check for None, faz uma busca leve em pastas comuns do usuário."""
    affected: list[dict] = []
    candidates: list[Path] = []
    if repo_roots_to_check:
        candidates = [Path(p).expanduser().resolve() for p in repo_roots_to_check]
    else:
        code_home = Path.home() / "code"
        if code_home.is_dir():
            # Busca rasa: primeiro nível de ~/code procurando .gitignore com marker
            try:
                for entry in code_home.iterdir():
                    gi = entry / ".gitignore"
                    if gi.is_file():
                        candidates.append(entry)
            except Exception:
                pass
    seen = set()
    for root in candidates:
        try:
            root = root.resolve()
        except Exception:
            continue
        if root in seen:
            continue
        seen.add(root)
        gi = root / ".gitignore"
        if not gi.is_file():
            continue
        try:
            content = gi.read_text()
        except Exception:
            continue
        if GITIGNORE_MARKER_BEGIN not in content:
            continue
        # Build new content removing block between markers
        new_lines: list[str] = []
        inside = False
        removed_lines = 0
        for line in content.splitlines(keepends=True):
            if line.rstrip("\n") == GITIGNORE_MARKER_BEGIN:
                inside = True
                removed_lines += 1
                continue
            if line.rstrip("\n") == GITIGNORE_MARKER_END:
                inside = False
                removed_lines += 1
                continue
            if inside:
                removed_lines += 1
                continue
            new_lines.append(line)
        if dry_run:
            affected.append(
                {
                    "repo_root": str(root),
                    "gitignore": str(gi),
                    "action": "[dry-run] removeria snippet (linhas a remover: " + str(removed_lines) + ")",
                    "removed_lines": removed_lines,
                }
            )
            continue
        # trailing newline safety
        new_content = "".join(new_lines)
        if not new_content.endswith("\n"):
            new_content += "\n"
        gi.write_text(new_content)
        affected.append(
            {
                "repo_root": str(root),
                "gitignore": str(gi),
                "action": "removido snippet",
                "removed_lines": removed_lines,
            }
        )
    return affected


def eject_plan(
    che_home: Optional[Path] = None,
    trash_root: Optional[Path] = None,
    keep_git_repo: bool = True,
    scan_client_repos: Optional[list[Path]] = None,
) -> dict:
    """Retorna um plano do que o eject vai fazer, SEM escrever nada.
    Usado pelo dry-run e como pre-check do apply."""
    che_home = _resolve_che_home(che_home)
    trash_root = _trash_ensure(che_home, trash_root)
    install_kind = _detect_install_kind(che_home)
    adapters = _detect_adapters(che_home)
    ts = _utc_ts_slug()
    trash_slug = f"che-eject--{che_home.name}--{ts}"
    trash_dir = trash_root / trash_slug
    plan = {
        "che_home": str(che_home),
        "install_kind": install_kind,
        "trash_root": str(trash_root),
        "trash_slug": trash_slug,
        "trash_dir": str(trash_dir),
        "adapters": adapters,
        "keep_git_repo_user_choice": keep_git_repo,
        "destructive_blacklist_never_touches": {
            "dirs_inside_che_home": list(CHE_REPO_BLACKLIST_DIRS),
            "files_inside_che_home": list(CHE_REPO_BLACKLIST_FILES),
        },
        "what_will_happen": [],
    }
    # Step 1: adapters
    for name, info in adapters.items():
        if name == "cursor":
            plan["what_will_happen"].append(
                {
                    "step": f"eject-adapter-{name}",
                    "kind": "informational",
                    "note": info["details"].get("note", ""),
                }
            )
            continue
        plan["what_will_happen"].append(
            {
                "step": f"eject-adapter-{name}",
                "kind": "uninstall-script" if info["installed_heuristic"] else "skip-not-installed",
                "script": str(info["uninstall_script"]),
            }
        )
    # Step 2: ~/.trae destino (git clone vs copy)
    if install_kind == "git-clone":
        if keep_git_repo:
            plan["what_will_happen"].append(
                {
                    "step": "eject-che-home",
                    "kind": "keep-as-regular-repo",
                    "note": (
                        "Mantendo ~/.trae como diretório comum (continua sendo um repo git "
                        "seu). Para remover o hook global do Trae: Settings → Rules → remover "
                        "as referências ao AGENTS.md e user_rules."
                    ),
                }
            )
        else:
            plan["what_will_happen"].append(
                {
                    "step": "eject-che-home",
                    "kind": "move-to-trash-keep-blacklist",
                    "note": (
                        f"Move TODO CONTEÚDO NÃO-BLACKLIST de {che_home} → {trash_dir}. "
                        "Blacklist (user_rules/, memory/, bindings/registry.jsonl, .git/) "
                        "PERMANECE no lugar. NENHUM rm. Tudo mv para .trash/che-eject/ com manifesto."
                    ),
                }
            )
    else:
        plan["what_will_happen"].append(
            {
                "step": "eject-che-home",
                "kind": "move-to-trash-keep-blacklist",
                "note": (
                    f"Move TODO CONTEÚDO NÃO-BLACKLIST de {che_home} → {trash_dir}. "
                    "Blacklist (user_rules/, memory/, bindings/registry.jsonl) PERMANECE. "
                    "NENHUM rm."
                ),
            }
        )
    # Step 3: client .gitignore snippets
    snippets = _remove_client_gitignore_snippets(scan_client_repos, dry_run=True)
    plan["what_will_happen"].append(
        {
            "step": "eject-client-gitignore",
            "kind": "remove-injected-blacklist-snippets",
            "affected_count": len(snippets),
            "affected": snippets,
        }
    )
    return plan


def eject_apply(plan: dict, dry_run: bool = True, confirmed: bool = False, i_know_what_im_doing: bool = False) -> dict:
    """Aplica o plano de eject.
    SAFETY GATES: (1) dry_run=True por default; (2) confirmed=True requerido;
    (3) i_know_what_im_doing=True requerido. Falta qualquer um = só retorna plano."""
    if not confirmed or not i_know_what_im_doing:
        return {
            "status": "blocked-safety-gates",
            "required_flags": ["--confirmed", "--i-know-what-im-doing", "(--apply or dry_run=False)"],
            "note": (
                "Eject é uma operação destrutiva controlada. Para rodar de verdade, "
                "forneça --confirmed --i-know-what-im-doing --apply. "
                "NENHUM arquivo é apagado; tudo vai para .trash/che-eject/ com restore disponível."
            ),
            "plan": plan,
        }
    if dry_run:
        return {"status": "dry-run", "plan": plan}
    che_home = Path(plan["che_home"])
    trash_dir = Path(plan["trash_dir"])
    keep_git = bool(plan["keep_git_repo_user_choice"])
    install_kind = plan["install_kind"]
    result = {"status": "applied", "che_home": str(che_home), "steps": []}
    # Step 1: adapters
    for name, info in plan["adapters"].items():
        if name == "cursor" or not info["installed_heuristic"]:
            result["steps"].append({"adapter": name, "status": "skipped", "note": str(info["details"])})
            continue
        script = Path(info["uninstall_script"])
        rc, out = _run_uninstall_script(script, dry_run=False)
        result["steps"].append(
            {
                "adapter": name,
                "status": "ok" if rc == 0 else f"fail-rc-{rc}",
                "output_tail": (out[-800:] if out else ""),
            }
        )
    # Step 2: move che-home non-blacklist para trash (se não for keep)
    should_move = not (install_kind == "git-clone" and keep_git)
    if should_move:
        trash_dir.mkdir(parents=True, exist_ok=True)
        moved_count = 0
        kept_count = 0
        for entry in che_home.iterdir():
            name = entry.name
            if name in CHE_REPO_BLACKLIST_DIRS:
                kept_count += 1
                continue
            if str(entry.relative_to(che_home)) in CHE_REPO_BLACKLIST_FILES:
                kept_count += 1
                continue
            dest = trash_dir / name
            if dest.exists():
                # não deve ocorrer pois trash_dir tem timestamp único; segurança extra
                dest = trash_dir / f"{name}--{_utc_ts_slug()}"
            shutil.move(str(entry), str(dest))
            moved_count += 1
        manifest = {
            "ejected_at_utc": datetime.now(timezone.utc).isoformat(),
            "che_home": str(che_home),
            "install_kind": install_kind,
            "items_moved_count": moved_count,
            "items_kept_blacklist_count": kept_count,
            "kept_blacklist": {
                "dirs": [d for d in CHE_REPO_BLACKLIST_DIRS if (che_home / d).exists()],
                "files": [f for f in CHE_REPO_BLACKLIST_FILES if (che_home / f).exists()],
            },
        }
        _manifest_path(trash_dir).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        result["steps"].append(
            {
                "kind": "che-home-moved-to-trash",
                "trash_dir": str(trash_dir),
                "moved_count": moved_count,
                "kept_blacklist_count": kept_count,
                "manifest": str(_manifest_path(trash_dir)),
            }
        )
    else:
        kept_note = "mantido como repo/diretório comum (user_rules/memory/bindings intocados)."
        # também cria manifesto mínimo em trash_dir vazio, para que restore seja possível caso mude de ideia
        trash_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "ejected_at_utc": datetime.now(timezone.utc).isoformat(),
            "che_home": str(che_home),
            "install_kind": install_kind,
            "items_moved_count": 0,
            "kept_blacklist_count": 0,
            "keep_as_regular_repo": True,
        }
        _manifest_path(trash_dir).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        result["steps"].append(
            {
                "kind": "che-home-kept",
                "note": kept_note,
                "manifest": str(_manifest_path(trash_dir)),
            }
        )
    # Step 3: .gitignore snippets clientes
    snippets_info = next((w for w in plan["what_will_happen"] if w["step"] == "eject-client-gitignore"), None)
    affected_repos = None
    if snippets_info and snippets_info["affected_count"] > 0:
        affected_repos = [Path(a["repo_root"]) for a in snippets_info["affected"]]
    done_snippets = _remove_client_gitignore_snippets(affected_repos, dry_run=False)
    result["steps"].append(
        {
            "kind": "client-gitignore-snippets-removed",
            "count": len(done_snippets),
            "items": done_snippets,
        }
    )
    # Final hint
    result["hints"] = [
        "Nenhum arquivo foi apagado. Itens movidos estão em: " + str(trash_dir),
        f"Para desfazer: python3 -m che_core.cli eject restore --trash-slug {plan['trash_slug']}",
        "Se quiser também remover ~/.che-workspaces/.registry/ (L2 projects), faça manualmente "
        "(é blacklist do eject por conter metadados de projetos atrelados a worktrees ainda em uso).",
    ]
    return result


def eject_trash_list(trash_root: Optional[Path] = None) -> list[dict]:
    if trash_root is not None:
        trash_root = _trash_ensure(Path.home(), trash_root)
    else:
        trash_root = _trash_ensure(_resolve_che_home(), None)
    out: list[dict] = []
    if not trash_root.is_dir():
        return out
    for d in sorted(trash_root.iterdir()):
        if not d.is_dir():
            continue
        manifest = _manifest_path(d)
        entry = {
            "trash_slug": d.name,
            "trash_dir": str(d),
            "manifest_exists": manifest.is_file(),
            "manifest": None,
        }
        if manifest.is_file():
            try:
                entry["manifest"] = json.loads(manifest.read_text())
            except Exception as e:
                entry["manifest"] = {"error": str(e)}
        out.append(entry)
    return out


def eject_restore(
    trash_slug: str, trash_root: Optional[Path] = None, dry_run: bool = True, confirmed: bool = False
) -> dict:
    """Reverte um eject. Valor padrão dry_run=True (mesma safety gate dos outros).
    confirmed=True necessário para aplicar."""
    if trash_root is not None:
        trash_root = _trash_ensure(Path.home(), trash_root)
    else:
        trash_root = _trash_ensure(_resolve_che_home(), None)
    trash_dir = trash_root / trash_slug
    if not trash_dir.is_dir():
        raise FileNotFoundError(f"Trash slug não encontrado: {trash_slug} em {trash_root}")
    manifest = _manifest_path(trash_dir)
    if not manifest.is_file():
        raise FileNotFoundError(f"Manifesto ausente em {manifest}. Restore abortado.")
    manifest_data = json.loads(manifest.read_text())
    che_home = Path(manifest_data["che_home"])
    result = {
        "status": "dry-run" if dry_run or not confirmed else "applied",
        "trash_slug": trash_slug,
        "trash_dir": str(trash_dir),
        "che_home": str(che_home),
        "moved_back_count": 0,
        "skipped_count": 0,
        "items": [],
    }
    if dry_run or not confirmed:
        if not confirmed:
            result["status"] = "blocked-missing-confirmed"
            result["note"] = (
                "Para restaurar de verdade, forneça --confirmed --apply. "
                "Itens em che_home conflitantes NÃO são sobrescritos (fica em skipped)."
            )
        preview = []
        for entry in trash_dir.iterdir():
            if entry.name == "eject-manifest.json":
                continue
            preview.append(entry.name)
        result["items_preview_count"] = len(preview)
        return result
    for entry in trash_dir.iterdir():
        if entry.name == "eject-manifest.json":
            continue
        dest = che_home / entry.name
        if dest.exists():
            result["items"].append({"name": entry.name, "status": "skipped-dest-exists"})
            result["skipped_count"] += 1
            continue
        shutil.move(str(entry), str(dest))
        result["items"].append({"name": entry.name, "status": "restored"})
        result["moved_back_count"] += 1
    # Reinstala adapters após restore (best-effort)
    setup_script = che_home / "scripts" / "setup-adapters.sh"
    if setup_script.is_file():
        rc, out = _run_uninstall_script(setup_script, dry_run=False)
        result["adapter_reinstall"] = {
            "script": str(setup_script),
            "exit_code": rc,
            "output_tail": (out[-500:] if out else ""),
        }
    return result
