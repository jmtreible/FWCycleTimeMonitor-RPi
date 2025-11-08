"""FW Cycle Time Monitor package."""

from importlib import metadata

try:
    __version__ = metadata.version("fw-cycle-monitor")
except metadata.PackageNotFoundError:  # pragma: no cover - during development
    __version__ = "0.0.0"

__all__ = ["__version__"]
