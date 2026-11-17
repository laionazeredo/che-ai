"""Static guard for PowerShell 5.1 compatibility in the Windows installer scripts.

The Windows installer has to run on Windows PowerShell 5.1, which ships with every Windows 10/11
machine. Three defects reached users because nothing checked that: `$PSCmdlet` under `iex`,
`Invoke-RestMethod -OutFile` (PowerShell 6+), and `Join-Path` with three arguments (PowerShell 6+).

PSScriptAnalyzer's `PSUseCompatibleCmdlets` does **not** catch the `Join-Path` case — verified
against the broken revision, which it reports as clean — so the rule is enforced here instead. These
are deliberately narrow textual checks: they are cheap, deterministic, and need no PowerShell on the
runner. Anything subtler still needs a real Windows host.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PS_FILES = sorted(list((REPO_ROOT / "scripts").glob("*.ps1")) + list((REPO_ROOT / "adapters").glob("**/*.ps1")))

#: Constructs that exist only from PowerShell 6 onwards.
FORBIDDEN = {
    r"\?\?": "null-coalescing operator (PowerShell 7)",
    r"-AdditionalChildPath": "Join-Path multi-segment form (PowerShell 6)",
    r"\$IsWindows": "$IsWindows automatic variable (PowerShell 6)",
    r"Get-ChildItem[^\n]*\s-(File|Directory)\b": "Get-ChildItem -File/-Directory (PowerShell 3+ only on 7)",
}


def _argument_count(line: str, start: int) -> int:
    """Count the arguments of the call whose arguments begin at ``start``.

    Tracks quotes and parentheses so a nested call or a string with spaces counts as one argument,
    and stops at the closing parenthesis of the enclosing expression or a statement separator.
    """
    line = line.rstrip()
    if line.endswith("`"):
        line = line[:-1]

    count = 0
    depth = 0
    quote = ""
    in_token = False
    i = start

    while i < len(line):
        char = line[i]
        if quote:
            if char == quote:
                quote = ""
            i += 1
            continue
        if char in "'\"":
            quote = char
            if not in_token:
                count += 1
                in_token = True
            i += 1
            continue
        if char == "(":
            depth += 1
            if not in_token:
                count += 1
                in_token = True
            i += 1
            continue
        if char == ")":
            depth -= 1
            if depth < 0:
                break
            i += 1
            continue
        if char in " \t" and depth == 0:
            in_token = False
            i += 1
            continue
        if char in "};|" and depth == 0:
            break
        if not in_token:
            count += 1
            in_token = True
        i += 1

    return count


def test_the_scanner_counts_arguments_the_way_powershell_binds_them() -> None:
    cases = [
        ("Join-Path $Source 'scripts' 'render_hooks.py'", 3),
        ("Join-Path $Target $Relative", 2),
        ("Join-Path $TraeHome $pointer.Key `", 2),
        ("$counts[(Join-Path $TraeHome 'skills')]", 2),
        ("Join-Path ([System.IO.Path]::GetTempPath()) ('che-' + $x + '.json')", 2),
        ("Join-Path $env:USERPROFILE '.trae' })", 2),
    ]

    for line, expected in cases:
        start = line.index("Join-Path") + len("Join-Path")
        assert _argument_count(line, start) == expected, line


def test_join_path_never_takes_more_than_two_arguments() -> None:
    """`-ChildPath` is the only child parameter before PowerShell 6."""
    offenders = []
    for path in PS_FILES:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in re.finditer(r"Join-Path\b", line):
                if _argument_count(line, match.end()) > 2:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}: {line.strip()}")

    assert offenders == [], "Join-Path with 3+ arguments is PowerShell 6+ only:\n" + "\n".join(offenders)


@pytest.mark.parametrize("pattern,why", list(FORBIDDEN.items()))
def test_no_powershell_6_plus_constructs(pattern: str, why: str) -> None:
    offenders = []
    for path in PS_FILES:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if re.search(pattern, line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}: {line.strip()}")

    assert offenders == [], f"{why} is not available on PowerShell 5.1:\n" + "\n".join(offenders)
