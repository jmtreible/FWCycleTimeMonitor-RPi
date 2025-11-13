# Debug Self-Test Not Running at Boot

## Diagnostic Steps

Please run these commands on your Raspberry Pi to diagnose why the self-test isn't running:

### 1. Check Configuration

```bash
# View the config file
cat ~/.config/fw_cycle_monitor/remote_supervisor.json

# Look for these specific settings:
# "enabled": true
# "startup_self_test": true
# "mock_mode": false
```

**Expected output:**
```json
{
  "stacklight": {
    "enabled": true,
    "mock_mode": false,
    "active_low": true,
    "startup_self_test": true,
    ...
  }
}
```

---

### 2. Check Service Logs

```bash
# View the last startup logs
sudo journalctl -u fw-remote-supervisor.service -b | grep -i "self-test\|startup\|stacklight"

# Or view all logs since last boot
sudo journalctl -u fw-remote-supervisor.service --since "10 minutes ago"
```

**What to look for:**
- `Refreshing settings cache on startup` ← Service started
- `Initializing stack light controller for startup self-test` ← Self-test starting
- `Running startup self-test sequence for stack lights` ← Actually running
- `Startup self-test sequence completed successfully` ← Completed

**If you see:**
- `Stack light control is disabled in configuration` → enabled: false
- `startup_self_test is false` → startup_self_test: false
- No self-test messages at all → Check logs for errors

---

### 3. Manual Test

If the self-test isn't running at boot, test manually:

```bash
# Get your API key
export API_KEY=$(cat ~/.config/fw_cycle_monitor/remote_supervisor.json | grep -oP '(?<="api_keys": \[")[^"]+')

# Restart the service and watch logs in real-time
sudo systemctl restart fw-remote-supervisor.service
sudo journalctl -u fw-remote-supervisor.service -f
```

Watch for the self-test messages in the logs. It should start within 5-10 seconds of service startup.

---

### 4. Check Service Status

```bash
# Make sure service is actually starting at boot
sudo systemctl is-enabled fw-remote-supervisor.service
# Should output: "enabled"

# Check if service is currently running
sudo systemctl status fw-remote-supervisor.service
# Should show "active (running)"
```

---

### 5. Force Configuration Check

```bash
# Test if the config is being read correctly
python3 << 'EOF'
import sys
sys.path.insert(0, '/opt/fw-cycle-monitor/src')

from fw_cycle_monitor.remote_supervisor.settings import get_settings

settings = get_settings()
print(f"Stack light enabled: {settings.stacklight.enabled}")
print(f"Startup self-test: {settings.stacklight.startup_self_test}")
print(f"Mock mode: {settings.stacklight.mock_mode}")
print(f"Pins: Green={settings.stacklight.green_pin}, Amber={settings.stacklight.amber_pin}, Red={settings.stacklight.red_pin}")
EOF
```

**Expected output:**
```
Stack light enabled: True
Startup self-test: True
Mock mode: False
Pins: Green=26, Amber=20, Red=21
```

---

## Common Issues and Fixes

### Issue 1: `startup_self_test` is missing from config

**Fix:**
```bash
nano ~/.config/fw_cycle_monitor/remote_supervisor.json

# Add "startup_self_test": true to the stacklight section:
"stacklight": {
  "enabled": true,
  "mock_mode": false,
  "active_low": true,
  "startup_self_test": true,  # <-- Add this line
  "pins": {
    ...
  }
}

# Restart service
sudo systemctl restart fw-remote-supervisor.service
```

---

### Issue 2: Service starts before network is ready

If the service starts too early, the stack light initialization might fail.

**Check:**
```bash
# View the service unit file
cat /etc/systemd/system/fw-remote-supervisor.service | grep -A 3 "\[Unit\]"
```

**Should see:**
```
[Unit]
Description=FW Cycle Monitor Remote Supervisor API
After=network-online.target
Wants=network-online.target
```

---

### Issue 3: GPIO permissions not set up

**Check:**
```bash
# Verify user is in gpio group
groups operation1 | grep gpio

# If not in gpio group, the self-test might fail silently
```

**Fix:**
```bash
sudo usermod -a -G gpio operation1

# Restart service
sudo systemctl restart fw-remote-supervisor.service
```

---

### Issue 4: Service crashes during self-test

**Check for crashes:**
```bash
# Look for errors or crashes
sudo journalctl -u fw-remote-supervisor.service -n 100 | grep -i "error\|fail\|crash\|exception"
```

**Common errors:**
- `RuntimeError: Not running on a RPi` → RPi.GPIO not available
- `Permission denied` → GPIO permissions issue
- `No module named 'RPi'` → GPIO library not installed

---

## Manual Self-Test Trigger

If you want to manually trigger the self-test:

```bash
# Method 1: Restart the service (triggers on startup)
sudo systemctl restart fw-remote-supervisor.service

# Method 2: Use the API directly (if self-test endpoint exists)
export API_KEY="your-api-key"
curl -H "X-API-Key: $API_KEY" -X POST http://localhost:8443/stacklight/test
```

---

## Expected Boot Behavior

When the Raspberry Pi boots:

1. **System starts** (~5-10 seconds)
2. **Network comes online** (~10-20 seconds)
3. **fw-remote-supervisor.service starts** (~20-30 seconds after boot)
4. **Self-test runs automatically** (~30-35 seconds after boot)
5. **Self-test completes** (~56-61 seconds after boot - self-test is 26 seconds)

**Total time from boot to self-test completion:** ~1 minute

To verify, after a reboot:
```bash
# Check uptime
uptime

# Check when service started
sudo systemctl status fw-remote-supervisor.service | grep "Active:"

# Check self-test logs
sudo journalctl -u fw-remote-supervisor.service -b | grep "self-test"
```

---

## Quick Fix Script

If everything looks correct but it's still not working:

```bash
#!/bin/bash
# Quick fix for self-test not running

echo "Checking configuration..."
cat ~/.config/fw_cycle_monitor/remote_supervisor.json | grep -A 8 "stacklight"

echo ""
echo "Restarting service..."
sudo systemctl restart fw-remote-supervisor.service

echo ""
echo "Waiting for service to start..."
sleep 3

echo ""
echo "Checking logs for self-test..."
sudo journalctl -u fw-remote-supervisor.service -n 20 | grep -i "self-test"

echo ""
echo "Current service status:"
sudo systemctl status fw-remote-supervisor.service | grep "Active:"
```

---

## What to Report Back

Please run the diagnostic steps above and share:

1. **Output of step 1** (configuration check)
2. **Output of step 2** (service logs)
3. **Output of step 5** (Python config test)
4. **Any error messages you see**

This will help me determine why the self-test isn't running at boot!
