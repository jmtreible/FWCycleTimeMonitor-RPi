"""GPIO monitoring logic for the FW Cycle Time Monitor."""

from __future__ import annotations

import csv
import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from .config import AppConfig
from .state import MachineState, load_cycle_state, save_cycle_state

LOGGER = logging.getLogger(__name__)

__all__ = ["CycleMonitor", "GPIOUnavailableError", "MonitorStats"]

try:  # pragma: no cover - hardware-specific import
    import RPi.GPIO as GPIO  # type: ignore

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    _GPIO_AVAILABLE = True
except Exception:  # pragma: no cover - executed on non-RPi systems
    GPIO = None  # type: ignore
    _GPIO_AVAILABLE = False


class GPIOUnavailableError(RuntimeError):
    """Raised when RPi.GPIO is not available on the current system."""


@dataclass
class MonitorStats:
    """Statistics about monitoring events."""

    last_event_time: Optional[datetime] = None
    events_logged: int = 0


class _CycleCounter:
    """Track cycle numbers with automatic daily resets."""

    def __init__(self, reset_hour: int = 3):
        self._reset_hour = reset_hour
        self._count = 0
        self._next_reset: Optional[datetime] = None

    def _calculate_next_reset(self, reference: datetime) -> datetime:
        cycle_reset = reference.replace(
            hour=self._reset_hour, minute=0, second=0, microsecond=0
        )
        if reference < cycle_reset:
            return cycle_reset
        return cycle_reset + timedelta(days=1)

    def configure(self, reference: datetime, current_count: int) -> None:
        """Configure the counter based on an existing reference timestamp."""

        self._count = current_count
        self._next_reset = self._calculate_next_reset(reference)

    def record(self, timestamp: datetime) -> int:
        """Increment the cycle count for the given timestamp."""

        if self._next_reset is None:
            self.configure(timestamp, self._count)

        while self._next_reset and timestamp >= self._next_reset:
            self._count = 0
            self._next_reset = self._next_reset + timedelta(days=1)

        self._count += 1
        return self._count

    @property
    def count(self) -> int:
        return self._count


class CycleMonitor:
    """Monitor a GPIO pin for rising edges and log cycle times."""

    def __init__(self, config: AppConfig, callback: Optional[Callable[[datetime], None]] = None):
        self.config = config
        self._callback = callback
        self._lock = threading.Lock()
        self._stats = MonitorStats()
        self._running = False
        self._counter = _CycleCounter(config.reset_hour)
        self._counter_initialized = False
        self._csv_initialized = False
        self._csv_header = ["cycle_number", "machine_id", "timestamp"]
        self._pending_rows: list[list[str]] = []
        self._pending_loaded = False

    @property
    def stats(self) -> MonitorStats:
        return self._stats

    @property
    def csv_path(self) -> Path:
        """Return the CSV path associated with the current configuration."""

        return self.config.csv_path()

    @property
    def is_running(self) -> bool:
        """Report whether the monitor is actively watching the GPIO pin."""

        with self._lock:
            return self._running

    def _restore_counter_state(self) -> None:
        """Initialise the cycle counter from persisted state if available."""

        persisted_state = load_cycle_state(self.config.machine_id)
        sidecar_state = self._load_sidecar_state()

        chosen_state: Optional[MachineState]
        if persisted_state and sidecar_state:
            if sidecar_state.last_timestamp > persisted_state.last_timestamp:
                LOGGER.info(
                    "Using sidecar state for %s (more recent than config directory)",
                    self.config.machine_id,
                )
                chosen_state = sidecar_state
                try:
                    save_cycle_state(
                        self.config.machine_id,
                        last_cycle=sidecar_state.last_cycle,
                        last_timestamp=sidecar_state.last_timestamp,
                    )
                except Exception:
                    LOGGER.exception(
                        "Failed to sync sidecar state back to config directory for %s",
                        self.config.machine_id,
                    )
            else:
                LOGGER.debug(
                    "Using config directory state for %s; sidecar timestamp=%s",
                    self.config.machine_id,
                    sidecar_state.last_timestamp.isoformat(),
                )
                chosen_state = persisted_state
                self._persist_sidecar_state(
                    persisted_state.last_cycle, persisted_state.last_timestamp
                )
        else:
            chosen_state = persisted_state or sidecar_state

        if not chosen_state:
            LOGGER.debug("No persisted cycle state to restore for %s", self.config.machine_id)
            self._counter_initialized = False
            return

        reference = chosen_state.last_timestamp
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        reference = reference.astimezone()

        LOGGER.info(
            "Initialising cycle counter from persisted state: machine=%s last_cycle=%s",
            self.config.machine_id,
            chosen_state.last_cycle,
        )
        self._counter.configure(reference, chosen_state.last_cycle)
        self._counter_initialized = True

    def start(self) -> None:
        if not _GPIO_AVAILABLE:
            raise GPIOUnavailableError(
                "RPi.GPIO is not available. Run on a Raspberry Pi with the library installed."
            )

        with self._lock:
            if self._running:
                LOGGER.debug("CycleMonitor already running")
                return
            LOGGER.info("Starting monitor on pin %s for machine %s", self.config.gpio_pin, self.config.machine_id)
            self._restore_counter_state()
            self._prepare_storage()
            self._setup_gpio()
            self._running = True

    def stop(self) -> None:
        if not _GPIO_AVAILABLE:
            return

        with self._lock:
            if not self._running:
                return
            LOGGER.info("Stopping monitor on pin %s", self.config.gpio_pin)
            try:
                GPIO.remove_event_detect(self.config.gpio_pin)  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - best effort cleanup
                LOGGER.debug("Event detect removal failed", exc_info=True)
            GPIO.cleanup(self.config.gpio_pin)  # type: ignore[attr-defined]
            self._running = False

    def reset_cycle_counter(self, reference: Optional[datetime] = None) -> None:
        """Manually reset the cycle counter so the next event logs as cycle 1."""

        reference_time = (reference or datetime.now(timezone.utc)).astimezone()
        with self._lock:
            self._counter.configure(reference_time, 0)
            self._counter_initialized = True
        try:
            save_cycle_state(
                self.config.machine_id,
                last_cycle=0,
                last_timestamp=reference_time,
            )
        except Exception:  # pragma: no cover - best effort persistence
            LOGGER.exception("Failed to persist manual reset state for %s", self.config.machine_id)
        self._persist_sidecar_state(0, reference_time)
        LOGGER.info(
            "Cycle counter manually reset; next cycle will start at 1 using %s as reference",
            reference_time.isoformat(),
        )

    def _setup_gpio(self) -> None:
        """Configure edge detection on the configured GPIO pin."""

        # Guard against partially-initialised GPIO modules. Users occasionally
        # install the package on non-Raspberry Pi systems which leaves
        # ``RPi.GPIO`` mocked or missing key attributes.  That can manifest as
        # confusing ``IndentationError`` reports when Python tries to execute
        # a module that previously failed to import the GPIO constants.  By
        # validating the essentials up front we fail fast with a clear
        # exception message instead of propagating obscure interpreter errors
        # to the launcher.
        if not hasattr(GPIO, "setup") or not hasattr(GPIO, "add_event_detect"):
            raise GPIOUnavailableError(
                "RPi.GPIO is missing required attributes. Ensure the library is fully installed on the Raspberry Pi."
            )

        pin = self.config.gpio_pin

        # ``add_event_detect`` raises ``RuntimeError`` if the pin already has
        # edge detection configured.  This can happen when the monitor is
        # restarted without a clean shutdown (for example, after a crash or
        # power loss).  Clear any lingering configuration before attempting to
        # initialise the pin so subsequent setup calls succeed.
        try:
            GPIO.remove_event_detect(pin)  # type: ignore[attr-defined]
        except RuntimeError:
            # No prior event detector was registered, which is fine.
            pass
        except Exception:  # pragma: no cover - best effort cleanup
            LOGGER.debug("Ignoring error while clearing existing edge detection", exc_info=True)

        try:
            GPIO.cleanup(pin)  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - best effort cleanup
            LOGGER.debug("Ignoring error during GPIO cleanup for pin %s", pin, exc_info=True)

        try:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # type: ignore[attr-defined]
        except RuntimeError as exc:
            raise RuntimeError(
                "Failed to configure GPIO pin %s. Ensure the process has permission to access GPIO and no other service is using the pin." % pin
            ) from exc

        try:
            GPIO.add_event_detect(  # type: ignore[attr-defined]
                pin,
                GPIO.RISING,
                callback=self._handle_event,
                bouncetime=200,
            )
        except RuntimeError as exc:
            # Occasionally the underlying GPIO driver refuses to register the
            # edge detector on the first attempt (particularly on systems using
            # the newer lgpio backend).  Retry once after a full cleanup to give
            # the kernel a chance to release the line before we escalate the
            # failure to the caller.
            LOGGER.warning("First attempt to add edge detection on pin %s failed; retrying", pin, exc_info=True)
            try:
                GPIO.cleanup(pin)  # type: ignore[attr-defined]
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # type: ignore[attr-defined]
                GPIO.add_event_detect(  # type: ignore[attr-defined]
                    pin,
                    GPIO.RISING,
                    callback=self._handle_event,
                    bouncetime=200,
                )
            except Exception as final_exc:
                raise RuntimeError(
                    "Failed to add edge detection on GPIO pin %s. Confirm the pin is wired correctly and that no other process has it reserved." % pin
                ) from final_exc

    def _handle_event(self, channel: int) -> None:  # pragma: no cover - triggered by GPIO
        timestamp = datetime.now(timezone.utc).astimezone()
        cycle_number = self._record_event(timestamp)
        if cycle_number is None:
            return

        with self._lock:
            self._stats.last_event_time = timestamp
            self._stats.events_logged += 1

        if self._callback:
            try:
                self._callback(timestamp)
            except Exception:  # pragma: no cover - UI callback errors
                LOGGER.exception("Cycle event callback failed")

    def simulate_event(self) -> datetime:
        """Simulate an event for testing environments without GPIO.

        Returns the timestamp that was logged.
        """

        timestamp = datetime.now(timezone.utc).astimezone()
        with self._lock:
            if not self._counter_initialized:
                self._restore_counter_state()
        self._record_event(timestamp)
        with self._lock:
            self._stats.last_event_time = timestamp
            self._stats.events_logged += 1
        if self._callback:
            self._callback(timestamp)
        return timestamp

    def _prepare_storage(self) -> None:
        if self._csv_initialized:
            if not self._pending_loaded:
                self._load_pending_rows()
            return
        csv_path = self.config.csv_path()
        try:
            Path(self.config.csv_directory).mkdir(parents=True, exist_ok=True)
            self._ensure_shared_permissions(Path(self.config.csv_directory), directory=True)
        except OSError:
            LOGGER.exception("Failed to create CSV directory %s", self.config.csv_directory)
            raise

        if not csv_path.exists():
            try:
                with csv_path.open("w", newline="") as csv_file:
                    writer = csv.writer(csv_file)
                    writer.writerow(self._csv_header)
                self._ensure_shared_permissions(csv_path)
            except OSError:
                LOGGER.exception("Failed to initialize CSV file at %s", csv_path)
                raise
            if not self._counter_initialized:
                reference = datetime.now(timezone.utc).astimezone()
                self._counter.configure(reference, 0)
                self._counter_initialized = True
            self._csv_initialized = True
            return

        seed = self._ensure_migrated(csv_path)
        if seed and not self._counter_initialized:
            reference, last_count = seed
            if reference.tzinfo is None:
                reference = reference.replace(tzinfo=timezone.utc)
            self._counter.configure(reference.astimezone(), last_count)
            self._counter_initialized = True

        last_timestamp: Optional[datetime] = None
        last_count = 0
        try:
            with csv_path.open("r", newline="") as csv_file:
                reader = csv.reader(csv_file)
                header = next(reader, None)
                if header != self._csv_header:
                    LOGGER.warning("Unexpected CSV header in %s; reinitializing file", csv_path)
                    csv_file.close()
                    with csv_path.open("w", newline="") as new_csv:
                        writer = csv.writer(new_csv)
                        writer.writerow(self._csv_header)
                    if not self._counter_initialized:
                        reference = datetime.now(timezone.utc).astimezone()
                        self._counter.configure(reference, 0)
                        self._counter_initialized = True
                    self._csv_initialized = True
                    return
                for row in reader:
                    if len(row) < 3:
                        continue
                    try:
                        timestamp = datetime.fromisoformat(row[2])
                    except ValueError:
                        continue
                    last_timestamp = timestamp
                    try:
                        last_count = int(row[0])
                    except ValueError:
                        last_count = 0
        except OSError:
            LOGGER.exception("Failed to read existing CSV file %s", csv_path)
            raise

        if not self._counter_initialized:
            reference = last_timestamp or datetime.now(timezone.utc).astimezone()
            if reference.tzinfo is None:
                reference = reference.replace(tzinfo=timezone.utc)
            self._counter.configure(reference.astimezone(), last_count)
            self._counter_initialized = True
        self._ensure_shared_permissions(csv_path)
        self._csv_initialized = True
        self._load_pending_rows()

    def _ensure_migrated(self, csv_path: Path) -> Optional[tuple[datetime, int]]:
        try:
            with csv_path.open("r", newline="") as csv_file:
                reader = csv.reader(csv_file)
                rows = list(reader)
        except OSError:
            LOGGER.exception("Failed to open CSV file %s for migration", csv_path)
            raise

        if not rows:
            try:
                with csv_path.open("w", newline="") as csv_file:
                    writer = csv.writer(csv_file)
                    writer.writerow(self._csv_header)
            except OSError:
                LOGGER.exception("Failed to write header to empty CSV %s", csv_path)
                raise
            reference = datetime.now(timezone.utc).astimezone()
            return (reference, 0)

        header, data_rows = rows[0], rows[1:]
        if header == self._csv_header:
            return None

        LOGGER.info("Migrating CSV file %s to include cycle numbers", csv_path)
        counter = _CycleCounter()
        migrated_rows = []
        for row in data_rows:
            if len(row) < 2:
                continue
            ts_str = row[-1]
            try:
                timestamp = datetime.fromisoformat(ts_str)
            except ValueError:
                continue
            cycle_number = counter.record(timestamp)
            migrated_rows.append([cycle_number, row[0], timestamp.isoformat()])

        try:
            with csv_path.open("w", newline="") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(self._csv_header)
                writer.writerows(migrated_rows)
        except OSError:
            LOGGER.exception("Failed to migrate CSV file %s", csv_path)
            raise

        if migrated_rows:
            last_cycle, _, ts_str = migrated_rows[-1]
            try:
                last_timestamp = datetime.fromisoformat(ts_str)
            except ValueError:
                last_timestamp = datetime.now(timezone.utc).astimezone()
            return (last_timestamp, int(last_cycle))
        else:
            reference = datetime.now(timezone.utc).astimezone()
            return (reference, 0)

    def _record_event(self, timestamp: datetime) -> Optional[int]:
        try:
            self._prepare_storage()
        except Exception:
            LOGGER.exception("Unable to prepare storage for cycle events")
            return None

        cycle_number = self._counter.record(timestamp)
        csv_path = self.config.csv_path()
        row = [str(cycle_number), self.config.machine_id, timestamp.isoformat()]
        if not self._append_with_retry(csv_path, row):
            LOGGER.warning(
                "Cycle #%s queued locally; CSV %s is currently unavailable", cycle_number, csv_path
            )
        try:
            save_cycle_state(
                self.config.machine_id,
                last_cycle=cycle_number,
                last_timestamp=timestamp,
            )
        except Exception:  # pragma: no cover - best effort persistence
            LOGGER.exception("Failed to persist cycle state for %s", self.config.machine_id)
        self._persist_sidecar_state(cycle_number, timestamp)
        return cycle_number

    # -----------------
    # Pending row logic

    def _spool_path(self) -> Path:
        csv_path = self.config.csv_path()
        return csv_path.with_name(csv_path.name + ".pending")

    def _load_pending_rows(self) -> None:
        if self._pending_loaded:
            return
        spool_path = self._spool_path()
        if spool_path.exists():
            try:
                with spool_path.open("r", newline="") as spool_file:
                    reader = csv.reader(spool_file)
                    for row in reader:
                        if len(row) >= 3:
                            self._pending_rows.append(row[:3])
            except OSError:
                LOGGER.exception("Failed to read pending events from %s", spool_path)
        self._pending_loaded = True

    def _persist_pending_rows(self) -> None:
        spool_path = self._spool_path()
        if not self._pending_rows:
            if spool_path.exists():
                try:
                    spool_path.unlink()
                except OSError:
                    LOGGER.debug("Unable to remove empty spool file %s", spool_path, exc_info=True)
            return
        try:
            with spool_path.open("w", newline="") as spool_file:
                writer = csv.writer(spool_file)
                writer.writerows(self._pending_rows)
            self._ensure_shared_permissions(spool_path, file_mode=0o660)
        except OSError:
            LOGGER.exception("Failed to persist pending events to %s", spool_path)

    def _open_for_append(self, path: Path):
        """Open ``path`` for appending with shared-friendly flags."""

        flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
        fd = os.open(path, flags, 0o664)
        try:
            os.lseek(fd, 0, os.SEEK_END)
            return os.fdopen(fd, "a", newline="")
        except Exception:
            os.close(fd)
            raise

    def _append_with_retry(self, csv_path: Path, new_row: list[str]) -> bool:
        with self._lock:
            if not self._pending_loaded:
                self._load_pending_rows()
            rows_to_write = [row for row in self._pending_rows]
            rows_to_write.append(new_row)
            try:
                with self._open_for_append(csv_path) as csv_file:
                    writer = csv.writer(csv_file)
                    writer.writerows(rows_to_write)
                self._pending_rows.clear()
                self._persist_pending_rows()
                self._ensure_shared_permissions(csv_path)
                LOGGER.debug(
                    "Logged cycle #%s at %s to %s", new_row[0], new_row[2], csv_path
                )
                return True
            except OSError:
                LOGGER.warning(
                    "CSV file %s is busy; queueing cycle #%s for retry", csv_path, new_row[0]
                )
                self._pending_rows = rows_to_write
                self._persist_pending_rows()
                return False

    # -----------------
    # Sidecar state persistence

    def _state_sidecar_path(self) -> Path:
        csv_path = self.config.csv_path()
        return csv_path.with_name(csv_path.name + ".state.json")

    def _load_sidecar_state(self) -> Optional[MachineState]:
        sidecar = self._state_sidecar_path()
        if not sidecar.exists():
            return None
        try:
            payload = json.loads(sidecar.read_text())
        except (OSError, json.JSONDecodeError):
            LOGGER.warning("Failed to read sidecar state from %s", sidecar, exc_info=True)
            return None

        try:
            last_cycle = int(payload["last_cycle"])
            timestamp = datetime.fromisoformat(payload["last_timestamp"])
        except (KeyError, ValueError, TypeError):
            LOGGER.warning("Sidecar state at %s is invalid", sidecar)
            return None

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return MachineState(
            machine_id=self.config.machine_id,
            last_cycle=last_cycle,
            last_timestamp=timestamp,
        )

    def _persist_sidecar_state(self, last_cycle: int, timestamp: datetime) -> None:
        sidecar = self._state_sidecar_path()
        try:
            sidecar.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            LOGGER.exception("Unable to create directory for sidecar state %s", sidecar)
            return

        payload = {
            "last_cycle": int(last_cycle),
            "last_timestamp": timestamp.isoformat(),
        }
        suffix = sidecar.suffix
        tmp_path = (
            sidecar.with_suffix(suffix + ".tmp") if suffix else sidecar.with_name(sidecar.name + ".tmp")
        )
        try:
            tmp_path.write_text(json.dumps(payload))
            tmp_path.replace(sidecar)
            self._ensure_shared_permissions(sidecar, file_mode=0o660)
        except OSError:
            LOGGER.exception("Failed to persist sidecar state to %s", sidecar)
            try:
                tmp_path.unlink(missing_ok=True)  # type: ignore[arg-type]
            except OSError:
                LOGGER.debug("Failed to remove temporary sidecar file %s", tmp_path, exc_info=True)

    def _ensure_shared_permissions(self, path: Path, file_mode: int = 0o664, directory: bool = False) -> None:
        """Apply permissive permissions so other users can read the CSV output."""

        if not path.exists():
            return
        mode = 0o775 if directory else file_mode
        try:
            current = path.stat().st_mode & 0o777
            if current != mode:
                path.chmod(mode)
        except OSError:
            LOGGER.debug("Unable to adjust permissions for %s", path, exc_info=True)
