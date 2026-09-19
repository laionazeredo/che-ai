#!/usr/bin/env python3
"""Bootstrap the Che org + skills into a running Paperclip instance.

Runs *inside* the Paperclip container. Three responsibilities, all idempotent:

  1. mint a board API key and persist it under ``$PAPERCLIP_HOME/.che/board-key``.
     A ``local_trusted`` loopback request is implicitly trusted, so the key can
     be minted without any credentials -- and it keeps working after the
     instance is switched to ``authenticated``.
  2. import ``package/`` (company + agents + skills) into the instance,
     targeting the existing company when present (``collisionStrategy=replace``)
     and creating it otherwise. Re-running never duplicates.
  3. attach the imported root agent(s) -- the PM -- under the company's
     pre-existing lead. Paperclip's onboarding always creates a lead agent
     before any import, so the PM must not become a second root. See
     ``attach_roots_to_lead``.

Stdlib only, so it runs on the stock Paperclip image.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("PAPERCLIP_API_URL", "http://127.0.0.1:3100").rstrip("/")
PACKAGE_DIR = os.environ.get(
    "CHE_PACKAGE_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "package"),
)
# Unset means "auto-detect": join the company that already has a lead agent.
COMPANY = os.environ.get("CHE_COMPANY") or None
KEY_PATH = os.environ.get(
    "CHE_BOARD_KEY_PATH",
    os.path.join(os.environ.get("PAPERCLIP_HOME", "/paperclip"), ".che", "board-key"),
)
KEY_NAME = os.environ.get("CHE_BOARD_KEY_NAME", "che-bootstrap")


def request(method: str, path: str, body: dict | None = None, key: str | None = None):
    """Return ``(status, parsed_body)``; never raises on HTTP errors."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            status = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        status = exc.code
    except urllib.error.URLError as exc:
        return 0, {"error": f"cannot reach {BASE}: {exc.reason}"}
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, {"error": raw[:400]}


def read_saved_key() -> str | None:
    try:
        with open(KEY_PATH, encoding="utf-8") as handle:
            token = handle.read().strip()
        return token or None
    except FileNotFoundError:
        return None


def save_key(token: str) -> None:
    os.makedirs(os.path.dirname(KEY_PATH), exist_ok=True)
    with open(KEY_PATH, "w", encoding="utf-8") as handle:
        handle.write(token + "\n")
    os.chmod(KEY_PATH, 0o600)


def resolve_key() -> str | None:
    """Return a usable board key, minting one when running under local_trusted."""
    saved = read_saved_key()
    if saved:
        status, _ = request("GET", "/api/companies", key=saved)
        if status == 200:
            print(f"board key: reusing {KEY_PATH}")
            return saved
        print(f"board key: saved key rejected (HTTP {status}), minting a new one")

    status, body = request("POST", "/api/board-api-keys", {"name": KEY_NAME})
    if status != 201 or not body.get("token"):
        print(
            f"board key: cannot mint (HTTP {status}: {body.get('error')}).\n"
            "  A board key can only be minted with local loopback trust, i.e. while the\n"
            "  instance runs with PAPERCLIP_DEPLOYMENT_MODE=local_trusted. Either start it\n"
            f"  that way, or drop a key at {KEY_PATH} and re-run.",
            file=sys.stderr,
        )
        return None
    save_key(body["token"])
    print(f"board key: minted '{KEY_NAME}' -> {KEY_PATH}")
    return body["token"]


def collect_package(root: str) -> dict[str, str]:
    files: dict[str, str] = {}
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            full = os.path.join(dirpath, name)
            files[os.path.relpath(full, root)] = open(full, encoding="utf-8").read()
    return files


def slugify(value: str | None) -> str:
    """Mirror Paperclip's ``normalizeAgentUrlKey`` so slugs compare equal."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def package_agent_slugs(files: dict[str, str]) -> set[str]:
    """The agent slugs the package owns, from its ``agents/<slug>/`` layout."""
    return {path.split("/")[1] for path in files if path.startswith("agents/") and len(path.split("/")) > 2}


def find_company(key: str, ref: str) -> str | None:
    """Resolve a company by id or by exact name."""
    if re.fullmatch(r"[0-9a-fA-F-]{36}", ref):
        return ref
    status, body = request("GET", "/api/companies", key=key)
    if status != 200 or not isinstance(body, list):
        print(f"companies: cannot list (HTTP {status}: {body.get('error')})", file=sys.stderr)
        return None
    for company in body:
        if company.get("name") == ref:
            return company.get("id")
    return None


def unowned_roots(key: str, company_id: str, our_slugs: set[str]) -> list[dict] | None:
    """Root agents in a company that the package does not own (its lead)."""
    status, agents = request("GET", f"/api/companies/{company_id}/agents", key=key)
    if status != 200 or not isinstance(agents, list):
        return None
    return [a for a in agents if not a.get("reportsTo") and slugify(a.get("name")) not in our_slugs]


def resolve_target(key: str, ref: str | None, our_slugs: set[str]) -> tuple[str | None, str]:
    """Pick the company to import into; ``None`` means "create one".

    An explicit `CHE_COMPANY` always wins. Otherwise the team joins the company
    that already has a lead agent -- the one onboarding creates -- rather than
    spawning a sibling company beside it.
    """
    if ref:
        company_id = find_company(key, ref)
        if company_id:
            return company_id, f"'{ref}'"
        return None, f"'{ref}' not found, creating it"

    status, companies = request("GET", "/api/companies", key=key)
    if status != 200 or not isinstance(companies, list):
        print(f"companies: cannot list (HTTP {status}), creating one", file=sys.stderr)
        return None, "cannot list companies, creating one"

    candidates = []
    for company in companies:
        leaves = unowned_roots(key, company["id"], our_slugs)
        if leaves and len(leaves) == 1:
            candidates.append((company, leaves[0]))

    if len(candidates) == 1:
        company, lead = candidates[0]
        return company["id"], f"'{company['name']}' (has lead '{lead.get('name')}')"
    if len(candidates) > 1:
        names = ", ".join(f"'{c['name']}'" for c, _ in candidates)
        print(
            f"  warn: {len(candidates)} companies have a lead agent ({names}); set CHE_COMPANY to pick one",
            file=sys.stderr,
        )
    return None, "no company with a single lead agent, creating one"


def attach_roots_to_lead(key: str, company_id: str, our_slugs: set[str]) -> None:
    """Re-parent the imported root agent(s) under the company's existing lead.

    Paperclip's onboarding always creates a lead agent before any import, so the
    PM arriving as a root would present itself as a second CEO. Any root agent
    the package does not own is that lead; when exactly one exists, the imported
    roots report to it.
    """
    status, agents = request("GET", f"/api/companies/{company_id}/agents", key=key)
    if status != 200 or not isinstance(agents, list):
        print(f"  warn: cannot list agents (HTTP {status}), skipping org attach", file=sys.stderr)
        return

    roots = [a for a in agents if not a.get("reportsTo") and slugify(a.get("name")) in our_slugs]
    if not roots:
        print("  org: imported team already reports to someone")
        return

    candidates = [a for a in agents if not a.get("reportsTo") and slugify(a.get("name")) not in our_slugs]
    if not candidates:
        print("  org: no pre-existing lead agent; the PM stays at the root (fresh company)")
        return
    if len(candidates) > 1:
        names = ", ".join(str(a.get("name")) for a in candidates)
        print(f"  warn: {len(candidates)} root agents predate the import ({names}); set the manager in the UI")
        return

    lead = candidates[0]
    for agent in roots:
        status, body = request("PATCH", f"/api/agents/{agent['id']}", {"reportsTo": lead["id"]}, key=key)
        if status == 200:
            print(f"  org: {agent.get('name')} now reports to {lead.get('name')}")
        else:
            print(
                f"  warn: could not attach {agent.get('name')} to {lead.get('name')} "
                f"(HTTP {status}: {body.get('error')})",
                file=sys.stderr,
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default=PACKAGE_DIR, help="package directory to import")
    parser.add_argument(
        "--company",
        default=COMPANY,
        help="target company name or id; auto-detected from the onboarding lead when unset",
    )
    parser.add_argument("--mint-only", action="store_true", help="mint the board key and stop")
    parser.add_argument(
        "--import-only",
        action="store_true",
        help="import with the saved key, without minting",
    )
    args = parser.parse_args()

    key = read_saved_key() if args.import_only else resolve_key()
    if args.import_only and not key:
        print(f"board key: none at {KEY_PATH}", file=sys.stderr)
        return 1
    if not key:
        return 1
    if args.mint_only:
        return 0

    files = collect_package(args.package)
    if not files:
        print(f"package: nothing to import under {args.package}", file=sys.stderr)
        return 1

    our_slugs = package_agent_slugs(files)
    company_id, reason = resolve_target(key, args.company, our_slugs)
    print(f"target: {reason}")
    target = {"mode": "existing_company", "companyId": company_id} if company_id else {"mode": "new_company"}
    body = {
        "source": {"type": "inline", "files": files, "expectedFileCount": len(files)},
        "target": target,
        "collisionStrategy": "replace",
        # `include.company` rewrites the target's name, description and logo, so
        # it is only safe when we are the ones creating the company. On an
        # existing company it would rename the board's own company.
        "include": {"company": company_id is None, "agents": True, "skills": True, "issues": True},
    }
    status, result = request("POST", "/api/companies/import", body, key=key)
    if status not in (200, 201):
        print(f"import: failed (HTTP {status}: {result.get('error')})", file=sys.stderr)
        return 1

    agents = result.get("agents", [])
    skills = result.get("skills", [])
    imported_company_id = (result.get("company") or {}).get("id") or company_id
    print(
        f"import: company '{result.get('company', {}).get('name')}'"
        f" {result.get('company', {}).get('action')}"
        f" | agents {len(agents)} | skills {len(skills)}"
        f" | files {len(files)}"
    )
    for agent in agents:
        print(f"  agent {agent.get('slug'):<10} {agent.get('action')}")
    # A re-import reports one "will be overwritten" warning per existing entity,
    # which is just the idempotent replace path; collapse it to a single line.
    overwritten = sum(1 for w in result.get("warnings") or [] if "will be overwritten" in w)
    other = [w for w in (result.get("warnings") or []) if "will be overwritten" not in w]
    if overwritten:
        print(f"  note: {overwritten} existing entries replaced")
    for warning in other:
        print(f"  warn: {warning}")

    attach_roots_to_lead(key, imported_company_id, our_slugs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
