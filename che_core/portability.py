import json
import os
import shutil
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from che_core.paths import compute_paths, get_workspaces_root, get_che_home

def export_project(worktree_root: str, output_file: str) -> str:
    """
    Export durable project data (L2 and L3) to a tar.gz archive.
    Excludes sessions and ephemeral data.
    """
    # Use a dummy session ID as we don't care about session data
    paths = compute_paths(worktree_root, "export-session")
    
    project_dir = Path(paths["CHE_PROJECT_DIR"])
    workspace_shared = Path(paths["CHE_WORKSPACE_SHARED"])
    
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")
        
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Metadata
        metadata = {
            "version": "1.0",
            "exported_at": datetime.utcnow().isoformat(),
            "project_slug": paths["CHE_PROJECT_SLUG"],
            "worktree_slug": paths["CHE_WORKTREE_SLUG"],
            "workspace_name": paths["CHE_WORKSPACE_NAME"],
            "original_worktree_root": str(Path(worktree_root).resolve())
        }
        
        with open(tmp_path / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
            
        # Copy Project Level (L2)
        shutil.copytree(project_dir, tmp_path / "project")
        
        # Copy Worktree Shared Level (L3)
        if workspace_shared.exists():
            shutil.copytree(workspace_shared, tmp_path / "worktree_shared")
            
        # Create archive
        output_path = Path(output_file).resolve()
        if output_path.suffix != ".gz":
            output_path = output_path.with_suffix(".che.tar.gz")
            
        with tarfile.open(output_path, "w:gz") as tar:
            tar.add(tmp_path, arcname=".")
            
        return str(output_path)

def import_project(archive_path: str, target_workspace: Optional[str] = None) -> Dict[str, Any]:
    """
    Import project data from a tar.gz archive.
    Handles naming conflicts by appending a timestamp suffix.
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
        
        # Resolve Project Dir (L2)
        target_project_dir = workspaces_root / ".registry" / "projects" / project_slug
        if target_project_dir.exists():
            suffix = datetime.now().strftime("%Y%m%d-%H%M%S")
            project_slug = f"{project_slug}--imported-{suffix}"
            target_project_dir = workspaces_root / ".registry" / "projects" / project_slug
            
        # Resolve Worktree Shared (L3)
        target_workspace_dir = workspaces_root / workspace_name / worktree_slug
        if target_workspace_dir.exists():
            suffix = datetime.now().strftime("%Y%m%d-%H%M%S")
            worktree_slug = f"{worktree_slug}--imported-{suffix}"
            target_workspace_dir = workspaces_root / workspace_name / worktree_slug
            
        # Move Project Level
        target_project_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp_path / "project"), str(target_project_dir))
        
        # Move Worktree Shared Level
        imported_shared_path = tmp_path / "worktree_shared"
        target_shared_path = target_workspace_dir / ".wt"
        if imported_shared_path.exists():
            target_shared_path.mkdir(parents=True, exist_ok=True)
            # Merge contents of imported_shared_path into target_shared_path
            for item in imported_shared_path.iterdir():
                dest = target_shared_path / item.name
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                shutil.move(str(item), str(dest))
                
        return {
            "project_slug": project_slug,
            "worktree_slug": worktree_slug,
            "workspace_name": workspace_name,
            "project_dir": str(target_project_dir),
            "worktree_dir": str(target_workspace_dir)
        }
