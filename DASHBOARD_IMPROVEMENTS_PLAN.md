# Dashboard Improvements Implementation Plan

## Current State Analysis

### ✅ Already Implemented
- Stack light controls (Green/Amber/Red buttons)
- Test sequence button
- All Off button
- Visual indicators (buttons change color when active)
- Service start/stop/restart controls
- Machine status monitoring
- Auto-refresh functionality

### ✅ Data Already Available But Not Displayed
- **Metrics data** is being fetched (`GetMetricsAsync`)
  - `LastCycleSeconds` - most recent cycle time
  - `WindowAverages` - dictionary of time windows (5min, 15min, 30min, 60min, etc.)
- Metrics are in `MachineStatus.Metrics` but not shown in UI

---

## Improvement Tasks

### 1. ✅ Display Average Cycle Time Information

**Status:** Data available, just needs UI display

**Implementation:**
Add metrics display to each machine card in `Home.razor`

**UI Design:**
```
┌─────────────────────────────────┐
│ Machine 01          [active]    │
├─────────────────────────────────┤
│ Group: Line A                   │
│ 192.168.1.100:8443              │
│                                  │
│ Cycle Times:                    │
│ Last: 45.2s                     │
│ 5min avg:  46.1s                │
│ 15min avg: 45.8s                │
│ 30min avg: 46.3s                │
│ 60min avg: 45.9s                │
│                                  │
│ Stack Lights: [G][A][R]         │
│ [Test] [All Off]                │
└─────────────────────────────────┘
```

**Code Changes:**
- Add metrics display section in card body
- Format times in seconds with 1 decimal place
- Show "No data" when null
- Color code based on thresholds (optional)

**Files to Modify:**
- `FWCycleDashboard/Components/Pages/Home.razor`

---

### 2. ✅ Visual Stack Light Indicators

**Status:** Buttons already change color when active (DONE)

**Current Implementation:**
- Green button: `btn-success` (solid) when on, `btn-outline-success` when off
- Amber button: `btn-warning` (solid) when on, `btn-outline-warning` when off
- Red button: `btn-danger` (solid) when on, `btn-outline-danger` when off

**Enhancement Options:**

**Option A:** Add LED-style indicators above buttons
```html
<div class="d-flex gap-2 mb-2">
    <div class="led-indicator @(status.StackLight.Green ? "led-green-on" : "led-off")"></div>
    <div class="led-indicator @(status.StackLight.Amber ? "led-amber-on" : "led-off")"></div>
    <div class="led-indicator @(status.StackLight.Red ? "led-red-on" : "led-off")"></div>
</div>
```

**Option B:** Traffic light style indicator
```
🟢 ⚫ ⚫  (Green on)
⚫ 🟡 ⚫  (Amber on)
⚫ ⚫ 🔴  (Red on)
```

**Recommendation:** Option A with CSS for better appearance

**Files to Modify:**
- `FWCycleDashboard/Components/Pages/Home.razor`
- `FWCycleDashboard/wwwroot/app.css` (add LED indicator styles)

---

### 3. ✅ Test Sequence Button

**Status:** ALREADY IMPLEMENTED (line 134-138 in Home.razor)

Button exists and calls `TestStackLight(machine)` method.

**No changes needed.**

---

### 4. 🔄 Remote Power Management (Shutdown/Reboot/Boot)

**Status:** Requires new API endpoints and implementation

#### 4.1 Shutdown and Reboot (Straightforward)

**Backend Implementation:**

Add new API endpoints to `api.py`:

```python
@app.post("/system/shutdown")
async def shutdown_system(_: str | None = Depends(require_api_key)):
    """Shut down the Raspberry Pi."""
    try:
        subprocess.run(["sudo", "shutdown", "-h", "now"], check=True)
        return {"success": True, "message": "System shutting down"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/system/reboot")
async def reboot_system(_: str | None = Depends(require_api_key)):
    """Reboot the Raspberry Pi."""
    try:
        subprocess.run(["sudo", "reboot"], check=True)
        return {"success": True, "message": "System rebooting"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Sudo Configuration:**
Add to `/etc/sudoers.d/fw-cycle-monitor`:
```
operation1 ALL=(ALL) NOPASSWD: /sbin/shutdown, /sbin/reboot
```

**Dashboard Implementation:**
- Add C# methods to `RemoteSupervisorClient.cs`
- Add buttons to dashboard UI
- Add confirmation dialogs (prevent accidental shutdowns)

**Safety Features:**
- Require confirmation dialog
- Show countdown timer (e.g., "Shutting down in 5... 4... 3...")
- Log all power actions
- Disable button after click to prevent double-clicks

---

#### 4.2 Remote Boot (Wake-on-LAN)

**Challenge:** Raspberry Pi must be powered to receive network commands. PoE solves this!

**PoE + Wake-on-LAN Strategy:**

Since your Pis are PoE-powered:
1. Pi is always powered (even when "shut down")
2. After shutdown, Pi is in low-power state but PoE keeps it powered
3. Wake-on-LAN (WoL) packet can wake it from low-power state

**Requirements:**
1. PoE HAT that supports Wake-on-LAN (not all do)
2. Enable WoL in Raspberry Pi configuration
3. Dashboard machine must be on same network or have routing configured

**Implementation Steps:**

**Step 1: Enable WoL on Raspberry Pi**

Check if your PoE HAT supports WoL:
```bash
# Check network interface
ip link show

# Check WoL status
sudo ethtool eth0 | grep "Wake-on"
```

Enable WoL:
```bash
# Install ethtool
sudo apt-get install ethtool

# Enable WoL
sudo ethtool -s eth0 wol g

# Make persistent (add to /etc/rc.local or systemd service)
```

Create systemd service for WoL:
```ini
[Unit]
Description=Enable Wake-on-LAN
After=network.target

[Service]
Type=oneshot
ExecStart=/sbin/ethtool -s eth0 wol g

[Install]
WantedBy=multi-user.target
```

**Step 2: Dashboard WoL Implementation**

Add WoL library to dashboard:
```xml
<!-- FWCycleDashboard.csproj -->
<PackageReference Include="WakeOnLan" Version="2.0.0" />
```

Add WoL method to `RemoteSupervisorClient.cs`:
```csharp
public async Task<(bool success, string? error)> WakeMachineAsync(Machine machine)
{
    try
    {
        // Get MAC address from database or config
        var macAddress = machine.MacAddress;
        if (string.IsNullOrEmpty(macAddress))
        {
            return (false, "MAC address not configured for this machine");
        }

        // Send magic packet
        var mac = PhysicalAddress.Parse(macAddress.Replace(":", "").Replace("-", ""));
        await WOL.WakeAsync(mac);

        return (true, null);
    }
    catch (Exception ex)
    {
        return (false, ex.Message);
    }
}
```

Add MAC address field to Machine model:
```csharp
// Data/Machine.cs
public string? MacAddress { get; set; }
```

**Step 3: Dashboard UI**

Add power management buttons:
```html
<div class="btn-group btn-group-sm" role="group">
    <button class="btn btn-outline-primary"
            @onclick="() => WakeMachine(machine)"
            disabled="@(status.IsOnline)">
        Boot
    </button>
    <button class="btn btn-outline-warning"
            @onclick="() => RebootMachine(machine)"
            disabled="@(!status.IsOnline)">
        Reboot
    </button>
    <button class="btn btn-outline-danger"
            @onclick="() => ShutdownMachine(machine)"
            disabled="@(!status.IsOnline)">
        Shutdown
    </button>
</div>
```

**Alternative: Network-Controlled Power Switch**

If WoL doesn't work with your PoE HAT:

**Option 1:** Smart PoE Switch
- Use a managed PoE switch with API (e.g., UniFi, Cisco)
- Dashboard sends command to switch to disable/enable PoE port
- Cycling power forces reboot

**Option 2:** Smart Power Strip/Relay
- Connect PoE injector to smart relay
- Dashboard controls relay via HTTP API
- Power cycle = reboot

**Option 3:** GPIO-Controlled Power (Advanced)**
- Add external relay to Pi GPIO
- Relay controls its own power input
- Pi can trigger its own power cycle (requires careful circuit design)

---

## Implementation Priority

### Phase 1: Quick Wins (1-2 hours)
1. ✅ Add cycle time metrics display to dashboard
2. ✅ Add LED-style stack light indicators
3. ✅ Test sequence button (already done)

### Phase 2: Power Management - Shutdown/Reboot (2-3 hours)
1. Add shutdown/reboot API endpoints
2. Configure sudo permissions
3. Add dashboard UI buttons
4. Add confirmation dialogs
5. Test thoroughly

### Phase 3: Remote Boot - Research & Test (2-4 hours)
1. Test WoL capability with current PoE HAT
2. Implement WoL if supported
3. Or research alternative power control methods
4. Document findings and recommendations

---

## Files to Modify

### Backend (Raspberry Pi)
- `src/fw_cycle_monitor/remote_supervisor/api.py` - Add power management endpoints
- `scripts/install_fw_cycle_monitor.sh` - Add sudo permissions for shutdown/reboot
- `/etc/sudoers.d/fw-cycle-monitor` - sudo configuration

### Dashboard (C#)
- `FWCycleDashboard/Components/Pages/Home.razor` - UI updates
- `FWCycleDashboard/Services/RemoteSupervisorClient.cs` - API client methods
- `FWCycleDashboard/Services/RemoteSupervisorModels.cs` - Add response models
- `FWCycleDashboard/Data/Machine.cs` - Add MacAddress field (for WoL)
- `FWCycleDashboard/wwwroot/app.css` - LED indicator styles
- `FWCycleDashboard/FWCycleDashboard.csproj` - Add WoL package (if implementing WoL)

---

## Testing Checklist

### Metrics Display
- [ ] Last cycle time shows correctly
- [ ] Average times display for all windows
- [ ] "No data" shows when metrics unavailable
- [ ] Times formatted correctly (1 decimal place)

### Stack Light Indicators
- [ ] LED indicators match button states
- [ ] Indicators update when lights change
- [ ] Visual style is clear and attractive

### Power Management
- [ ] Shutdown button shows confirmation
- [ ] Shutdown actually shuts down Pi
- [ ] Reboot button shows confirmation
- [ ] Reboot actually reboots Pi
- [ ] Buttons disabled/enabled correctly based on online status
- [ ] Actions logged to command history

### Wake-on-LAN (if implemented)
- [ ] WoL enabled on Pi
- [ ] MAC address configured for each machine
- [ ] Boot button sends magic packet
- [ ] Pi actually wakes up from shutdown state
- [ ] Boot button disabled when machine online

---

## Safety Considerations

### Power Management Risks
1. **Accidental Shutdown:** Use confirmation dialogs
2. **Data Loss:** Ensure services shut down gracefully
3. **Lost Access:** Test thoroughly before deploying to production
4. **Multiple Simultaneous Shutdowns:** Add rate limiting

### Recommended Safeguards
```csharp
// Confirmation dialog
var confirmed = await JSRuntime.InvokeAsync<bool>(
    "confirm",
    $"Are you sure you want to shut down {machine.MachineId}? This cannot be undone remotely."
);
if (!confirmed) return;

// Log action
_logger.LogWarning("User initiated shutdown for machine {MachineId}", machine.Id);

// Add to command history
DbContext.CommandHistory.Add(new CommandHistory {
    MachineId = machine.Id,
    Command = "system:shutdown",
    Success = true,
    Timestamp = DateTime.UtcNow
});
```

---

## Questions to Answer Before Implementation

### For Remote Boot:
1. **What PoE HAT model are you using?**
   - Official Raspberry Pi PoE HAT?
   - Third-party PoE HAT?

2. **Does your PoE switch support port control?**
   - Managed switch with API?
   - Unmanaged switch?

3. **Acceptable boot method?**
   - Wake-on-LAN preferred?
   - OK with power cycling via smart switch?
   - Need fully automated solution?

### For Dashboard:
1. **Which metrics to show by default?**
   - All time windows or just a few?
   - Last cycle time always visible?

2. **Stack light indicator style preference?**
   - LED circles (Option A)?
   - Traffic light emoji (Option B)?
   - Current button style is sufficient?

3. **Power button placement?**
   - In machine card footer?
   - Separate power management section?
   - Context menu/dropdown?

---

## Next Steps

1. **Review this plan** and confirm approach
2. **Answer questions above** to finalize implementation details
3. **Start with Phase 1** (metrics + LED indicators) - safe and straightforward
4. **Test Phase 2** (shutdown/reboot) on ONE Pi first
5. **Research Phase 3** (Wake-on-LAN) - may require hardware verification

Would you like me to proceed with Phase 1 (metrics display + LED indicators) first?
