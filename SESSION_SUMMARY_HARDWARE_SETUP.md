# Session Summary - Hardware Setup and Startup Self-Test Implementation

**Date:** January 13, 2025
**Branch:** `feature/stack-light-control`
**Commit:** ec448a4

---

## What Was Requested

You asked for the following:

1. **Verify Dependencies:** Confirm that the monitor and supervisor have all necessary dependencies to control the Waveshare relay module
2. **Wiring Instructions:** Provide wiring diagrams for:
   - Waveshare 3-channel relay HAT for stack lights
   - Phoenix Contact 2903359 relay for mold close signal (GPIO 23)
3. **Startup Self-Test:** Add a self-test sequence that runs when the monitor service starts at boot

**Self-Test Sequence Requested:**
- Green on (2s) → Green off
- Amber on (2s) → Amber off
- Red on (2s) → Red off
- Green on (2s) → Green off
- Amber on (2s) → Amber off
- Red on (2s) → Red off (2s pause)
- All on (2s) → All off (2s pause)
- All on (2s) → All off
- Return to normal function

---

## What Was Completed

### ✅ 1. Dependencies Verified

**GPIO Libraries - CONFIRMED INSTALLED:**
- The installer script (`scripts/install_fw_cycle_monitor.sh:56`) installs:
  - `RPi.GPIO` (primary GPIO library)
  - `lgpio` (modern GPIO library)
  - `rpi-lgpio` (compatibility layer)

**Stack Light Controller - VERIFIED:**
- `stacklight_controller.py` supports both RPi.GPIO and lgpio with automatic fallback
- Active-low relay handling is correctly implemented
- Mock mode works for testing without hardware

**Pin Configuration - CORRECT:**
| Relay Channel | BCM GPIO Pin | Physical Pin | Stack Light Color |
|---------------|--------------|--------------|-------------------|
| CH1 (Relay 1) | GPIO 26      | Pin 37       | Green             |
| CH2 (Relay 2) | GPIO 20      | Pin 38       | Amber             |
| CH3 (Relay 3) | GPIO 21      | Pin 40       | Red               |

**Mold Close Signal - ALREADY IMPLEMENTED:**
- GPIO 23 (BCM, Physical Pin 16) is already configured in `gpio_monitor.py:316`
- Pull-down resistor configured
- Edge detection with 200ms debounce
- No code changes needed - existing implementation is correct

### ✅ 2. Comprehensive Wiring Guide Created

**New File:** `HARDWARE_WIRING_GUIDE.md`

**Contents:**
- **Part 1:** Waveshare Relay Board for Stack Lights
  - Physical connection instructions
  - GPIO pin assignments (BCM mode)
  - Relay characteristics (active-low operation, 5A @ 250VAC rating)
  - Complete wiring diagrams with safety notes
  - Stack light wiring steps

- **Part 2:** Phoenix Contact 2903359 for Mold Close Signal
  - Relay specifications (24V DC coil, SPST-NO contact)
  - GPIO 23 pin assignment
  - Wiring configuration with isolation
  - Connection diagrams
  - Integration with existing code

- **Part 3:** Complete Pin Assignment Summary
  - Full GPIO pin map
  - Power connections

- **Part 4:** Wiring Checklist
  - Pre-installation checklist
  - Step-by-step installation verification
  - Power-up sequence

- **Part 5:** Testing Procedures
  - Stack light relay testing with curl commands
  - Mold close signal testing
  - Log monitoring instructions

- **Part 6:** Startup Self-Test Sequence Documentation
  - Sequence details
  - Monitoring the self-test
  - How to disable if needed

- **Safety Warnings & Troubleshooting**

### ✅ 3. Startup Self-Test Implementation

**New Functionality Added:**

1. **stacklight_controller.py:**
   - Added `startup_self_test()` method (lines 210-276)
   - Implements exact sequence requested
   - Total duration: ~26 seconds
   - Returns success/failure status
   - Full error handling and logging

2. **settings.py:**
   - Added `startup_self_test: bool = True` to `StackLightSettings` dataclass
   - Configurable via JSON config file
   - Enabled by default

3. **api.py:**
   - Modified `startup_event()` to run self-test on service startup
   - Only runs if `stacklight.enabled` and `stacklight.startup_self_test` are both true
   - Logs success/failure to system journal

4. **install_fw_cycle_monitor.sh:**
   - Updated config template to include `"startup_self_test": true`
   - New installations will have self-test enabled by default

**Configuration Example:**
```json
{
  "stacklight": {
    "enabled": true,
    "mock_mode": false,
    "active_low": true,
    "startup_self_test": true,
    "pins": {
      "green": 26,
      "amber": 20,
      "red": 21
    }
  }
}
```

---

## Files Modified

| File | Changes |
|------|---------|
| `HARDWARE_WIRING_GUIDE.md` | **NEW** - 479 lines of comprehensive wiring documentation |
| `stacklight_controller.py` | Added `startup_self_test()` method (+68 lines) |
| `settings.py` | Added `startup_self_test` field to StackLightSettings (+2 lines) |
| `api.py` | Modified startup event to run self-test (+17 lines) |
| `install_fw_cycle_monitor.sh` | Updated config template (+1 line) |

**Total:** 567 lines added, 1 line removed

---

## How to Use

### Installation on Raspberry Pi

```bash
# Clone the feature branch
cd ~
git clone -b feature/stack-light-control https://github.com/jmtreible/FWCycleTimeMonitor-RPi.git
cd FWCycleTimeMonitor-RPi

# Run the installer
sudo bash scripts/install_fw_cycle_monitor.sh

# Save the API key that's displayed!
```

### Wiring the Hardware

**Follow the comprehensive guide:** `HARDWARE_WIRING_GUIDE.md`

**Key Points:**
1. Mount Waveshare relay HAT on Raspberry Pi GPIO header
2. Wire stack lights to relay NO (Normally Open) contacts
3. Wire mold close signal to Phoenix Contact relay
4. Phoenix Contact relay output connects to GPIO 23

### Enable Hardware Mode

After wiring is complete, disable mock mode:

```bash
# Edit the configuration
nano ~/.config/fw_cycle_monitor/remote_supervisor.json

# Change "mock_mode" from true to false
"stacklight": {
  "enabled": true,
  "mock_mode": false,  # <-- Change this
  "active_low": true,
  "startup_self_test": true,
  ...
}

# Restart the service
sudo systemctl restart fw-remote-supervisor.service
```

### Watch the Self-Test

```bash
# Restart service and monitor logs
sudo systemctl restart fw-remote-supervisor.service
sudo journalctl -u fw-remote-supervisor.service -f
```

You should see:
```
INFO: Running startup self-test sequence for stack lights
INFO: Set lights - Green=True, Amber=False, Red=False
INFO: Set lights - Green=False, Amber=False, Red=False
... (sequence continues)
INFO: Startup self-test sequence completed successfully
INFO: Stack light startup self-test completed: Self-test completed - all relays functioning
```

### Disable Self-Test (Optional)

If you want to skip the self-test on startup:

```bash
nano ~/.config/fw_cycle_monitor/remote_supervisor.json

# Set startup_self_test to false
"stacklight": {
  ...
  "startup_self_test": false,
  ...
}
```

---

## Testing Checklist

### Before Hardware Connection
- [x] Dependencies verified (RPi.GPIO, lgpio installed)
- [x] Code implementation complete
- [x] Configuration template updated
- [x] Self-test works in mock mode

### After Hardware Connection
- [ ] Waveshare relay HAT physically mounted on Pi
- [ ] Stack lights wired to relays
- [ ] Phoenix Contact relay installed
- [ ] Mold close signal connected to GPIO 23
- [ ] Mock mode disabled in config
- [ ] Service restarted
- [ ] Self-test observed running on boot
- [ ] All three stack lights illuminate during self-test
- [ ] Mold close signal triggers cycle events
- [ ] Dashboard controls work correctly
- [ ] API endpoints respond correctly

---

## API Endpoints (Already Implemented)

All endpoints require `X-API-Key` header.

```bash
export API_KEY="your-api-key"
export PI_IP="192.168.x.x"

# Get stack light status
curl -H "X-API-Key: $API_KEY" http://$PI_IP:8443/stacklight/status

# Set stack lights
curl -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"green": true, "amber": false, "red": false}' \
  http://$PI_IP:8443/stacklight/set

# Run test sequence (manual trigger)
curl -H "X-API-Key: $API_KEY" \
  -X POST \
  http://$PI_IP:8443/stacklight/test

# Turn all lights off
curl -H "X-API-Key: $API_KEY" \
  -X POST \
  http://$PI_IP:8443/stacklight/off
```

---

## Safety Notes

⚠️ **IMPORTANT SAFETY WARNINGS:**

1. **High Voltage:** Stack lights may operate at 120VAC or 240VAC
2. **Disconnect Power:** Always disconnect all power before wiring
3. **GPIO Protection:** Never connect >3.3V directly to Raspberry Pi GPIO pins
4. **Use Isolation:** Phoenix Contact relay provides electrical isolation for mold close signal
5. **Proper Wire Gauge:** Use 18 AWG or larger for stack light circuits
6. **Follow Codes:** Comply with local electrical codes and regulations
7. **Machine Safety:** Don't interrupt machine control circuits - use read-only signal taps

---

## Troubleshooting

See `HARDWARE_WIRING_GUIDE.md` Part 5 for detailed troubleshooting procedures.

**Quick Checks:**

1. **Self-test not running:**
   - Check config: `"startup_self_test": true`
   - Check logs: `sudo journalctl -u fw-remote-supervisor.service -n 50`

2. **Lights not working:**
   - Verify mock_mode is false
   - Check GPIO permissions: `groups operation1 | grep gpio`
   - Verify relay board connection

3. **Mold close not triggering:**
   - Check Phoenix Contact relay is energized (listen for click)
   - Verify 24V DC signal from machine
   - Check GPIO 23 state: `gpio read 23`

---

## Next Steps

1. **Wire the Hardware:**
   - Follow `HARDWARE_WIRING_GUIDE.md` step-by-step
   - Complete wiring checklist
   - Test each component individually

2. **Enable Hardware Mode:**
   - Set `"mock_mode": false`
   - Restart service
   - Verify self-test runs

3. **Validate Functionality:**
   - Confirm all three stack lights work
   - Test mold close signal triggering
   - Test dashboard controls
   - Verify API endpoints

4. **Production Deployment:**
   - Once testing is complete on one machine
   - Merge `feature/stack-light-control` into `main`
   - Deploy to additional machines as needed

---

## Summary

All requested features have been implemented and tested:

✅ **Dependencies Verified** - All GPIO libraries are installed by the installer
✅ **Wiring Guide Complete** - Comprehensive 479-line documentation created
✅ **Self-Test Implemented** - Exact sequence requested, runs on startup
✅ **Configuration Ready** - Installer creates correct config with self-test enabled
✅ **Fully Documented** - Testing procedures, safety warnings, troubleshooting included

The system is ready for hardware installation and testing. All code changes have been committed to the `feature/stack-light-control` branch and pushed to GitHub.

---

## Git Information

**Branch:** feature/stack-light-control
**Latest Commit:** ec448a4
**Commit Message:** "Add stack light startup self-test and hardware wiring documentation"

**To pull latest changes:**
```bash
cd ~/FWCycleTimeMonitor-RPi
git fetch origin
git checkout feature/stack-light-control
git pull origin feature/stack-light-control
```

---

## Questions?

If you encounter any issues during hardware installation or testing, refer to:
1. `HARDWARE_WIRING_GUIDE.md` - Comprehensive wiring and troubleshooting
2. `STACKLIGHT_INSTALLATION_GUIDE.md` - Software installation and API testing
3. Service logs: `sudo journalctl -u fw-remote-supervisor.service -f`
