"""Utilities to keep the local checkout in sync with the upstream repository."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

LOGGER = logging.getLogger(__name__)


def _run_git_command(args: list[str], repo_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "LC_ALL": "C"},
    )


def determine_repo_path(default: Optional[Path] = None) -> Path:
    """Return the path to the project repository.

    Prefers the ``FW_CYCLE_MONITOR_REPO`` environment variable when set and
    otherwise falls back to the provided default or the package directory.
    """

    repo_env = os.environ.get("FW_CYCLE_MONITOR_REPO")
    if repo_env:
        try:
            return Path(repo_env).expanduser()
        except (OSError, RuntimeError):
            LOGGER.warning("Invalid FW_CYCLE_MONITOR_REPO value: %s", repo_env, exc_info=True)

    if default is not None:
        return default

    # ``fw_cycle_monitor`` lives in ``src/fw_cycle_monitor`` so two parents up
    # yields the repository root when running from an installed checkout.
    return Path(__file__).resolve().parents[2]


def update_repository(repo_path: Path, remote: str = "origin", branch: str = "main") -> bool:
    """Fetch updates from the remote and fast-forward if needed.

    Returns ``True`` when a new revision was pulled.
    """

    git_dir = repo_path / ".git"
    if not git_dir.exists():
        LOGGER.info("%s is not a git repository; skipping update", repo_path)
        return False

    try:
        remotes = _run_git_command(["remote"], repo_path).stdout.splitlines()
    except subprocess.CalledProcessError as exc:
        LOGGER.warning("Git command failed: %s", exc)
        return False

    if remote not in remotes:
        LOGGER.info("Remote '%s' is not configured; skipping update", remote)
        return False

    try:
        _run_git_command(["fetch", remote], repo_path)
        local_rev = _run_git_command(["rev-parse", "HEAD"], repo_path).stdout.strip()
        remote_rev = _run_git_command(["rev-parse", f"{remote}/{branch}"], repo_path).stdout.strip()
    except subprocess.CalledProcessError as exc:
        LOGGER.warning("Git command failed: %s", exc)
        return False

    if local_rev == remote_rev:
        LOGGER.info("Repository already up to date")
        return False

    LOGGER.info("Updating repository to %s", remote_rev)
    try:
        _run_git_command(["pull", "--ff-only", remote, branch], repo_path)
        return True
    except subprocess.CalledProcessError:
        LOGGER.exception("Failed to fast-forward repository")
        return False


def relaunch_if_updated(repo_path: Path, module: str) -> Optional[int]:
    """Update the repository and relaunch the provided module when changed.

    Returns the exit code of the relaunched process when a restart occurred.
    """

    if update_repository(repo_path):
        LOGGER.info("Repository updated; relaunching %s", module)
        import sys

        args = [sys.executable, "-m", module]
        try:
            completed = subprocess.run(args, cwd=repo_path)
            return completed.returncode
        except OSError as exc:
            LOGGER.exception("Failed to relaunch %s: %s", module, exc)
            return 1
    return None


def sync_environment(repo_path: Path, extras: Optional[str] = None) -> bool:
    """Reinstall the project into the active interpreter.

    When the repository updates we need to refresh the site-packages copy of
    the project so new modules and dependency pins are available.  This helper
    issues a ``pip install --upgrade`` against the local checkout.
    """

    extras = (extras or "").strip()
    if extras:
        target = f"{repo_path}[{extras}]"
    else:
        target = str(repo_path)

    LOGGER.info("Synchronising virtual environment from %s", target)
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", target],
            check=True,
        )
    except subprocess.CalledProcessError:
        LOGGER.exception("Failed to update Python package from %s", target)
        return False

    return True
