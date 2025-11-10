"""FastAPI application exposing remote supervisor endpoints."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, status

from ..config import load_config
from ..metrics import calculate_cycle_statistics
from .auth import require_api_key
from .models import ConfigSnapshot, MetricsResponse, ServiceActionResponse, ServiceStatusResponse
from .service_control import ServiceCommandError, restart_service, start_service, status_summary, stop_service
from .settings import get_settings

LOGGER = logging.getLogger(__name__)

app = FastAPI(title="FW Cycle Monitor Remote Supervisor", version="1.0.0")


@app.get("/service/status", response_model=ServiceStatusResponse)
async def get_status(_: str | None = Depends(require_api_key)) -> Dict[str, Any]:
    """Return the systemd unit status."""

    return status_summary()


@app.post("/service/start", response_model=ServiceActionResponse)
async def start(_: str | None = Depends(require_api_key)) -> Dict[str, Any]:
    """Start the monitor service."""

    try:
        summary = status_summary()
        if summary.get("active_state") == "active":
            LOGGER.info("Service already active; returning status without change")
            return {"action": "start", **summary}
        start_service()
        return {"action": "start", **status_summary()}
    except ServiceCommandError as exc:
        LOGGER.error("Failed to start service: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start service: {exc}",
        ) from exc


@app.post("/service/stop", response_model=ServiceActionResponse)
async def stop(_: str | None = Depends(require_api_key)) -> Dict[str, Any]:
    """Stop the monitor service."""

    try:
        stop_service()
        return {"action": "stop", **status_summary()}
    except ServiceCommandError as exc:
        LOGGER.error("Failed to stop service: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop service: {exc}",
        ) from exc


@app.post("/service/restart", response_model=ServiceActionResponse)
async def restart(_: str | None = Depends(require_api_key)) -> Dict[str, Any]:
    """Restart the monitor service."""

    try:
        restart_service()
        return {"action": "restart", **status_summary()}
    except ServiceCommandError as exc:
        LOGGER.error("Failed to restart service: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart service: {exc}",
        ) from exc


@app.get("/config", response_model=ConfigSnapshot)
async def config(_: str | None = Depends(require_api_key)) -> Dict[str, Any]:
    """Return the currently active monitor configuration."""

    config = load_config()
    return {
        "machine_id": config.machine_id,
        "gpio_pin": config.gpio_pin,
        "csv_path": str(config.csv_path()),
        "reset_hour": config.reset_hour,
    }


@app.get("/metrics/summary", response_model=MetricsResponse)
async def metrics(_: str | None = Depends(require_api_key)) -> Dict[str, Any]:
    """Return live cycle statistics for dashboards."""

    settings = get_settings()
    if not settings.metrics_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metrics collection disabled",
        )

    config = load_config()
    statistics = calculate_cycle_statistics(config.machine_id)
    return {
        "machine_id": config.machine_id,
        "last_cycle_seconds": statistics.last_cycle_seconds,
        "window_averages": statistics.window_averages,
    }
