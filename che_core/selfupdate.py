"""`che update` — bring this Che installation to the latest `main`, in one command.

WHY A COMMAND AT ALL
--------------------
`scripts/self-update-che.sh` already exists and works, and it was not enough. It defaults to a dry
run, so the ordinary path is two invocations with an `--apply` in between; it clones a second copy of
the repository through `gh` into `/tmp` only to run `git pull` on the checkout it already had; and —
the part that actually cost someone an afternoon — it has no Python counterpart to the `pnpm install`
it runs when `package.json` changes. A change to `pyproject.toml` was invisible to it.

That gap is not cosmetic. Che installs **editable**, so `import che_core` resolves into the
checkout: a pull makes every *code* change live on the spot, while a change to `dependencies` sits
in the file and does nothing until something reinstalls. This command treats `pyproject.toml` as the
trigger to reinstall, which is exactly what the shell scripts have always done for JavaScript.

WHAT "TRANSPARENT" MEANS HERE
-----------------------------
One command, no flags, no dry-run gate — and no surprises. Those two goals collide in precisely one
place, and how it is resolved is the whole design:

* **Fast-forward only.** ``git merge --ff-only`` cannot invent a merge commit and cannot rewrite a
  local one. When it cannot fast-forward, nothing is changed and the reason is printed.
* **A dirty working tree is a refusal, not a stash.** Stashing edits so an update fits is not
  transparency; it is a quiet change to work someone was not finished with. The things this command
  must never touch — ``user_rules/``, ``bindings/``, ``memory/`` — are gitignored, so they cannot
  even appear as dirty. Only a *tracked* file that was modified blocks the run.
* **A branch that is not the remote's default is a refusal.** "Get the latest from main" does not
  mean "move me off my branch".
* **Already current is success**, with nothing done — not an error, and not a reinstall.

Everything else is a refusal that names its remedy, so `--check` and the real run share one code
path and cannot disagree about what would happen.

HOST WIRING
-----------
A pull moves the *checkout*; it does not move the *installation*. The adapters wire Che into an IDE
by symlinking each command, skill and hook one at a time, so a command renamed upstream gains no
new link and keeps the old one, which now dangles. The user is left with a completion list that
offers a command resolving to nothing, and nothing telling them why.

So a real run re-links every adapter already wired to this checkout — including when the checkout
was already current. Converging the host is a different question from downloading commits, and only
one of the two is answered by `git merge`. Adapters that were never installed are left alone: Che
does not wire itself into a host the user never asked it to touch.

NOT IN SCOPE
------------
A checkout that is not a git repo (a zip install) is refused rather than half-handled: that path
needs a fetch of the official source, and ``scripts/self-update-che.sh`` already owns it. Two
implementations of one merge would be two chances to disagree.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from che_core.paths import resolve_che_home
from che_core.project_layout import hermetic_git_env

#: Exit codes. Branch on these, not on the text — the messages are for humans and may be reworded.
UPDATE_OK = 0
#: Not a Che checkout, not a git checkout, or unusable arguments.
UPDATE_USAGE = 2
#: The working tree was not in a state this command will move. Nothing was changed.
UPDATE_REFUSED = 3
#: The remote could not be reached. Nothing was changed.
UPDATE_FETCH_FAILED = 4
#: The code was updated but the CLI could not be reinstalled, so its dependencies may be stale.
UPDATE_REINSTALL_FAILED = 5

#: Network git operations are allowed to be slow; they are not allowed to hang forever.
_GIT_TIMEOUT_SECONDS = 300

#: How many incoming subjects to name. The count is always the true one.
_MAX_SUBJECTS = 20

DEFAULT_REMOTE = "origin"


class UpdateRefused(Exception):
    """A state this command will not move. Carries the exit code the CLI should use."""

    def __init__(self, reason: str, code: int = UPDATE_REFUSED):
        super().__init__(reason)
        self.reason = reason
        self.code = code


def _git(args: List[str], home: Path) -> Optional[subprocess.CompletedProcess]:
    """Run one git command against ``home`` hermetically; ``None`` when git cannot be launched.

    Hermetic because the answer must be about ``-C <home>`` and nothing else: an agent session
    runs with ``GIT_DIR`` and friends already exported, and honouring those would make this command
    answer about whichever repository happened to be ambient.
    """
    try:
        return subprocess.run(
            ["git", "-C", str(home), *args],
            capture_output=True,
            text=True,
            check=False,
            env=hermetic_git_env(),
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _probe(args: List[str], home: Path) -> Optional[str]:
    """Run a read-only git command; its trimmed stdout, or ``None`` on any failure."""
    result = _git(args, home)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _lines(args: List[str], home: Path) -> List[str]:
    """Line-oriented git output, where a leading space is data rather than padding.

    This deliberately does **not** go through `_probe`. `git status --porcelain` opens every record
    with two status columns, so a modified-but-unstaged file reads `` M path``; trimming the whole
    stdout — correct for a single scalar like a SHA — would eat that first column and silently
    shorten the path it is supposed to report.
    """
    result = _git(args, home)
    if result is None or result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def _is_che_checkout(home: Path) -> bool:
    return (home / "CHE_RULES.md").is_file() and (home / "skills").is_dir()


def find_checkout(che_home: Optional[str] = None) -> Path:
    """The Che checkout to update: the caller's explicit path, or the canonical cascade.

    ``$CHE_HOME`` → ``$HARNESS_HOME`` → ``~/.che-ai`` → ``~/.trae``, the same resolution
    ``che eject`` uses, because a second answer to "where is Che installed" is a second bug.
    """
    if che_home:
        candidate = Path(che_home).expanduser().resolve()
        if not _is_che_checkout(candidate):
            raise UpdateRefused(f"{candidate} is not a Che checkout (no CHE_RULES.md, or no skills/).", UPDATE_USAGE)
        return candidate

    candidate = resolve_che_home()
    if not _is_che_checkout(candidate):
        raise UpdateRefused(
            f"{candidate} is not a Che checkout (no CHE_RULES.md, or no skills/). "
            "Pass --che-home if yours lives elsewhere.",
            UPDATE_USAGE,
        )
    return candidate


def _default_branch(home: Path, remote: str) -> str:
    """The remote's default branch, which is what "the latest on main" means concretely.

    ``refs/remotes/<remote>/HEAD`` is the authoritative answer and costs nothing, but it is only
    set by a clone or an explicit ``git remote set-head``, so it is backed by a probe for the two
    names the project has ever used. Nothing here asks the network.
    """
    symbolic = _probe(["symbolic-ref", "--short", f"refs/remotes/{remote}/HEAD"], home)
    if symbolic and symbolic.startswith(f"{remote}/"):
        return symbolic[len(remote) + 1 :]

    for candidate in ("main", "master"):
        if _probe(["rev-parse", "--verify", "--quiet", f"refs/remotes/{remote}/{candidate}"], home):
            return candidate

    raise UpdateRefused(
        f"cannot tell which branch is the default on '{remote}' "
        f"(no refs/remotes/{remote}/HEAD, no {remote}/main, no {remote}/master).",
        UPDATE_USAGE,
    )


def _refuse_unsafe_state(home: Path, branch: str, default: str) -> None:
    """The two ways a working tree can be wrong for a fast-forward. Both fail closed."""
    modified = _lines(["status", "--porcelain", "--untracked-files=no"], home)
    if modified:
        #: Porcelain is fixed-width: two status columns, a space, then the path. Slicing keeps a
        #: path with spaces intact where `split()[-1]` would not.
        listed = ", ".join(sorted(line[3:].strip() for line in modified)[:_MAX_SUBJECTS])
        raise UpdateRefused(
            f"{len(modified)} tracked file(s) have uncommitted changes ({listed}). "
            "Commit them, or `git stash push -m 'wip before che update'` them, then run again. "
            "Nothing was changed.",
        )

    if branch != default:
        raise UpdateRefused(
            f"this checkout is on '{branch}', not on the default branch '{default}'. "
            f"Switch with `git -C {home} switch {default}` and run again. Nothing was changed.",
        )


def inspect(che_home: Optional[str] = None, remote: str = DEFAULT_REMOTE) -> Dict[str, Any]:
    """Fetch, then decide what an update would do — **without writing to the working tree**.

    Fetching does write inside ``.git`` (that is how it learns), which is why this is not called
    "check": it is the shared first half of both ``--check`` and the real run, so the two can never
    report different futures for the same repository.
    """
    home = find_checkout(che_home)

    if not _probe(["rev-parse", "--git-dir"], home):
        raise UpdateRefused(
            f"{home} is not a git checkout, so there is nothing to fast-forward. "
            "Zip installs are updated by `scripts/self-update-che.sh`.",
            UPDATE_USAGE,
        )

    branch = _probe(["rev-parse", "--abbrev-ref", "HEAD"], home)
    if branch in (None, "HEAD"):
        raise UpdateRefused(f"{home} is on a detached HEAD. Switch to a branch and run again.", UPDATE_REFUSED)

    default = _default_branch(home, remote)
    _refuse_unsafe_state(home, branch, default)

    fetched = _git(["fetch", remote], home)
    if fetched is None or fetched.returncode != 0:
        detail = (fetched.stderr.strip().splitlines() or ["git fetch failed"])[-1] if fetched else "git fetch failed"
        raise UpdateRefused(f"cannot reach '{remote}': {detail}", UPDATE_FETCH_FAILED)

    upstream = f"{remote}/{default}"
    if not _probe(["rev-parse", "--verify", "--quiet", f"refs/remotes/{upstream}"], home):
        raise UpdateRefused(f"'{remote}' has no '{default}' branch to update from.", UPDATE_USAGE)

    head = _probe(["rev-parse", "HEAD"], home) or ""
    target = _probe(["rev-parse", upstream], home) or ""
    behind = int(_probe(["rev-list", "--count", f"HEAD..{upstream}"], home) or "0")
    ahead = int(_probe(["rev-list", "--count", f"{upstream}..HEAD"], home) or "0")

    if ahead:
        raise UpdateRefused(
            f"this checkout has {ahead} commit(s) '{upstream}' does not, so a fast-forward would "
            "discard them. A fast-forward is the only update this command performs; rebase or "
            "push them first. Nothing was changed.",
        )

    subjects = _lines(["log", "--format=%h %s", f"HEAD..{upstream}"], home)
    touched = _lines(["diff", "--name-only", f"HEAD..{upstream}"], home)

    return {
        "che_home": str(home),
        "branch": branch,
        "remote": remote,
        "upstream": upstream,
        "default_branch": default,
        "head": head,
        "target": target,
        "head_short": head[:7],
        "target_short": target[:7],
        "behind": behind,
        "ahead": ahead,
        "commits": subjects[:_MAX_SUBJECTS],
        "commits_omitted": max(0, len(subjects) - _MAX_SUBJECTS),
        "files": touched,
        #: The trigger for the reinstall below. `pyproject.toml` is the only file whose change can
        #: leave the installed CLI out of step with the code, because it is the only one that
        #: declares what the CLI must import.
        "declares_dependencies": "pyproject.toml" in touched,
        "up_to_date": behind == 0,
    }


def reinstall_cli(
    che_home: Path, runner: Callable[..., subprocess.CompletedProcess] = subprocess.run
) -> Dict[str, Any]:
    """Reinstall the CLI in place so a changed ``pyproject.toml`` actually takes effect.

    pipx first, because that is how the README installs Che and how `che` found itself on PATH. The
    ``pip --user`` fallback mirrors ``scripts/install-che.sh``, including its ``--break-system-packages``
    retry: a PEP 668 environment refuses the first form and accepts the second, and discovering that
    during an update is not the moment to hand someone a second command to run.
    """
    attempts: List[List[str]] = []
    if shutil.which("pipx"):
        attempts.append(["pipx", "install", "-e", str(che_home), "--force"])
    attempts.append([sys.executable, "-m", "pip", "install", "--user", "-e", str(che_home)])
    attempts.append([sys.executable, "-m", "pip", "install", "--user", "-e", str(che_home), "--break-system-packages"])

    last_output = ""
    for command in attempts:
        try:
            result = runner(command, capture_output=True, text=True, check=False, timeout=_GIT_TIMEOUT_SECONDS)
        except (OSError, subprocess.SubprocessError) as exc:
            last_output = str(exc)
            continue
        last_output = (result.stdout + result.stderr).strip()
        if result.returncode == 0:
            return {"ok": True, "command": command, "output": last_output.splitlines()[-4:]}
    return {"ok": False, "command": attempts[0], "output": last_output.splitlines()[-8:]}


#: Where each adapter wires itself, and which environment variable overrides that home. The table
#: answers exactly one question — "is this adapter installed?" — so `che update` can refresh the
#: ones that exist and leave the rest alone. `cursor` is deliberately absent: its installer prints
#: instructions for the user to run rather than linking anything, so there is nothing to re-run.
_ADAPTERS: List[Dict[str, Any]] = [
    {
        "name": "trae",
        "home_env": "TRAE_HOME",
        "default_home": ".trae",
        "collections": ("commands", "skills", "hooks"),
    },
    {
        "name": "claude",
        "home_env": "CLAUDE_CONFIG_DIR",
        "default_home": ".claude",
        "collections": ("commands", "skills"),
    },
    {
        "name": "codex",
        "home_env": "CODEX_HOME",
        "default_home": ".codex",
        "collections": ("commands",),
    },
]

#: The marker the adapters forward from `scripts/prune-che-symlinks.sh`.
_PRUNE_MARKER = "CHE_PRUNE_REMOVED="


def _points_into(entry: Path, checkout: Path) -> bool:
    """Is this symlink one of Che's?

    Compares the link *text*, not what it resolves to, and that is the point: an installation whose
    Che links are all dangling is precisely the state that has to be repaired, so "still resolves"
    cannot be part of the question.
    """
    if not entry.is_symlink():
        return False
    try:
        link = os.readlink(entry)
    except OSError:
        return False
    candidate = Path(link) if os.path.isabs(link) else entry.parent / link
    candidate = Path(os.path.normpath(str(candidate)))
    root = Path(os.path.normpath(str(checkout)))
    return candidate == root or root in candidate.parents


def detect_installed_adapters(checkout: Path, environ: Optional[Dict[str, str]] = None) -> List[str]:
    """Names of the adapters already wired to this checkout.

    Evidence is a symlink into the checkout, never the mere existence of a home directory: a user
    who happens to have ``~/.claude`` because they use Claude Code has not thereby asked Che to
    install itself there.
    """
    env = os.environ if environ is None else environ
    home_root = Path(env.get("HOME") or str(Path.home()))
    found: List[str] = []
    for spec in _ADAPTERS:
        home = Path(env.get(spec["home_env"]) or home_root / spec["default_home"])
        if not home.is_dir():
            continue
        for collection in spec["collections"]:
            target = home / collection
            if not target.is_dir():
                continue
            try:
                entries = list(target.iterdir())
            except OSError:
                continue
            if any(_points_into(entry, checkout) for entry in entries):
                found.append(spec["name"])
                break
    return found


def _count_pruned(output: str) -> int:
    """Sum the markers the adapters forward from the pruner."""
    total = 0
    for line in output.splitlines():
        marker = line.strip()
        if marker.startswith(_PRUNE_MARKER):
            try:
                total += int(marker[len(_PRUNE_MARKER) :])
            except ValueError:
                continue
    return total


def relink_adapters(
    checkout: Path,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    environ: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Re-run the installer of every adapter already wired to this checkout.

    Re-running is what closes the gap a pull cannot: the new symlinks appear and the pruner drops
    the dangling ones. A failure here is reported, never raised — the code did update, and saying
    so is more useful than aborting because an IDE home was read-only.
    """
    names = detect_installed_adapters(checkout, environ)
    result: Dict[str, Any] = {"adapters": [], "orphans_removed": 0, "failed": []}
    for name in names:
        script = checkout / "adapters" / name / "install.sh"
        if not script.is_file():
            continue
        try:
            completed = runner(
                ["bash", str(script)],
                capture_output=True,
                text=True,
                check=False,
                timeout=_GIT_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            result["failed"].append({"adapter": name, "error": str(exc)})
            continue
        result["adapters"].append(name)
        result["orphans_removed"] += _count_pruned(completed.stdout or "")
        if completed.returncode != 0:
            result["failed"].append({"adapter": name, "returncode": completed.returncode})
    return result


def update(
    che_home: Optional[str] = None,
    remote: str = DEFAULT_REMOTE,
    check_only: bool = False,
    reinstaller: Optional[Callable[[Path], Dict[str, Any]]] = None,
    relinker: Optional[Callable[[Path], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Bring the checkout to the latest ``main``, then converge the host wiring.

    ``reinstaller`` and ``relinker`` are injectable so the tests can exercise the two *decisions* —
    reinstall the CLI, re-link the adapters — without running a package manager or an installer.
    The decisions are the contract; pipx and the adapter scripts are not things a test suite should
    be invoking.
    """
    state = inspect(che_home, remote=remote)
    state["updated"] = False
    state["reinstall"] = None
    state["relink"] = None

    if check_only:
        state["status"] = "up-to-date" if state["up_to_date"] else "would-update"
        return state

    home = Path(state["che_home"])

    if not state["up_to_date"]:
        merged = _git(["merge", "--ff-only", state["upstream"]], home)
        if merged is None or merged.returncode != 0:
            detail = (merged.stderr.strip().splitlines() or ["git merge failed"])[-1] if merged else "git merge failed"
            raise UpdateRefused(f"fast-forward failed and nothing was changed: {detail}")
        state["updated"] = True

    state["status"] = "updated" if state["updated"] else "up-to-date"

    # Converge the host on EVERY real run, not only when the checkout moved. A renamed command
    # leaves a dangling symlink behind and gains no new one, so an up-to-date checkout can still be
    # a broken installation — and the second run is exactly when the user expects that fixed.
    state["relink"] = (relinker or relink_adapters)(home)

    if not state["updated"] or not state["declares_dependencies"]:
        return state

    result = (reinstaller or reinstall_cli)(home)
    state["reinstall"] = result
    if not result.get("ok"):
        # The code moved; only the packages did not. That is a distinct, actionable outcome rather
        # than a failure of the update — hence its own exit code.
        state["status"] = "updated-without-reinstall"
    return state


def exit_code(state: Dict[str, Any]) -> int:
    if state["status"] == "updated-without-reinstall":
        return UPDATE_REINSTALL_FAILED
    return UPDATE_OK


def _relink_sentence(relink: Optional[Dict[str, Any]]) -> str:
    """Say what actually happened to the host wiring.

    This line used to read "skills, rules and hooks are symlinked into this checkout, so they are
    already live" — true of a file that already had a link, and false of every file a rename added,
    which is exactly how a user ends up with a command that never appears in completion.
    """
    if relink is None:
        return "Host wiring was not refreshed."
    names = relink.get("adapters") or []
    failed = relink.get("failed") or []
    if not names and not failed:
        return "No host adapter is wired to this checkout, so there was nothing to re-link."
    parts: List[str] = []
    if names:
        parts.append(f"Re-linked {len(names)} adapter(s) ({', '.join(names)})")
        parts.append(f"{relink.get('orphans_removed', 0)} stale symlink(s) removed")
    if failed:
        names_failed = ", ".join(str(item.get("adapter")) for item in failed)
        parts.append(f"{len(failed)} adapter(s) could not be re-linked ({names_failed})")
    return ", ".join(parts) + "."


def summarise(state: Dict[str, Any]) -> str:
    """The one-line human summary, per status. Same contract as the other gates' summaries."""
    if state["status"] == "would-update":
        return (
            f"{state['behind']} commit(s) available on {state['upstream']}: "
            f"{state['head_short']} -> {state['target_short']}."
        )

    if state["status"] == "up-to-date":
        lines = [f"Che is already at the latest {state['upstream']} ({state['head_short']})."]
    else:
        lines = [f"Che updated: {state['head_short']} -> {state['target_short']} ({state['behind']} commit(s))."]
        if state["reinstall"] is None:
            lines.append("No dependency change, so the installed CLI was left alone.")
        elif state["reinstall"].get("ok"):
            lines.append("Dependencies changed: the CLI was reinstalled in place.")
        else:
            lines.append(
                "Dependencies changed but the CLI could NOT be reinstalled — "
                f"run it yourself: {' '.join(state['reinstall']['command'])}"
            )
    lines.append(_relink_sentence(state.get("relink")))
    return " ".join(lines)
