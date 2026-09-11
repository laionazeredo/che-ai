import argparse
import json
import sys
from pathlib import Path

from che_core.decisions import append_decision_jsonl
from che_core.paths import (
    assert_outside_worktree,
    compute_paths,
    ensure_session_dirs,
    output_path,
    write_file_atomic,
)
from che_core.portability import export_project, import_project
from che_core.registry import registry_append_jsonl, registry_lookup_last
from che_core.task_engine import (
    graph_summary,
    list_tasks,
    resume_task,
    set_status_task,
    show_task,
)


def _print_json(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def _build_filters_from_args(args) -> dict:
    filters = {}
    if args.status:
        filters["status"] = [s.strip().upper() for s in args.status.split(",")]
    if args.domain:
        filters["domain"] = [d.strip().lower() for d in args.domain.split(",")]
    if args.ready_only:
        filters["ready_only"] = True
    return filters


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

    # output_path (storage boundary resolver — replaces legacy che_output_path)
    parser_out = subparsers.add_parser(
        "output_path",
        help="Resolve the canonical path for a Che artifact outside the worktree.",
    )
    parser_out.add_argument("type", help="Artifact type (e.g. qa, spec, task, review, adr).")
    parser_out.add_argument("slug", help="Human-readable slug for the filename.")
    parser_out.add_argument("related_id", help="Related id (ticket/feature id); pass '' to omit.")
    parser_out.add_argument("scope", choices=["session", "workspace"], help="Storage scope.")
    parser_out.add_argument("ext", help="File extension without the dot (e.g. md, json).")
    parser_out.add_argument("suffix", nargs="?", default="", help="Optional filename suffix.")

    # write_file_atomic (stdin -> target, tmp+rename — replaces che_write_file_atomic)
    parser_write = subparsers.add_parser(
        "write_file_atomic",
        help="Atomically write stdin bytes to a target path outside the worktree.",
    )
    parser_write.add_argument("target", help="Destination path (must be outside the worktree).")

    # assert_outside_worktree (hard-stop guard — replaces che_assert_outside_worktree)
    parser_assert = subparsers.add_parser(
        "assert_outside_worktree",
        help="Hard-stop (exit 99) if a candidate path falls inside the worktree.",
    )
    parser_assert.add_argument("candidate_path")
    parser_assert.add_argument("worktree_root")
    parser_assert.add_argument("--label", default="path")

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

    # config
    parser_config = subparsers.add_parser("config", help="Set session configuration flags.")
    parser_config.add_argument("session_id")
    parser_config.add_argument("worktree_root")
    parser_config.add_argument("--lang-chat", choices=["en", "pt-BR"], help="Language for agent chat dialogue.")
    parser_config.add_argument("--lang-docs", choices=["en", "pt-BR"], help="Language for documentation and commits.")
    parser_config.add_argument("--lang-report", choices=["en", "pt-BR"], help="Language for generated reports.")
    parser_config.add_argument(
        "--pt-check", choices=["ENABLED", "DISABLED"], help="Enable/disable Portuguese text detection hook."
    )
    parser_config.add_argument("--flags", help="Raw JSON string of extra flags to merge.")

    # export
    parser_export = subparsers.add_parser("export")
    parser_export.add_argument("worktree_root")
    parser_export.add_argument("output_file")
    parser_export.add_argument(
        "--include-db",
        action="store_true",
        help="Optional: include SQLite databases (state + rag) in export if they exist and total size <= limit.",
    )
    parser_export.add_argument(
        "--db-size-limit-mb",
        type=int,
        default=250,
        help="Maximum total size of databases to include in export (MB). Default = 250MB.",
    )

    # import
    parser_import = subparsers.add_parser("import")
    parser_import.add_argument("archive_path")
    parser_import.add_argument("--workspace", default=None)
    parser_import.add_argument(
        "--include-db",
        action="store_true",
        help="Also restore SQLite databases if present in the archive.",
    )

    # TASK ENGINE SUBCOMMANDS =================================================
    parser_tasks = subparsers.add_parser("task", help="Che multi-domain task graph.")
    task_subs = parser_tasks.add_subparsers(dest="task_cmd", required=True)

    pt_list = task_subs.add_parser("list")
    pt_list.add_argument("worktree_root")
    pt_list.add_argument("--status", default=None, help="e.g. TODO,IN_PROGRESS,DONE")
    pt_list.add_argument("--domain", default=None, help="e.g. ux,engineering")
    pt_list.add_argument(
        "--ready-only", action="store_true", help="Only tasks with dependencies DONE + handoff existing."
    )

    pt_show = task_subs.add_parser("show")
    pt_show.add_argument("worktree_root")
    pt_show.add_argument("task_id")

    pt_resume = task_subs.add_parser("resume")
    pt_resume.add_argument("worktree_root")
    pt_resume.add_argument("task_id")
    pt_resume.add_argument("--session-id", required=True)

    pt_set = task_subs.add_parser("set-status")
    pt_set.add_argument("worktree_root")
    pt_set.add_argument("task_id")
    pt_set.add_argument("status")
    pt_set.add_argument("--session-id", default=None)
    pt_set.add_argument("--reason", default=None)

    pt_summary = task_subs.add_parser("graph-summary")
    pt_summary.add_argument("worktree_root")

    # STATE STORE SUBCOMMANDS (SQLite FTS5) ==================================
    parser_state = subparsers.add_parser("state", help="Che SQLite state store (FTS5 index).")
    state_subs = parser_state.add_subparsers(dest="state_cmd", required=True)

    ps_rebuild = state_subs.add_parser("rebuild-index")
    ps_rebuild.add_argument("worktree_root")

    ps_query = state_subs.add_parser("query")
    ps_query.add_argument(
        "--sql",
        required=True,
        help="Parameterised SQL query (use ? for placeholders). E.g. SELECT id,title FROM tasks WHERE domain=?",
    )
    ps_query.add_argument("--bind", nargs="*", default=[], help="Values for ? placeholders (textual order)")
    ps_query.add_argument(
        "--worktree-root",
        default=None,
        help="Target worktree (some queries do not require it).",
    )
    ps_query.add_argument("--json", action="store_true", dest="json_out", help="Return JSON instead of a table.")

    ps_sanitize = state_subs.add_parser("sanitize")
    ps_sanitize.add_argument("worktree_root")
    ps_sanitize.add_argument(
        "--max-age-days",
        type=int,
        default=180,
        help="Maximum age of records to keep (old decisions / bindings / sessions). Default = 180 days.",
    )
    ps_sanitize.add_argument(
        "--max-decisions",
        type=int,
        default=5000,
        help="Maximum number of decisions.log entries to keep in state store. Older ones are purged.",
    )
    ps_sanitize.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show how many records would be deleted, without applying changes.",
    )

    ps_search = state_subs.add_parser("search")
    ps_search.add_argument("worktree_root")
    ps_search.add_argument("query_text")
    ps_search.add_argument("--top-k", type=int, default=15)
    ps_search.add_argument(
        "--scope",
        default="all",
        help="all | tasks | specs | decisions | envelopes. Default = all.",
    )

    # RAG / VECTOR STORE SUBCOMMANDS (SQLite-vec, optional) ==================
    parser_rag = subparsers.add_parser("rag", help="Che RAG embeddings (sqlite-vec, optional).")
    rag_subs = parser_rag.add_subparsers(dest="rag_cmd", required=True)

    pr_build = rag_subs.add_parser("build-index")
    pr_build.add_argument("worktree_root")
    pr_build.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="Tokens per chunk before embeddings. Default 512.",
    )
    pr_build.add_argument(
        "--provider",
        default="auto",
        help="auto | none | sentence-transformers | openai | anthropic. none = only BM25 without vectors.",
    )

    pr_rag_search = rag_subs.add_parser("search")
    pr_rag_search.add_argument("worktree_root")
    pr_rag_search.add_argument("query_text")
    pr_rag_search.add_argument("--top-k", type=int, default=10)
    pr_rag_search.add_argument(
        "--hybrid",
        action="store_true",
        default=True,
        help="Hybrid search BM25 + vector rerank (default True).",
    )

    # WORKSPACE MGMT SUBCOMMANDS (L1) =============================================
    parser_ws = subparsers.add_parser("workspace", help="Manage Che workspaces (L1 workspaces root).")
    ws_subs = parser_ws.add_subparsers(dest="ws_cmd", required=True)

    # create (primary)
    pw_create = ws_subs.add_parser("create", help="Create a new L1 workspace.")
    pw_create.add_argument("name", help="Workspace name (will be slugified).")
    pw_create.add_argument("--worktree-root", default=None, help="Optional worktree to define primary workspace.")

    ws_subs.add_parser("list", help="List existing workspaces + projects count.")

    pw_remove = ws_subs.add_parser("remove")
    pw_remove.add_argument("name", help="Workspace slug to move to trash (DOES NOT delete, moves to .trash/).")
    pw_remove.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Default: only show, DO NOT move. Set --no-dry-run to apply.",
    )
    pw_remove.add_argument(
        "--no-dry-run", dest="dry_run", action="store_false", help="Effectively move. Requires --confirm as well."
    )
    pw_remove.add_argument(
        "--confirm",
        dest="confirmed",
        action="store_true",
        default=False,
        help="Mandatory safety gate after reviewing --dry-run.",
    )

    pw_restore = ws_subs.add_parser("restore")
    pw_restore.add_argument("trash_slug", help="Trash entry slug (e.g. workspace--foo--20260904-235959).")

    ws_subs.add_parser("trash-list", help="Contents of the .trash/ folder.")

    # PROJECT MGMT SUBCOMMANDS (L2) =============================================
    parser_proj = subparsers.add_parser("project", help="Manage L2 projects (.registry/projects/<slug>).")
    proj_subs = parser_proj.add_subparsers(dest="proj_cmd", required=True)

    # create (primary), add and init (aliases)
    pj_create = proj_subs.add_parser("create", aliases=["add", "init"], help="Create/Add an L2 project to a workspace.")
    pj_create.add_argument("worktree_root", help="Project worktree root to add.")
    pj_create.add_argument("--workspace", required=True, help="Target workspace name (MANDATORY).")
    pj_create.add_argument(
        "--domain",
        default="engineering",
        help="Default Politburo domain: engineering|ux|product|devops|copywriting|social|seo-analytics.",
    )
    pj_create.add_argument(
        "--name", dest="friendly_name", default=None, help="Friendly name (default: <workspace>--<folder>)."
    )
    pj_create.add_argument("--session-id", default="project-create-cli", help="Session ID to create initial L3 dirs.")

    proj_subs.add_parser("list", help="List L2 projects + existing architecture/profile/db.")

    pj_remove = proj_subs.add_parser("remove")
    pj_remove.add_argument("project_slug", help="Project slug to move to trash (DOES NOT delete, moves to .trash/).")
    pj_remove.add_argument("workspace_name", help="Name of the workspace containing the project.")
    pj_remove.add_argument("--dry-run", action="store_true", default=True, help="Default: only show, DO NOT move.")
    pj_remove.add_argument(
        "--no-dry-run", dest="dry_run", action="store_false", help="Effectively move. Requires --confirm as well."
    )
    pj_remove.add_argument(
        "--confirm", dest="confirmed", action="store_true", default=False, help="Mandatory safety gate."
    )

    pj_restore = proj_subs.add_parser("restore")
    pj_restore.add_argument("trash_slug", help="Trash entry slug.")

    # EJECT SUBCOMMANDS (safe Che uninstallation) ============================
    parser_eject = subparsers.add_parser(
        "eject",
        help="Safely eject Che: uninstall adapters, move non-blacklist files to trash, restore.",
    )
    parser_eject.add_argument(
        "--che-home",
        default=None,
        help="Che directory override (default: resolves the Che home cascade automatically).",
    )
    parser_eject.add_argument(
        "--trash-root",
        default=None,
        help="Trash root override (default: ~/.che-workspaces/.trash/che-eject).",
    )
    parser_eject.add_argument(
        "--keep-git-repo",
        action="store_true",
        default=True,
        help="(git-clone only) Keep .git/ intact after eject (default True). Use --no-keep-git-repo to remove it.",
    )
    parser_eject.add_argument(
        "--no-keep-git-repo",
        dest="keep_git_repo",
        action="store_false",
        help="Also remove the .git/ directory on eject (only for copy-install or if explicitly overridden).",
    )
    parser_eject.add_argument(
        "--scan-client-repos",
        nargs="*",
        default=None,
        help="Optional list of client projects to clean the CHE PLANNING ARTIFACTS BLACKLIST snippet from .gitignore.",
    )
    parser_eject.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Default: only display plan, DO NOT write anything. Use --apply to apply.",
    )
    parser_eject.add_argument(
        "--apply",
        dest="dry_run",
        action="store_false",
        help="Effectively apply the eject. Requires --confirmed and --i-know-what-im-doing.",
    )
    parser_eject.add_argument(
        "--confirmed",
        action="store_true",
        default=False,
        help="Safety gate 1/2: explicit confirmation after reviewing --dry-run.",
    )
    parser_eject.add_argument(
        "--i-know-what-im-doing",
        action="store_true",
        default=False,
        help="Safety gate 2/2: double confirmation of user awareness of risk.",
    )
    eject_subs = parser_eject.add_subparsers(dest="eject_cmd", required=True)

    eject_subs.add_parser(
        "plan",
        help="(default) Generate eject plan, apply or just display based on --dry-run/--apply.",
    )

    eject_subs.add_parser(
        "trash-list",
        help="List all ejects already sent to trash (with JSON manifests).",
    )

    pe_restore = eject_subs.add_parser(
        "restore",
        help="Restore a previous eject, moving from trash to che_home and running setup-adapters.",
    )
    pe_restore.add_argument("trash_slug", help="Trash entry slug (e.g. che-eject--abc123--20260904-235959).")
    pe_restore.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Default: only show restore plan. Use --apply to apply.",
    )
    pe_restore.add_argument(
        "--apply",
        dest="dry_run",
        action="store_false",
        help="Effectively restore. Requires --confirmed.",
    )
    pe_restore.add_argument(
        "--confirmed",
        action="store_true",
        default=False,
        help="Mandatory safety gate to apply the restore.",
    )

    args = parser.parse_args()

    if args.command == "compute_paths":
        paths = compute_paths(args.worktree_root, args.session_id, args.cwd)
        for k, v in paths.items():
            print(f'export {k}="{v}"')
        return

    if args.command == "ensure_dirs":
        ensure_session_dirs(args.worktree_root, args.session_id, args.cwd)
        return

    if args.command == "output_path":
        print(output_path(args.type, args.slug, args.related_id, args.scope, args.ext, args.suffix))
        return

    if args.command == "write_file_atomic":
        write_file_atomic(args.target, sys.stdin.buffer.read())
        return

    if args.command == "assert_outside_worktree":
        assert_outside_worktree(args.candidate_path, args.worktree_root, args.label)
        return

    if args.command == "registry_append":
        registry_append_jsonl(args.session_id, args.status, args.worktree_root, args.payload)
        return

    if args.command == "registry_lookup":
        entry = registry_lookup_last(args.session_id)
        if entry:
            _print_json(entry)
        else:
            sys.exit(1)
        return

    if args.command == "decision_append":
        append_decision_jsonl(
            args.worktree_root,
            args.event_type,
            args.payload,
            session_id=args.session_id,
            spec_id=args.spec_id,
        )
        return

    if args.command == "config":
        payload = {"flags": {}}
        if args.lang_chat:
            payload["flags"]["LANG_CHAT"] = args.lang_chat
        if args.lang_docs:
            payload["flags"]["LANG_DOCS"] = args.lang_docs
        if args.lang_report:
            payload["flags"]["LANG_REPORT"] = args.lang_report
        if args.pt_check:
            payload["flags"]["LANG_PT_CHECK"] = args.pt_check
        if args.flags:
            try:
                extra = json.loads(args.flags)
                if isinstance(extra, dict):
                    payload["flags"].update(extra)
            except Exception as e:
                print(f"Error parsing --flags: {e}", file=sys.stderr)
                sys.exit(2)

        registry_append_jsonl(args.session_id, "FLAGS", args.worktree_root, json.dumps(payload))
        print(f"Configuration updated for session {args.session_id}")
        return

    if args.command == "export":
        out = export_project(
            args.worktree_root,
            args.output_file,
            include_db=args.include_db,
            db_size_limit_mb=args.db_size_limit_mb,
        )
        print(f"Project exported to: {out}")
        return

    if args.command == "import":
        res = import_project(
            args.archive_path,
            target_workspace=args.workspace,
            include_db=args.include_db,
        )
        _print_json(res)
        return

    if args.command == "task":
        if args.task_cmd == "list":
            flt = _build_filters_from_args(args)
            _print_json(list_tasks(args.worktree_root, flt))
        elif args.task_cmd == "show":
            _print_json(show_task(args.worktree_root, args.task_id))
        elif args.task_cmd == "resume":
            _print_json(resume_task(args.worktree_root, args.task_id, args.session_id))
        elif args.task_cmd == "set-status":
            _print_json(
                set_status_task(
                    args.worktree_root,
                    args.task_id,
                    args.status,
                    session_id=args.session_id,
                    reason=args.reason,
                )
            )
        elif args.task_cmd == "graph-summary":
            _print_json(graph_summary(args.worktree_root))
        return

    if args.command == "state":
        from che_core.state_store import (
            query_state_db,
            rebuild_state_index,
            sanitize_state,
            search_state,
        )

        if args.state_cmd == "rebuild-index":
            res = rebuild_state_index(args.worktree_root)
            _print_json(res)
        elif args.state_cmd == "query":
            res = query_state_db(
                args.sql,
                args.bind,
                worktree_root=args.worktree_root,
                as_json=args.json_out,
            )
            if isinstance(res, (list, dict)):
                _print_json(res)
            else:
                print(res)
        elif args.state_cmd == "sanitize":
            res = sanitize_state(
                args.worktree_root,
                max_age_days=args.max_age_days,
                max_decisions=args.max_decisions,
                dry_run=args.dry_run,
            )
            _print_json(res)
        elif args.state_cmd == "search":
            res = search_state(
                args.worktree_root,
                args.query_text,
                top_k=args.top_k,
                scope=args.scope,
            )
            _print_json(res)
        return

    if args.command == "rag":
        from che_core.rag import build_rag_index, search_rag

        if args.rag_cmd == "build-index":
            res = build_rag_index(
                args.worktree_root,
                chunk_size=args.chunk_size,
                provider=args.provider,
            )
            _print_json(res)
        elif args.rag_cmd == "search":
            res = search_rag(
                args.worktree_root,
                args.query_text,
                top_k=args.top_k,
                hybrid=args.hybrid,
            )
            _print_json(res)
        return

    if args.command == "workspace":
        from che_core.workspaces import add_workspace, list_trash, list_workspaces, remove_workspace, restore_workspace

        if args.ws_cmd == "create":
            res = add_workspace(args.name, worktree_root=args.worktree_root)
        elif args.ws_cmd == "list":
            res = list_workspaces()
        elif args.ws_cmd == "remove":
            res = remove_workspace(args.name, dry_run=args.dry_run, confirmed=args.confirmed)
        elif args.ws_cmd == "restore":
            res = restore_workspace(args.trash_slug)
        elif args.ws_cmd == "trash-list":
            res = list_trash()
        else:
            parser.error(f"Unknown workspace subcommand: {args.ws_cmd}")
            return
        _print_json(res)
        return

    if args.command == "project":
        from che_core.workspaces import init_project, list_projects, remove_project, restore_project

        if args.proj_cmd in ["create", "add", "init"]:
            res = init_project(
                args.worktree_root,
                workspace_name=args.workspace,
                domain=args.domain,
                friendly_name=args.friendly_name,
                session_id=args.session_id,
            )
        elif args.proj_cmd == "list":
            res = list_projects()
        elif args.proj_cmd == "remove":
            res = remove_project(args.project_slug, args.workspace_name, dry_run=args.dry_run, confirmed=args.confirmed)
        elif args.proj_cmd == "restore":
            res = restore_project(args.trash_slug)
        else:
            parser.error(f"Unknown project subcommand: {args.proj_cmd}")
            return
        _print_json(res)
        return

    if args.command == "eject":
        from che_core.eject import eject_apply, eject_plan, eject_restore, eject_trash_list

        if args.eject_cmd == "plan":
            scan_repos = [Path(p).expanduser().resolve() for p in (args.scan_client_repos or [])] or None
            plan = eject_plan(
                che_home=Path(args.che_home).expanduser().resolve() if args.che_home else None,
                trash_root=Path(args.trash_root).expanduser().resolve() if args.trash_root else None,
                keep_git_repo=args.keep_git_repo,
                scan_client_repos=scan_repos,
            )
            res = eject_apply(
                plan,
                dry_run=args.dry_run,
                confirmed=args.confirmed,
                i_know_what_im_doing=args.i_know_what_im_doing,
            )
        elif args.eject_cmd == "trash-list":
            res = eject_trash_list(
                trash_root=Path(args.trash_root).expanduser().resolve() if args.trash_root else None,
            )
        elif args.eject_cmd == "restore":
            res = eject_restore(
                args.trash_slug,
                trash_root=Path(args.trash_root).expanduser().resolve() if args.trash_root else None,
                dry_run=args.dry_run,
                confirmed=args.confirmed,
            )
        else:
            parser.error(f"Unknown eject subcommand: {args.eject_cmd}")
            return
        _print_json(res)
        return


if __name__ == "__main__":
    main()
