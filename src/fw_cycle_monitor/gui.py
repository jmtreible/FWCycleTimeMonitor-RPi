"""Tkinter GUI for configuring and running the cycle time monitor."""

from __future__ import annotations

import logging
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from .config import AppConfig, load_config, save_config
from .gpio_monitor import CycleMonitor
from .metrics import AVERAGE_WINDOWS, calculate_cycle_statistics
from .state import load_cycle_state
from .remote_supervisor.settings import get_settings, refresh_settings
from .remote_supervisor.stacklight_controller import StackLightController

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
        self._stacklight_controller: Optional[StackLightController] = None

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
        self._initialize_stacklight_controller()

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

        # Config reload button
        stacklight_reload_frame = ttk.Frame(stacklight_frame)
        stacklight_reload_frame.grid(row=3, column=0, columnspan=4, pady=(8, 0), sticky="ew")

        ttk.Button(stacklight_reload_frame, text="Reload Config", command=self._reload_stacklight_config).grid(
            row=0, column=0
        )
        ttk.Label(stacklight_reload_frame, text="(Use after changing mock_mode in config file)", foreground="#777777", font=("TkDefaultFont", 8)).grid(
            row=0, column=1, padx=(8, 0), sticky="w"
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

    def _initialize_stacklight_controller(self) -> None:
        """Initialize the stack light controller with settings from config."""
        try:
            settings = get_settings()
            if not settings.stacklight.enabled:
                self._stacklight_status_var.set("Disabled in configuration")
                return

            pins = {
                "green": settings.stacklight.green_pin,
                "amber": settings.stacklight.amber_pin,
                "red": settings.stacklight.red_pin,
            }

            self._stacklight_controller = StackLightController(
                pins=pins,
                mock_mode=settings.stacklight.mock_mode,
                active_low=settings.stacklight.active_low
            )

            mode = "MOCK MODE" if settings.stacklight.mock_mode else "Hardware Mode"
            active_type = "active-low" if settings.stacklight.active_low else "active-high"
            self._stacklight_status_var.set(f"Ready ({mode}, {active_type})")
            self._refresh_stacklight_state()
            LOGGER.info("Stack light controller initialized in GUI")

        except Exception as exc:
            LOGGER.error(f"Failed to initialize stack light controller: {exc}", exc_info=True)
            self._stacklight_status_var.set(f"Error: {exc}")

    def _refresh_stacklight_state(self) -> None:
        """Refresh the UI to show current stack light state."""
        if self._stacklight_controller is None:
            return

        try:
            state = self._stacklight_controller.get_light_state()
            self._stacklight_green_var.set(state["green"])
            self._stacklight_amber_var.set(state["amber"])
            self._stacklight_red_var.set(state["red"])
        except Exception as exc:
            LOGGER.error(f"Failed to refresh stack light state: {exc}", exc_info=True)

    def _set_stacklight_from_ui(self) -> None:
        """Set stack light state from checkbox values."""
        if self._stacklight_controller is None:
            messagebox.showwarning("Stack Light", "Stack light controller not initialized", parent=self)
            return

        try:
            green = self._stacklight_green_var.get()
            amber = self._stacklight_amber_var.get()
            red = self._stacklight_red_var.get()

            result = self._stacklight_controller.set_light_state(green, amber, red)

            if not result["success"]:
                messagebox.showerror(
                    "Stack Light Error",
                    f"Failed to set lights: {result.get('error', 'Unknown error')}",
                    parent=self
                )
        except Exception as exc:
            LOGGER.error(f"Failed to set stack light: {exc}", exc_info=True)
            messagebox.showerror("Error", f"Failed to control stack lights: {exc}", parent=self)

    def _quick_set(self, green: bool, amber: bool, red: bool) -> None:
        """Quick set stack lights to specific pattern."""
        if self._stacklight_controller is None:
            messagebox.showwarning("Stack Light", "Stack light controller not initialized", parent=self)
            return

        try:
            result = self._stacklight_controller.set_light_state(green, amber, red)

            if result["success"]:
                self._refresh_stacklight_state()
            else:
                messagebox.showerror(
                    "Stack Light Error",
                    f"Failed to set lights: {result.get('error', 'Unknown error')}",
                    parent=self
                )
        except Exception as exc:
            LOGGER.error(f"Failed to set stack light: {exc}", exc_info=True)
            messagebox.showerror("Error", f"Failed to control stack lights: {exc}", parent=self)

    def _test_stacklight(self) -> None:
        """Run test sequence on stack lights."""
        if self._stacklight_controller is None:
            messagebox.showwarning("Stack Light", "Stack light controller not initialized", parent=self)
            return

        try:
            # Disable buttons during test
            self._stacklight_status_var.set("Running test sequence...")
            self.update()

            result = self._stacklight_controller.test_sequence()

            if result["success"]:
                self._stacklight_status_var.set(f"Test complete ({result.get('duration_seconds', 0)}s)")
                self._refresh_stacklight_state()
            else:
                self._stacklight_status_var.set("Test failed")
                messagebox.showerror(
                    "Stack Light Error",
                    f"Test sequence failed: {result.get('error', 'Unknown error')}",
                    parent=self
                )
        except Exception as exc:
            LOGGER.error(f"Stack light test failed: {exc}", exc_info=True)
            messagebox.showerror("Error", f"Test sequence failed: {exc}", parent=self)
        finally:
            # Restore status
            settings = get_settings()
            mode = "MOCK MODE" if settings.stacklight.mock_mode else "Hardware Mode"
            active_type = "active-low" if settings.stacklight.active_low else "active-high"
            self._stacklight_status_var.set(f"Ready ({mode}, {active_type})")

    def _turn_off_all_stacklights(self) -> None:
        """Turn off all stack lights."""
        if self._stacklight_controller is None:
            messagebox.showwarning("Stack Light", "Stack light controller not initialized", parent=self)
            return

        try:
            result = self._stacklight_controller.turn_off_all()

            if result["success"]:
                self._refresh_stacklight_state()
            else:
                messagebox.showerror(
                    "Stack Light Error",
                    f"Failed to turn off lights: {result.get('error', 'Unknown error')}",
                    parent=self
                )
        except Exception as exc:
            LOGGER.error(f"Failed to turn off stack lights: {exc}", exc_info=True)
            messagebox.showerror("Error", f"Failed to turn off stack lights: {exc}", parent=self)

    def _reload_stacklight_config(self) -> None:
        """Reload stack light configuration and reinitialize controller."""
        try:
            # Clean up existing controller
            if self._stacklight_controller is not None:
                try:
                    self._stacklight_controller.cleanup()
                except Exception as cleanup_exc:
                    LOGGER.warning(f"Error during cleanup: {cleanup_exc}")
                self._stacklight_controller = None

            # Force refresh of cached settings
            LOGGER.info("Refreshing settings cache...")
            refresh_settings()

            # Reinitialize with new config
            self._initialize_stacklight_controller()

            messagebox.showinfo(
                "Config Reloaded",
                "Stack light configuration reloaded successfully.\nCheck the status line for current mode.",
                parent=self
            )
        except Exception as exc:
            LOGGER.error(f"Failed to reload stack light config: {exc}", exc_info=True)
            messagebox.showerror("Error", f"Failed to reload config: {exc}", parent=self)

    def _on_close(self) -> None:
        if self._status_job is not None:
            try:
                self.after_cancel(self._status_job)
            except Exception:  # pragma: no cover - defensive cleanup
                LOGGER.debug("Failed to cancel scheduled status refresh", exc_info=True)
            self._status_job = None

        # Cleanup stack light controller
        if self._stacklight_controller is not None:
            try:
                self._stacklight_controller.cleanup()
            except Exception:  # pragma: no cover - defensive cleanup
                LOGGER.debug("Failed to cleanup stack light controller", exc_info=True)

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
