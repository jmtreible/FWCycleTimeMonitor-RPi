# Hardware Wiring Guide - FW Cycle Monitor

## Overview
This guide provides detailed wiring instructions for connecting the stack light relays and the mold close signal relay to the Raspberry Pi.

---

## Components Required

1. **Raspberry Pi** (Model 3B+ or newer recommended)
2. **Waveshare RPi Relay Board** (3-channel) - for stack lights
   - Product: https://www.waveshare.com/rpi-relay-board.htm
   - Specifications: 5A 250V AC / 5A 30V DC per channel
3. **Phoenix Contact 2903359** (RIF-0-RPT-24DC/1AU) - for mold close signal
   - SPST-NO relay, 24V DC coil, DIN rail mountable
4. **Stack Light Tower** (Green/Amber/Red)
5. **Mold Close Signal Source** (from injection molding machine)

---

## Part 1: Waveshare Relay Board for Stack Lights

### Physical Connection to Raspberry Pi

The Waveshare RPi Relay Board connects directly to the Raspberry Pi 40-pin GPIO header.

**Important:** The relay board mounts on top of the Raspberry Pi GPIO pins. Ensure proper seating of all pins.

### GPIO Pin Assignments (BCM Mode)

| Relay Channel | BCM GPIO Pin | Physical Pin | Color Assignment | Function |
|---------------|--------------|--------------|------------------|----------|
| CH1 (Relay 1) | GPIO 26      | Pin 37       | **GREEN**        | Machine Running / Good Status |
| CH2 (Relay 2) | GPIO 20      | Pin 38       | **AMBER**        | Warning / Caution |
| CH3 (Relay 3) | GPIO 21      | Pin 40       | **RED**          | Error / Stopped |

### Relay Characteristics

- **Active Low Operation:** GPIO LOW = Relay ON (energized), GPIO HIGH = Relay OFF (de-energized)
- **LED Indicators:** Each relay has an onboard LED that illuminates when the relay is energized
- **Contact Rating:** 5A @ 250VAC or 5A @ 30VDC
- **Optical Isolation:** Photo-coupled isolation protects Raspberry Pi from high voltage circuits

### Stack Light Wiring

Each relay on the Waveshare board has three terminals:
- **COM** - Common terminal
- **NO** - Normally Open (closes when relay energizes)
- **NC** - Normally Closed (opens when relay energizes)

**Recommended Wiring (using NO contacts):**

```
Stack Light Power Supply (+24V DC or 120V AC depending on your lights)
        |
        +----[Fuse/Breaker]
        |
        +----> COM (Relay 1 - Green)
        |         |
        |         NO ----> Green Light ----> Power Supply GND/Neutral
        |
        +----> COM (Relay 2 - Amber)
        |         |
        |         NO ----> Amber Light ----> Power Supply GND/Neutral
        |
        +----> COM (Relay 3 - Red)
                  |
                  NO ----> Red Light ----> Power Supply GND/Neutral
```

**Wiring Steps:**

1. **Disconnect all power** before wiring
2. For **Green Light:**
   - Connect power supply positive/hot to Relay 1 COM terminal
   - Connect Relay 1 NO terminal to green light positive/hot
   - Connect green light negative/neutral to power supply negative/neutral
3. For **Amber Light:**
   - Connect power supply positive/hot to Relay 2 COM terminal
   - Connect Relay 2 NO terminal to amber light positive/hot
   - Connect amber light negative/neutral to power supply negative/neutral
4. For **Red Light:**
   - Connect power supply positive/hot to Relay 3 COM terminal
   - Connect Relay 3 NO terminal to red light positive/hot
   - Connect red light negative/neutral to power supply negative/neutral

**Safety Notes:**
- Use appropriate wire gauge for your voltage and current (minimum 18 AWG recommended)
- Follow local electrical codes
- Add inline fuses for each circuit
- Ensure all connections are properly terminated and insulated
- For AC wiring, follow proper hot/neutral/ground conventions

---

## Part 2: Phoenix Contact 2903359 for Mold Close Signal

### Relay Specifications

- **Model:** Phoenix Contact 2903359 (RIF-0-RPT-24DC/1AU)
- **Type:** Plug-in relay module with DIN rail base
- **Coil Voltage:** 24V DC
- **Contact Type:** 1 Form A (SPST-NO - Single Pole Single Throw, Normally Open)
- **Contact Rating:** Typically 6A @ 250VAC / 6A @ 30VDC (verify datasheet)
- **Mounting:** DIN rail (NS 35/7.5)

### GPIO Pin Assignment

| Signal Name | BCM GPIO Pin | Physical Pin | Pull-up/down | Function |
|-------------|--------------|--------------|--------------|----------|
| Mold Close  | GPIO 23      | Pin 16       | PULL_DOWN    | Detects mold close signal |

### Wiring Configuration

The Phoenix Contact relay acts as an **input isolator** to safely interface the mold close signal from the injection molding machine to the Raspberry Pi.

**Connection Diagram:**

```
Injection Molding Machine                    Phoenix Contact Relay              Raspberry Pi
Mold Close Signal Output                     2903359                            GPIO 23

[Machine Signal] ----+                  +--------+
                     |                  |        |
+24V DC Signal ------+---> Coil A1 (+) |        |
                                        | Relay  |
Machine GND -------> Coil A2 (-)       |        |
                                        |        |
+3.3V (Pin 1) -----------------------  Contact ----> GPIO 23 (Pin 16)
                                        |        |
                                        +--------+
Raspberry Pi GND (Pin 6) -----------> Contact GND
```

**Terminal Connections:**

1. **Relay Coil Side (Input from Machine):**
   - Terminal **A1** (+): Connect to mold close signal positive from injection molding machine (+24V when closed)
   - Terminal **A2** (-): Connect to mold close signal ground/negative from injection molding machine

2. **Relay Contact Side (Output to Raspberry Pi):**
   - **Contact Terminal 1**: Connect to Raspberry Pi +3.3V (Physical Pin 1)
   - **Contact Terminal 2**: Connect to Raspberry Pi GPIO 23 (BCM 23, Physical Pin 16)
   - **Reference Ground**: Connect a ground wire from Raspberry Pi GND (Physical Pin 6) to the relay DIN rail ground or machine ground for reference

**Alternative Wiring (if using different logic levels):**

If you prefer to use the internal pull-down resistor in the Raspberry Pi:

```
Raspberry Pi +3.3V (Pin 1) ---> Relay Contact Terminal 1
Relay Contact Terminal 2 -------> GPIO 23 (Pin 16)
(GPIO 23 configured with PULL_DOWN in software - already done in gpio_monitor.py:316)
```

When the mold closes:
1. Machine energizes the relay coil with +24V DC
2. Relay contact closes, connecting +3.3V to GPIO 23
3. Raspberry Pi detects a rising edge on GPIO 23
4. Cycle event is logged

### Existing Code Configuration

The mold close signal monitoring is **already implemented** in `src/fw_cycle_monitor/gpio_monitor.py`:

```python
# Line 316: GPIO is configured with pull-down resistor
GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Lines 328-333: Edge detection on BOTH rising and falling edges with 200ms debounce
GPIO.add_event_detect(
    pin,
    GPIO.BOTH,
    callback=self._handle_event,
    bouncetime=200,
)
```

This means:
- **Pull-down configured:** GPIO 23 reads LOW when relay is open
- **Rising edge triggers cycle:** When mold closes, GPIO 23 goes HIGH and triggers a cycle count
- **Debounce:** 200ms debounce prevents false triggers from contact bounce

**No code changes needed** - the existing `CycleMonitor` class handles GPIO 23 monitoring.

---

## Part 3: Complete Pin Assignment Summary

### Raspberry Pi GPIO Pin Map (BCM Mode)

| BCM GPIO | Physical Pin | Function | Direction | Pull Mode | Connected To |
|----------|--------------|----------|-----------|-----------|--------------|
| GPIO 23  | Pin 16       | Mold Close Signal Input | IN | PULL_DOWN | Phoenix Contact relay contact |
| GPIO 26  | Pin 37       | Stack Light Green Control | OUT | - | Waveshare Relay CH1 |
| GPIO 20  | Pin 38       | Stack Light Amber Control | OUT | - | Waveshare Relay CH2 |
| GPIO 21  | Pin 40       | Stack Light Red Control | OUT | - | Waveshare Relay CH3 |

### Power Connections

| Physical Pin | Function | Notes |
|--------------|----------|-------|
| Pin 1        | +3.3V    | For Phoenix Contact relay contact (if needed) |
| Pin 2/4      | +5V      | Waveshare board may use this for relay coil power |
| Pin 6/9/14/20/25/30/34/39 | GND | Common ground references |

---

## Part 4: Wiring Checklist

### Pre-Installation
- [ ] Raspberry Pi powered OFF
- [ ] All power supplies disconnected
- [ ] Proper wire gauge selected (18 AWG or larger for stack lights)
- [ ] Fuses/circuit protection ready

### Waveshare Relay Board Installation
- [ ] Waveshare board firmly seated on Raspberry Pi GPIO header
- [ ] All 40 pins properly aligned and connected
- [ ] Board mounting screws tightened (if applicable)

### Stack Light Wiring
- [ ] Green light wired to Relay 1 (CH1)
- [ ] Amber light wired to Relay 2 (CH2)
- [ ] Red light wired to Relay 3 (CH3)
- [ ] All NO (Normally Open) contacts used
- [ ] Common terminals connected to power source
- [ ] Lights return path connected to power supply neutral/ground
- [ ] All connections properly insulated

### Phoenix Contact Relay Installation
- [ ] DIN rail mounted securely
- [ ] Relay module inserted into base and locked
- [ ] Coil A1 (+) connected to machine +24V mold close signal
- [ ] Coil A2 (-) connected to machine ground
- [ ] Contact terminal 1 connected to Pi +3.3V (Pin 1) if needed
- [ ] Contact terminal 2 connected to Pi GPIO 23 (Pin 16)
- [ ] Ground reference established between Pi and machine

### Power-Up Sequence
- [ ] Visual inspection of all connections
- [ ] Check for shorts with multimeter (power still OFF)
- [ ] Apply power to Raspberry Pi
- [ ] Verify Raspberry Pi boots normally
- [ ] Apply power to stack lights
- [ ] Apply power to mold close relay circuit
- [ ] Test functionality using software commands

---

## Part 5: Testing Procedures

### Testing Stack Light Relays

After installation, test each relay using the Remote Supervisor API:

```bash
# Set your API key and Pi IP
export API_KEY="your-api-key-here"
export PI_IP="192.168.x.x"

# Test green light
curl -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"green": true, "amber": false, "red": false}' \
  http://$PI_IP:8443/stacklight/set

# Test amber light
curl -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"green": false, "amber": true, "red": false}' \
  http://$PI_IP:8443/stacklight/set

# Test red light
curl -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"green": false, "amber": false, "red": true}' \
  http://$PI_IP:8443/stacklight/set

# Run full test sequence
curl -H "X-API-Key: $API_KEY" \
  -X POST \
  http://$PI_IP:8443/stacklight/test

# Turn all off
curl -H "X-API-Key: $API_KEY" \
  -X POST \
  http://$PI_IP:8443/stacklight/off
```

**Startup Self-Test:** When the remote supervisor service starts, it will automatically run a self-test sequence (see Part 6 below).

### Testing Mold Close Signal

1. **Visual Test:**
   ```bash
   # Monitor GPIO 23 state
   gpio readall | grep " 23"
   ```

2. **Watch Log While Triggering:**
   ```bash
   # In one terminal, watch the logs
   sudo journalctl -u fw-cycle-monitor.service -f

   # In another terminal or physically trigger the mold close signal
   # You should see cycle events logged
   ```

3. **Manual Trigger (for testing without machine):**
   - Temporarily connect GPIO 23 (Pin 16) to +3.3V (Pin 1)
   - You should see a cycle event logged
   - Disconnect and reconnect to simulate multiple cycles

---

## Part 6: Startup Self-Test Sequence

The remote supervisor service automatically runs a self-test sequence when it starts. This validates that all stack light relays are functioning properly.

### Sequence Details

The startup self-test runs the following pattern:

1. **Green ON** (2 seconds) → **Green OFF**
2. **Amber ON** (2 seconds) → **Amber OFF**
3. **Red ON** (2 seconds) → **Red OFF**
4. **Green ON** (2 seconds) → **Green OFF**
5. **Amber ON** (2 seconds) → **Amber OFF**
6. **Red ON** (2 seconds) → **Red OFF** (2 seconds pause)
7. **All ON** (2 seconds) → **All OFF** (2 seconds pause)
8. **All ON** (2 seconds) → **All OFF**
9. Return to normal operation

**Total Duration:** ~26 seconds

### Monitoring the Self-Test

To watch the self-test when the service starts:

```bash
# Restart the service and watch logs
sudo systemctl restart fw-remote-supervisor.service
sudo journalctl -u fw-remote-supervisor.service -f
```

You should see log messages indicating the self-test is running:
```
INFO: Running startup self-test sequence for stack lights
INFO: Self-test complete - all relays functioning
```

### Disabling the Self-Test

If you need to disable the startup self-test, edit the configuration:

```bash
nano ~/.config/fw_cycle_monitor/remote_supervisor.json
```

Add `"startup_self_test": false` to the `stacklight` section:

```json
"stacklight": {
  "enabled": true,
  "mock_mode": false,
  "active_low": true,
  "startup_self_test": false,
  "pins": {
    "green": 26,
    "amber": 20,
    "red": 21
  }
}
```

Then restart the service:
```bash
sudo systemctl restart fw-remote-supervisor.service
```

---

## Safety Warnings

⚠️ **ELECTRICAL HAZARDS:**
- Stack lights may operate at high voltage (120VAC or 240VAC)
- Always disconnect power before making connections
- Use proper wire gauge and insulation
- Follow local electrical codes and regulations
- Have a qualified electrician review high-voltage installations

⚠️ **GPIO PROTECTION:**
- Never connect voltages >3.3V directly to Raspberry Pi GPIO pins
- Use isolation relays (like Phoenix Contact 2903359) for external signals
- The Waveshare board provides optical isolation for stack light control
- Incorrect wiring can permanently damage the Raspberry Pi

⚠️ **MACHINE SAFETY:**
- Ensure the mold close signal does not interfere with machine operation
- Use read-only signal taps - never interrupt machine control circuits
- Consult machine manufacturer documentation
- Follow OSHA and safety regulations for industrial equipment

---

## Troubleshooting

### Stack Lights Not Working

1. **Check Configuration:**
   ```bash
   cat ~/.config/fw_cycle_monitor/remote_supervisor.json
   ```
   Ensure `"mock_mode": false` for hardware operation

2. **Check Service Status:**
   ```bash
   sudo systemctl status fw-remote-supervisor.service
   ```

3. **Check Permissions:**
   ```bash
   groups operation1 | grep gpio
   ```
   User should be in `gpio` group

4. **Check GPIO State:**
   ```bash
   gpio readall | grep -E " 26| 20| 21"
   ```

5. **Check Relay Board Connection:**
   - Verify Waveshare board is fully seated on GPIO header
   - Check for bent pins
   - Verify board power LED is lit

### Mold Close Signal Not Triggering

1. **Verify Signal Voltage:**
   - Use multimeter to measure voltage at Phoenix Contact coil terminals
   - Should be ~24V DC when mold is closed

2. **Check Relay Operation:**
   - Listen for audible "click" when relay energizes
   - Check relay LED indicator (if present)

3. **Verify GPIO Connection:**
   ```bash
   # Read GPIO 23 state
   gpio read 23
   ```
   Should be 1 when mold is closed, 0 when open

4. **Check Service Logs:**
   ```bash
   sudo journalctl -u fw-cycle-monitor.service -n 50
   ```
   Look for GPIO initialization and event detection messages

---

## Technical References

- **Waveshare RPi Relay Board:** https://www.waveshare.com/wiki/RPi_Relay_Board
- **Phoenix Contact 2903359:** https://www.phoenixcontact.com/en-us/products/relay-module-rif-0-rpt-24dc-1au-2903359
- **Raspberry Pi GPIO Pinout:** https://pinout.xyz/
- **RPi.GPIO Documentation:** https://sourceforge.net/p/raspberry-gpio-python/wiki/Home/

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2025-01-13 | 1.0 | Initial wiring guide creation |
