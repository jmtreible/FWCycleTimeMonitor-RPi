# Troubleshooting Guide - Stack Light GUI Buttons Not Working

## Diagnostic Steps

Please run these commands on the Raspberry Pi and share the results:

### 1. Check if the API is responding

```bash
# Get your API key
cat ~/.config/fw_cycle_monitor/remote_supervisor.json | grep -A 1 api_keys

# Test the stack light status endpoint
export API_KEY="your-key-from-above"
curl -H "X-API-Key: $API_KEY" http://localhost:8443/stacklight/status
```

**Expected result:** Should return JSON with green, amber, red states

---

### 2. Test setting a light via API directly

```bash
# Try to set green light on
curl -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"green": true, "amber": false, "red": false}' \
  http://localhost:8443/stacklight/set

# Check the status again
curl -H "X-API-Key: $API_KEY" http://localhost:8443/stacklight/status
```

**Expected result:**
- First command should return success: true
- Second command should show green: true

---

### 3. Check service logs for errors

```bash
# Watch the logs while you try to click a button in the GUI
sudo journalctl -u fw-remote-supervisor.service -f
```

Then click a stack light button in the GUI and see what appears in the logs.

---

### 4. Check dashboard connection

From your dashboard machine (where you're accessing the web UI):

```bash
# Replace with your Pi's IP address
export PI_IP="192.168.x.x"
export API_KEY="your-key"

# Test from dashboard machine
curl -H "X-API-Key: $API_KEY" http://$PI_IP:8443/stacklight/status
```

---

### 5. Check browser console for errors

In your web browser:
1. Open the FWCycleDashboard
2. Press **F12** to open Developer Tools
3. Click on the **Console** tab
4. Try clicking a stack light button
5. Look for any red error messages

---

## Common Issues and Fixes

### Issue 1: API returns 404 "Stack light control is disabled"

**Fix:**
```bash
nano ~/.config/fw_cycle_monitor/remote_supervisor.json
# Ensure: "enabled": true
sudo systemctl restart fw-remote-supervisor.service
```

---

### Issue 2: Buttons are greyed out (disabled)

**Cause:** Dashboard thinks the machine is offline

**Fix:**
1. Check if the remote supervisor service is running:
   ```bash
   sudo systemctl status fw-remote-supervisor.service
   ```
2. Verify the IP address is correct in the dashboard machine configuration

---

### Issue 3: Buttons click but nothing happens

**Possible causes:**
1. **API key mismatch** - Dashboard using wrong API key
2. **Network issue** - Dashboard can't reach the Pi
3. **Service crashed** - Remote supervisor service stopped

**Debug:**
```bash
# Check if service is running
sudo systemctl status fw-remote-supervisor.service

# Check for crashes
sudo journalctl -u fw-remote-supervisor.service -n 50 | grep -i error

# Restart service
sudo systemctl restart fw-remote-supervisor.service
```

---

### Issue 4: Lights worked before, but not after restart

**Possible cause:** The startup self-test might be interfering

**Test:**
1. Wait 30 seconds after service restart (let self-test complete)
2. Try clicking the buttons again

**Or temporarily disable self-test:**
```bash
nano ~/.config/fw_cycle_monitor/remote_supervisor.json
# Set: "startup_self_test": false
sudo systemctl restart fw-remote-supervisor.service
```

---

## Quick Test Sequence

Run these in order:

```bash
# 1. Get API key
export API_KEY=$(cat ~/.config/fw_cycle_monitor/remote_supervisor.json | grep -oP '(?<="api_keys": \[")[^"]+')
echo "API Key: $API_KEY"

# 2. Check service is running
sudo systemctl status fw-remote-supervisor.service | grep Active

# 3. Test API directly
curl -H "X-API-Key: $API_KEY" http://localhost:8443/stacklight/status

# 4. Set green light
curl -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"green": true, "amber": false, "red": false}' \
  http://localhost:8443/stacklight/set

# 5. Verify green is on
curl -H "X-API-Key: $API_KEY" http://localhost:8443/stacklight/status

# 6. Turn all off
curl -H "X-API-Key: $API_KEY" -X POST http://localhost:8443/stacklight/off
```

---

## What to Report Back

Please share:

1. **Output of step 1** (status endpoint response)
2. **Output of step 2** (set light response)
3. **Any errors in service logs** (step 3)
4. **Browser console errors** (step 5)
5. **Specific behavior:**
   - Do the buttons change color when clicked?
   - Do the physical lights respond?
   - Does the "Test" button work but individual buttons don't?
   - Does "All Off" work?

This will help identify the exact issue!
