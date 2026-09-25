import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from che_core.diagnostics import diagnosed, fail
from che_core.memory_store import append_decision
from che_core.paths import (
    assert_outside_worktree,
    compute_paths,
    ensure_session_dirs,
    output_path,
    write_file_atomic,
)
from che_core.pixel_sources import (
    BACKENDS_WITH_EXTRACTOR,
    BACKENDS_WITHOUT_EXTRACTOR,
    DECLARED_BACKENDS,
)
from che_core.portability import export_project, import_project
from che_core.project_layout import DOMAIN_SLUGS
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


def _load_json(path: str):
    """Read a JSON artefact, surfacing a path-bearing error instead of a bare traceback."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        fail("UNREADABLE_INPUT", path=path, detail=str(exc))
    except json.JSONDecodeError as exc:
        fail("INVALID_JSON", path=path, detail=str(exc))


def _build_filters_from_args(args) -> dict:
    filters = {}
    if args.status:
        filters["status"] = [s.strip().upper() for s in args.status.split(",")]
    if args.domain:
        filters["domain"] = [d.strip().lower() for d in args.domain.split(",")]
    if args.ready_only:
        filters["ready_only"] = True
    return filters


#: Subfolder of the worktree-side design tree holding one screen's pixel-check inputs.
_PIXEL_CHECK_DIRNAME = "pixel-check"


def _pixel_artifact_paths(
    worktree_root: str,
    session_id: str,
    sub_product: str,
    breakpoint: str,
    backend: str,
    related_id: str,
    attempt: int,
) -> dict:
    """Resolve the artifact set gate `ux-pixel-check-gate` runs on (§2.3, §4.1–§4.3).

    Until now the gate's recipe and the CLI reference both used Undefined shell
    variables, so every run invented its own paths and none of them could be found
    again. Two storage classes make that unacceptable in opposite directions:

    * The **map**, the **raw design capture** and the **per-element record** are
      evidence a reviewer reads in the PR diff, and §4.3 freezes the map as
      regression — so they live inside the worktree under
      ``design/<sub_product>/pixel-check/`` with stable per-breakpoint names. A
      timestamped name would make "frozen" a fiction: the next run could not find
      the previous one, and a re-run would look like a new map.
    * The **DOM facts** and the **report** measure one particular attempt. §5 allows
      exactly one free retry, so attempt 1 and attempt 2 must both survive; the
      attempt number is in the filename rather than overwriting, which is what makes
      the retry budget auditable after the fact.

    The sub-product's design tree must already exist. Refusing otherwise keeps a
    mistyped slug from creating a parallel design root that no skill owns.
    """
    wt_root = Path(worktree_root).resolve()
    if not wt_root.is_dir():
        fail("NOT_A_DIRECTORY", path=wt_root)

    design_dir = wt_root / "design" / sub_product
    if not design_dir.is_dir():
        fail("DESIGN_TREE_MISSING", path=design_dir)

    label = breakpoint.strip()
    if not label or "/" in label or label in (".", ".."):
        fail("INVALID_BREAKPOINT_LABEL", breakpoint=breakpoint)

    if backend in BACKENDS_WITHOUT_EXTRACTOR:
        # This flag picks the raw-capture NAMING CONVENTION, not just a label, and there
        # is none to pick for a backend no session has ever been recorded from. Inventing
        # one would put a filename in the recipe that nothing can write.
        fail(
            "NO_CAPTURE_CONVENTION",
            backend=backend,
            backends=", ".join(sorted(BACKENDS_WITH_EXTRACTOR)),
        )

    if attempt < 1:
        fail("INVALID_ATTEMPT", attempt=attempt)

    paths = ensure_session_dirs(str(wt_root), session_id)
    # `output_path` resolves its roots from the environment, because every shell
    # caller reaches it through `eval "$(che compute_paths …)"`. This command is meant
    # to be self-sufficient, so it seeds the roots it needs from what it just resolved.
    os.environ["CHE_SESSION_DIR"] = paths["CHE_SESSION_DIR"]
    os.environ["CHE_WORKSPACE_SHARED"] = paths["CHE_WORKSPACE_SHARED"]

    check_dir = design_dir / _PIXEL_CHECK_DIRNAME
    slug = f"{sub_product}-{label}"
    # OpenPencil's raw artefact is the committed .op source itself; the Figma bridge
    # returns text that has no home of its own, so the capture is dumped beside the map.
    raw_path = design_dir / "source" / "home.op" if backend == "openpencil" else check_dir / f"{label}.design-raw.txt"

    return {
        "CHE_PIXEL_DIR": str(check_dir),
        "CHE_PIXEL_MAP": str(check_dir / f"{label}.map.json"),
        "CHE_PIXEL_DESIGN_FACTS": str(check_dir / f"{label}.design-facts.json"),
        "CHE_PIXEL_DESIGN_RAW": str(raw_path),
        "CHE_PIXEL_DOM_FACTS": output_path("design", f"{slug}-dom-facts", related_id, "session", "json"),
        "CHE_PIXEL_REPORT": output_path("design", f"{slug}-check-attempt{attempt}", related_id, "session", "json"),
        # §4.5 evidence. Session-side because it is a picture of one attempt at one
        # breakpoint, regenerable at will, and attaching it to the PR is a human step —
        # nothing in the repository should carry a stale rendering of a fixed layout.
        "CHE_PIXEL_DESIGN_IMAGE": output_path("design", f"{slug}-design", related_id, "session", "png"),
        "CHE_PIXEL_DOM_SCREENSHOT": output_path("design", f"{slug}-dom", related_id, "session", "png"),
        "CHE_PIXEL_VISUAL_DIFF": output_path("design", f"{slug}-visual-diff", related_id, "session", "png"),
        # The per-element crop, which is a different instrument from the frame delta: cropping
        # to each element's own box is what makes the residue §6.1 lists readable at all, since a
        # whole-frame percentage is dominated by antialiasing and font loading. Named here rather
        # than derived from the diff's filename, so no recipe invents a path of its own.
        "CHE_PIXEL_CROP_REPORT": output_path(
            "design", f"{slug}-crop-report-attempt{attempt}", related_id, "session", "json"
        ),
        "CHE_PIXEL_CROP_SHEET": output_path(
            "design", f"{slug}-crop-sheet-attempt{attempt}", related_id, "session", "png"
        ),
    }


@diagnosed
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    # `che designer …` is forwarded verbatim to the domain sub-CLI before argparse
    # runs, because argparse's REMAINDER does not forward leading optionals
    # (e.g. `che designer --help`) — see bpo-17050.
    if argv and argv[0] == "designer":
        from che_core.designer import main as designer_main

        designer_main(argv[1:])
        return

    parser = argparse.ArgumentParser(description="Che Core CLI")
    # One flag an agent can always pass, whatever the command: `che --json <anything>`.
    # The per-subcommand `--json` flags keep working unchanged, so no existing caller breaks.
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_global",
        help="Machine-readable result for any command, success or failure. Goes before the command.",
    )
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

    # designer is dispatched before argparse (see top of main); registered here
    # only so it stays discoverable in `che --help`.
    subparsers.add_parser(
        "designer",
        help="Che Designer — git-native design tree (init, validate, tokens, stock).",
    )

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
        "--force",
        action="store_true",
        default=False,
        help=(
            "Allow a write statement (INSERT/UPDATE/DELETE/DDL). Reads are the default, and a write "
            "is refused with STATE_QUERY_NEEDS_FORCE without this flag."
        ),
    )
    ps_query.add_argument(
        "--worktree-root",
        default=None,
        help="Target worktree. Required in practice: the query opens that project's state database.",
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

    # PROJECT MGMT SUBCOMMANDS (flat layout) ====================================
    parser_proj = subparsers.add_parser("project", help="Manage flat projects (~/.che-workspaces/<slug>/).")
    proj_subs = parser_proj.add_subparsers(dest="proj_cmd", required=True)

    # create (primary), add and init (aliases)
    pj_create = proj_subs.add_parser("create", aliases=["add", "init"], help="Create/refresh a project for a git repo.")
    pj_create.add_argument("repo_path", help="Path to the git checkout this project tracks.")
    pj_create.add_argument("--slug", required=True, help="Project slug (MANDATORY, e.g. acme).")
    pj_create.add_argument(
        "--domain",
        default="engineering",
        help=f"Default domain: {'|'.join(DOMAIN_SLUGS)} (legacy aliases: ux→design, operation→devops).",
    )
    pj_create.add_argument("--name", dest="friendly_name", default=None, help="Friendly name (default: the slug).")

    proj_subs.add_parser("list", help="List flat projects + docs, worktrees and DB files.")

    pj_remove = proj_subs.add_parser("remove")
    pj_remove.add_argument("project_slug", help="Project slug to move to trash (never deleted).")
    pj_remove.add_argument("--dry-run", action="store_true", default=True, help="Default: only show, DO NOT move.")
    pj_remove.add_argument(
        "--no-dry-run", dest="dry_run", action="store_false", help="Effectively move. Requires --confirm as well."
    )
    pj_remove.add_argument(
        "--confirm", dest="confirmed", action="store_true", default=False, help="Mandatory safety gate."
    )

    pj_restore = proj_subs.add_parser("restore")
    pj_restore.add_argument("trash_slug", help="Trash entry slug.")

    proj_subs.add_parser("trash-list", help="Contents of the .trash/ folder.")

    # WORKTREE MGMT SUBCOMMANDS (the only thing that binds a filesystem path) ====
    parser_wt = subparsers.add_parser("worktree", help="Bind a checkout to a project (~/<project>/worktrees/<name>/).")
    wt_subs = parser_wt.add_subparsers(dest="wt_cmd", required=True)

    wt_add = wt_subs.add_parser("add", help="Bind a git checkout to a project. Idempotent — reuses an existing tree.")
    wt_add.add_argument("repo_path", help="Absolute path to the git checkout.")
    wt_add.add_argument("--project", required=True, help="Owning project slug.")
    wt_add.add_argument("--name", required=True, help="Worktree name (e.g. main, feat-checkout).")
    wt_add.add_argument("--force", action="store_true", default=False, help="Adopt a directory without a binding.")

    wt_list = wt_subs.add_parser("list", help="List the worktrees bound to a project.")
    wt_list.add_argument("--project", required=True, help="Project slug.")

    wt_show = wt_subs.add_parser("show", help="Show one worktree binding.")
    wt_show.add_argument("project_slug", help="Project slug.")
    wt_show.add_argument("worktree_name", help="Worktree name.")

    wt_remove = wt_subs.add_parser("remove", help="Trash-safe removal of a worktree folder (never the repo).")
    wt_remove.add_argument("project_slug", help="Project slug.")
    wt_remove.add_argument("worktree_name", help="Worktree name.")
    wt_remove.add_argument("--dry-run", action="store_true", default=True, help="Default: only show, DO NOT move.")
    wt_remove.add_argument(
        "--no-dry-run", dest="dry_run", action="store_false", help="Effectively move. Requires --confirm as well."
    )
    wt_remove.add_argument(
        "--confirm", dest="confirmed", action="store_true", default=False, help="Mandatory safety gate."
    )

    # CHE SELF-UPDATE =========================================================
    parser_update = subparsers.add_parser(
        "update",
        aliases=["self-update", "upgrade"],
        help="Fast-forward this Che checkout to the latest main, and reload the CLI if it must.",
    )
    parser_update.add_argument(
        "--check",
        action="store_true",
        default=False,
        help="Report what an update would bring, without applying it. Nothing is written.",
    )
    parser_update.add_argument(
        "--che-home",
        default=None,
        help="Che checkout to update. Defaults to $CHE_HOME -> $HARNESS_HOME -> ~/.che-ai -> ~/.trae.",
    )
    parser_update.add_argument(
        "--remote",
        default="origin",
        help="Git remote to read from. Its default branch is what gets fast-forwarded.",
    )
    parser_update.add_argument("--json", action="store_true", default=False, help="Print the full result.")

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

    # PIXEL GATE SUBCOMMANDS (the §3.4 comparator of ux-pixel-check-gate) =======
    parser_pixel = subparsers.add_parser(
        "pixel",
        help="Run the ux-pixel-check gate: join design + DOM facts and score them numerically.",
    )
    pixel_subs = parser_pixel.add_subparsers(dest="pixel_cmd", required=True)

    px_check = pixel_subs.add_parser(
        "check",
        help="Compare design facts against DOM facts. Exit 0=PASS, 1=FAIL, 3=INCONCLUSIVE, 2=bad input.",
    )
    px_check.add_argument(
        "--map",
        required=True,
        help="design-map.json: {element: {design_node, selector}} — the only join between the two sides.",
    )
    px_check.add_argument("--dom", required=True, help="dom-facts.json, keyed by CSS selector.")
    design_group = px_check.add_mutually_exclusive_group(required=True)
    design_group.add_argument("--design", help="design-facts.json already keyed by design node id.")
    design_group.add_argument(
        "--design-source",
        help="Raw design artefact to extract from: a get_figma_data response, or an OpenPencil .op file.",
    )
    px_check.add_argument(
        "--design-backend",
        choices=DECLARED_BACKENDS,
        default=None,
        help=(
            "Extractor for --design-source. Never inferred from the file's shape. "
            "With --design it is provenance only, so any declared backend is accepted — "
            "the bag was produced elsewhere and mislabelling it would be the lie."
        ),
    )
    px_check.add_argument("--breakpoint", default="", help="Breakpoint label, recorded as report provenance.")
    px_check.add_argument(
        "--design-viewport",
        type=int,
        default=None,
        help="Viewport width the design frame was captured at. Must agree with --dom-viewport when both are given.",
    )
    px_check.add_argument(
        "--dom-viewport",
        type=int,
        default=None,
        help="Viewport width the DOM was measured at. A mismatch with --design-viewport is refused, not scored.",
    )
    px_check.add_argument(
        "--attempt",
        type=int,
        default=1,
        help=(
            "Pass number over this screen. §5 allows 2 (the first measurement plus one free retry); "
            "a higher value is refused unless --override-reason is given."
        ),
    )
    px_check.add_argument(
        "--override-reason",
        default="",
        help="The user's verbatim acceptance, recorded in the report. Required to exceed --attempt 2.",
    )
    px_check.add_argument("--out", default=None, help="Write the JSON report here (atomic, outside-worktree safe).")
    px_check.add_argument(
        "--design-facts-out",
        default=None,
        help=(
            "Write the §4.1 per-element record here. Pass $CHE_PIXEL_DESIGN_FACTS: it is committed "
            "beside the map, INSIDE the worktree, so this is the one output that bypasses the "
            "outside-worktree guard on purpose."
        ),
    )
    px_check.add_argument("--json", action="store_true", default=False, help="Print the full JSON report.")

    px_paths = pixel_subs.add_parser(
        "paths",
        help="Resolve the gate's artifact set as `export CHE_PIXEL_*` lines (eval-able).",
    )
    px_paths.add_argument("worktree_root", help="Absolute path to the user worktree")
    px_paths.add_argument("session_id", help="Che session id (sess-...)")
    px_paths.add_argument(
        "--sub-product",
        required=True,
        help="Sub-product slug — its design tree must already exist (che designer init)",
    )
    px_paths.add_argument("--breakpoint", required=True, help="Breakpoint label, e.g. lg")
    px_paths.add_argument(
        "--backend",
        required=True,
        choices=DECLARED_BACKENDS,
        help=(
            "Design backend (§3). Declared here so a backend the domain names but the engine "
            "cannot read is refused with its reason instead of an 'invalid choice' typo message."
        ),
    )
    px_paths.add_argument("--related-id", default="", help="Ticket/feature id, used to group the session artifacts")
    px_paths.add_argument("--attempt", type=int, default=1, help="Pass number; it is part of the report filename")

    px_diff = pixel_subs.add_parser(
        "diff",
        help="§4.5 whole-frame diff (evidence only). Writes the picture; never exits non-zero on a difference.",
    )
    px_diff.add_argument("--design", required=True, help="Design raster, e.g. $CHE_PIXEL_DESIGN_IMAGE")
    px_diff.add_argument("--dom", required=True, help="Implementation screenshot, e.g. $CHE_PIXEL_DOM_SCREENSHOT")
    px_diff.add_argument("--out", required=True, help="Where to write the diff PNG, e.g. $CHE_PIXEL_VISUAL_DIFF")
    px_diff.add_argument(
        "--threshold",
        type=float,
        default=0.1,
        help="pixelmatch matching threshold (0-1); smaller is more sensitive. §4.5 fixes it at 0.1.",
    )
    px_diff.add_argument("--json", action="store_true", default=False, help="Print the numbers as JSON.")

    px_crop = pixel_subs.add_parser(
        "crop",
        help="§4.5 per-element crops (evidence only). Writes the report and, optionally, the strip.",
    )
    px_crop.add_argument("--design", required=True, help="Design raster, e.g. $CHE_PIXEL_DESIGN_IMAGE")
    px_crop.add_argument("--dom", required=True, help="Implementation screenshot, e.g. $CHE_PIXEL_DOM_SCREENSHOT")
    px_crop.add_argument(
        "--map",
        required=True,
        help="design-map.json, each entry carrying a `design_box` in the design image's own pixels.",
    )
    px_crop.add_argument("--dom-facts", required=True, help="dom-facts.json, keyed by CSS selector.")
    px_crop.add_argument("--out", required=True, help="Where to write the report JSON, e.g. $CHE_PIXEL_CROP_REPORT")
    px_crop.add_argument(
        "--sheet",
        default=None,
        help=(
            "Where to write the design|implementation|diff strip, e.g. $CHE_PIXEL_CROP_SHEET. "
            "Omitted when every element was refused, so `sheet` in the report names only a real file."
        ),
    )
    px_crop.add_argument("--threshold", type=float, default=0.1, help="pixelmatch matching threshold (0-1).")
    px_crop.add_argument("--json", action="store_true", default=False, help="Print the report as JSON.")

    args = parser.parse_args(argv)

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
            # Used to be `sys.exit(1)` with nothing printed: an agent got a number and an empty
            # stream, with no way to tell a missing binding from a corrupt registry.
            fail("NO_REGISTRY_ENTRY", session_id=args.session_id)
        return

    if args.command == "decision_append":
        append_decision(
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
            except json.JSONDecodeError as exc:
                fail("INVALID_FLAGS_JSON", detail=str(exc))
            if isinstance(extra, dict):
                payload["flags"].update(extra)

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
                force=args.force,
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

    if args.command == "project":
        from che_core.workspaces import init_project, list_projects, list_trash, remove_project, restore_project

        if args.proj_cmd in ["create", "add", "init"]:
            res = init_project(
                args.repo_path,
                slug=args.slug,
                domain=args.domain,
                friendly_name=args.friendly_name,
            )
        elif args.proj_cmd == "list":
            res = list_projects()
        elif args.proj_cmd == "remove":
            res = remove_project(args.project_slug, dry_run=args.dry_run, confirmed=args.confirmed)
        elif args.proj_cmd == "restore":
            res = restore_project(args.trash_slug)
        elif args.proj_cmd == "trash-list":
            res = list_trash()
        else:
            parser.error(f"Unknown project subcommand: {args.proj_cmd}")
            return
        _print_json(res)
        return

    if args.command == "pixel":
        from che_core.pixel import (
            design_facts_record,
            exit_code,
            remediation_steps,
            resolve_design_source,
            run_check,
            summarise,
        )
        from che_core.pixel_dom import fact_bag_summary, validate_dom_facts

        if args.pixel_cmd == "paths":
            for key, value in _pixel_artifact_paths(
                args.worktree_root,
                args.session_id,
                args.sub_product,
                args.breakpoint,
                args.backend,
                args.related_id,
                args.attempt,
            ).items():
                print(f'export {key}="{value}"')
            return

        if args.pixel_cmd == "diff":
            from che_core.pixel_visual import frame_diff, save_rgba

            try:
                output, differing, refusal = frame_diff(args.design, args.dom, args.threshold)
            except (OSError, ValueError) as exc:
                fail("PIXEL_INPUT_INVALID", detail=str(exc))
            if refusal is not None or output is None:
                # §4.5: differing sizes are refused rather than scored, because the number
                # `pixelmatch` would return is computed against the wrong pixels. Bad input → 2.
                fail("PIXEL_SIZE_MISMATCH", detail=refusal)

            save_rgba(output, args.out)
            counted = int(output.shape[0] * output.shape[1])
            antialiased = int(((output[..., 0] == 255) & (output[..., 1] == 255) & (output[..., 2] == 0)).sum())
            payload = {
                "design_image": str(args.design),
                "dom_image": str(args.dom),
                "pixelmatch_threshold": args.threshold,
                "diff_image": str(args.out),
                "pixels": counted,
                "differing_pixels": differing,
                "antialiased_pixels": antialiased,
                "ratio": 0 if counted == 0 else round(differing / counted, 6),
            }
            if args.json:
                _print_json(payload)
            else:
                print(f"{100.0 * differing / counted:.2f}% of pixels differ ({differing}/{counted})")
                print("Evidence only, never a verdict: this ratio is not a threshold (§4.5).")
            # Deliberately exit 0: a screen that differs is the finding, not a failure to run.
            return

        if args.pixel_cmd == "crop":
            from che_core.pixel_visual import build_crop_report, public_crop_report, render_crop_sheet, save_rgba

            try:
                report = build_crop_report(
                    args.design,
                    args.dom,
                    args.map,
                    args.dom_facts,
                    args.threshold,
                    # Progress goes to stderr so `--json` keeps stdout parseable, and so a
                    # refusal reaches the operator's eye rather than only the report file.
                    log=lambda line: print(line, file=sys.stderr),
                )
            except (OSError, ValueError) as exc:
                fail("PIXEL_INPUT_INVALID", detail=str(exc))

            sheet = render_crop_sheet(report) if args.sheet else None
            if sheet is not None and args.sheet:
                save_rgba(sheet, args.sheet)
            payload = public_crop_report(report, sheet is not None, args.sheet)
            write_file_atomic(args.out, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
            if args.json:
                _print_json(payload)
            else:
                print(f"{payload['compared']} of {len(payload['elements'])} element(s) compared")
                print(f"report: {args.out}" + (f" · sheet: {args.sheet}" if payload["sheet"] else ""))
                print("Evidence only, never a verdict: the ratios are not pass marks (§4.5).")
            return

        if args.pixel_cmd != "check":
            parser.error(f"Unknown pixel subcommand: {args.pixel_cmd}")
            return

        if args.design_source and not args.design_backend:
            fail("INVALID_DESIGN_SOURCE", backends=", ".join(DECLARED_BACKENDS))

        try:
            design_map = _load_json(args.map)
            dom_facts = _load_json(args.dom)
            if args.design:
                design_facts = _load_json(args.design)
                backend = args.design_backend or ""
            else:
                node_ids = [
                    entry["design_node"]
                    for entry in design_map.values()
                    if isinstance(entry, dict) and isinstance(entry.get("design_node"), str)
                ]
                design_facts = resolve_design_source(Path(args.design_source), args.design_backend, node_ids)
                backend = args.design_backend
            if not isinstance(design_map, dict) or not isinstance(dom_facts, dict):
                raise ValueError("--map and --dom must each contain a JSON object at the root")
            # The bag is checked for shape and units BEFORE anything is scored, because a
            # wrong unit is silent: `line_height: 24` would be scored as an enormous
            # deviation rather than reported as the px-vs-ratio mistake it is, and a
            # selector the map names but the bag omits would become a false
            # `missing_from_dom` failure rather than the extraction error it is.
            problems = validate_dom_facts(
                dom_facts,
                [
                    entry["selector"]
                    for entry in design_map.values()
                    if isinstance(entry, dict) and isinstance(entry.get("selector"), str)
                ],
            )
            if problems:
                fail(
                    "DOM_FACTS_UNUSABLE",
                    count=len(problems),
                    problems="\n".join(f"  - {problem}" for problem in problems),
                )
            report = run_check(
                design_map,
                design_facts,
                dom_facts,
                backend=backend,
                breakpoint=args.breakpoint,
                design_viewport=args.design_viewport,
                dom_viewport=args.dom_viewport,
                attempt=args.attempt,
                override_reason=args.override_reason,
                # Digests of the two inputs, so a later run can tell "the same check
                # again" from "the check was moved": a changed digest means the map or
                # the design was edited, and comparing scores across that is meaningless.
                design_map_sha256=hashlib.sha256(Path(args.map).read_bytes()).hexdigest(),
                design_source_sha256=hashlib.sha256(Path(args.design_source or args.design).read_bytes()).hexdigest(),
            )
        except ValueError as exc:
            fail("PIXEL_INPUT_INVALID", detail=str(exc))

        payload = report.to_json()
        payload["summary"] = summarise(report)
        # What the bag declared about itself: the consequence of a thin extraction shows up
        # in `unverified_categories`, but the cause does not.
        payload["dom_fact_bag"] = fact_bag_summary(dom_facts)
        if args.design_facts_out:
            # §4.1's human record. Written AFTER the run is scored, so a refused run leaves
            # no file behind — the artefact is only worth having if it describes a check
            # that actually happened. And written directly rather than through
            # `write_file_atomic`, because the guard that helper enforces is exactly what
            # this file is exempt from: it is committed beside the map, inside the worktree.
            record = design_facts_record(design_map, design_facts, args.breakpoint)
            target = Path(args.design_facts_out)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.out:
            write_file_atomic(args.out, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
        if args.json:
            _print_json(payload)
        else:
            print(summarise(report))
            for step in remediation_steps(report):
                print(f"  fix: {step}")
        sys.exit(exit_code(report))

    if args.command == "worktree":
        from che_core.worktrees import add_worktree, list_worktrees, remove_worktree, show_worktree

        if args.wt_cmd == "add":
            res = add_worktree(args.project, args.repo_path, args.name, force=args.force)
        elif args.wt_cmd == "list":
            res = list_worktrees(args.project)
        elif args.wt_cmd == "show":
            res = show_worktree(args.project_slug, args.worktree_name)
        elif args.wt_cmd == "remove":
            res = remove_worktree(
                args.project_slug,
                args.worktree_name,
                dry_run=args.dry_run,
                confirmed=args.confirmed,
            )
        else:
            parser.error(f"Unknown worktree subcommand: {args.wt_cmd}")
            return
        _print_json(res)
        return

    if args.command in ("update", "self-update", "upgrade"):
        from che_core.selfupdate import UpdateRefused, exit_code, summarise, update

        try:
            state = update(che_home=args.che_home, remote=args.remote, check_only=args.check)
        except UpdateRefused as exc:
            # A refusal is the command declining to move a working tree it was not asked to move —
            # not a crash. The reason already carries the remedy, so print it and use its code.
            print(f"Error: {exc.reason}", file=sys.stderr)
            sys.exit(exc.code)

        if args.json:
            _print_json(state)
        else:
            print(summarise(state))
            # Name what is coming (or what arrived). "Update available" with no subjects is a
            # prompt to go and look, which is the opposite of what this command is for.
            for subject in state["commits"]:
                print(f"  {subject}")
            if state["commits_omitted"]:
                print(f"  … and {state['commits_omitted']} more")
        sys.exit(exit_code(state))

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
