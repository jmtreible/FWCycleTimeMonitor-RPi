"""Entry point that checks for updates before launching the application."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from . import gui
from .updater import relaunch_if_updated

LOGGER = logging.getLogger(__name__)


def _detect_repo_root() -> Path:
    """Return the nearest parent directory that looks like the project root."""

    module_path = Path(__file__).resolve()
    for candidate in module_path.parents:
        if (candidate / ".git").exists():
            return candidate

    # Fallback to the top-level package directory (two levels up from this file)
    try:
        return module_path.parents[1]
    except IndexError:  # pragma: no cover - only triggered in unusual layouts
        return module_path.parent


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    repo_env = os.environ.get("FW_CYCLE_MONITOR_REPO")
    if repo_env:
        repo_path = Path(repo_env).expanduser()
    else:
        repo_path = _detect_repo_root()

    LOGGER.info("Checking for updates in %s", repo_path)
    relaunch_code = relaunch_if_updated(repo_path, "fw_cycle_monitor")
    if relaunch_code is not None:
        LOGGER.info("Relaunch returned %s", relaunch_code)
        return relaunch_code

    LOGGER.info("Launching FW Cycle Time Monitor GUI")
    return gui.main()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
