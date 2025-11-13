"""FastAPI application exposing remote supervisor endpoints."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, status

from ..config import load_config
from ..metrics import calculate_cycle_statistics
from .auth import require_api_key
from .models import (
    ConfigSnapshot,
    MetricsResponse,
    ServiceActionResponse,
    ServiceStatusResponse,
    StackLightResponse,
    StackLightSetRequest,
    StackLightState,
    SystemActionResponse,
)
from .service_control import ServiceCommandError, restart_service, start_service, status_summary, stop_service
from .settings import get_settings, refresh_settings
from .stacklight_controller import StackLightController

LOGGER = logging.getLogger(__name__)

app = FastAPI(title="FW Cycle Monitor Remote Supervisor", version="1.0.0")

# Global stack light controller instance
_stacklight_controller: Optional[StackLightController] = None


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


@app.post("/system/reboot", response_model=SystemActionResponse)
async def reboot_system(_: str | None = Depends(require_api_key)) -> Dict[str, Any]:
    """Reboot the Raspberry Pi system."""
    import subprocess

    try:
        LOGGER.warning("System reboot requested via API")
        # Initiate immediate reboot
        subprocess.Popen(["sudo", "shutdown", "-r", "now"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        return {
            "action": "reboot",
            "success": True,
            "message": "System reboot initiated - Pi will restart immediately"
        }
    except Exception as exc:
        LOGGER.error("Failed to initiate system reboot: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate system reboot: {exc}",
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


def _get_stacklight_controller() -> StackLightController:
    """Get or initialize the stack light controller."""
    global _stacklight_controller

    settings = get_settings()

    if not settings.stacklight.enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stack light control is disabled in configuration",
        )

    if _stacklight_controller is None:
        pins = {
            "green": settings.stacklight.green_pin,
            "amber": settings.stacklight.amber_pin,
            "red": settings.stacklight.red_pin,
        }
        _stacklight_controller = StackLightController(
            pins=pins,
            mock_mode=settings.stacklight.mock_mode,
            active_low=settings.stacklight.active_low
        )
        LOGGER.info("Stack light controller initialized")

    return _stacklight_controller


@app.post("/stacklight/set", response_model=StackLightResponse)
async def set_stacklight(
    request: StackLightSetRequest,
    _: str | None = Depends(require_api_key)
) -> Dict[str, Any]:
    """Set the state of stack lights."""

    try:
        controller = _get_stacklight_controller()
        result = controller.set_light_state(
            green=request.green,
            amber=request.amber,
            red=request.red
        )

        if result["success"]:
            return {
                "success": True,
                "state": result["state"],
                "timestamp": result["timestamp"]
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "state": result.get("state")
            }
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Failed to set stack light state: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set stack light state: {e}",
        ) from e


@app.get("/stacklight/status", response_model=StackLightState)
async def get_stacklight_status(_: str | None = Depends(require_api_key)) -> Dict[str, Any]:
    """Get the current state of stack lights."""

    try:
        controller = _get_stacklight_controller()
        return controller.get_light_state()
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Failed to get stack light status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stack light status: {e}",
        ) from e


@app.post("/stacklight/test", response_model=StackLightResponse)
async def test_stacklight(_: str | None = Depends(require_api_key)) -> Dict[str, Any]:
    """Run a test sequence on all stack lights."""

    try:
        controller = _get_stacklight_controller()
        result = controller.test_sequence()
        return result
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Failed to run stack light test: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run stack light test: {e}",
        ) from e


@app.post("/stacklight/off", response_model=StackLightResponse)
async def turn_off_stacklight(_: str | None = Depends(require_api_key)) -> Dict[str, Any]:
    """Turn off all stack lights."""

    try:
        controller = _get_stacklight_controller()
        result = controller.turn_off_all()

        if result["success"]:
            return {
                "success": True,
                "state": result["state"],
                "timestamp": result["timestamp"]
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "state": result.get("state")
            }
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Failed to turn off stack lights: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to turn off stack lights: {e}",
        ) from e


@app.on_event("startup")
async def startup_event():
    """Refresh settings cache and run startup self-test on startup."""
    LOGGER.info("Refreshing settings cache on startup")
    refresh_settings()

    # Run startup self-test if stack lights are enabled
    settings = get_settings()
    if settings.stacklight.enabled and settings.stacklight.startup_self_test:
        try:
            LOGGER.info("Initializing stack light controller for startup self-test")
            controller = _get_stacklight_controller()
            result = controller.startup_self_test()

            if result["success"]:
                LOGGER.info(f"Stack light startup self-test completed: {result.get('message')}")
            else:
                LOGGER.warning(f"Stack light startup self-test failed: {result.get('error')}")
        except Exception as e:
            LOGGER.error(f"Failed to run stack light startup self-test: {e}", exc_info=True)


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    global _stacklight_controller

    if _stacklight_controller is not None:
        LOGGER.info("Cleaning up stack light controller on shutdown")
        _stacklight_controller.cleanup()
        _stacklight_controller = None
