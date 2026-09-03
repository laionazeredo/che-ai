import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from che_core.paths import compute_paths, ensure_session_dirs
from che_core.registry import registry_append_jsonl


def main():
    parser = argparse.ArgumentParser(description="Che X-Ray Preflight")
    parser.add_argument("worktree_root", help="Absolute path to the worktree")
    parser.add_argument("session_id", nargs="?", help="Session ID")
    parser.add_argument("--finalize", action="store_true", help="Run the final steps to write the templates")
    parser.add_argument("--files-scanned", type=int, default=0, help="Number of files scanned (for finalize)")

    args = parser.parse_args()
    wt_root = Path(args.worktree_root).resolve()

    if not wt_root.is_dir():
        print(f"[che-xray] ❌ WORKTREE_ROOT {wt_root} is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    session_id = args.session_id or os.environ.get("CHE_CURRENT_SESSION_ID") or os.environ.get("SESSION_ID")
    if not session_id:
        session_id = f"xray-standalone-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    paths = compute_paths(str(wt_root), session_id)
    ensure_session_dirs(str(wt_root), session_id)

    project_dir = Path(paths["CHE_PROJECT_DIR"])
    project_dir.mkdir(parents=True, exist_ok=True)

    xray_project_profile_path = project_dir / "project_profile.md"
    xray_architecture_path = project_dir / "architecture.md"

    graphify_ok = (
        1 if subprocess.run(["command", "-v", "graphify"], shell=True, capture_output=True).returncode == 0 else 0
    )

    if not args.finalize:
        print(f"XRAY_PROJECT_PROFILE_PATH={xray_project_profile_path}")
        print(f"XRAY_ARCHITECTURE_PATH={xray_architecture_path}")
        print(f"GRAPHIFY_OK={graphify_ok}")
        print(f"CHE_PROJECT_SLUG={paths['CHE_PROJECT_SLUG']}")
        print(f"CHE_PROJECT_DIR={project_dir}")
        print(
            "\nPreflight complete. Write the required files to the paths above, then run this script with --finalize."
        )
    else:
        # Step 7c: Audit trail append
        payload = {
            "project_slug": paths["CHE_PROJECT_SLUG"],
            "graphify_used": bool(graphify_ok),
            "files_scanned": args.files_scanned,
            "stack_version": "2026-09-01",
        }
        registry_append_jsonl(session_id, "XRAY_SCAN", str(wt_root), json.dumps(payload))
        print(f"[che-xray] ✅ DONE — Finalized audit trail for {paths['CHE_PROJECT_SLUG']}")


if __name__ == "__main__":
    main()
