"""GPIO monitoring logic for the FW Cycle Time Monitor."""

from __future__ import annotations

import csv
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from .config import AppConfig

LOGGER = logging.getLogger(__name__)

__all__ = ["CycleMonitor", "GPIOUnavailableError", "MonitorStats"]

try:  # pragma: no cover - hardware-specific import
    import RPi.GPIO as GPIO  # type: ignore

    GPIO.setmode(GPIO.BCM)
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
        self._counter = _CycleCounter()
        self._csv_initialized = False
        self._csv_header = ["cycle_number", "machine_id", "timestamp"]

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

        GPIO.setup(self.config.gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # type: ignore[attr-defined]
        GPIO.add_event_detect(  # type: ignore[attr-defined]
            self.config.gpio_pin,
            GPIO.RISING,
            callback=self._handle_event,
            bouncetime=200,
        )

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
        self._record_event(timestamp)
        with self._lock:
            self._stats.last_event_time = timestamp
            self._stats.events_logged += 1
        if self._callback:
            self._callback(timestamp)
        return timestamp

    def _prepare_storage(self) -> None:
        if self._csv_initialized:
            return
        csv_path = self.config.csv_path()
        try:
            Path(self.config.csv_directory).mkdir(parents=True, exist_ok=True)
        except OSError:
            LOGGER.exception("Failed to create CSV directory %s", self.config.csv_directory)
            raise

        if not csv_path.exists():
            try:
                with csv_path.open("w", newline="") as csv_file:
                    writer = csv.writer(csv_file)
                    writer.writerow(self._csv_header)
            except OSError:
                LOGGER.exception("Failed to initialize CSV file at %s", csv_path)
                raise
            reference = datetime.now(timezone.utc).astimezone()
            self._counter.configure(reference, 0)
            self._csv_initialized = True
            return

        if not self._ensure_migrated(csv_path):
            return

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
                    reference = datetime.now(timezone.utc).astimezone()
                    self._counter.configure(reference, 0)
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

        reference = last_timestamp or datetime.now(timezone.utc).astimezone()
        self._counter.configure(reference, last_count)
        self._csv_initialized = True

    def _ensure_migrated(self, csv_path: Path) -> bool:
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
            self._counter.configure(reference, 0)
            self._csv_initialized = True
            return False

        header, data_rows = rows[0], rows[1:]
        if header == self._csv_header:
            return True

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
            self._counter.configure(last_timestamp, int(last_cycle))
        else:
            reference = datetime.now(timezone.utc).astimezone()
            self._counter.configure(reference, 0)

        self._csv_initialized = True
        return False

    def _record_event(self, timestamp: datetime) -> Optional[int]:
        try:
            self._prepare_storage()
        except Exception:
            LOGGER.exception("Unable to prepare storage for cycle events")
            return None

        cycle_number = self._counter.record(timestamp)
        csv_path = self.config.csv_path()
        try:
            with csv_path.open("a", newline="") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow([cycle_number, self.config.machine_id, timestamp.isoformat()])
            LOGGER.debug("Logged cycle #%s at %s to %s", cycle_number, timestamp.isoformat(), csv_path)
        except OSError:
            LOGGER.exception("Failed to write cycle event to %s", csv_path)
            return None

        return cycle_number
