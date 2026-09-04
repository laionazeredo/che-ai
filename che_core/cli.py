import argparse
import json
import sys

from che_core.decisions import append_decision_jsonl
from che_core.paths import compute_paths, ensure_session_dirs
from che_core.registry import registry_append_jsonl, registry_lookup_last
from che_core.portability import export_project, import_project


def main():
    parser = argparse.ArgumentParser(description="Che Core CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # paths
    parser_paths = subparsers.add_parser("compute_paths")
    parser_paths.add_argument("worktree_root")
    parser_paths.add_argument("session_id")
    parser_paths.add_argument("--cwd", default=None)

    # ensure_dirs
    parser_ensure = subparsers.add_parser("ensure_dirs")
    parser_ensure.add_argument("worktree_root")
    parser_ensure.add_argument("session_id")
    parser_ensure.add_argument("--cwd", default=None)

    # append_registry
    parser_reg_app = subparsers.add_parser("registry_append")
    parser_reg_app.add_argument("session_id")
    parser_reg_app.add_argument("status")
    parser_reg_app.add_argument("worktree_root")
    parser_reg_app.add_argument("payload", nargs="?", default="{}")

    # lookup_registry
    parser_reg_look = subparsers.add_parser("registry_lookup")
    parser_reg_look.add_argument("session_id")

    # append_decision
    parser_dec_app = subparsers.add_parser("decision_append")
    parser_dec_app.add_argument("worktree_root")
    parser_dec_app.add_argument("event_type")
    parser_dec_app.add_argument("payload", nargs="?", default="{}")
    parser_dec_app.add_argument("--session-id", default=None)
    parser_dec_app.add_argument("--spec-id", default=None)

    # export
    parser_export = subparsers.add_parser("export")
    parser_export.add_argument("worktree_root")
    parser_export.add_argument("output_file")

    # import
    parser_import = subparsers.add_parser("import")
    parser_import.add_argument("archive_path")
    parser_import.add_argument("--workspace", default=None)

    args = parser.parse_args()

    if args.command == "compute_paths":
        paths = compute_paths(args.worktree_root, args.session_id, args.cwd)
        # Export as bash format
        for k, v in paths.items():
            print(f'export {k}="{v}"')

    elif args.command == "ensure_dirs":
        ensure_session_dirs(args.worktree_root, args.session_id, args.cwd)

    elif args.command == "registry_append":
        registry_append_jsonl(args.session_id, args.status, args.worktree_root, args.payload)

    elif args.command == "registry_lookup":
        entry = registry_lookup_last(args.session_id)
        if entry:
            print(json.dumps(entry, ensure_ascii=False, indent=2))
        else:
            sys.exit(1)

    elif args.command == "decision_append":
        append_decision_jsonl(
            args.worktree_root, args.event_type, args.payload, session_id=args.session_id, spec_id=args.spec_id
        )

    elif args.command == "export":
        out = export_project(args.worktree_root, args.output_file)
        print(f"Project exported to: {out}")

    elif args.command == "import":
        res = import_project(args.archive_path, target_workspace=args.workspace)
        print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
