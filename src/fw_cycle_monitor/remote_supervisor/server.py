"""Entrypoint for hosting the remote supervisor API."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Optional

import uvicorn

from . import settings
from .api import app
from ..updater import determine_repo_path, sync_environment, update_repository

LOGGER = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the FW Cycle Monitor remote supervisor API server")
    parser.add_argument("--host", default=None, help="Interface to bind (overrides config file)")
    parser.add_argument("--port", type=int, default=None, help="Port to bind (overrides config file)")
    parser.add_argument("--certfile", type=Path, default=None, help="TLS certificate file")
    parser.add_argument("--keyfile", type=Path, default=None, help="TLS private key file")
    parser.add_argument("--ca-bundle", type=Path, default=None, help="Custom CA bundle for client cert validation")
    parser.add_argument("--reload-settings", action="store_true", help="Reload settings before starting")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    repo_path = determine_repo_path(Path(__file__).resolve().parents[3])
    extras = os.environ.get("FW_CYCLE_MONITOR_INSTALL_EXTRAS")
    LOGGER.info("Ensuring repository at %s is up to date", repo_path)
    if update_repository(repo_path):
        LOGGER.info("Repository updated; refreshing Python package")
        if not sync_environment(repo_path, extras):
            LOGGER.warning(
                "Failed to refresh installed package; the remote supervisor may run with stale dependencies"
            )

    if args.reload_settings:
        LOGGER.info("Reloading supervisor settings before launch")
        settings.refresh_settings()

    supervisor_settings = settings.get_settings()

    host = args.host or supervisor_settings.host
    port = args.port or supervisor_settings.port
    certfile = args.certfile or supervisor_settings.certfile
    keyfile = args.keyfile or supervisor_settings.keyfile

    LOGGER.info("Starting remote supervisor on %s:%s targeting unit %s", host, port, supervisor_settings.unit_name)

    uvicorn.run(
        app,
        host=str(host),
        port=int(port),
        ssl_certfile=str(certfile) if certfile else None,
        ssl_keyfile=str(keyfile) if keyfile else None,
        log_level="debug" if args.verbose else "info",
    )


if __name__ == "__main__":  # pragma: no cover
    main()
