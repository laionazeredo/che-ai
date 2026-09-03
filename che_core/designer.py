import os
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

from che_core.paths import compute_paths, ensure_session_dirs

def run_bootstrap(worktree_root: str, session_id: str, mode: str, slug: str):
    wt_root = Path(worktree_root).resolve()
    
    if not wt_root.is_dir():
        print(f"[che-social-ui-designer] ❌ WORKTREE_ROOT {wt_root} is not a valid directory.", file=sys.stderr)
        sys.exit(1)
        
    paths = compute_paths(str(wt_root), session_id)
    ensure_session_dirs(str(wt_root), session_id)
    
    design_root = Path(os.environ.get("CHE_DESIGN_ROOT") or (Path(paths["CHE_WORKSPACE_SHARED"]) / "design"))
    
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    design_dir = design_root / f"{mode}-{slug}-{date_str}"
    
    design_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"CHE_DESIGN_ROOT={design_root}")
    print(f"CHE_DESIGN_DIR={design_dir}")
    print("\nBootstrap complete. Export these variables to use in the subsequent design gates.")

def main():
    parser = argparse.ArgumentParser(description="Che Social UI Designer Helper")
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    
    p_boot = subparsers.add_parser("bootstrap")
    p_boot.add_argument("worktree_root")
    p_boot.add_argument("session_id")
    p_boot.add_argument("mode", help="Design mode (e.g., A, B, C, D)")
    p_boot.add_argument("slug", help="Design slug (e.g., post-natal)")
    
    args = parser.parse_args()
    
    if args.cmd == "bootstrap":
        run_bootstrap(args.worktree_root, args.session_id, args.mode, args.slug)

if __name__ == "__main__":
    main()
