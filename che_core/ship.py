import os
import sys
import argparse
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path
import fnmatch

from che_core.paths import compute_paths, ensure_session_dirs, get_workspaces_root, get_che_home
from che_core.registry import registry_append_jsonl

BLACKLIST_PATTERNS = [
    ".trae/**", "decisions.log.jsonl", "decisions.log.md", "decisions.log",
    "decision.log.jsonl", "decision.log.md", "decision.log",
    "task_graph.md", "manual_test_plan.md", "final_summary.md",
    "execution_batches.md", "batch_execution_report.md",
    "merge_audit.md", "merge_audit.jsonl",
    "scope-report.md", "scope-report.json", "scope_check_report.md", "scope_check_report.json",
    "scope-check_*.md", "scope-check_*.json",
    "spec_*.md", "SPEC-*.md", "gh_stack_plan.md", "session.md", "envelope.md", "task_envelope.md",
    "graphify-out/**",
    "**/qa_evidence/**", "**/qa-evidence/**", "**/manual-test-screenshots/**", "**/screenshots/**",
    "che-review-report.md", "che-compliance-report.md", "flockr-review-report.md",
    "reports/**", "HCR-*.md", "HCR-*.json", "REVIEW-*.md", "REVIEW-*.json",
    "review-*.md", "review-*.json", "summary.md", "summary.json",
    "seo_report.md", "seo_report.json",
    "diff-context_*.md", "diff-context_*.json",
    "pr_comments/**", "pr-comments-*.md", "pr-comments-*.json",
    "*.adr.md", "ADR-*.md"
]

def run_preflight(worktree_root: str, session_id: str):
    wt_root = Path(worktree_root).resolve()
    
    if not wt_root.is_dir():
        print(f"[che-ship] ❌ WORKTREE_ROOT {wt_root} is not a valid directory.", file=sys.stderr)
        sys.exit(1)
        
    paths = compute_paths(str(wt_root), session_id)
    ensure_session_dirs(str(wt_root), session_id)
    
    related_id = f"ship-{paths['CHE_WORKTREE_SLUG']}"
    
    # Helper function to generate report paths
    def get_report_path(slug: str, ext: str) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        report_dir = Path(paths["CHE_WORKSPACE_SHARED"]) / "reports" / related_id
        report_dir.mkdir(parents=True, exist_ok=True)
        return str(report_dir / f"{ts}-{slug}.{ext}")

    ship_scope_check_report = get_report_path("ship-scope-check", "md")
    ship_code_review_report = get_report_path("ship-code-review", "md")
    ship_compliance_heavy_report = get_report_path("ship-compliance-heavy", "md")
    ship_qa_gate_log = get_report_path("ship-qa-gate", "log")
    
    backup_dir = Path(paths["CHE_WORKSPACE_SHARED"]) / "legacy_binding_cleanup" / "artifact-cleanup-backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"SHIP_SCOPE_CHECK_REPORT={ship_scope_check_report}")
    print(f"SHIP_CODE_REVIEW_REPORT={ship_code_review_report}")
    print(f"SHIP_COMPLIANCE_HEAVY_REPORT={ship_compliance_heavy_report}")
    print(f"SHIP_QA_GATE_LOG={ship_qa_gate_log}")
    print(f"ARTIFACT_CLEANUP_BACKUP_DIR={backup_dir}")
    print("\nPreflight complete. Export these variables to use in the subsequent gates.")

def is_blacklisted(filepath: str) -> bool:
    for pattern in BLACKLIST_PATTERNS:
        if fnmatch.fnmatch(filepath, pattern) or fnmatch.fnmatch(filepath.split('/')[-1], pattern):
            return True
        if pattern.endswith("/**") and filepath.startswith(pattern[:-3]):
            return True
    return False

def run_blacklist_check(worktree_root: str, session_id: str):
    wt_root = Path(worktree_root).resolve()
    
    paths = compute_paths(str(wt_root), session_id)
    backup_dir = Path(paths["CHE_WORKSPACE_SHARED"]) / "legacy_binding_cleanup" / "artifact-cleanup-backup"
    
    # Find all files
    all_files = []
    for root, dirs, files in os.walk(wt_root):
        if '.git' in dirs:
            dirs.remove('.git')
        for f in files:
            rel_path = os.path.relpath(os.path.join(root, f), wt_root)
            all_files.append(rel_path)
            
    blacklisted = [f for f in all_files if is_blacklisted(f)]
    
    if not blacklisted:
        print("✅ No blacklisted planning artifacts found in the worktree.")
        return
        
    print(f"⚠️ Found {len(blacklisted)} blacklisted files in the worktree.")
    
    untracked_moved = []
    tracked_found = []
    
    for bf in blacklisted:
        full_path = wt_root / bf
        # Stage 1: unstage
        subprocess.run(["git", "-C", str(wt_root), "reset", "HEAD", "--", bf], capture_output=True)
        
        # Check if tracked
        res = subprocess.run(["git", "-C", str(wt_root), "ls-files", "--error-unmatch", bf], capture_output=True)
        if res.returncode != 0:
            # Untracked
            backup_path = backup_dir / bf
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(full_path, backup_path)
            full_path.unlink()
            untracked_moved.append(bf)
        else:
            # Tracked
            tracked_found.append(bf)
            
    if tracked_found:
        print("\n🔴 PLANNING ARTIFACTS BLACKLIST — TRACKED FILES FOUND (committed before):")
        for f in tracked_found:
            print(f"  · {f}")
        print("\nThese are che internal files and MUST NOT live in user-code git history.")
        print("Options:")
        print(f"  A = Untrack them (git rm --cached each), KEEP local copies MOVED to {backup_dir}")
        print("  B = I will handle manually. Cancel ship.")
        sys.exit(2)
        
    if untracked_moved:
        print("\n🧹 Moved untracked files to backup:")
        for f in untracked_moved:
            print(f"  · {f}")

def main():
    parser = argparse.ArgumentParser(description="Che Ship Helper")
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    
    p_preflight = subparsers.add_parser("preflight")
    p_preflight.add_argument("worktree_root")
    p_preflight.add_argument("session_id")
    
    p_blacklist = subparsers.add_parser("blacklist_check")
    p_blacklist.add_argument("worktree_root")
    p_blacklist.add_argument("session_id")
    
    args = parser.parse_args()
    
    if args.cmd == "preflight":
        run_preflight(args.worktree_root, args.session_id)
    elif args.cmd == "blacklist_check":
        run_blacklist_check(args.worktree_root, args.session_id)

if __name__ == "__main__":
    main()
