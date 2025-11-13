"""Stack light GPIO controller with mock mode support."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any

LOGGER = logging.getLogger(__name__)


class StackLightController:
    """Controls stack light outputs via GPIO with mock mode support."""

    def __init__(self, pins: Dict[str, int], mock_mode: bool = False, active_low: bool = True):
        """
        Initialize the stack light controller.

        Args:
            pins: Dictionary with keys 'green', 'amber', 'red' mapping to GPIO pin numbers
            mock_mode: If True, simulates GPIO without hardware
            active_low: If True, relays are activated by LOW signal (typical for relay modules)
        """
        self.pins = pins
        self.mock_mode = mock_mode
        self.active_low = active_low
        self.state = {"green": False, "amber": False, "red": False}
        self.last_updated = None
        self.gpio = None

        if not mock_mode:
            try:
                import RPi.GPIO as GPIO
                self.gpio = GPIO
                LOGGER.info("Using RPi.GPIO for stack light control")
            except ImportError:
                try:
                    import lgpio
                    self.gpio = lgpio
                    LOGGER.info("Using lgpio for stack light control")
                except ImportError:
                    LOGGER.warning("No GPIO library available, falling back to mock mode")
                    self.mock_mode = True

        self._initialize()

    def _initialize(self) -> None:
        """Initialize GPIO pins."""
        if self.mock_mode:
            LOGGER.info("Stack light controller initialized in MOCK mode")
            LOGGER.info(f"Pin configuration: Green={self.pins['green']}, "
                       f"Amber={self.pins['amber']}, Red={self.pins['red']}")
            return

        try:
            if hasattr(self.gpio, 'setmode'):
                # RPi.GPIO style
                self.gpio.setmode(self.gpio.BCM)
                self.gpio.setwarnings(False)
                for color, pin in self.pins.items():
                    self.gpio.setup(pin, self.gpio.OUT)
                    # Initialize all relays to OFF state
                    # For active_low: HIGH = OFF, LOW = ON
                    initial_value = self.gpio.HIGH if self.active_low else self.gpio.LOW
                    self.gpio.output(pin, initial_value)
                    LOGGER.info(f"Initialized {color} light on GPIO BCM pin {pin} (active_low={self.active_low})")
            else:
                # lgpio style
                self.gpio_chip = self.gpio.gpiochip_open(0)
                for color, pin in self.pins.items():
                    # Initialize all relays to OFF state
                    initial_value = 1 if self.active_low else 0
                    self.gpio.gpio_claim_output(self.gpio_chip, pin, initial_value)
                    LOGGER.info(f"Initialized {color} light on GPIO BCM pin {pin} (active_low={self.active_low})")

            LOGGER.info("Stack light GPIO initialization complete")
        except Exception as e:
            LOGGER.error(f"Failed to initialize GPIO: {e}", exc_info=True)
            LOGGER.warning("Falling back to mock mode")
            self.mock_mode = True

    def set_light_state(self, green: bool, amber: bool, red: bool) -> Dict[str, Any]:
        """
        Set the state of all three lights.

        Args:
            green: True to turn on green light
            amber: True to turn on amber light
            red: True to turn on red light

        Returns:
            Dictionary with success status and current state
        """
        try:
            self.state = {"green": green, "amber": amber, "red": red}
            self.last_updated = datetime.now(timezone.utc)

            if self.mock_mode:
                LOGGER.info(f"MOCK: Set lights - Green={green}, Amber={amber}, Red={red}")
            else:
                if hasattr(self.gpio, 'output'):
                    # RPi.GPIO style
                    for color, value in self.state.items():
                        pin = self.pins[color]
                        # For active_low: ON=LOW, OFF=HIGH
                        # For active_high: ON=HIGH, OFF=LOW
                        if self.active_low:
                            gpio_value = self.gpio.LOW if value else self.gpio.HIGH
                        else:
                            gpio_value = self.gpio.HIGH if value else self.gpio.LOW
                        self.gpio.output(pin, gpio_value)
                else:
                    # lgpio style
                    for color, value in self.state.items():
                        pin = self.pins[color]
                        # For active_low: ON=0, OFF=1
                        # For active_high: ON=1, OFF=0
                        if self.active_low:
                            gpio_value = 0 if value else 1
                        else:
                            gpio_value = 1 if value else 0
                        self.gpio.gpio_write(self.gpio_chip, pin, gpio_value)

                LOGGER.info(f"Set lights - Green={green}, Amber={amber}, Red={red}")

            return {
                "success": True,
                "state": self.state.copy(),
                "timestamp": self.last_updated.isoformat()
            }
        except Exception as e:
            LOGGER.error(f"Failed to set light state: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "state": self.state.copy()
            }

    def get_light_state(self) -> Dict[str, Any]:
        """
        Get the current state of all lights.

        Returns:
            Dictionary with current light states and last updated timestamp
        """
        return {
            "green": self.state["green"],
            "amber": self.state["amber"],
            "red": self.state["red"],
            "last_updated": self.last_updated.isoformat() if self.last_updated else None
        }

    def turn_off_all(self) -> Dict[str, Any]:
        """
        Turn off all lights.

        Returns:
            Dictionary with success status and current state
        """
        return self.set_light_state(False, False, False)

    def test_sequence(self, duration_per_light: float = 2.0) -> Dict[str, Any]:
        """
        Run a test sequence cycling through each light.

        Sequence: Green -> Amber -> Red -> All Off

        Args:
            duration_per_light: Time in seconds to display each light

        Returns:
            Dictionary with success status and total duration
        """
        try:
            LOGGER.info(f"Starting stack light test sequence ({duration_per_light}s per light)")

            # Green
            self.set_light_state(True, False, False)
            time.sleep(duration_per_light)

            # Amber
            self.set_light_state(False, True, False)
            time.sleep(duration_per_light)

            # Red
            self.set_light_state(False, False, True)
            time.sleep(duration_per_light)

            # All off
            self.set_light_state(False, False, False)
            time.sleep(duration_per_light)

            total_duration = duration_per_light * 4

            LOGGER.info("Stack light test sequence completed")

            return {
                "success": True,
                "message": "Test sequence completed",
                "duration_seconds": total_duration
            }
        except Exception as e:
            LOGGER.error(f"Test sequence failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def startup_self_test(self) -> Dict[str, Any]:
        """
        Run a comprehensive startup self-test sequence.

        Sequence:
        - Green ON (2s) -> Green OFF
        - Amber ON (2s) -> Amber OFF
        - Red ON (2s) -> Red OFF
        - Green ON (2s) -> Green OFF
        - Amber ON (2s) -> Amber OFF
        - Red ON (2s) -> Red OFF (2s pause)
        - All ON (2s) -> All OFF (2s pause)
        - All ON (2s) -> All OFF

        Total duration: ~26 seconds

        Returns:
            Dictionary with success status and total duration
        """
        try:
            LOGGER.info("Running startup self-test sequence for stack lights")

            # First cycle through each light twice
            for cycle in range(2):
                # Green
                self.set_light_state(True, False, False)
                time.sleep(2.0)
                self.set_light_state(False, False, False)

                # Amber
                self.set_light_state(False, True, False)
                time.sleep(2.0)
                self.set_light_state(False, False, False)

                # Red
                self.set_light_state(False, False, True)
                time.sleep(2.0)
                self.set_light_state(False, False, False)

                # Pause after red on second cycle
                if cycle == 1:
                    time.sleep(2.0)

            # All lights ON then OFF twice
            for cycle in range(2):
                self.set_light_state(True, True, True)
                time.sleep(2.0)
                self.set_light_state(False, False, False)

                # Pause after first all-off
                if cycle == 0:
                    time.sleep(2.0)

            LOGGER.info("Startup self-test sequence completed successfully")

            return {
                "success": True,
                "message": "Self-test completed - all relays functioning",
                "duration_seconds": 26
            }
        except Exception as e:
            LOGGER.error(f"Startup self-test failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": "Self-test failed"
            }

    def cleanup(self) -> None:
        """Clean up GPIO resources."""
        if self.mock_mode:
            LOGGER.info("MOCK: Cleaning up GPIO resources")
            return

        try:
            # Turn off all lights
            self.turn_off_all()

            if self.gpio:
                if hasattr(self.gpio, 'cleanup'):
                    # RPi.GPIO style
                    self.gpio.cleanup()
                elif hasattr(self, 'gpio_chip'):
                    # lgpio style
                    self.gpio.gpiochip_close(self.gpio_chip)

                LOGGER.info("Stack light GPIO cleanup complete")
        except Exception as e:
            LOGGER.error(f"Failed to cleanup GPIO: {e}", exc_info=True)
