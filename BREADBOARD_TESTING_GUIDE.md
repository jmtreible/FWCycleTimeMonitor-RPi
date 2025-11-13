# Breadboard Testing Guide - Stack Light Relays with LEDs

## Overview
This guide shows you how to test the Waveshare 3-channel relay HAT using a breadboard and low-voltage LEDs before connecting high-voltage stack lights.

---

## Components Needed

### Required:
- ✅ Raspberry Pi (already have)
- ✅ Waveshare RPi Relay Board (3-channel) - already have
- 🔴 Red LED (for testing red channel)
- 🟡 Yellow/Amber LED (for testing amber channel)
- 🟢 Green LED (for testing green channel)
- 3x 220Ω to 330Ω resistors (current limiting resistors for LEDs)
- Breadboard
- Jumper wires (male-to-male and male-to-female)

### Power Options (choose one):
**Option A: Use Raspberry Pi 5V** (simplest)
- No external power supply needed
- Limited to Pi's 5V output capability

**Option B: Use external 5V or 12V DC power supply** (recommended for full testing)
- 5V or 12V DC wall adapter
- Barrel jack connector or wire leads

---

## Understanding the Waveshare Relay Board

### Relay Contact Configuration
Each relay has 3 terminals:
- **COM** (Common)
- **NO** (Normally Open) - Closes when relay is energized
- **NC** (Normally Closed) - Opens when relay is energized

### For LED Testing, We'll Use NO Contacts
When the software turns a light "ON":
- GPIO pin goes LOW (active-low configuration)
- Relay energizes
- NO contact closes, completing the LED circuit
- LED illuminates

---

## Wiring Diagram - Option A: Using Raspberry Pi 5V

This is the simplest setup for testing.

### Circuit Schematic (Per Channel)

```
Raspberry Pi 5V (Pin 2 or 4)
        |
        +---> COM (Relay Channel)
                  |
                  NO ---> [220Ω Resistor] ---> [LED Anode (+)]
                                                      |
                                                 [LED Cathode (-)]
                                                      |
Raspberry Pi GND (Pin 6, 9, 14, 20, 25, 30, 34, or 39) <---+
```

### Step-by-Step Wiring Instructions

**Prerequisites:**
1. Power OFF the Raspberry Pi
2. Mount the Waveshare relay board on the Pi's GPIO header
3. Ensure all 40 pins are properly seated

**Breadboard Setup:**

1. **Power Rails:**
   ```
   Breadboard (+) rail ---> Raspberry Pi +5V (Physical Pin 2 or 4)
   Breadboard (-) rail ---> Raspberry Pi GND (Physical Pin 6)
   ```

2. **Green LED Circuit (Relay 1 - CH1):**
   ```
   Waveshare Relay 1 COM ---> Breadboard (+) rail
   Waveshare Relay 1 NO ---> 220Ω resistor ---> Green LED anode (+, longer leg)
   Green LED cathode (-, shorter leg) ---> Breadboard (-) rail
   ```

3. **Amber/Yellow LED Circuit (Relay 2 - CH2):**
   ```
   Waveshare Relay 2 COM ---> Breadboard (+) rail
   Waveshare Relay 2 NO ---> 220Ω resistor ---> Amber LED anode (+)
   Amber LED cathode (-) ---> Breadboard (-) rail
   ```

4. **Red LED Circuit (Relay 3 - CH3):**
   ```
   Waveshare Relay 3 COM ---> Breadboard (+) rail
   Waveshare Relay 3 NO ---> 220Ω resistor ---> Red LED anode (+)
   Red LED cathode (-) ---> Breadboard (-) rail
   ```

### Visual Breadboard Layout

```
Raspberry Pi
+5V (Pin 2) -----> [Breadboard + Rail] -----> COM of all 3 relays
GND (Pin 6) -----> [Breadboard - Rail]

Relay 1 (Green):
  NO ----> [220Ω] ----> Green LED (+) ----> (-) to breadboard - rail

Relay 2 (Amber):
  NO ----> [220Ω] ----> Amber LED (+) ----> (-) to breadboard - rail

Relay 3 (Red):
  NO ----> [220Ω] ----> Red LED (+) ----> (-) to breadboard - rail
```

**Important Notes for Option A:**
- The Raspberry Pi 5V pins can supply up to ~1A total
- Each LED draws ~20mA, so 3 LEDs = ~60mA total (well within limits)
- This is safe for testing
- Do NOT connect high-power loads to Pi 5V pins

---

## Wiring Diagram - Option B: Using External Power Supply

For more realistic testing (closer to actual stack light operation).

### Circuit Schematic

```
External DC Power Supply (5V or 12V)
        (+) -----> Breadboard (+) rail -----> COM of all 3 relays
        (-) -----> Breadboard (-) rail

Relay 1 (Green):
  NO ----> [220Ω for 5V or 470Ω for 12V] ----> Green LED (+) ----> (-) to breadboard - rail

Relay 2 (Amber):
  NO ----> [220Ω for 5V or 470Ω for 12V] ----> Amber LED (+) ----> (-) to breadboard - rail

Relay 3 (Red):
  NO ----> [220Ω for 5V or 470Ω for 12V] ----> Red LED (+) ----> (-) to breadboard - rail
```

**Resistor Values:**
- **5V supply:** Use 220Ω resistors
- **12V supply:** Use 470Ω to 1kΩ resistors (to limit LED current)

**Important Notes for Option B:**
- External supply ground MUST be connected to Raspberry Pi ground for common reference
- This isolates the LED power from the Pi, more like real stack lights
- Can test with higher voltages safely (up to 12V DC with appropriate resistors)

---

## LED Polarity Guide

**How to Identify LED Polarity:**

```
        Longer Leg = Anode (+)
             |
         ____|____
        |         |
        |   LED   |  <-- Flat edge on cathode side
        |_________|
             |
        Shorter Leg = Cathode (-)
```

**Visual Inspection:**
- **Anode (+):** Longer leg, goes to resistor (connected to relay NO)
- **Cathode (-):** Shorter leg, flat edge on LED body, goes to ground

**If You Cut the Legs:**
- Look inside the LED: larger metal piece = cathode (-)
- Flat edge on LED case = cathode (-)

---

## Testing Procedure

### 1. Pre-Power Checks

Before powering on:

- [ ] All relay board pins properly seated on Pi GPIO header
- [ ] LEDs installed with correct polarity (long leg to resistor)
- [ ] All resistors connected (220Ω for 5V, 470Ω for 12V)
- [ ] Power and ground rails connected
- [ ] No short circuits (use multimeter to check)

### 2. Software Configuration

**Ensure the software is installed and configured:**

```bash
# If not already installed, install from feature branch
cd ~
git clone -b feature/stack-light-control https://github.com/jmtreible/FWCycleTimeMonitor-RPi.git
cd FWCycleTimeMonitor-RPi
sudo bash scripts/install_fw_cycle_monitor.sh
```

**Configure for hardware mode:**

```bash
# Edit configuration
nano ~/.config/fw_cycle_monitor/remote_supervisor.json
```

**Important:** Set `"mock_mode": false` to enable hardware control:

```json
{
  "stacklight": {
    "enabled": true,
    "mock_mode": false,        // <-- MUST be false for hardware
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

Save and exit (Ctrl+X, Y, Enter)

### 3. Power On and Test

**Start the service:**

```bash
# Restart the remote supervisor service
sudo systemctl restart fw-remote-supervisor.service

# Watch the logs
sudo journalctl -u fw-remote-supervisor.service -f
```

**Expected Behavior:**

Within a few seconds of service startup, you should see the **startup self-test sequence**:

1. **Green LED** lights up for 2 seconds, then off
2. **Amber LED** lights up for 2 seconds, then off
3. **Red LED** lights up for 2 seconds, then off
4. **Green LED** lights up for 2 seconds, then off (repeat cycle)
5. **Amber LED** lights up for 2 seconds, then off
6. **Red LED** lights up for 2 seconds, then off, 2 second pause
7. **All three LEDs** light up for 2 seconds, then off, 2 second pause
8. **All three LEDs** light up for 2 seconds, then off
9. All LEDs remain off (normal operation)

**Total self-test duration:** ~26 seconds

**Logs should show:**
```
INFO: Running startup self-test sequence for stack lights
INFO: Set lights - Green=True, Amber=False, Red=False
INFO: Set lights - Green=False, Amber=False, Red=False
... (continues through sequence)
INFO: Startup self-test sequence completed successfully
```

### 4. Manual LED Testing via API

After the self-test completes, test manual control:

```bash
# Set your API key (from installation)
export API_KEY="your-api-key-here"

# Test green LED
curl -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"green": true, "amber": false, "red": false}' \
  http://localhost:8443/stacklight/set

# Wait a few seconds, observe green LED is on

# Test amber LED
curl -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"green": false, "amber": true, "red": false}' \
  http://localhost:8443/stacklight/set

# Test red LED
curl -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"green": false, "amber": false, "red": true}' \
  http://localhost:8443/stacklight/set

# Test all LEDs on
curl -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"green": true, "amber": true, "red": true}' \
  http://localhost:8443/stacklight/set

# Turn all LEDs off
curl -H "X-API-Key: $API_KEY" \
  -X POST \
  http://localhost:8443/stacklight/off
```

### 5. Test the Manual Test Sequence

```bash
# Run the built-in test sequence
curl -H "X-API-Key: $API_KEY" \
  -X POST \
  http://localhost:8443/stacklight/test
```

This should cycle through Green → Amber → Red → All Off (2 seconds each).

---

## Troubleshooting

### LEDs Don't Light Up During Self-Test

**Check:**
1. **Mock mode disabled?**
   ```bash
   cat ~/.config/fw_cycle_monitor/remote_supervisor.json | grep mock_mode
   ```
   Should show: `"mock_mode": false`

2. **Service running?**
   ```bash
   sudo systemctl status fw-remote-supervisor.service
   ```
   Should show: `active (running)`

3. **Relay board properly connected?**
   - Power off Pi
   - Reseat the Waveshare board on GPIO header
   - Ensure all pins make contact

4. **Check GPIO permissions:**
   ```bash
   groups operation1 | grep gpio
   ```
   User should be in `gpio` group

5. **Verify relay operation:**
   - Listen for relay "click" when LED should turn on
   - If you hear clicks but LED doesn't light, check LED wiring

### Specific LED Doesn't Work

**Check LED polarity:**
- Swap the LED around (reverse polarity)
- If it lights up, you had it backwards

**Check resistor connection:**
- Verify resistor is firmly in breadboard
- Verify continuity with multimeter

**Test the LED directly:**
- Temporarily connect LED+resistor directly from +5V to GND
- If LED doesn't light, the LED may be bad

### Relays Click But No LED

**Check:**
1. **Power to breadboard:**
   ```bash
   # Measure voltage at breadboard + rail with multimeter
   # Should read ~5V (Option A) or your supply voltage (Option B)
   ```

2. **LED current path:**
   - Verify resistor is between relay NO and LED anode
   - Verify LED cathode goes to ground rail
   - Check for loose connections

3. **Test with multimeter:**
   - Set multimeter to continuity mode
   - When relay is ON, there should be continuity from COM to NO
   - When relay is OFF, no continuity

### All Relays Stay On (or Off)

**Check active_low setting:**
```bash
cat ~/.config/fw_cycle_monitor/remote_supervisor.json | grep active_low
```
Should show: `"active_low": true`

If set to `false`, the relay logic is inverted.

---

## Safety Notes for Breadboard Testing

✅ **Safe Practices:**
- Use only 5V or 12V DC for LED testing
- Keep current under 100mA total
- Use appropriate current-limiting resistors
- Verify polarity before applying power

⚠️ **Do NOT:**
- Connect AC voltage to breadboard
- Exceed 12V DC on breadboard circuits
- Bypass current-limiting resistors
- Touch relay contacts while powered

---

## Success Criteria

After completing breadboard testing, you should have verified:

- [ ] All three relay channels operate independently
- [ ] Startup self-test sequence runs correctly (26 seconds)
- [ ] Green LED controlled by GPIO 26 (Relay 1)
- [ ] Amber LED controlled by GPIO 20 (Relay 2)
- [ ] Red LED controlled by GPIO 21 (Relay 3)
- [ ] API commands control LEDs correctly
- [ ] Manual test sequence works
- [ ] Relays click audibly when switching
- [ ] LEDs illuminate with correct polarity
- [ ] Service logs show successful operations

---

## Next Steps After Successful Breadboard Testing

Once breadboard testing is complete and all LEDs work correctly:

1. **Disconnect breadboard testing setup**
   - Power off Raspberry Pi
   - Carefully remove all breadboard wiring
   - Keep the Waveshare relay board mounted on Pi

2. **Wire the actual stack lights**
   - Follow `HARDWARE_WIRING_GUIDE.md` Part 1
   - Use the same relay terminals (COM and NO)
   - Observe all high-voltage safety precautions

3. **No software changes needed**
   - The configuration is already set for hardware mode
   - Self-test will run on next boot
   - All API endpoints will work with stack lights

---

## Shopping List (If You Need to Purchase Components)

### Minimum for Testing:
- 3x Standard LEDs (Red, Yellow/Amber, Green) - ~$0.10 each
- 3x 220Ω resistors - ~$0.05 each
- 1x Breadboard (400 tie-points) - ~$3-5
- 10x Jumper wires (male-to-male) - ~$2-5
- 5x Jumper wires (male-to-female, if not using GPIO pins directly) - ~$2-5

**Total cost: ~$5-10**

### Optional:
- LED assortment kit (usually 100+ LEDs, 5 colors) - ~$8-12
- Resistor kit (multiple values, 100-500 pieces) - ~$10-15
- Jumper wire kit (M-M, M-F, F-F) - ~$10-15

### Where to Buy:
- **Amazon:** Search "breadboard LED kit" or "electronics component kit"
- **Electronics stores:** Micro Center, Fry's Electronics
- **Online:** Adafruit, SparkFun, Digi-Key, Mouser
- **Local:** Radio Shack (if still in your area), hobby shops

---

## Alternative: Test Without Breadboard

If you don't want to use a breadboard, you can verify relay operation without LEDs:

### Audible Test:
1. Restart the service: `sudo systemctl restart fw-remote-supervisor.service`
2. Listen for relay clicks during the 26-second self-test sequence
3. You should hear distinct "click-click" sounds as each relay turns on/off

### Visual Test (Relay Board LEDs):
- The Waveshare board has onboard LEDs for each relay channel
- Watch these LEDs during the self-test sequence
- They should illuminate when each relay is energized

### Multimeter Test:
1. Set multimeter to continuity or resistance mode
2. Place probes on COM and NO terminals of relay 1
3. Run a curl command to turn green light on
4. Multimeter should show continuity (beep or ~0Ω)
5. Turn green light off, continuity should break
6. Repeat for other channels

This verifies the relays are working before wiring stack lights!

---

## Quick Reference: Pin Mapping

| Color | GPIO BCM | Physical Pin | Relay CH | LED Color |
|-------|----------|--------------|----------|-----------|
| Green | 26       | 37           | CH1      | Green     |
| Amber | 20       | 38           | CH2      | Yellow    |
| Red   | 21       | 40           | CH3      | Red       |

**Power Pins:**
- +5V: Physical Pin 2 or 4
- GND: Physical Pin 6, 9, 14, 20, 25, 30, 34, or 39

---

## Questions or Issues?

If you encounter problems during breadboard testing:

1. Check `sudo journalctl -u fw-remote-supervisor.service -f` for errors
2. Verify `"mock_mode": false` in config
3. Verify user is in `gpio` group
4. Double-check LED polarity
5. Test LEDs independently with direct power
6. Verify relay board is fully seated on GPIO header

**The self-test sequence is your best diagnostic tool** - if it runs correctly, your hardware is working!
