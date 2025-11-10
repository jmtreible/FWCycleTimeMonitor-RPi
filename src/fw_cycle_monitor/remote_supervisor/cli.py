"""Command line client for the remote supervisor service."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import httpx

DEFAULT_BASE_URL = "https://localhost:8443"


@dataclass
class CLISettings:
    base_url: str
    api_key: Optional[str]
    verify: Union[bool, str, Path]
    timeout: float


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interact with the FW Cycle Monitor remote supervisor")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Supervisor base URL, e.g. https://pi01:8443")
    parser.add_argument("--api-key", default=None, help="API key to use when authentication is enabled")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    parser.add_argument("--ca-cert", default=None, help="Path to CA bundle for TLS verification")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS verification (not recommended)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Fetch the service status")
    subparsers.add_parser("start", help="Start the remote service")
    subparsers.add_parser("stop", help="Stop the remote service")
    subparsers.add_parser("restart", help="Restart the remote service")
    subparsers.add_parser("config", help="Show the current monitor configuration")
    subparsers.add_parser("metrics", help="Show recent cycle metrics")

    return parser


def parse_cli(argv: Optional[list[str]] = None) -> tuple[CLISettings, argparse.Namespace]:
    parser = build_parser()
    args = parser.parse_args(argv)

    verify: Union[bool, str, Path]
    if args.insecure:
        verify = False
    elif args.ca_cert:
        verify = Path(args.ca_cert)
    else:
        verify = True

    cli_settings = CLISettings(
        base_url=args.base_url.rstrip("/"),
        api_key=args.api_key,
        verify=verify,
        timeout=args.timeout,
    )
    return cli_settings, args


def _make_client(settings: CLISettings) -> httpx.Client:
    headers = {}
    if settings.api_key:
        headers["X-API-Key"] = settings.api_key
    verify: Union[bool, str] | Path
    if isinstance(settings.verify, Path):
        verify = str(settings.verify)
    else:
        verify = settings.verify
    return httpx.Client(base_url=settings.base_url, headers=headers, verify=verify, timeout=settings.timeout)


def _handle_response(response: httpx.Response) -> int:
    if response.status_code >= 400:
        sys.stderr.write(f"Error {response.status_code}: {response.text}\n")
        return 1
    try:
        payload = response.json()
    except ValueError:
        print(response.text)
        return 0
    print(json.dumps(payload, indent=2))
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    cli_settings, args = parse_cli(argv)
    with _make_client(cli_settings) as client:
        if args.command == "status":
            response = client.get("/service/status")
        elif args.command == "start":
            response = client.post("/service/start")
        elif args.command == "stop":
            response = client.post("/service/stop")
        elif args.command == "restart":
            response = client.post("/service/restart")
        elif args.command == "config":
            response = client.get("/config")
        elif args.command == "metrics":
            response = client.get("/metrics/summary")
        else:
            raise RuntimeError(f"Unknown command {args.command}")
    return _handle_response(response)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
