"""Tkinter GUI for configuring and running the cycle time monitor."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tkinter as tk
import urllib.request
import urllib.error
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional, Dict, Any

from .config import AppConfig, load_config, save_config
from .gpio_monitor import CycleMonitor
from .metrics import AVERAGE_WINDOWS, calculate_cycle_statistics
from .state import load_cycle_state
from .remote_supervisor.settings import get_settings, refresh_settings

LOGGER = logging.getLogger(__name__)


SERVICE_NAME = "fw-cycle-monitor.service"


class Application(tk.Tk):
    """Main GUI application."""

    def __init__(self) -> None:
        super().__init__()
        self.title("FW Cycle Time Monitor")
        self.resizable(False, False)

        self._config = load_config()
        self._status_job: Optional[str] = None
        self._api_base_url: Optional[str] = None
        self._api_key: Optional[str] = None

        self._machine_var = tk.StringVar(value=self._config.machine_id)
        self._pin_var = tk.StringVar(value=str(self._config.gpio_pin))
        self._directory_var = tk.StringVar(value=str(self._config.csv_directory))
        self._reset_hour_var = tk.StringVar(value=str(self._config.reset_hour))
        self._status_var = tk.StringVar(value="Checking…")
        self._last_event_var = tk.StringVar(value="—")
        self._events_logged_var = tk.StringVar(value="0")
        self._last_cycle_time_var = tk.StringVar(value="—")
        self._cycle_average_vars = {minutes: tk.StringVar(value="—") for minutes in AVERAGE_WINDOWS}

        # Stack light status variables
        self._stacklight_status_var = tk.StringVar(value="Not initialized")
        self._stacklight_green_var = tk.BooleanVar(value=False)
        self._stacklight_amber_var = tk.BooleanVar(value=False)
        self._stacklight_red_var = tk.BooleanVar(value=False)

        self._build_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_service_status()
        self._schedule_status_refresh()
        self._initialize_stacklight_api()

    # UI Construction -------------------------------------------------
    def _build_widgets(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text="Machine ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self._machine_var, width=20).grid(row=0, column=1, sticky="ew")

        ttk.Label(frame, text="GPIO Pin (BCM)").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=self._pin_var, width=20).grid(row=1, column=1, sticky="ew", pady=(8, 0))

        ttk.Label(frame, text="CSV Directory").grid(row=2, column=0, sticky="w", pady=(8, 0))
        directory_entry = ttk.Entry(frame, textvariable=self._directory_var, width=30)
        directory_entry.grid(row=2, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(frame, text="Browse…", command=self._select_directory).grid(row=2, column=2, padx=(8, 0), pady=(8, 0))

        ttk.Label(frame, text="Reset Hour (0–23)").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=self._reset_hour_var, width=20).grid(row=3, column=1, sticky="ew", pady=(8, 0))

        frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=(16, 0), sticky="ew")
        ttk.Button(button_frame, text="Apply", command=self._apply_config).grid(row=0, column=0, padx=(0, 8))
        self._start_button = ttk.Button(
            button_frame, text="Start Service", command=self._start_monitor, state=tk.DISABLED
        )
        self._start_button.grid(row=0, column=1, padx=(0, 8))
        self._stop_button = ttk.Button(
            button_frame, text="Stop Service", command=self._stop_monitor, state=tk.DISABLED
        )
        self._stop_button.grid(row=0, column=2, padx=(0, 8))
        ttk.Button(button_frame, text="Log Test Event", command=self._log_test_event).grid(row=0, column=3)

        status_frame = ttk.LabelFrame(frame, text="Status", padding=12)
        status_frame.grid(row=5, column=0, columnspan=3, pady=(16, 0), sticky="ew")

        ttk.Label(status_frame, text="State:").grid(row=0, column=0, sticky="w")
        ttk.Label(status_frame, textvariable=self._status_var).grid(row=0, column=1, sticky="w")

        ttk.Label(status_frame, text="Last Event:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(status_frame, textvariable=self._last_event_var).grid(row=1, column=1, sticky="w", pady=(8, 0))

        ttk.Label(status_frame, text="Events Logged:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Label(status_frame, textvariable=self._events_logged_var).grid(row=2, column=1, sticky="w", pady=(8, 0))

        ttk.Label(status_frame, text="Last Cycle Time:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Label(status_frame, textvariable=self._last_cycle_time_var).grid(
            row=3, column=1, sticky="w", pady=(8, 0)
        )

        for index, minutes in enumerate(AVERAGE_WINDOWS, start=4):
            ttk.Label(status_frame, text=f"Average ({minutes} min):").grid(
                row=index, column=0, sticky="w", pady=(8, 0)
            )
            ttk.Label(status_frame, textvariable=self._cycle_average_vars[minutes]).grid(
                row=index, column=1, sticky="w", pady=(8, 0)
            )

        # Stack Light Control Section
        stacklight_frame = ttk.LabelFrame(frame, text="Stack Light Control", padding=12)
        stacklight_frame.grid(row=6, column=0, columnspan=3, pady=(16, 0), sticky="ew")

        # Status row
        ttk.Label(stacklight_frame, text="Status:").grid(row=0, column=0, sticky="w")
        ttk.Label(stacklight_frame, textvariable=self._stacklight_status_var, foreground="#555555").grid(
            row=0, column=1, columnspan=3, sticky="w"
        )

        # Individual light controls
        ttk.Label(stacklight_frame, text="Lights:").grid(row=1, column=0, sticky="w", pady=(8, 0))

        self._green_check = ttk.Checkbutton(
            stacklight_frame, text="Green", variable=self._stacklight_green_var,
            command=lambda: self._set_stacklight_from_ui()
        )
        self._green_check.grid(row=1, column=1, sticky="w", pady=(8, 0))

        self._amber_check = ttk.Checkbutton(
            stacklight_frame, text="Amber", variable=self._stacklight_amber_var,
            command=lambda: self._set_stacklight_from_ui()
        )
        self._amber_check.grid(row=1, column=2, sticky="w", pady=(8, 0))

        self._red_check = ttk.Checkbutton(
            stacklight_frame, text="Red", variable=self._stacklight_red_var,
            command=lambda: self._set_stacklight_from_ui()
        )
        self._red_check.grid(row=1, column=3, sticky="w", pady=(8, 0))

        # Quick action buttons
        stacklight_button_frame = ttk.Frame(stacklight_frame)
        stacklight_button_frame.grid(row=2, column=0, columnspan=4, pady=(12, 0), sticky="ew")

        ttk.Button(stacklight_button_frame, text="Test Sequence", command=self._test_stacklight).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(stacklight_button_frame, text="All Off", command=self._turn_off_all_stacklights).grid(
            row=0, column=1, padx=(0, 8)
        )
        ttk.Button(stacklight_button_frame, text="Green Only", command=lambda: self._quick_set(True, False, False)).grid(
            row=0, column=2, padx=(0, 8)
        )
        ttk.Button(stacklight_button_frame, text="Amber Only", command=lambda: self._quick_set(False, True, False)).grid(
            row=0, column=3, padx=(0, 8)
        )
        ttk.Button(stacklight_button_frame, text="Red Only", command=lambda: self._quick_set(False, False, True)).grid(
            row=0, column=4, padx=(0, 8)
        )

        # Config reload and service restart buttons
        stacklight_reload_frame = ttk.Frame(stacklight_frame)
        stacklight_reload_frame.grid(row=3, column=0, columnspan=4, pady=(8, 0), sticky="ew")

        ttk.Button(stacklight_reload_frame, text="Reload Config", command=self._reload_stacklight_config).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(stacklight_reload_frame, text="Restart Remote Supervisor", command=self._restart_remote_supervisor).grid(
            row=0, column=1, padx=(0, 8)
        )
        ttk.Label(stacklight_reload_frame, text="(Reload GUI config or restart API service)", foreground="#777777", font=("TkDefaultFont", 8)).grid(
            row=0, column=2, padx=(8, 0), sticky="w"
        )

        version = self._resolve_version()
        ttk.Label(frame, text=f"Version: {version}", foreground="#555555").grid(
            row=7, column=0, columnspan=3, sticky="w", pady=(16, 0)
        )

    # Actions ---------------------------------------------------------
    def _select_directory(self) -> None:
        selected = filedialog.askdirectory(title="Select CSV Directory", initialdir=self._directory_var.get())
        if selected:
            self._directory_var.set(selected)

    def _start_monitor(self) -> None:
        try:
            config = self._read_config_from_ui()
        except ValueError as exc:
            messagebox.showerror("Invalid configuration", str(exc), parent=self)
            return

        save_config(config)
        self._config = config
        if not self._control_service("start"):
            return

        self._status_var.set("Starting…")
        self._start_button.configure(state=tk.DISABLED)
        self._stop_button.configure(state=tk.DISABLED)
        self._refresh_cycle_stats()
        self._schedule_status_refresh(delay=1000)

    def _stop_monitor(self) -> None:
        if not self._control_service("stop"):
            return
        self._status_var.set("Stopping…")
        self._start_button.configure(state=tk.DISABLED)
        self._stop_button.configure(state=tk.DISABLED)
        self._schedule_status_refresh(delay=1000)

    def _log_test_event(self) -> None:
        try:
            config = self._read_config_from_ui()
        except ValueError as exc:
            messagebox.showerror("Invalid configuration", str(exc), parent=self)
            return

        save_config(config)
        self._config = config

        monitor = CycleMonitor(config)
        try:
            timestamp = monitor.simulate_event()
        except Exception as exc:  # pragma: no cover - unexpected disk errors
            LOGGER.exception("Failed to log test event")
            messagebox.showerror("Error", f"Failed to log test event: {exc}", parent=self)
            return

        self._last_event_var.set(timestamp.isoformat())
        self._refresh_cycle_stats()

    def _apply_config(self) -> None:
        try:
            config = self._read_config_from_ui()
        except ValueError as exc:
            messagebox.showerror("Invalid configuration", str(exc), parent=self)
            return

        save_config(config)
        self._config = config
        self._machine_var.set(config.machine_id)
        self._directory_var.set(str(config.csv_directory))
        self._reset_hour_var.set(str(config.reset_hour))
        self._refresh_cycle_stats()

    def _control_service(self, action: str) -> bool:
        try:
            result = subprocess.run(
                ["systemctl", action, SERVICE_NAME],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError:
            messagebox.showerror(
                "Service control unavailable",
                "systemctl is not available on this system. The service cannot be managed from the GUI.",
                parent=self,
            )
            return False
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.exception("systemctl %s failed", action)
            messagebox.showerror("Error", f"Failed to control service: {exc}", parent=self)
            return False

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            LOGGER.error("systemctl %s %s failed: %s", action, SERVICE_NAME, error_msg)
            messagebox.showerror(
                "Service control failed",
                f"systemctl {action} {SERVICE_NAME} returned {result.returncode}:\n{error_msg}\n"
                "You may need administrative privileges to manage the service.",
                parent=self,
            )
            return False

        return True

    def _query_service_state(self) -> str:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", SERVICE_NAME],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError:
            return "unavailable"
        except Exception:  # pragma: no cover - defensive logging
            LOGGER.exception("Failed to query service state")
            return "unknown"

        state = result.stdout.strip()
        if result.returncode == 0:
            return state or "active"
        if state:
            return state
        if result.returncode == 3:
            return "inactive"
        return "unknown"

    def _refresh_service_status(self) -> None:
        state = self._query_service_state()
        if state == "active":
            self._status_var.set("Running")
            self._start_button.configure(state=tk.DISABLED)
            self._stop_button.configure(state=tk.NORMAL)
        elif state in {"activating", "reloading"}:
            self._status_var.set("Starting…")
            self._start_button.configure(state=tk.DISABLED)
            self._stop_button.configure(state=tk.DISABLED)
        elif state in {"inactive", "deactivating"}:
            self._status_var.set("Stopped")
            self._start_button.configure(state=tk.NORMAL)
            self._stop_button.configure(state=tk.DISABLED)
        elif state == "failed":
            self._status_var.set("Failed")
            self._start_button.configure(state=tk.NORMAL)
            self._stop_button.configure(state=tk.DISABLED)
        elif state == "unavailable":
            self._status_var.set("Service control unavailable")
            self._start_button.configure(state=tk.DISABLED)
            self._stop_button.configure(state=tk.DISABLED)
        else:
            self._status_var.set(state.capitalize() if state else "Unknown")
            self._start_button.configure(state=tk.NORMAL)
            self._stop_button.configure(state=tk.NORMAL)

        self._refresh_cycle_stats()

    def _schedule_status_refresh(self, delay: int = 5000) -> None:
        if self._status_job is not None:
            self.after_cancel(self._status_job)
        self._status_job = self.after(delay, self._periodic_refresh)

    def _periodic_refresh(self) -> None:
        self._status_job = None
        self._refresh_service_status()
        self._schedule_status_refresh()

    def _refresh_cycle_stats(self) -> None:
        machine_id = self._machine_var.get().strip().upper()
        if not machine_id:
            self._events_logged_var.set("0")
            self._last_event_var.set("—")
            self._last_cycle_time_var.set("—")
            for var in self._cycle_average_vars.values():
                var.set("—")
            return

        state = load_cycle_state(machine_id)
        if state:
            self._events_logged_var.set(str(state.last_cycle))
            self._last_event_var.set(state.last_timestamp.isoformat())
        else:
            self._events_logged_var.set("0")
            self._last_event_var.set("—")

        stats = calculate_cycle_statistics(machine_id)
        self._last_cycle_time_var.set(self._format_duration(stats.last_cycle_seconds))
        for minutes, var in self._cycle_average_vars.items():
            var.set(self._format_duration(stats.window_averages.get(minutes)))
    
    def _format_duration(self, seconds: Optional[float]) -> str:
        if seconds is None:
            return "—"
        total_seconds = int(round(seconds))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _read_config_from_ui(self) -> AppConfig:
        machine_id = self._machine_var.get().strip().upper()
        if not machine_id:
            raise ValueError("Machine ID is required")
        try:
            gpio_pin = int(self._pin_var.get())
        except ValueError as exc:
            raise ValueError("GPIO pin must be an integer") from exc
        csv_directory = Path(self._directory_var.get()).expanduser()
        if not csv_directory:
            raise ValueError("CSV directory is required")
        try:
            reset_hour = int(self._reset_hour_var.get())
        except ValueError as exc:
            raise ValueError("Reset hour must be an integer between 0 and 23") from exc
        if not 0 <= reset_hour <= 23:
            raise ValueError("Reset hour must be between 0 and 23")

        return AppConfig(
            machine_id=machine_id,
            gpio_pin=gpio_pin,
            csv_directory=csv_directory,
            reset_hour=reset_hour,
        )

    def _resolve_version(self) -> str:
        try:
            from . import __version__

            return __version__
        except Exception:  # pragma: no cover - metadata lookup
            return "development"

    def _initialize_stacklight_api(self) -> None:
        """Initialize connection to stack light API."""
        try:
            settings = get_settings()
            if not settings.stacklight.enabled:
                self._stacklight_status_var.set("Disabled in configuration")
                return

            # Get API configuration
            self._api_base_url = f"http://{settings.host}:{settings.port}"
            if settings.api_keys and len(settings.api_keys) > 0:
                self._api_key = settings.api_keys[0]
            else:
                self._stacklight_status_var.set("Error: No API key configured")
                LOGGER.error("No API key found in remote supervisor configuration")
                return

            mode = "MOCK MODE" if settings.stacklight.mock_mode else "Hardware Mode"
            self._stacklight_status_var.set(f"Ready (API mode - {mode})")
            self._refresh_stacklight_state()
            LOGGER.info(f"Stack light API initialized - connecting to {self._api_base_url}")

        except Exception as exc:
            LOGGER.error(f"Failed to initialize stack light API: {exc}", exc_info=True)
            self._stacklight_status_var.set(f"Error: {exc}")

    def _api_request(self, endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Make an HTTP request to the remote supervisor API."""
        if not self._api_base_url or not self._api_key:
            return None

        url = f"{self._api_base_url}{endpoint}"
        headers = {"X-API-Key": self._api_key}

        try:
            if method == "GET":
                req = urllib.request.Request(url, headers=headers)
            else:  # POST
                headers["Content-Type"] = "application/json"
                json_data = json.dumps(data).encode('utf-8') if data else None
                req = urllib.request.Request(url, data=json_data, headers=headers, method=method)

            with urllib.request.urlopen(req, timeout=10) as response:
                response_data = response.read().decode('utf-8')
                return json.loads(response_data) if response_data else {}

        except urllib.error.HTTPError as exc:
            LOGGER.error(f"HTTP {exc.code} error from API {endpoint}: {exc.reason}")
            return None
        except urllib.error.URLError as exc:
            LOGGER.error(f"URL error from API {endpoint}: {exc.reason}")
            return None
        except Exception as exc:
            LOGGER.error(f"Failed to make API request to {endpoint}: {exc}", exc_info=True)
            return None

    def _refresh_stacklight_state(self) -> None:
        """Refresh the UI to show current stack light state."""
        if not self._api_base_url or not self._api_key:
            return

        try:
            state = self._api_request("/stacklight/status")
            if state:
                self._stacklight_green_var.set(state.get("green", False))
                self._stacklight_amber_var.set(state.get("amber", False))
                self._stacklight_red_var.set(state.get("red", False))
        except Exception as exc:
            LOGGER.error(f"Failed to refresh stack light state: {exc}", exc_info=True)

    def _set_stacklight_from_ui(self) -> None:
        """Set stack light state from checkbox values."""
        if not self._api_base_url or not self._api_key:
            messagebox.showwarning("Stack Light", "API not initialized", parent=self)
            return

        try:
            green = self._stacklight_green_var.get()
            amber = self._stacklight_amber_var.get()
            red = self._stacklight_red_var.get()

            data = {"green": green, "amber": amber, "red": red}
            result = self._api_request("/stacklight/set", method="POST", data=data)

            if result and result.get("success"):
                self._refresh_stacklight_state()
            elif result:
                messagebox.showerror(
                    "Stack Light Error",
                    f"Failed to set lights: {result.get('error', 'Unknown error')}",
                    parent=self
                )
            else:
                messagebox.showerror(
                    "Connection Error",
                    "Failed to connect to remote supervisor API",
                    parent=self
                )
        except Exception as exc:
            LOGGER.error(f"Failed to set stack light: {exc}", exc_info=True)
            messagebox.showerror("Error", f"Failed to control stack lights: {exc}", parent=self)

    def _quick_set(self, green: bool, amber: bool, red: bool) -> None:
        """Quick set stack lights to specific pattern."""
        if not self._api_base_url or not self._api_key:
            messagebox.showwarning("Stack Light", "API not initialized", parent=self)
            return

        try:
            data = {"green": green, "amber": amber, "red": red}
            result = self._api_request("/stacklight/set", method="POST", data=data)

            if result and result.get("success"):
                self._refresh_stacklight_state()
            elif result:
                messagebox.showerror(
                    "Stack Light Error",
                    f"Failed to set lights: {result.get('error', 'Unknown error')}",
                    parent=self
                )
            else:
                messagebox.showerror(
                    "Connection Error",
                    "Failed to connect to remote supervisor API",
                    parent=self
                )
        except Exception as exc:
            LOGGER.error(f"Failed to set stack light: {exc}", exc_info=True)
            messagebox.showerror("Error", f"Failed to control stack lights: {exc}", parent=self)

    def _test_stacklight(self) -> None:
        """Run test sequence on stack lights."""
        if not self._api_base_url or not self._api_key:
            messagebox.showwarning("Stack Light", "API not initialized", parent=self)
            return

        try:
            # Disable buttons during test
            self._stacklight_status_var.set("Running test sequence...")
            self.update()

            result = self._api_request("/stacklight/test", method="POST")

            if result and result.get("success"):
                self._stacklight_status_var.set(f"Test complete ({result.get('duration_seconds', 0)}s)")
                self._refresh_stacklight_state()
            elif result:
                self._stacklight_status_var.set("Test failed")
                messagebox.showerror(
                    "Stack Light Error",
                    f"Test sequence failed: {result.get('error', 'Unknown error')}",
                    parent=self
                )
            else:
                self._stacklight_status_var.set("Connection failed")
                messagebox.showerror(
                    "Connection Error",
                    "Failed to connect to remote supervisor API",
                    parent=self
                )
        except Exception as exc:
            LOGGER.error(f"Stack light test failed: {exc}", exc_info=True)
            messagebox.showerror("Error", f"Test sequence failed: {exc}", parent=self)
        finally:
            # Restore status
            settings = get_settings()
            mode = "MOCK MODE" if settings.stacklight.mock_mode else "Hardware Mode"
            self._stacklight_status_var.set(f"Ready (API mode - {mode})")

    def _turn_off_all_stacklights(self) -> None:
        """Turn off all stack lights."""
        if not self._api_base_url or not self._api_key:
            messagebox.showwarning("Stack Light", "API not initialized", parent=self)
            return

        try:
            result = self._api_request("/stacklight/off", method="POST")

            if result and result.get("success"):
                self._refresh_stacklight_state()
            elif result:
                messagebox.showerror(
                    "Stack Light Error",
                    f"Failed to turn off lights: {result.get('error', 'Unknown error')}",
                    parent=self
                )
            else:
                messagebox.showerror(
                    "Connection Error",
                    "Failed to connect to remote supervisor API",
                    parent=self
                )
        except Exception as exc:
            LOGGER.error(f"Failed to turn off stack lights: {exc}", exc_info=True)
            messagebox.showerror("Error", f"Failed to turn off stack lights: {exc}", parent=self)

    def _reload_stacklight_config(self) -> None:
        """Reload stack light configuration and reinitialize API connection."""
        try:
            # Force refresh of cached settings
            LOGGER.info("Refreshing settings cache...")
            refresh_settings()

            # Reinitialize API connection with new config
            self._initialize_stacklight_api()

            messagebox.showinfo(
                "Config Reloaded",
                "Stack light configuration reloaded successfully.\nCheck the status line for current mode.",
                parent=self
            )
        except Exception as exc:
            LOGGER.error(f"Failed to reload stack light config: {exc}", exc_info=True)
            messagebox.showerror("Error", f"Failed to reload config: {exc}", parent=self)

    def _restart_remote_supervisor(self) -> None:
        """Restart the remote supervisor service."""
        try:
            # Ask for confirmation
            response = messagebox.askyesno(
                "Restart Service",
                "This will restart the fw-remote-supervisor service.\n\n"
                "The API will be unavailable for a few seconds.\n\n"
                "Continue?",
                parent=self
            )

            if not response:
                return

            LOGGER.info("Restarting fw-remote-supervisor service...")

            # Restart the service (using sudo - sudoers configured for NOPASSWD)
            result = subprocess.run(
                ["sudo", "systemctl", "restart", "fw-remote-supervisor.service"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                LOGGER.error(f"Failed to restart fw-remote-supervisor: {error_msg}")
                messagebox.showerror(
                    "Restart Failed",
                    f"Failed to restart fw-remote-supervisor service:\n{error_msg}\n\n"
                    "You may need to run this with sudo permissions.",
                    parent=self
                )
                return

            # Wait a moment for service to start
            import time
            time.sleep(2)

            # Check if service is running
            check_result = subprocess.run(
                ["sudo", "systemctl", "is-active", "fw-remote-supervisor.service"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            service_state = check_result.stdout.strip()

            if service_state == "active":
                messagebox.showinfo(
                    "Service Restarted",
                    "The fw-remote-supervisor service has been restarted successfully.\n\n"
                    "The API and dashboard can now use the updated configuration.",
                    parent=self
                )
            else:
                messagebox.showwarning(
                    "Service Status Unknown",
                    f"Service restart command completed, but status is: {service_state}\n\n"
                    "Check the logs with: sudo journalctl -u fw-remote-supervisor -n 20",
                    parent=self
                )

        except FileNotFoundError:
            messagebox.showerror(
                "systemctl not available",
                "The systemctl command is not available.\n\n"
                "Please restart the service manually:\n"
                "sudo systemctl restart fw-remote-supervisor",
                parent=self
            )
        except Exception as exc:
            LOGGER.error(f"Failed to restart remote supervisor: {exc}", exc_info=True)
            messagebox.showerror("Error", f"Failed to restart service: {exc}", parent=self)

    def _on_close(self) -> None:
        if self._status_job is not None:
            try:
                self.after_cancel(self._status_job)
            except Exception:  # pragma: no cover - defensive cleanup
                LOGGER.debug("Failed to cancel scheduled status refresh", exc_info=True)
            self._status_job = None

        # No cleanup needed for API mode - remote supervisor handles GPIO
        LOGGER.info("Closing GUI - stack light control via API remains active")

        self.destroy()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        app = Application()
    except tk.TclError as exc:
        LOGGER.error("Unable to start the GUI: %s", exc)
        LOGGER.error(
            "A graphical environment is required. Launch the application from the Raspberry Pi desktop or an X11 session."
        )
        return 1
    try:
        app.mainloop()
    except KeyboardInterrupt:  # pragma: no cover - allow ctrl+c
        LOGGER.info("Application interrupted")
        return 0

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
