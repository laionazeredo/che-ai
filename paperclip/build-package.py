#!/usr/bin/env python3
"""Generate the importable Paperclip company package from the Che repo.

The package is the single thing Paperclip needs to import. It carries BOTH the
org (agents, roles, org chart, cron routine) AND every Che skill, because the
company-import path also imports the skills found in the package
(``companySkills.importPackageFiles`` runs whenever ``include.skills`` or
``include.agents`` is set). So one import = org + skills + per-agent skill
assignment — no second manual step.

Layout produced (``paperclip/package``):

    COMPANY.md
    .paperclip.yaml
    agents/<slug>/AGENTS.md      # frontmatter gains `skills:` from AGENT_SKILLS
    skills/<slug>/SKILL.md       # copied from ../skills
    skills/<slug>/references/...
    tasks/<slug>/TASK.md

Skills are copied TEXT-ONLY and with ``scripts/`` removed:
  - binaries would be fetched as text by the GitHub source resolver and corrupt,
  - ``scripts/`` raises the skill trust level to ``scripts_executables``, which
    the import hard-blocks for external sources.

Usage:  python3 build-package.py [--check]
"""

import argparse
import shutil
import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parent
SEED_DIR = MODULE_DIR / "seed"
PACKAGE_DIR = MODULE_DIR / "package"
SKILLS_SRC = REPO_ROOT / "skills"

# Directories never copied from a skill.
EXCLUDED_DIRS = {"scripts", "__pycache__", ".git"}
# Extensions considered safe text (anything else is skipped).
TEXT_EXT = {
    ".md",
    ".markdown",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".cjs",
    ".css",
    ".html",
    ".toon",
    ".csv",
}

# Which Che skills each agent gets (frontmatter `skills:` -> desiredSkills).
# Keys are the skill directory names. Edit here; the generator injects them.
AGENT_SKILLS = {
    "pm": [
        "che-act",
        "che-spec",
        "che-plan",
        "che-onboarding",
        "che-xray",
        "che-archeology",
        "che-architect",
        "che-graph",
        "che-explain",
        "che-pr-comments",
        "che-decisions-query",
        "che-executor-dispatcher",
        "engineering-contracts",
        "architecture-strategy-expert",
        "project-management-expert",
    ],
    "engineer": [
        "engineering-contracts",
        "che-developer",
        "che-graph",
        "che-merge-resolver",
        "che-debugger-bugfix",
        "che-ci-fixer",
        "gh-stack",
        "typescript-expert",
        "python-expert",
        "rust-expert",
        "golang-expert",
        "frontend-modern-stack",
        "backend-runtime-expert",
        "devops-infra-expert",
        "postgres-supabase-expert",
        "database-design-expert",
        "ecommerce-expert",
        "ai-agent-orchestrator",
    ],
    "designer": [
        "che-social-ui-designer",
        "frontend-modern-stack",
        "accessibility-expert",
        "penpot-expert",
        "web-performance-expert",
        "digital-marketing-expert",
        "remotion-video-production",
    ],
    "qa": [
        "che-qa",
        "che-scope-checker",
        "che-code-review",
        "che-compliance",
        "che-manual-test-executor",
        "che-ship",
        "engineering-contracts",
        "web-performance-expert",
    ],
}


def split_frontmatter(text):
    """Return (frontmatter_lines, body). Tolerates a file with no frontmatter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return lines[1:index], "\n".join(lines[index + 1 :]).lstrip("\n")
    return [], text


def render_agent_markdown(source_path, skills):
    """Copy an agent AGENTS.md, injecting/replacing its `skills:` list."""
    frontmatter, body = split_frontmatter(source_path.read_text(encoding="utf-8"))
    kept = [line for line in frontmatter if not line.lstrip().startswith("skills:")]
    if len(kept) != len(frontmatter):
        raise SystemExit(f"{source_path}: frontmatter must not declare `skills:` (it is generated)")
    rendered = ["---", *kept, "skills:"] + [f"  - {skill}" for skill in skills] + ["---", "", body]
    return "\n".join(rendered).rstrip("\n") + "\n"


def copy_skill(skill_dir, target_dir):
    """Copy one skill text-only, skipping binaries and scripts/."""
    skipped = []
    copied = 0
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(skill_dir)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            skipped.append(str(relative))
            continue
        if path.suffix.lower() not in TEXT_EXT:
            skipped.append(str(relative))
            continue
        destination = target_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        copied += 1
    return copied, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="report without writing")
    args = parser.parse_args()

    if not SKILLS_SRC.is_dir():
        raise SystemExit(f"skills directory not found: {SKILLS_SRC}")
    if not SEED_DIR.is_dir():
        raise SystemExit(f"seed directory not found: {SEED_DIR}")

    available = sorted(d.name for d in SKILLS_SRC.iterdir() if d.is_dir())
    unknown = sorted({s for skills in AGENT_SKILLS.values() for s in skills} - set(available))
    if unknown:
        raise SystemExit("AGENT_SKILLS references unknown skills: " + ", ".join(unknown))
    unassigned = sorted(set(available) - {s for skills in AGENT_SKILLS.values() for s in skills})

    if args.check:
        print(f"skills available : {len(available)}")
        print(f"skills assigned  : {len(available) - len(unassigned)}")
        print(f"unassigned       : {', '.join(unassigned) or '(none)'}")
        return

    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)
    shutil.copytree(SEED_DIR, PACKAGE_DIR)

    for agent_slug, skills in AGENT_SKILLS.items():
        source = SEED_DIR / "agents" / agent_slug / "AGENTS.md"
        if not source.is_file():
            raise SystemExit(f"missing agent seed: {source}")
        target = PACKAGE_DIR / "agents" / agent_slug / "AGENTS.md"
        target.write_text(render_agent_markdown(source, skills), encoding="utf-8")

    total_files = 0
    for skill_name in available:
        copied, skipped = copy_skill(SKILLS_SRC / skill_name, PACKAGE_DIR / "skills" / skill_name)
        total_files += copied
        if skipped:
            print(
                f"  {skill_name}: skipped {len(skipped)} file(s) ({', '.join(skipped[:3])}"
                f"{'...' if len(skipped) > 3 else ''})",
                file=sys.stderr,
            )

    print(f"package written : {PACKAGE_DIR}")
    print(f"agents          : {len(AGENT_SKILLS)}")
    print(f"skills          : {len(available)} ({total_files} files)")
    if unassigned:
        print(f"note: {len(unassigned)} skill(s) not assigned to any agent: {', '.join(unassigned)}")


if __name__ == "__main__":
    main()
