"""Tkinter GUI for configuring and running the cycle time monitor."""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from .config import AppConfig, load_config, save_config
from .gpio_monitor import CycleMonitor, GPIOUnavailableError

LOGGER = logging.getLogger(__name__)


class Application(tk.Tk):
    """Main GUI application."""

    def __init__(self) -> None:
        super().__init__()
        self.title("FW Cycle Time Monitor")
        self.resizable(False, False)

        self._config = load_config()
        self._monitor: Optional[CycleMonitor] = None

        self._machine_var = tk.StringVar(value=self._config.machine_id)
        self._pin_var = tk.StringVar(value=str(self._config.gpio_pin))
        self._directory_var = tk.StringVar(value=str(self._config.csv_directory))
        self._status_var = tk.StringVar(value="Stopped")
        self._last_event_var = tk.StringVar(value="—")
        self._events_logged_var = tk.StringVar(value="0")
        self._simulated_events = 0

        self._build_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

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

        frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=(16, 0), sticky="ew")
        self._start_button = ttk.Button(button_frame, text="Start Monitoring", command=self._start_monitor)
        self._start_button.grid(row=0, column=0, padx=(0, 8))
        self._stop_button = ttk.Button(button_frame, text="Stop", command=self._stop_monitor, state=tk.DISABLED)
        self._stop_button.grid(row=0, column=1, padx=(0, 8))
        ttk.Button(button_frame, text="Log Test Event", command=self._log_test_event).grid(row=0, column=2)

        status_frame = ttk.LabelFrame(frame, text="Status", padding=12)
        status_frame.grid(row=4, column=0, columnspan=3, pady=(16, 0), sticky="ew")

        ttk.Label(status_frame, text="State:").grid(row=0, column=0, sticky="w")
        ttk.Label(status_frame, textvariable=self._status_var).grid(row=0, column=1, sticky="w")

        ttk.Label(status_frame, text="Last Event:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(status_frame, textvariable=self._last_event_var).grid(row=1, column=1, sticky="w", pady=(8, 0))

        ttk.Label(status_frame, text="Events Logged:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Label(status_frame, textvariable=self._events_logged_var).grid(row=2, column=1, sticky="w", pady=(8, 0))

        version = self._resolve_version()
        ttk.Label(frame, text=f"Version: {version}", foreground="#555555").grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(16, 0)
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
        monitor = CycleMonitor(config, callback=self._handle_cycle_event)
        try:
            monitor.start()
        except GPIOUnavailableError as exc:
            messagebox.showerror("GPIO unavailable", str(exc), parent=self)
            return
        except Exception as exc:  # pragma: no cover - unexpected hardware errors
            LOGGER.exception("Failed to start monitor")
            messagebox.showerror("Error", f"Failed to start monitoring: {exc}", parent=self)
            return

        self._monitor = monitor
        self._status_var.set("Running")
        self._start_button.configure(state=tk.DISABLED)
        self._stop_button.configure(state=tk.NORMAL)
        self._simulated_events = 0
        self._events_logged_var.set(str(self._monitor.stats.events_logged))
        if self._monitor.stats.last_event_time:
            self._last_event_var.set(self._monitor.stats.last_event_time.isoformat())
        else:
            self._last_event_var.set("Waiting…")

    def _stop_monitor(self) -> None:
        if not self._monitor:
            return
        self._monitor.stop()
        self._monitor = None
        self._status_var.set("Stopped")
        self._start_button.configure(state=tk.NORMAL)
        self._stop_button.configure(state=tk.DISABLED)

    def _log_test_event(self) -> None:
        try:
            config = self._read_config_from_ui()
        except ValueError as exc:
            messagebox.showerror("Invalid configuration", str(exc), parent=self)
            return

        monitor = self._monitor or CycleMonitor(config, callback=self._handle_cycle_event)
        try:
            timestamp = monitor.simulate_event()
        except Exception as exc:  # pragma: no cover - unexpected disk errors
            LOGGER.exception("Failed to log test event")
            messagebox.showerror("Error", f"Failed to log test event: {exc}", parent=self)
            return

        if not self._monitor:
            # refresh display when running in simulation-only mode
            self._simulated_events += 1
            self._events_logged_var.set(str(self._simulated_events))
            self._last_event_var.set(timestamp.isoformat())

    def _handle_cycle_event(self, timestamp: datetime) -> None:
        self.after(0, self._update_event_display, timestamp)

    def _update_event_display(self, timestamp: datetime) -> None:
        if self._monitor:
            self._events_logged_var.set(str(self._monitor.stats.events_logged))
        self._last_event_var.set(timestamp.isoformat())

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
        return AppConfig(machine_id=machine_id, gpio_pin=gpio_pin, csv_directory=csv_directory)

    def _resolve_version(self) -> str:
        try:
            from . import __version__

            return __version__
        except Exception:  # pragma: no cover - metadata lookup
            return "development"

    def _on_close(self) -> None:
        if self._monitor:
            self._monitor.stop()
        self.destroy()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    app = Application()
    try:
        app.mainloop()
    except KeyboardInterrupt:  # pragma: no cover - allow ctrl+c
        LOGGER.info("Application interrupted")
        sys.exit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
