import re
from pathlib import Path

import pytest

# The list of forbidden commands/patterns in bash code blocks inside markdown skills.
# The goal is to force the extraction of complex logic into the `che_core` Python package.
FORBIDDEN_BASH_PATTERNS = [
    r"\brm\s+-r",  # No recursive removal
    r"\bcurl\b",  # No external network calls in bash (do it in python)
    r"\bwget\b",  # No external network calls
    r"\beval\b",  # No dynamic evaluation
    r"\bexec\b",  # No process replacement
    r"\bkill\b",  # No process killing
    r">\s*/dev/null",  # Hiding output is usually a code smell for hidden logic
    r"\bawk\b",  # Text processing should be done in python
    r"\bsed\b",  # Text processing should be done in python
    r"\bfind\b",  # File traversal should be done in python
]

# Files to exclude from the security check while they are being refactored to Python
EXCLUDED_FILES = [
    "skills/che-ship/SKILL.md",
    "skills/che-decisions-query/SKILL.md",
    "skills/che-merge-resolver/SKILL.md",
    "skills/che-qa/SKILL.md",
    "skills/che-executor-dispatcher/SKILL.md",
    "skills/che-developer/SKILL.md",
    "skills/che-onboarding/SKILL.md",
    "skills/che-graph/SKILL.md",
    "skills/che-compliance/SKILL.md",
    "skills/che-social-ui-designer/SKILL.md",
]

# Patterns that we explicitly want to allow
ALLOWED_COMMANDS = [
    "python3 -m che_core",
    "git",
    "gh",
]


def extract_code_blocks(md_content: str, lang: str) -> list[str]:
    """Extract all code blocks of a specific language from a markdown string."""
    pattern = rf"```{lang}\n(.*?)\n```"
    # re.DOTALL makes '.' match newlines as well
    return re.findall(pattern, md_content, flags=re.DOTALL)


def test_no_forbidden_bash_commands():
    """Scan all SKILL.md files and ensure no forbidden bash commands exist in code blocks."""
    project_root = Path(__file__).parent.parent
    skills_dir = project_root / "skills"

    if not skills_dir.exists():
        pytest.skip("Skills directory not found")

    violations = []

    for skill_file in skills_dir.rglob("SKILL.md"):
        rel_path = str(skill_file.relative_to(project_root))
        if rel_path in EXCLUDED_FILES:
            continue

        content = skill_file.read_text(encoding="utf-8")
        bash_blocks = extract_code_blocks(content, "bash")

        for block in bash_blocks:
            lines = block.split("\n")
            for line_idx, line in enumerate(lines):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                for forbidden_pattern in FORBIDDEN_BASH_PATTERNS:
                    if re.search(forbidden_pattern, line):
                        # Allow exceptions for specific lines if they contain allowed commands
                        # and aren't obviously malicious
                        is_allowed = any(allowed in line for allowed in ALLOWED_COMMANDS)
                        # Specific exception for the ship preflight which uses sed in comments
                        is_comment_mention = (
                            line.startswith("ARTIFACT_CLEANUP_BACKUP_DIR") and "sed" in forbidden_pattern
                        )

                        if not (is_allowed or is_comment_mention):
                            violations.append(
                                f"File: {skill_file.relative_to(project_root)}\n"
                                f"Line {line_idx + 1} of bash block contains forbidden pattern '{forbidden_pattern}':\n"
                                f"> {line}"
                            )

    if violations:
        error_msg = "Security/Complexity violation in Markdown skills.\n"
        error_msg += "The following bash blocks contain forbidden commands. Complex logic must be extracted to the `che_core` Python package:\n\n"
        error_msg += "\n\n".join(violations)
        pytest.fail(error_msg)


def test_no_python_code_blocks_in_skills():
    """Ensure that we don't have raw Python code blocks in SKILL.md.
    Python code belongs in the che_core package, not inside markdown."""
    project_root = Path(__file__).parent.parent
    skills_dir = project_root / "skills"

    if not skills_dir.exists():
        pytest.skip("Skills directory not found")

    violations = []

    for skill_file in skills_dir.rglob("SKILL.md"):
        rel_path = str(skill_file.relative_to(project_root))
        if rel_path in EXCLUDED_FILES:
            continue

        content = skill_file.read_text(encoding="utf-8")
        python_blocks = extract_code_blocks(content, "python")

        # We allow small python blocks if they are explicitly marked as examples or snippets,
        # but warn if they get too large.
        for block in python_blocks:
            lines = block.strip().split("\n")
            if len(lines) > 15:  # More than 15 lines of python in a markdown file is a code smell
                violations.append(
                    f"File: {skill_file.relative_to(project_root)}\n"
                    f"Contains a Python block of {len(lines)} lines. Python logic > 15 lines MUST be extracted to `che_core`."
                )

    if violations:
        error_msg = "Complexity violation in Markdown skills.\n"
        error_msg += "\n".join(violations)
        pytest.fail(error_msg)
