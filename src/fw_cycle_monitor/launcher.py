"""Entry point that checks for updates before launching the application."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from . import gui
from .updater import relaunch_if_updated

LOGGER = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    repo_env = os.environ.get("FW_CYCLE_MONITOR_REPO")
    if repo_env:
        repo_path = Path(repo_env).expanduser()
    else:
        repo_path = Path(__file__).resolve().parent.parent

    LOGGER.info("Checking for updates in %s", repo_path)
    relaunch_code = relaunch_if_updated(repo_path, "fw_cycle_monitor")
    if relaunch_code is not None:
        LOGGER.info("Relaunch returned %s", relaunch_code)
        return relaunch_code

    LOGGER.info("Launching FW Cycle Time Monitor GUI")
    gui.main()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
