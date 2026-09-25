import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from che_core.diagnostics import diagnosed, fail
from che_core.paths import compute_paths, ensure_session_dirs

# Sub-product slug contract: lowercase, digits, dash, underscore; must START with
# alphanumeric. Hard-rejects path traversal (`../../etc`), absolute paths, dotfiles.
_SUB_PRODUCT_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")

# Canonical Stitch DESIGN.md section order (SPEC §4.5 + Stitch DESIGN.md spec).
# Single source of truth — validator, render and downstream tooling all reference this list.
_CANONICAL_SECTIONS = (
    "Overview",
    "Colors",
    "Typography",
    "Layout",
    "Elevation & Depth",
    "Shapes",
    "Components",
    "Do's and Don'ts",
)

# Image magic-byte signatures (stdlib only — no Pillow in the che runtime).
# AB-4: a provider that returns an HTML error page / 403 / placeholder MUST be
# rejected before any file is written under design/assets/.
_IMAGE_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"\xff\xd8\xff", ".jpg"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"RIFF", ".webp"),
    (b"<?xml", ".svg"),
    (b"<svg", ".svg"),
)

# HTML/placeholder markers — anything starting with these is a non-image payload.
_PLACEHOLDER_MARKERS = (
    b"<!DOCTYPE",
    b"<!doctype",
    b"<html",
    b"<head",
    b"<body",
    b"<title",
)


def _che_home_root() -> Path:
    """Locate the che_core package root (where domains/, skills/, templates/ live)."""
    return Path(__file__).resolve().parent.parent


def run_init(worktree_root: str, session_id: str, sub_product: str) -> int:
    """F0 Tracer — write the git-native design tree inside the worktree.

    PRE: worktree_root exists; session_id is non-empty; sub_product matches _SUB_PRODUCT_SLUG_RE.
    POST: <wt>/design/DESIGN.md AND <wt>/design/tokens/tokens.json exist; returns 0.
    ABORTS (sys.exit(2)): invalid slug, no files written anywhere.

    See che-design-domain-v1 SPEC §4.2 B-1 (positive) and §4.3 AB-1 (negative).
    """
    if not isinstance(worktree_root, str) or not worktree_root:
        fail("MISSING_WORKTREE_ROOT")
    if not isinstance(session_id, str) or not session_id:
        fail("MISSING_SESSION_ID")
    if not isinstance(sub_product, str) or not _SUB_PRODUCT_SLUG_RE.match(sub_product):
        fail("INVALID_SUB_PRODUCT_SLUG", sub_product=sub_product, pattern=_SUB_PRODUCT_SLUG_RE.pattern)

    wt_root = Path(worktree_root).resolve()
    if not wt_root.is_dir():
        fail("NOT_A_DIRECTORY", path=wt_root)

    # Design root MUST live inside the worktree — refuse any resolved path outside.
    design_root = wt_root / "design"
    sub_product_dir = design_root / sub_product

    # Defensive: even if a future refactor adds symlinks, the resolved path must
    # stay under the worktree. is_relative_to is Python 3.9+; project targets py39.
    try:
        design_root_resolved = design_root.resolve(strict=False)
        wt_root_resolved = wt_root.resolve(strict=False)
        if not (design_root_resolved == wt_root_resolved or wt_root_resolved in design_root_resolved.parents):
            fail(
                "DESIGN_ROOT_ESCAPES_WORKTREE",
                design_root=design_root_resolved,
                worktree_root=wt_root_resolved,
            )
    except (OSError, RuntimeError) as e:
        fail("PATH_UNRESOLVABLE", path=design_root, detail=str(e))

    # Resolve templates relative to che_core package — no hardcoded absolute paths.
    che_home = _che_home_root()
    design_md_template = che_home / "domains" / "ux" / "templates" / "DESIGN.md.template"
    tokens_json_template = che_home / "domains" / "ux" / "templates" / "tokens.json.template"

    if not design_md_template.is_file():
        fail("TEMPLATE_MISSING", name="DESIGN.md", path=design_md_template)
    if not tokens_json_template.is_file():
        fail("TEMPLATE_MISSING", name="tokens.json", path=tokens_json_template)

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    design_root.mkdir(parents=True, exist_ok=True)
    sub_product_dir.mkdir(parents=True, exist_ok=True)
    (design_root / "tokens").mkdir(parents=True, exist_ok=True)

    design_md = design_root / "DESIGN.md"
    tokens_json = design_root / "tokens" / "tokens.json"

    # Render DESIGN.md from template (placeholders stay literal in F0; F2 fills them).
    md_text = design_md_template.read_text(encoding="utf-8")
    md_text = md_text.replace("{{sub_product}}", sub_product).replace("{{created_at}}", created_at)
    design_md.write_text(md_text, encoding="utf-8")

    # Render tokens.json — keep JSON parseable even with placeholder strings.
    json_text = tokens_json_template.read_text(encoding="utf-8")
    json_text = json_text.replace("{{sub_product}}", sub_product).replace("{{created_at}}", created_at)
    tokens_json.write_text(json_text, encoding="utf-8")

    # F3: sub-product-specific files live under design/<sub_product>/. R5 (sub-product isolation)
    # guarantees that `git diff --name-only` after init for sub-product B touches ONLY
    # `design/<B>/` + `design/DESIGN.md` (top-level aggregator), never `design/<A>/` for any other sub-product A.
    (sub_product_dir / "tokens").mkdir(parents=True, exist_ok=True)
    sub_design_md = sub_product_dir / "DESIGN.md"
    sub_tokens_json = sub_product_dir / "tokens" / "tokens.json"
    sub_md_text = md_text  # same rendered template content for this sub-product
    sub_json_text = json_text
    sub_design_md.write_text(sub_md_text, encoding="utf-8")
    sub_tokens_json.write_text(sub_json_text, encoding="utf-8")

    # Bootstrap any session dirs the user may need (cheap, idempotent, NON-FATAL).
    # The design tree is the F0 deliverable; session scaffolding is opportunistic.
    # NOTE: `compute_paths` signals an unbound worktree with `sys.exit(3)`, i.e. a
    # `SystemExit` — which is a BaseException and therefore NOT caught by
    # `except Exception`. Catching it explicitly is what makes the "non-fatal"
    # contract above actually hold.
    try:
        ensure_session_dirs(str(wt_root), session_id)
    except (Exception, SystemExit):
        pass

    print(f"CHE_DESIGN_DIR={design_root}")
    print(f"CHE_DESIGN_SUB_PRODUCT_DIR={sub_product_dir}")
    print(f"CHE_DESIGN_TOKENS_FILE={tokens_json}")
    print(f"CHE_DESIGN_SUB_PRODUCT_DESIGN_MD={sub_design_md}")
    print(f"CHE_DESIGN_SUB_PRODUCT_TOKENS_FILE={sub_tokens_json}")
    return 0


def run_tokens_render(worktree_root: str) -> int:
    """F2 Tokens render — re-render DESIGN.md frontmatter + tokens.styles.css from tokens.json.

    SPEC §4.2 B-3 (positive): two renders → byte-identical DESIGN.md + tokens.styles.css (idempotent).
    SPEC §4.5 R4 (DRY): tokens.json is the single source of truth; DESIGN.md frontmatter must mirror it.
    SPEC §4.7 A-1 (assertive): design_dir must exist before render.
    SPEC §4.7 A-2 (assertive): tokens.json must have a `colors` key.

    PRE: worktree_root exists; design/ exists; tokens/tokens.json exists + parses as JSON + has `colors`.
    POST: DESIGN.md frontmatter equals tokens.json; tokens.styles.css contains --color-* vars.
    ABORTS (sys.exit(2)): any PRE violation; no files written.
    """
    if not isinstance(worktree_root, str) or not worktree_root:
        fail("MISSING_WORKTREE_ROOT")

    wt_root = Path(worktree_root).resolve()
    if not wt_root.is_dir():
        fail("NOT_A_DIRECTORY", path=wt_root)

    # A-1: design_dir must exist before render (no auto-create — keeps the F0/F2 boundary clean).
    design_root = wt_root / "design"
    if not design_root.is_dir():
        fail("DESIGN_TREE_MISSING", path=design_root, worktree_root=wt_root)

    tokens_json = design_root / "tokens" / "tokens.json"
    if not tokens_json.is_file():
        fail("TOKENS_JSON_MISSING", path=tokens_json, worktree_root=wt_root)

    try:
        tokens = json.loads(tokens_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail("INVALID_JSON", path=tokens_json, detail=str(e))

    # A-2: tokens.json must have a `colors` object.
    if not isinstance(tokens, dict) or "colors" not in tokens or not isinstance(tokens["colors"], dict):
        fail("TOKENS_MISSING_COLORS")

    # Read template fresh every render so any template edits propagate without a rebuild.
    che_home = _che_home_root()
    template_path = che_home / "domains" / "ux" / "templates" / "DESIGN.md.template"
    if not template_path.is_file():
        fail("TEMPLATE_MISSING", name="DESIGN.md", path=template_path)
    rendered = template_path.read_text(encoding="utf-8")

    # Substitute all placeholders sourced from tokens.json (R4 single-source).
    colors = tokens["colors"]
    typography = tokens.get("typography", {})
    rounded = tokens.get("rounded", {})
    components = tokens.get("components", {})

    rendered = rendered.replace("{{sub_product}}", str(tokens.get("sub_product", "untitled")))
    rendered = rendered.replace("{{created_at}}", str(tokens.get("created_at", "")))
    rendered = rendered.replace("{{primary_color}}", str(colors.get("primary", "#3B82F6")))
    rendered = rendered.replace("{{secondary_color}}", str(colors.get("secondary", "#10B981")))
    rendered = rendered.replace("{{surface_color}}", str(colors.get("surface", "#FFFFFF")))
    rendered = rendered.replace("{{on_surface_color}}", str(colors.get("on_surface", "#0F172A")))
    rendered = rendered.replace("{{font_family_sans}}", str(typography.get("font_family_sans", "Inter")))
    rendered = rendered.replace("{{font_family_serif}}", str(typography.get("font_family_serif", "Georgia")))
    rendered = rendered.replace("{{type_scale}}", str(typography.get("scale", "1.250")))
    rendered = rendered.replace("{{radius_sm}}", str(rounded.get("sm", "2px")))
    rendered = rendered.replace("{{radius_md}}", str(rounded.get("md", "8px")))
    rendered = rendered.replace("{{radius_lg}}", str(rounded.get("lg", "16px")))
    rendered = rendered.replace("{{radius_full}}", str(rounded.get("full", "9999px")))
    button = components.get("button", {})
    card = components.get("card", {})
    rendered = rendered.replace("{{button_radius}}", str(button.get("radius", "md")))
    rendered = rendered.replace("{{button_height}}", str(button.get("height", "40px")))
    rendered = rendered.replace("{{card_radius}}", str(card.get("radius", "lg")))
    rendered = rendered.replace("{{card_padding}}", str(card.get("padding", "24px")))

    design_md = design_root / "DESIGN.md"
    design_md.write_text(rendered, encoding="utf-8")

    # Render tokens.styles.css from the same tokens.json (single source).
    css_lines: list[str] = [":root {"]
    for name, value in colors.items():
        css_lines.append(f"  --color-{name}: {value};")
    for name, value in rounded.items():
        unit = "px" if isinstance(value, (int, float)) else ""
        css_lines.append(f"  --radius-{name}: {value}{unit};")
    spacing = tokens.get("spacing", {})
    if isinstance(spacing, dict) and "base" in spacing:
        css_lines.append(f"  --spacing-base: {spacing['base']}px;")
    if "font_family_sans" in typography:
        css_lines.append(f"  --font-family-sans: {typography['font_family_sans']};")
    css_lines.append("}")
    styles_path = design_root / "tokens" / "tokens.styles.css"
    styles_path.write_text("\n".join(css_lines) + "\n", encoding="utf-8")

    print(f"CHE_DESIGN_MD={design_md}")
    print(f"CHE_TOKENS_STYLES_CSS={styles_path}")
    return 0


def run_validate(design_md_path: str) -> int:
    """F1 Validator — check DESIGN.md against the Stitch DESIGN.md spec.

    SPEC §4.2 B-2 (positive): frontmatter + 8 canonical sections in order → exit 0.
    SPEC §4.3 AB-2/3 (negative): duplicate or missing canonical section → exit 1.
    SPEC §4.7 A-3 (assertive invariant): frontmatter delimiter count must be exactly 2.

    PRE: design_md_path points to an existing readable file.
    POST: returns 0 if DESIGN.md is structurally valid; 1 otherwise.
    Prints `errors=N` and a bullet list of issues to stdout. Then echoes the canonical
    sections in order so callers can grep `## Overview` etc.
    """
    if not isinstance(design_md_path, str) or not design_md_path:
        fail("MISSING_DESIGN_MD_PATH")

    md_path = Path(design_md_path)
    if not md_path.is_file():
        fail("DESIGN_MD_MISSING", path=md_path)

    text = md_path.read_text(encoding="utf-8")
    issues: list[str] = []

    # A-3: frontmatter delimiter count must be exactly 2 lines (`---` open + `---` close).
    delim_lines = sum(1 for line in text.splitlines() if line.strip() == "---")
    if delim_lines != 2:
        issues.append(f"frontmatter: expected exactly 2 `---` delimiter lines (A-3); found {delim_lines}")

    # Collect `## <Heading>` lines (the canonical sections + any extras).
    section_re = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
    found = section_re.findall(text)

    # AB-2: duplicates among the canonical set.
    canonical_set = set(_CANONICAL_SECTIONS)
    seen: list[str] = []
    duplicates: list[str] = []
    for s in found:
        if s in canonical_set:
            if s in seen:
                duplicates.append(s)
            else:
                seen.append(s)

    # AB-3: missing canonical sections.
    missing_sections = [s for s in _CANONICAL_SECTIONS if s not in seen]

    # B-2: relative order of canonical sections must match canonical order.
    order_correct = True
    last_idx = -1
    for s in seen:
        idx = _CANONICAL_SECTIONS.index(s)
        if idx < last_idx:
            order_correct = False
            break
        last_idx = idx

    if duplicates:
        for d in duplicates:
            issues.append(f"duplicate section: ## {d}")
    if missing_sections:
        for m in missing_sections:
            issues.append(f"missing section: ## {m}")
    if not order_correct and seen:
        issues.append("section order: canonical sections must appear in canonical order")

    print(f"errors={len(issues)}")
    for issue in issues:
        print(f"  - {issue}")
    # Echo canonical sections so callers can grep `## Overview` etc.
    for s in seen:
        print(f"## {s}")

    return 0 if not issues else 1


def _is_real_image(data: bytes) -> bool:
    """True if `data` looks like an image, False if it is HTML/placeholder/empty.

    AB-4: a provider returning an HTML error page / 403 / placeholder must be
    discarded BEFORE any file is written under design/assets/.
    """
    stripped = data.lstrip()
    if any(stripped.startswith(m) for m in _PLACEHOLDER_MARKERS):
        return False
    return any(data.startswith(m) for m, _ in _IMAGE_MAGIC)


def run_stock_add(
    worktree_root: str,
    asset_path: str,
    provider: str,
    license_id: str,
    source_url: str,
) -> int:
    """F4 Stock asset — copy a downloaded asset into design/assets/ + record provenance.

    SPEC §4.2 B-5 (positive): accepted asset lands under design/assets/ and
    design/assets/CREDITS.md gains one entry with provider= / license= / source_url=.
    SPEC §4.3 AB-4 (negative): an HTML/placeholder payload writes NOTHING and
    appends NO CREDITS entry; the pipeline advances to the next provider.

    PRE: worktree_root valid dir; asset_path exists; provider/license/source_url non-empty.
    POST: asset copied to design/assets/<basename>; CREDITS.md contains the entry; returns 0.
    ABORTS (sys.exit(2)): asset is not a real image; no files written.
    """
    if not isinstance(worktree_root, str) or not worktree_root:
        fail("MISSING_WORKTREE_ROOT")
    if not isinstance(asset_path, str) or not asset_path:
        fail("MISSING_ASSET_PATH")
    for label, value in (("provider", provider), ("license", license_id), ("source_url", source_url)):
        if not isinstance(value, str) or not value.strip():
            fail("MISSING_ASSET_METADATA", label=label)

    wt_root = Path(worktree_root).resolve()
    if not wt_root.is_dir():
        fail("NOT_A_DIRECTORY", path=wt_root)

    asset = Path(asset_path).resolve()
    if not asset.is_file():
        fail("ASSET_FILE_MISSING", path=asset)

    data = asset.read_bytes()
    if not _is_real_image(data):
        fail("ASSET_NOT_AN_IMAGE", name=asset.name)

    assets_dir = wt_root / "design" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    dest = assets_dir / asset.name
    dest.write_bytes(data)

    credits = assets_dir / "CREDITS.md"
    entry = (
        f"- {dest.name} | provider={provider.strip()} | "
        f"license={license_id.strip()} | source_url={source_url.strip()}\n"
    )
    header = "# design/assets/CREDITS.md\n\nThird-party asset provenance (R3). "
    header += "Every asset under design/assets/ MUST have a matching entry here.\n\n"
    if credits.is_file():
        credits.write_text(credits.read_text(encoding="utf-8") + entry, encoding="utf-8")
    else:
        credits.write_text(header + entry, encoding="utf-8")

    print(f"CHE_ASSET_FILE={dest}")
    print(f"CHE_CREDITS_FILE={credits}")
    return 0


def run_bootstrap(worktree_root: str, session_id: str, mode: str, slug: str):
    wt_root = Path(worktree_root).resolve()

    if not wt_root.is_dir():
        fail("NOT_A_DIRECTORY", path=wt_root)

    paths = compute_paths(str(wt_root), session_id)
    ensure_session_dirs(str(wt_root), session_id)

    design_root = Path(os.environ.get("CHE_DESIGN_ROOT") or (Path(paths["CHE_WORKSPACE_SHARED"]) / "design"))

    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    design_dir = design_root / f"{mode}-{slug}-{date_str}"

    design_dir.mkdir(parents=True, exist_ok=True)

    print(f"CHE_DESIGN_ROOT={design_root}")
    print(f"CHE_DESIGN_DIR={design_dir}")
    print("\nBootstrap complete. Export these variables to use in the subsequent design gates.")


def build_parser():
    """Declare the `che designer` surface and return the parser.

    Separate from :func:`dispatch` so ``che_core.manifest`` can walk it: `che designer …` is forwarded
    before argparse runs, so the `che` parser knows the command exists but nothing about its
    arguments. Walking this parser is what lets `che capabilities --json` describe it honestly.
    """
    parser = argparse.ArgumentParser(prog="che designer", description="Che Social UI Designer Helper")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    p_boot = subparsers.add_parser("bootstrap")
    p_boot.add_argument("worktree_root")
    p_boot.add_argument("session_id")
    p_boot.add_argument("mode", help="Design mode (e.g., A, B, C, D)")
    p_boot.add_argument("slug", help="Design slug (e.g., post-natal)")

    p_init = subparsers.add_parser(
        "init",
        help="F0 Tracer — write the git-native design tree inside the worktree (B-1).",
    )
    p_init.add_argument("worktree_root", help="Absolute path to the user worktree")
    p_init.add_argument("session_id", help="Che session id (sess-...)")
    p_init.add_argument(
        "--sub-product",
        required=True,
        help="Sub-product slug (lowercase alnum + dash/underscore; max 63 chars)",
    )

    p_val = subparsers.add_parser(
        "validate",
        help="F1 Validator — check DESIGN.md against the Stitch DESIGN.md spec (B-2 + A-3).",
    )
    p_val.add_argument("design_md_path", help="Absolute path to a DESIGN.md file")

    p_tokens = subparsers.add_parser(
        "tokens",
        help="F2 Tokens — subcommands to operate on design/tokens/tokens.json (single-source of truth).",
    )
    p_tokens_sub = p_tokens.add_subparsers(dest="tokens_cmd", required=True)
    p_tokens_render = p_tokens_sub.add_parser(
        "render",
        help="F2 Render — re-render DESIGN.md frontmatter + tokens.styles.css from tokens.json (B-3 + R4 + A-1/A-2).",
    )
    p_tokens_render.add_argument("worktree_root", help="Absolute path to the user worktree")

    p_stock = subparsers.add_parser(
        "stock",
        help="F4 Stock — subcommands to record third-party asset provenance (B-5 + AB-4 + R3).",
    )
    p_stock_sub = p_stock.add_subparsers(dest="stock_cmd", required=True)
    p_stock_add = p_stock_sub.add_parser(
        "add",
        help="F4 Add — copy a downloaded image into design/assets/ + append CREDITS.md entry (B-5 + AB-4).",
    )
    p_stock_add.add_argument("worktree_root", help="Absolute path to the user worktree")
    p_stock_add.add_argument("asset_path", help="Absolute path to the downloaded asset file")
    p_stock_add.add_argument("--provider", required=True, help="Provider name (e.g. unsplash)")
    p_stock_add.add_argument("--license", required=True, dest="license_id", help="Licence identifier (e.g. CC0)")
    p_stock_add.add_argument("--source-url", required=True, help="Source URL of the asset")

    return parser


def dispatch(argv=None):
    """Parse one `che designer …` invocation and run the selected command.

    Deliberately **undecorated**: ``che designer …`` reaches this through ``che_core.cli``, whose own
    ``@diagnosed`` wrapper owns failure rendering and is the only layer that saw the global ``--json``.
    Wrapping here as well would render the failure first — and always as prose, because the flag was
    consumed by the outer parser. Standalone use goes through :func:`main`, which does wrap.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "bootstrap":
        run_bootstrap(args.worktree_root, args.session_id, args.mode, args.slug)
        return

    if args.cmd == "init":
        rc = run_init(args.worktree_root, args.session_id, args.sub_product)
        sys.exit(rc)

    if args.cmd == "validate":
        rc = run_validate(args.design_md_path)
        sys.exit(rc)

    if args.cmd == "tokens" and args.tokens_cmd == "render":
        rc = run_tokens_render(args.worktree_root)
        sys.exit(rc)

    if args.cmd == "stock" and args.stock_cmd == "add":
        rc = run_stock_add(
            args.worktree_root,
            args.asset_path,
            args.provider,
            args.license_id,
            args.source_url,
        )
        sys.exit(rc)


@diagnosed
def main(argv=None):
    """Standalone entrypoint — ``python -m che_core.designer …``.

    ``che designer …`` does not come through here (see :func:`dispatch`).
    """
    dispatch(argv)


if __name__ == "__main__":
    main()
