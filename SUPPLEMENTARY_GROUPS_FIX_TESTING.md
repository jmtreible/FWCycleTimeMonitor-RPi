# SupplementaryGroups=gpio Fix - Testing Guide

## What Was Fixed

### The Problem
Previously, when the `fw-remote-supervisor` service was restarted using `systemctl restart` (either manually or via the GUI's "Restart Remote Supervisor" button), GPIO permissions would be lost, causing the service to fall back to MOCK mode.

**Symptoms:**
- Stack light controls worked perfectly after a system reboot
- After using "Restart Remote Supervisor" button or `sudo systemctl restart fw-remote-supervisor`, GPIO would fail with: `lgpio.error: 'GPIO not allocated'`
- Service would fall back to MOCK mode (logging only, no hardware control)
- Dashboard buttons would stop controlling the physical lights
- Only a full system reboot would restore GPIO functionality

**Root Cause:**
The systemd service file didn't explicitly include `SupplementaryGroups=gpio`. While the user was added to the gpio group, systemd only applied this group membership when the service started at boot time, not when manually restarted.

### The Solution
Added `SupplementaryGroups=gpio` to the systemd service file, which explicitly tells systemd to always apply gpio group membership to the service process, regardless of how it's started (boot, manual restart, etc.).

**Changes Made:**
1. Updated `systemd/fw-remote-supervisor.service` to include `SupplementaryGroups=gpio`
2. Updated `scripts/install_fw_cycle_monitor.sh` to generate service files with this setting
3. Updated documentation to reflect the fix

**Files Changed:**
- `systemd/fw-remote-supervisor.service` - Added SupplementaryGroups=gpio at line 12
- `scripts/install_fw_cycle_monitor.sh` - Added SupplementaryGroups=gpio at line 420
- `STACK_LIGHT_IMPLEMENTATION_SUMMARY.md` - Updated troubleshooting section

**Commit:** c5826e4 - "Add SupplementaryGroups=gpio to remote supervisor service"

---

## Testing Instructions for Next Session

### Prerequisites
1. Pull latest changes from GitHub (branch: feature/stack-light-control)
2. SSH into the Raspberry Pi
3. Have the dashboard open on your Windows PC

### Test Procedure

#### Step 1: Re-run the Installer
Since you have an existing installation, the installer needs to update your systemd service file:

```bash
cd ~/FWCycleTimeMonitor-RPi
git pull origin feature/stack-light-control
sudo ./scripts/install_fw_cycle_monitor.sh
```

The installer will detect the existing installation and update the systemd service file with the new `SupplementaryGroups=gpio` setting.

#### Step 2: Verify Service File Updated
Check that the service file now includes the SupplementaryGroups line:

```bash
sudo systemctl cat fw-remote-supervisor.service | grep -A 3 "\[Service\]"
```

**Expected output should include:**
```
[Service]
Type=simple
User=pi1
Group=pi1
SupplementaryGroups=gpio
```

#### Step 3: Restart the Service
Restart the service to apply the changes:

```bash
sudo systemctl restart fw-remote-supervisor
```

#### Step 4: Check Service Status
Verify the service started successfully:

```bash
sudo systemctl status fw-remote-supervisor
```

Should show "active (running)"

#### Step 5: Test GPIO Initialization
Check the logs to confirm GPIO initialization succeeded (not MOCK mode):

```bash
sudo journalctl -u fw-remote-supervisor -n 50 | grep -i "gpio\|mock\|stack"
```

**What to look for:**
- ✅ Should see: "Stack light controller initialized" (without "MOCK MODE")
- ✅ Should NOT see: "lgpio.error: 'GPIO not allocated'"
- ✅ Should NOT see: "Falling back to mock mode"

#### Step 6: Test Dashboard Control
On the dashboard:
1. Click the Green button
2. Verify the physical green LED turns on
3. Click the Amber button
4. Verify the physical amber LED turns on
5. Click the Red button
6. Verify the physical red LED turns on
7. Click "All Off"
8. Verify all LEDs turn off

**Status so far:** Dashboard should work ✅

#### Step 7: Test Config Change + Restart Cycle (THE CRITICAL TEST)
This is the scenario that previously failed:

1. Edit the config file:
```bash
nano ~/.config/fw_cycle_monitor/remote_supervisor.json
```

2. Change `active_low` from `false` to `true` (or vice versa - just change something)

3. Save and exit (Ctrl+X, Y, Enter)

4. **Option A - Via GUI:**
   - Launch the GUI: `fw-cycle-monitor-gui`
   - Click "Reload Config" button
   - Click "Restart Remote Supervisor" button

   **Option B - Via Command Line:**
   ```bash
   sudo systemctl restart fw-remote-supervisor
   ```

5. **Critical Check:** Watch the logs during restart:
```bash
sudo journalctl -u fw-remote-supervisor -f
```

6. From the **dashboard**, click the Green button

**Expected Behavior (SHOULD NOW WORK):**
- ✅ Physical green LED should turn on (with inverted behavior due to active_low change)
- ✅ Logs should show hardware GPIO control, NOT mock mode
- ✅ Dashboard should control lights successfully
- ✅ NO system reboot required

**Previous Behavior (SHOULD NOT HAPPEN ANYMORE):**
- ❌ GPIO permission denied
- ❌ Falling back to mock mode
- ❌ Dashboard buttons don't control physical lights
- ❌ Would require full system reboot to restore functionality

#### Step 8: Restore Original Config
Change the config back to your preferred setting:

```bash
nano ~/.config/fw_cycle_monitor/remote_supervisor.json
# Set active_low back to false (for breadboard)
```

Then restart again and verify it still works.

---

## Success Criteria

The fix is successful if:

1. ✅ **Service file includes** `SupplementaryGroups=gpio`
2. ✅ **Dashboard controls work** after fresh install
3. ✅ **Dashboard controls work** after `systemctl restart fw-remote-supervisor`
4. ✅ **Dashboard controls work** after config change + restart cycle
5. ✅ **No "GPIO not allocated" errors** in logs after restart
6. ✅ **No fallback to mock mode** after restart
7. ✅ **No system reboot required** to restore GPIO functionality

---

## What to Report

After testing, please report:

### 1. Service File Check
```bash
sudo systemctl cat fw-remote-supervisor.service | grep SupplementaryGroups
```
Output: [paste here]

### 2. Restart Test Logs
```bash
sudo journalctl -u fw-remote-supervisor -n 100 | grep -E "GPIO|mock|Stack light"
```
Output: [paste here]

### 3. Dashboard Control Test Results
- [ ] Green button works after restart
- [ ] Amber button works after restart
- [ ] Red button works after restart
- [ ] All Off button works after restart
- [ ] Test Sequence works after restart

### 4. Config Change + Restart Cycle Results
- [ ] Changed config successfully
- [ ] Restarted service (via GUI or systemctl)
- [ ] Dashboard still controls lights (no reboot needed)
- [ ] Logs show hardware mode (not mock mode)

---

## Troubleshooting If Test Fails

### If SupplementaryGroups line is missing from service file:
The installer might not have updated it. Manually edit:
```bash
sudo nano /etc/systemd/system/fw-remote-supervisor.service
```
Add this line under `[Service]`:
```
SupplementaryGroups=gpio
```
Then reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart fw-remote-supervisor
```

### If still getting GPIO errors after restart:
Check if user is in gpio group:
```bash
id pi1 | grep gpio
```
If not in group, add manually:
```bash
sudo usermod -a -G gpio pi1
```
Then restart service (NOT reboot):
```bash
sudo systemctl restart fw-remote-supervisor
```

### If dashboard still doesn't work:
Check API key matches between:
```bash
cat ~/.config/fw_cycle_monitor/remote_supervisor.json
```
And dashboard machine configuration.

---

## Expected Timeline

- **Install/Update:** 2-3 minutes
- **Testing Steps 1-6:** 5 minutes
- **Critical Test (Step 7):** 2 minutes
- **Total:** ~10 minutes

---

## Notes

- This fix eliminates the need for system reboots when changing stack light configuration
- The GUI "Restart Remote Supervisor" button now works correctly
- Multiple config change cycles can be performed without ever rebooting
- This is a critical usability improvement for production deployment

---

**Created:** 2025-11-12
**Branch:** feature/stack-light-control
**Commit:** c5826e4
**Status:** Ready for Testing
