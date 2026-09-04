import json
import shutil
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from che_core.paths import compute_paths, get_workspaces_root

STATE_DB_FILENAME = "che_state.sqlite"
RAG_DB_FILENAME = "che_rag.sqlite"


def _db_sizes(project_dir: Path) -> Dict[str, int]:
    sizes: Dict[str, int] = {}
    for name in (STATE_DB_FILENAME, RAG_DB_FILENAME):
        p = project_dir / name
        if p.exists() and p.is_file():
            sizes[name] = p.stat().st_size
    return sizes


def export_project(
    worktree_root: str,
    output_file: str,
    include_db: bool = False,
    db_size_limit_mb: int = 250,
) -> str:
    """
    Export durable project data (L2 and L3) to a tar.gz archive.
    Excludes sessions and ephemeral data.

    If include_db=True: includes che_state.sqlite + che_rag.sqlite IF total
    size <= db_size_limit_mb. Otherwise writes _db/SKIPPED.txt with reasons.
    """
    paths = compute_paths(worktree_root, "export-session")

    project_dir = Path(paths["CHE_PROJECT_DIR"])
    workspace_shared = Path(paths["CHE_WORKSPACE_SHARED"])

    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        db_total_bytes = 0
        db_skipped_reason: Optional[str] = None
        db_files_incl: Dict[str, str] = {}

        metadata: Dict[str, Any] = {
            "version": "1.1",
            "exported_at": datetime.utcnow().isoformat(),
            "project_slug": paths["CHE_PROJECT_SLUG"],
            "worktree_slug": paths["CHE_WORKTREE_SLUG"],
            "workspace_name": paths["CHE_WORKSPACE_NAME"],
            "original_worktree_root": str(Path(worktree_root).resolve()),
            "include_db": bool(include_db),
            "db_size_limit_mb": int(db_size_limit_mb),
            "db_total_bytes": 0,
            "db_skipped": None,
        }

        if include_db:
            sizes = _db_sizes(project_dir)
            db_total_bytes = sum(sizes.values())
            limit_bytes = db_size_limit_mb * 1024 * 1024
            metadata["db_total_bytes"] = db_total_bytes
            if sizes and db_total_bytes > limit_bytes:
                db_skipped_reason = (
                    f"Databases total {db_total_bytes} bytes "
                    f"({db_total_bytes / 1024 / 1024:.2f} MB) exceeds limit "
                    f"{db_size_limit_mb} MB ({limit_bytes} bytes). "
                    f"Per-file sizes: {sizes}. Use --db-size-limit-mb to raise."
                )
                metadata["db_skipped"] = db_skipped_reason
            elif sizes:
                db_folder = tmp_path / "_db"
                db_folder.mkdir(parents=True, exist_ok=True)
                for name, size in sizes.items():
                    shutil.copy2(project_dir / name, db_folder / name)
                    db_files_incl[name] = f"{size} bytes"

        if db_skipped_reason:
            db_folder = tmp_path / "_db"
            db_folder.mkdir(parents=True, exist_ok=True)
            note = (
                f"Che export include_db skipped.\n\n"
                f"{db_skipped_reason}\n\n"
                f"Run: che export --include-db --db-size-limit-mb N worktree path\n"
                f"where N is larger than current total ({db_total_bytes} bytes).\n"
            )
            (db_folder / "SKIPPED.txt").write_text(note, encoding="utf-8")

        with open(tmp_path / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        def _db_ignore(path: str, names) -> list:
            excluded = []
            if Path(path) == project_dir:
                if STATE_DB_FILENAME in names:
                    excluded.append(STATE_DB_FILENAME)
                if RAG_DB_FILENAME in names:
                    excluded.append(RAG_DB_FILENAME)
            if "sessions" in names:
                excluded.append("sessions")
            return excluded

        shutil.copytree(project_dir, tmp_path / "project", ignore=_db_ignore)

        if workspace_shared.exists():

            def ignore_sessions(path, names):
                if "sessions" in names:
                    return ["sessions"]
                return []

            shutil.copytree(workspace_shared, tmp_path / "worktree_shared", ignore=ignore_sessions)

        output_path = Path(output_file).resolve()
        if output_path.suffix != ".gz":
            output_path = output_path.with_suffix(".che.tar.gz")

        with tarfile.open(output_path, "w:gz") as tar:
            tar.add(tmp_path, arcname=".")

        return str(output_path)


def import_project(
    archive_path: str,
    target_workspace: Optional[str] = None,
    include_db: bool = False,
) -> Dict[str, Any]:
    """
    Import project data from a tar.gz archive.
    Handles naming conflicts by appending a timestamp suffix.

    If include_db=True and archive contains _db/*.sqlite files → they are
    moved into the target CHE_PROJECT_DIR with --import suffix if a file with
    the same name already exists.
    """
    archive_path = Path(archive_path).resolve()
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    workspaces_root = get_workspaces_root()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(path=tmp_path)

        metadata_file = tmp_path / "metadata.json"
        if not metadata_file.exists():
            raise ValueError("Invalid Che archive: metadata.json missing")

        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        project_slug = metadata["project_slug"]
        worktree_slug = metadata["worktree_slug"]
        workspace_name = target_workspace or metadata["workspace_name"]
        archive_include_db: bool = bool(metadata.get("include_db", False))
        archive_db_skipped = metadata.get("db_skipped", None)

        target_project_dir = workspaces_root / ".registry" / "projects" / project_slug
        if target_project_dir.exists():
            suffix = datetime.now().strftime("%Y%m%d-%H%M")
            project_slug = f"{project_slug}--import-{suffix}"
            target_project_dir = workspaces_root / ".registry" / "projects" / project_slug

        target_workspace_dir = workspaces_root / workspace_name / worktree_slug
        if target_workspace_dir.exists():
            suffix = datetime.now().strftime("%Y%m%d-%H%M")
            worktree_slug = f"{worktree_slug}--import-{suffix}"
            target_workspace_dir = workspaces_root / workspace_name / worktree_slug

        target_project_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp_path / "project"), str(target_project_dir))

        imported_shared_path = tmp_path / "worktree_shared"
        target_shared_path = target_workspace_dir / ".wt"
        if imported_shared_path.exists():
            target_shared_path.mkdir(parents=True, exist_ok=True)
            for item in imported_shared_path.iterdir():
                dest = target_shared_path / item.name
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                shutil.move(str(item), str(dest))

        db_imported: Dict[str, str] = {}
        db_skipped: Dict[str, str] = {}
        db_folder = tmp_path / "_db"
        if include_db and archive_include_db and db_folder.exists():
            for db_name in (STATE_DB_FILENAME, RAG_DB_FILENAME):
                src = db_folder / db_name
                if not src.exists():
                    continue
                dest = target_project_dir / db_name
                if dest.exists():
                    suffix = datetime.now().strftime("%Y%m%d-%H%M")
                    dest = target_project_dir / f"{Path(db_name).stem}--import-{suffix}{Path(db_name).suffix}"
                shutil.move(str(src), str(dest))
                db_imported[db_name] = str(dest)
            skipped_note = db_folder / "SKIPPED.txt"
            if skipped_note.exists():
                db_skipped["_note"] = skipped_note.read_text(encoding="utf-8")
        elif include_db and not archive_include_db:
            db_skipped["reason"] = "archive was created without --include-db flag (metadata.include_db=false)"
        elif include_db and archive_db_skipped:
            db_skipped["reason"] = (
                f"archive created with --include-db but DBs exceeded size limit during export: {archive_db_skipped}"
            )

        result: Dict[str, Any] = {
            "project_slug": project_slug,
            "worktree_slug": worktree_slug,
            "workspace_name": workspace_name,
            "project_dir": str(target_project_dir),
            "worktree_dir": str(target_workspace_dir),
        }
        if include_db:
            result["db"] = {
                "imported": db_imported,
                "skipped": db_skipped,
            }
        return result
