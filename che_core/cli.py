import argparse
import json
import sys

from che_core.decisions import append_decision_jsonl
from che_core.paths import compute_paths, ensure_session_dirs
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
    parser_export.add_argument(
        "--include-db",
        action="store_true",
        help="Opcional: inclui bancos de dados SQLite (state + rag) no export, se existirem e se tamanho <= limite.",
    )
    parser_export.add_argument(
        "--db-size-limit-mb",
        type=int,
        default=250,
        help="Limite máximo de tamanho SOMADO dos bancos para incluir no export (MB). Default = 250MB.",
    )

    # import
    parser_import = subparsers.add_parser("import")
    parser_import.add_argument("archive_path")
    parser_import.add_argument("--workspace", default=None)
    parser_import.add_argument(
        "--include-db",
        action="store_true",
        help="Restaura também bancos SQLite se presentes no archive.",
    )

    # TASK ENGINE SUBCOMMANDS =================================================
    parser_tasks = subparsers.add_parser("task", help="Che multi-domain task graph.")
    task_subs = parser_tasks.add_subparsers(dest="task_cmd", required=True)

    pt_list = task_subs.add_parser("list")
    pt_list.add_argument("worktree_root")
    pt_list.add_argument("--status", default=None, help="ex: TODO,IN_PROGRESS,DONE")
    pt_list.add_argument("--domain", default=None, help="ex: ux,engineering")
    pt_list.add_argument("--ready-only", action="store_true", help="apenas tasks com deps DONE + handoff existente.")

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
        help="Consulta SQL parametrizada (use ? para placeholders). Ex: SELECT id,title FROM tasks WHERE domain=?",
    )
    ps_query.add_argument("--bind", nargs="*", default=[], help="Valores para placeholders ? (ordem textual)")
    ps_query.add_argument(
        "--worktree-root",
        default=None,
        help="Worktree alvo (algumas consultas não precisam).",
    )
    ps_query.add_argument("--json", action="store_true", dest="json_out", help="Retorna JSON ao invés de tabela.")

    ps_sanitize = state_subs.add_parser("sanitize")
    ps_sanitize.add_argument("worktree_root")
    ps_sanitize.add_argument(
        "--max-age-days",
        type=int,
        default=180,
        help="Idade máxima de registros para manter (decisions / bindings / sessions old). Default = 180 dias.",
    )
    ps_sanitize.add_argument(
        "--max-decisions",
        type=int,
        default=5000,
        help="Número máximo de decisions.log entries a manter no state store. Mais antigos são purgados.",
    )
    ps_sanitize.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas mostra quantos registros seriam deletados, sem efetivar.",
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

    # RAG / VECTOR STORE SUBCOMMANDS (SQLite-vec, opcional) ==================
    parser_rag = subparsers.add_parser("rag", help="Che RAG embeddings (sqlite-vec, opcional).")
    rag_subs = parser_rag.add_subparsers(dest="rag_cmd", required=True)

    pr_build = rag_subs.add_parser("build-index")
    pr_build.add_argument("worktree_root")
    pr_build.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="Tokens por chunk antes de embeddings. Default 512.",
    )
    pr_build.add_argument(
        "--provider",
        default="auto",
        help="auto | none | sentence-transformers | openai | anthropic. none = só BM25 sem vetores.",
    )

    pr_rag_search = rag_subs.add_parser("search")
    pr_rag_search.add_argument("worktree_root")
    pr_rag_search.add_argument("query_text")
    pr_rag_search.add_argument("--top-k", type=int, default=10)
    pr_rag_search.add_argument(
        "--hybrid",
        action="store_true",
        default=True,
        help="Busca híbrida BM25 + rerank vetorial (default True).",
    )

    # WORKSPACE MGMT SUBCOMMANDS (L1) =============================================
    parser_ws = subparsers.add_parser("workspace", help="Gerencia workspaces Che (L1 workspaces root).")
    ws_subs = parser_ws.add_subparsers(dest="ws_cmd", required=True)

    pw_add = ws_subs.add_parser("add")
    pw_add.add_argument("name", help="Nome do workspace (será slugged).")
    pw_add.add_argument("--worktree-root", default=None, help="Worktree opcional para definir workspace principal.")

    ws_subs.add_parser("list", help="Lista workspaces existentes + projects count.")

    pw_remove = ws_subs.add_parser("remove")
    pw_remove.add_argument("name", help="Workspace slug a mover para lixeira (NÃO apaga, move para .trash/).")
    pw_remove.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Default: só mostra, NÃO move. Set --no-dry-run para efetivar.",
    )
    pw_remove.add_argument(
        "--no-dry-run", dest="dry_run", action="store_false", help="Efetivamente move. Requer também --confirm."
    )
    pw_remove.add_argument(
        "--confirm",
        dest="confirmed",
        action="store_true",
        default=False,
        help="Safety gate obrigatório após revisão do --dry-run.",
    )

    pw_restore = ws_subs.add_parser("restore")
    pw_restore.add_argument("trash_slug", help="Slug da entrada na lixeira (ex: workspace--foo--20260904-235959).")

    ws_subs.add_parser("trash-list", help="Conteúdo da lixeira .trash/.")

    # PROJECT MGMT SUBCOMMANDS (L2) =============================================
    parser_proj = subparsers.add_parser("project", help="Gerencia projects L2 (.registry/projects/<slug>).")
    proj_subs = parser_proj.add_subparsers(dest="proj_cmd", required=True)

    pj_init = proj_subs.add_parser("init")
    pj_init.add_argument("worktree_root", help="Worktree root do projeto a inicializar.")
    pj_init.add_argument("--workspace", default=None, help="Override workspace name (default = resolve via paths.py).")
    pj_init.add_argument(
        "--domain",
        default="engineering",
        help="Domínio Politburo default: engineering|ux|product|devops|copywriting|social|seo-analytics.",
    )
    pj_init.add_argument(
        "--name", dest="friendly_name", default=None, help="Nome amigável (default: slug from git origin)."
    )
    pj_init.add_argument("--session-id", default="project-init-cli", help="Session id para criar L3 dirs iniciais.")

    proj_subs.add_parser("list", help="Lista projects L2 + arquitetura/profile/db existentes.")

    pj_remove = proj_subs.add_parser("remove")
    pj_remove.add_argument("project_slug", help="Slug do projeto a mover para lixeira (NÃO apaga, move para .trash/).")
    pj_remove.add_argument("--dry-run", action="store_true", default=True, help="Default: só mostra, NÃO move.")
    pj_remove.add_argument(
        "--no-dry-run", dest="dry_run", action="store_false", help="Efetivamente move. Requer também --confirm."
    )
    pj_remove.add_argument(
        "--confirm", dest="confirmed", action="store_true", default=False, help="Safety gate obrigatório."
    )

    pj_restore = proj_subs.add_parser("restore")
    pj_restore.add_argument("trash_slug", help="Slug da entrada na lixeira.")

    args = parser.parse_args()

    if args.command == "compute_paths":
        paths = compute_paths(args.worktree_root, args.session_id, args.cwd)
        for k, v in paths.items():
            print(f'export {k}="{v}"')
        return

    if args.command == "ensure_dirs":
        ensure_session_dirs(args.worktree_root, args.session_id, args.cwd)
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

        if args.ws_cmd == "add":
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

        if args.proj_cmd == "init":
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
            res = remove_project(args.project_slug, dry_run=args.dry_run, confirmed=args.confirmed)
        elif args.proj_cmd == "restore":
            res = restore_project(args.trash_slug)
        else:
            parser.error(f"Unknown project subcommand: {args.proj_cmd}")
            return
        _print_json(res)
        return


if __name__ == "__main__":
    main()
