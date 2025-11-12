# Stack Light Installation and Testing Guide

## Overview
This guide walks you through installing the stack light control system on your Raspberry Pi and testing all functionality before connecting to the ERP system.

---

## Prerequisites

- Raspberry Pi with Raspbian/Raspberry Pi OS installed
- Waveshare 3-channel relay HAT (or compatible relay module)
- Network connection to the Pi
- Git installed on the Pi
- Sudo/root access

---

## Part 1: Installation on Raspberry Pi

### Step 1: Clone or Update Repository with Feature Branch

SSH into your Raspberry Pi, then choose one of the options below:

#### Option A: Fresh Installation (Clone Feature Branch Directly)

**Recommended for new installations:**

```bash
# Clone the feature branch directly
cd ~
git clone -b feature/stack-light-control https://github.com/jmtreible/FWCycleTimeMonitor-RPi.git
cd FWCycleTimeMonitor-RPi
```

#### Option B: Existing Repository (Update to Feature Branch)

**If you already have the repository cloned:**

```bash
# Navigate to existing repository
cd ~/FWCycleTimeMonitor-RPi

# Fetch latest changes
git fetch origin

# Switch to feature branch
git checkout feature/stack-light-control

# Pull latest updates
git pull origin feature/stack-light-control
```

#### Option C: Clone Main Repository Then Switch Branches

**Standard two-step approach:**

```bash
# Clone the repository
cd ~
git clone https://github.com/jmtreible/FWCycleTimeMonitor-RPi.git
cd FWCycleTimeMonitor-RPi

# Checkout the feature branch
git checkout feature/stack-light-control
```

**Note:** Once the feature is tested and merged to `main`, you can use:
```bash
git clone https://github.com/jmtreible/FWCycleTimeMonitor-RPi.git
```
(No need to specify the branch - it will use `main` by default)

### Step 2: Run the Installer

Run the installation script with sudo:

```bash
cd ~/FWCycleTimeMonitor-RPi
sudo bash scripts/install_fw_cycle_monitor.sh
```

The installer will:
- Install required system packages
- Create a Python virtual environment
- Install GPIO libraries (RPi.GPIO, lgpio)
- Deploy the code to `/opt/fw-cycle-monitor/`
- Configure systemd services
- Generate an API key for remote access

**IMPORTANT:** Save the API key that is displayed during installation. You'll need it for testing and dashboard access.

### Step 3: Verify Services are Running

Check that both services started successfully:

```bash
# Check the cycle monitor service
sudo systemctl status fw-cycle-monitor.service

# Check the remote supervisor service (API)
sudo systemctl status fw-remote-supervisor.service
```

Both should show `active (running)` in green.

### Step 4: Configure Stack Light Settings (Optional)

The stack light system runs in **mock mode by default**, which means it will work without hardware connected. This is perfect for initial testing.

To configure settings, edit the remote supervisor config file:

```bash
nano ~/.config/fw_cycle_monitor/remote_supervisor.json
```

Add or modify the `stacklight` section:

```json
{
  "host": "0.0.0.0",
  "port": 8443,
  "unit_name": "fw-cycle-monitor.service",
  "api_keys": [
    "your-api-key-here"
  ],
  "certfile": null,
  "keyfile": null,
  "metrics_enabled": true,
  "stacklight": {
    "enabled": true,
    "mock_mode": true,
    "active_low": true,
    "pins": {
      "green": 26,
      "amber": 20,
      "red": 21
    }
  }
}
```

**Configuration Options:**
- `enabled`: Set to `false` to completely disable stack light control
- `mock_mode`: Set to `true` for testing without hardware, `false` for real GPIO control
- `active_low`: Set to `true` for Waveshare relay HAT (LOW=ON), `false` for active-high relays
- `pins`: GPIO BCM pin numbers for each light

After editing, restart the service:

```bash
sudo systemctl restart fw-remote-supervisor.service
```

### Step 5: View Logs

Monitor the service logs to see stack light operations:

```bash
# View recent logs
sudo journalctl -u fw-remote-supervisor.service -n 50

# Follow logs in real-time
sudo journalctl -u fw-remote-supervisor.service -f
```

Look for messages like:
- `Stack light controller initialized in MOCK mode`
- `Initialized green light on GPIO BCM pin 26`
- `MOCK: Set lights - Green=True, Amber=False, Red=False`

---

## Part 2: Testing the Stack Light API

### Important: HTTP vs HTTPS

By default, the service runs in **HTTP mode** (not HTTPS) unless you configure SSL certificates. This is perfectly fine for testing and local network use.

**Symptoms of HTTP/HTTPS mismatch:**
- `curl: (35) OpenSSL/3.0.17: error:0A00010B:SSL routines::wrong version number`
- Connection refused or SSL errors

**Solution:** Use `http://` (not `https://`) in your curl commands unless you've configured SSL certificates.

### Test 1: Check API is Accessible

From the Pi itself or another computer on the network:

```bash
# Replace with your actual API key from installation
export API_KEY="your-api-key-here"

# Replace with your Pi's IP address (use localhost if testing from the Pi)
export PI_IP="localhost"  # Or use the actual IP like "192.168.1.100"

# Test basic connectivity - NOTE: Using http:// not https://
curl -H "X-API-Key: $API_KEY" http://$PI_IP:8443/service/status
```

**Note:** No `-k` flag needed for HTTP. Only use `-k` if you've configured HTTPS with self-signed certificates.

You should see JSON output with service status information.

### Test 2: Get Stack Light Status

```bash
curl -H "X-API-Key: $API_KEY" http://$PI_IP:8443/stacklight/status
```

**Expected Output:**
```json
{
  "green": false,
  "amber": false,
  "red": false,
  "last_updated": null
}
```

### Test 3: Turn On Green Light

```bash
curl -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"green": true, "amber": false, "red": false}' \
  http://$PI_IP:8443/stacklight/set
```

**Expected Output:**
```json
{
  "success": true,
  "state": {
    "green": true,
    "amber": false,
    "red": false
  },
  "timestamp": "2025-11-12T15:30:00Z"
}
```

Check the logs to see the mock operation:
```bash
sudo journalctl -u fw-remote-supervisor.service -n 5
```

You should see: `MOCK: Set lights - Green=True, Amber=False, Red=False`

### Test 4: Turn On Amber Light

```bash
curl -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"green": false, "amber": true, "red": false}' \
  http://$PI_IP:8443/stacklight/set
```

### Test 5: Turn On Red Light

```bash
curl -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"green": false, "amber": false, "red": true}' \
  http://$PI_IP:8443/stacklight/set
```

### Test 6: Run Test Sequence

```bash
curl -H "X-API-Key: $API_KEY" \
  -X POST \
  http://$PI_IP:8443/stacklight/test
```

**Expected Output:**
```json
{
  "success": true,
  "message": "Test sequence completed",
  "duration_seconds": 8.0
}
```

This will cycle through: Green → Amber → Red → All Off (2 seconds each)

Watch the logs in real-time to see the sequence:
```bash
sudo journalctl -u fw-remote-supervisor.service -f
```

### Test 7: Turn Off All Lights

```bash
curl -H "X-API-Key: $API_KEY" \
  -X POST \
  http://$PI_IP:8443/stacklight/off
```

### Test 8: Verify Status Again

```bash
curl -H "X-API-Key: $API_KEY" http://$PI_IP:8443/stacklight/status
```

All lights should be off and you should see a recent timestamp.

---

## Part 3: Testing with Real Hardware

### Step 1: Connect the Waveshare Relay HAT

1. **Power off the Raspberry Pi**: `sudo shutdown -h now`
2. **Connect the Waveshare 3-channel relay HAT** to the GPIO header
3. **Connect your stack lights**:
   - Relay 1 (CH1) → Green light
   - Relay 2 (CH2) → Amber light
   - Relay 3 (CH3) → Red light
4. **Ensure proper power supply** for the relays and lights (typically 24V AC/DC)
5. **Power on the Raspberry Pi**

### Step 2: Disable Mock Mode

Edit the configuration:

```bash
nano ~/.config/fw_cycle_monitor/remote_supervisor.json
```

Change `"mock_mode": true` to `"mock_mode": false`:

```json
"stacklight": {
  "enabled": true,
  "mock_mode": false,
  "active_low": true,
  "pins": {
    "green": 26,
    "amber": 20,
    "red": 21
  }
}
```

Restart the service:

```bash
sudo systemctl restart fw-remote-supervisor.service
```

### Step 3: Check Logs for GPIO Initialization

```bash
sudo journalctl -u fw-remote-supervisor.service -n 20
```

You should see:
```
Stack light controller initialized
Initialized green light on GPIO BCM pin 26 (active_low=True)
Initialized amber light on GPIO BCM pin 20 (active_low=True)
Initialized red light on GPIO BCM pin 21 (active_low=True)
Stack light GPIO initialization complete
```

### Step 4: Run Hardware Tests

**CAUTION:** The lights will now physically turn on/off!

```bash
# Set environment variables
export API_KEY="your-api-key-here"
export PI_IP="localhost"  # Or the Pi's IP address

# Test green light (should turn on physically)
curl -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"green": true, "amber": false, "red": false}' \
  http://$PI_IP:8443/stacklight/set

# Wait a few seconds and observe the green light

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

# Run full test sequence (watch the lights cycle)
curl -H "X-API-Key: $API_KEY" \
  -X POST \
  http://$PI_IP:8443/stacklight/test

# Turn all off
curl -H "X-API-Key: $API_KEY" \
  -X POST \
  http://$PI_IP:8443/stacklight/off
```

### Step 5: Verify with Multimeter (Optional)

If lights aren't working as expected, use a multimeter to test the relay outputs:

1. Set GPIO pin HIGH (relay should be OFF for active-low): No voltage on relay output
2. Set GPIO pin LOW (relay should be ON for active-low): Voltage present on relay output

---

## Part 4: Testing from the Dashboard

### Step 1: Configure Machine in Dashboard

1. Open the FWCycleDashboard web application
2. Navigate to **Machines** page
3. Click **Add Machine** and enter:
   - **Machine ID**: "Test Pi" (or your machine name)
   - **IP Address**: Your Pi's IP address
   - **Port**: 8443
   - **API Key**: The key from installation
   - **Use HTTPS**: Checked
4. Click **Save**

### Step 2: View Machine on Dashboard

1. Navigate to the **Home/Dashboard** page
2. Wait for auto-refresh or click **Refresh All**
3. You should see your machine card with:
   - Online status (green badge)
   - Service status
   - **Stack Lights** section with buttons

### Step 3: Test Stack Light Controls from UI

1. Click the **Green** button - it should turn solid green and the light should activate
2. Click the **Amber** button - it should turn solid yellow/amber and the light should switch
3. Click the **Red** button - it should turn solid red and the light should switch
4. Click **Test** - watch the full sequence run (takes ~8 seconds)
5. Click **All Off** - all lights should turn off

The dashboard will auto-refresh after each action to show the updated state.

### Step 4: Check Command History

Navigate to the **History** page to see all stack light commands that have been executed, including success/failure status.

---

## Part 5: Troubleshooting

### Problem: API Returns 404 for Stack Light Endpoints

**Solution:**
- Check that you're on the `feature/stack-light-control` branch
- Verify the service restarted after installation
- Check logs: `sudo journalctl -u fw-remote-supervisor.service -n 50`

### Problem: "Stack light control is disabled in configuration"

**Solution:**
- Edit `~/.config/fw_cycle_monitor/remote_supervisor.json`
- Set `"stacklight": { "enabled": true }`
- Restart service: `sudo systemctl restart fw-remote-supervisor.service`

### Problem: GPIO Permission Denied

**Solution:**
- Ensure the service is running as the correct user (not root)
- Check that the user is in the `gpio` group: `groups $USER`
- Add user to gpio group: `sudo usermod -a -G gpio $USER`
- Reboot if needed

### Problem: Wrong Pins Activating

**Solution:**
- Verify your relay module's pin mapping (may differ from Waveshare)
- Update pin configuration in `remote_supervisor.json`
- Restart service

### Problem: Lights Stay On When They Should Be Off

**Solution:**
- Your relay module may be active-HIGH instead of active-LOW
- Change `"active_low": false` in configuration
- Restart service

### Problem: Dashboard Shows "Offline"

**Solution:**
- Verify network connectivity: `ping <pi-ip>`
- Check firewall isn't blocking port 8443
- Verify API key is correct in dashboard machine config
- Check service is running: `sudo systemctl status fw-remote-supervisor.service`
- Test API manually with curl from the dashboard machine

### Problem: Test Sequence Doesn't Complete

**Solution:**
- Check logs for errors during the sequence
- The test takes 8 seconds - ensure you wait for completion
- If timing seems wrong, the GPIO operations may be taking longer than expected

---

## Part 6: Performance Verification

### Check Response Times

```bash
# Time a simple status request
time curl -H "X-API-Key: $API_KEY" http://$PI_IP:8443/stacklight/status

# Time a set operation
time curl -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"green": true, "amber": false, "red": false}' \
  http://$PI_IP:8443/stacklight/set
```

Typical response times should be under 100ms for status, under 200ms for set operations.

### Load Test (Optional)

Test rapid consecutive requests:

```bash
for i in {1..10}; do
  curl -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -X POST \
    -d '{"green": true, "amber": false, "red": false}' \
    http://$PI_IP:8443/stacklight/set
  sleep 0.5
done
```

Check logs to verify all requests were processed successfully.

---

## Part 7: Ready for ERP Integration

Once all tests pass, your system is ready for ERP integration!

### Information to Provide to ERP Team

1. **API Base URL**: `http://<pi-ip>:8443` (or `https://` if you configured SSL)
2. **API Key**: (from installation)
3. **SSL Certificate**: None by default (HTTP mode). If using HTTPS, it's self-signed (they may need to disable SSL verification)
4. **Implementation Plan**: Share `STACKLIGHT_IMPLEMENTATION_PLAN.md` with Phase 3 details

### Test ERP Integration

When the ERP team is ready to test:

1. Have them call the `/stacklight/set` endpoint with their logic
2. Monitor the logs on the Pi: `sudo journalctl -u fw-remote-supervisor.service -f`
3. Verify lights respond correctly to their cycle time calculations
4. Check the dashboard Command History for their API calls

---

## Part 8: Switching to Production

### Step 1: Merge Feature Branch

Once testing is complete and stable:

```bash
cd ~/FWCycleTimeMonitor-RPi
git checkout main
git merge feature/stack-light-control
git push origin main
```

### Step 2: Update on Other Machines

On other Raspberry Pis in your deployment:

```bash
cd ~/FWCycleTimeMonitor-RPi
git pull origin main
sudo bash scripts/install_fw_cycle_monitor.sh
```

### Step 3: Production Configuration

For production machines, set up the configuration properly:

```bash
nano ~/.config/fw_cycle_monitor/remote_supervisor.json
```

Ensure:
- `mock_mode: false` (if hardware is connected)
- Correct pin mappings for your relay module
- Secure API keys (unique per machine)

---

## Quick Reference: Common Commands

```bash
# View logs
sudo journalctl -u fw-remote-supervisor.service -f

# Restart service
sudo systemctl restart fw-remote-supervisor.service

# Check service status
sudo systemctl status fw-remote-supervisor.service

# Edit configuration
nano ~/.config/fw_cycle_monitor/remote_supervisor.json

# Test API connectivity
curl -H "X-API-Key: $API_KEY" http://$PI_IP:8443/stacklight/status

# Turn all lights off immediately
curl -H "X-API-Key: $API_KEY" -X POST http://$PI_IP:8443/stacklight/off
```

---

## Support

If you encounter issues not covered in this guide:

1. Check the logs first: `sudo journalctl -u fw-remote-supervisor.service -n 100`
2. Verify configuration: `cat ~/.config/fw_cycle_monitor/remote_supervisor.json`
3. Test basic API connectivity before testing stack lights
4. Start in mock mode before connecting real hardware
5. Verify GPIO permissions if using real hardware

---

## Next Steps

✅ Installation complete
✅ API tested
✅ Hardware tested (if connected)
✅ Dashboard tested
→ Ready for ERP integration!

Refer to `STACKLIGHT_IMPLEMENTATION_PLAN.md` Phase 3 for ERP integration details.
