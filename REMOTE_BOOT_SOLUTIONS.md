# Remote Boot Solutions for Raspberry Pi with PoE

## Executive Summary

**Wake-on-LAN (WoL) is NOT supported on Raspberry Pi hardware** - the Ethernet PHY doesn't support magic packets to wake from shutdown.

However, there are **THREE viable solutions** for remotely booting your PoE-powered Raspberry Pis after shutdown:

1. ✅ **Managed PoE Switch Control** (RECOMMENDED - Most Reliable)
2. ✅ **GPIO Wake Pin + External Controller** (Most Elegant)
3. ✅ **Just Don't Shut Down** (Simplest)

---

## Your Hardware

- **Raspberry Pi:** 4B (or 3B+)
- **PoE HAT:** Waveshare PoE HAT (B) - https://www.amazon.com/dp/B0928ZD7QQ
- **Network:** Managed PoE Switch (you confirmed)
- **Power:** 802.3af PoE

---

## Why Wake-on-LAN Doesn't Work

### Technical Limitations:
1. **No BIOS:** Raspberry Pi has no BIOS to respond to wake signals when powered off
2. **PHY Not Powered:** The Ethernet PHY is not powered during shutdown/halt
3. **No Wake Pin Wiring:** The PHY's WOL pin is not connected to the BCM chip
4. **Firmware Not Ready:** The firmware doesn't support wake-on-LAN signals

### What "Shutdown" Actually Means:
- When you run `shutdown -h now` on a Pi with PoE power:
  - CPU halts
  - Most components power down
  - PoE keeps board minimally powered (halt state)
  - Network interface is NOT active
  - **Cannot receive magic packets**

---

## Solution 1: Managed PoE Switch Control ⭐ RECOMMENDED

### How It Works:
1. Pi is powered by PoE (always has power available)
2. Dashboard sends API command to managed PoE switch
3. Switch disables PoE on that port (power cut)
4. Wait 2-3 seconds
5. Switch re-enables PoE on that port (power restored)
6. Pi boots automatically

### Requirements:
- ✅ Managed PoE switch with API or web interface
- ✅ Network access to switch management interface
- ✅ Switch API credentials

### Common Managed PoE Switches with API:

#### UniFi (Ubiquiti)
- **API:** Yes, via UniFi Controller
- **Port Control:** Full PoE on/off/cycle per port
- **Python Library:** `unifi_poe` (GitHub: ep1cman/unifi_poe)
- **Example:**
  ```bash
  # Install library
  pip install unifi-poe-control

  # Power cycle port
  unifi-poe-control --controller 192.168.1.1 --port 8 --action cycle
  ```

#### Cisco Small Business (SG series)
- **API:** SNMP, SSH, Web API
- **Port Control:** Yes, per-port PoE control
- **Example:** SNMP OID to disable/enable PoE

#### NETGEAR (GS series, M4250, M4300)
- **API:** SNMP, RESTful API (newer models)
- **Port Control:** Yes
- **Example:** Via NETGEAR Insight Cloud or local API

#### TP-Link (T-series, JetStream)
- **API:** SNMP, some models have HTTP API
- **Port Control:** Yes
- **Example:** SNMP commands

#### Meraki
- **API:** Full REST API
- **Port Control:** Yes
- **Example:**
  ```bash
  curl -H "X-Cisco-Meraki-API-Key: $API_KEY" \
    -X PUT \
    "https://api.meraki.com/api/v1/devices/{serial}/switch/ports/{portId}" \
    -d '{"poeEnabled": false}'
  ```

### Implementation Steps:

#### Step 1: Identify Your Switch
```bash
# What managed switch do you have?
# UniFi / Cisco / NETGEAR / TP-Link / Meraki / Other?
```

#### Step 2: Get API Credentials
- Enable API access on switch
- Create API user/token
- Document API endpoint URL

#### Step 3: Add C# Switch Control to Dashboard

Add NuGet package for HTTP API calls (already have this):
```xml
<!-- FWCycleDashboard.csproj -->
<PackageReference Include="System.Net.Http.Json" Version="8.0.0" />
```

Add switch configuration to `appsettings.json`:
```json
{
  "PoESwitch": {
    "Type": "UniFi",
    "ApiUrl": "https://192.168.1.1:8443",
    "Username": "admin",
    "Password": "your-password",
    "PortMappings": {
      "1": 8,    // Machine ID 1 is on switch port 8
      "2": 9,    // Machine ID 2 is on switch port 9
      "3": 10
    }
  }
}
```

Add `PoESwitchClient.cs`:
```csharp
public class PoESwitchClient
{
    private readonly HttpClient _httpClient;
    private readonly string _apiUrl;
    private readonly string _username;
    private readonly string _password;

    public async Task<bool> PowerCyclePortAsync(int portNumber)
    {
        // Disable PoE
        await SetPortPowerAsync(portNumber, false);

        // Wait for clean shutdown
        await Task.Delay(3000);

        // Re-enable PoE
        await SetPortPowerAsync(portNumber, true);

        return true;
    }

    private async Task<bool> SetPortPowerAsync(int portNumber, bool enabled)
    {
        // Implementation depends on your switch type
        // Example for UniFi:
        var payload = new { poe_mode = enabled ? "auto" : "off" };
        var response = await _httpClient.PostAsJsonAsync(
            $"{_apiUrl}/api/s/default/rest/device/{deviceId}/port/{portNumber}",
            payload
        );
        return response.IsSuccessStatusCode;
    }
}
```

Add to `Machine.cs`:
```csharp
public int? PoESwitchPort { get; set; }  // Which switch port this Pi is on
```

Add UI button:
```html
<button class="btn btn-outline-primary btn-sm"
        @onclick="() => BootMachine(machine)"
        disabled="@(status.IsOnline || machine.PoESwitchPort == null)">
    Boot (Power Cycle)
</button>
```

### Pros:
- ✅ Works 100% reliably
- ✅ No Pi configuration needed
- ✅ Centralized control
- ✅ Can power cycle even if Pi is frozen/unresponsive
- ✅ Uses existing infrastructure

### Cons:
- ❌ Requires managed switch with API
- ❌ Need to configure port mappings
- ❌ Hard power cycle (not graceful)
- ❌ Requires switch credentials in dashboard

---

## Solution 2: GPIO Wake Pin + External Controller

### How It Works:
1. Add a small external controller (e.g., ESP8266, Arduino, Raspberry Pi Zero W)
2. Controller connects to GPIO3 (Pin 5) and GND (Pin 6) on main Pi
3. Controller listens for HTTP requests from dashboard
4. When "boot" command received, controller shorts GPIO3 to GND momentarily
5. Main Pi wakes from halt state and boots

### Hardware Required:
- ESP8266 or ESP32 ($3-5)
- OR Raspberry Pi Zero W ($10-15)
- 2x wires per Pi (GPIO3 and GND)
- Relay module OR transistor for switching

### GPIO Wake Mechanism:
**Raspberry Pi Hardware Feature:**
- GPIO3 (Physical Pin 5) and GND (Physical Pin 6) can wake Pi from halt
- Shorting these pins momentarily triggers wake-up
- Works even when Pi is "shut down" but still powered (PoE keeps it powered)

### ESP8266 Setup:

**Wiring:**
```
ESP8266 GPIO2 ---> Transistor ---> Pi GPIO3 (Pin 5)
ESP8266 GND   ---> Pi GND (Pin 6)
```

**ESP8266 Code:**
```cpp
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

ESP8266WebServer server(80);
const int WAKE_PIN = 2;  // D4 on NodeMCU

void setup() {
  pinMode(WAKE_PIN, OUTPUT);
  digitalWrite(WAKE_PIN, HIGH);  // Open circuit normally

  WiFi.begin("YourSSID", "YourPassword");
  server.on("/wake", handleWake);
  server.begin();
}

void handleWake() {
  // Short GPIO3 to GND for 500ms
  digitalWrite(WAKE_PIN, LOW);
  delay(500);
  digitalWrite(WAKE_PIN, HIGH);

  server.send(200, "text/plain", "Wake signal sent");
}

void loop() {
  server.handleClient();
}
```

**Dashboard Integration:**
```csharp
// Add to Machine.cs
public string? WakeControllerUrl { get; set; }  // e.g., "http://192.168.1.50/wake"

// Add to RemoteSupervisorClient.cs
public async Task<bool> WakeMachineAsync(Machine machine)
{
    if (string.IsNullOrEmpty(machine.WakeControllerUrl))
        return false;

    try
    {
        var response = await _httpClient.GetAsync(machine.WakeControllerUrl);
        return response.IsSuccessStatusCode;
    }
    catch
    {
        return false;
    }
}
```

### Pi Zero W Alternative:
- Use second Pi Zero W as wake controller
- Can control multiple Pis
- More expensive but more flexible
- Can also monitor health, send alerts, etc.

### Pros:
- ✅ Elegant solution
- ✅ Low cost ($3-5 per Pi with ESP8266)
- ✅ No switch API needed
- ✅ Dedicated wake control
- ✅ Can add other monitoring functions

### Cons:
- ❌ Requires additional hardware installation
- ❌ More wiring/complexity
- ❌ Each Pi needs its own controller
- ❌ Another device to maintain
- ❌ Controller must be powered separately

---

## Solution 3: Don't Shut Down (Just Reboot)

### How It Works:
- Never actually shut down the Pi
- Only use `reboot` command
- For "off", just stop services but leave Pi running
- PoE keeps Pi powered at idle (~2-3W)

### Implementation:

**Dashboard Buttons:**
- ❌ Remove "Shutdown" button
- ✅ Keep "Reboot" button
- ✅ Add "Stop Services" button (stops monitoring but leaves Pi on)

**Power Consumption:**
- Idle Pi 4 with PoE HAT: ~2-3W
- Annual cost @ $0.12/kWh: ~$2.60 per Pi per year
- For 10 Pis: ~$26/year

**Benefits:**
- Always accessible remotely
- Instant "boot" (already running)
- No additional hardware
- No complex configurations

### Service Stop Command (Instead of Shutdown):
```python
# Add to api.py
@app.post("/system/stop-services")
async def stop_services(_: str | None = Depends(require_api_key)):
    """Stop monitoring services but leave system running."""
    try:
        subprocess.run(["sudo", "systemctl", "stop", "fw-cycle-monitor.service"], check=True)
        subprocess.run(["sudo", "systemctl", "stop", "fw-remote-supervisor.service"], check=True)
        return {"success": True, "message": "Services stopped - system still running"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Pros:
- ✅ Simplest solution
- ✅ No hardware needed
- ✅ No complex setup
- ✅ Always accessible
- ✅ Low power cost

### Cons:
- ❌ Pi always consuming power (minimal)
- ❌ Can't fully "shut down" remotely
- ❌ Services still running in background
- ❌ No true power savings

---

## Recommended Solution

### For Your Setup:

**Primary Recommendation: Solution 1 (Managed PoE Switch)**

**Why:**
- ✅ You already have a managed switch
- ✅ Most reliable (100% success rate)
- ✅ Centralized control
- ✅ Works even if Pi is frozen
- ✅ No additional hardware per Pi
- ✅ Clean power cycle

**Implementation Priority:**
1. **Phase 2a** - Add Shutdown and Reboot buttons (straightforward)
2. **Phase 2b** - Identify your managed switch model
3. **Phase 2c** - Implement switch API client
4. **Phase 2d** - Configure port mappings in database
5. **Phase 2e** - Add "Boot" button using power cycle

**Fallback:** Solution 3 (Don't Shut Down)
- If switch API is too complex
- Or if you can't access switch management
- Just skip shutdown feature, use reboot only

---

## Next Steps - Your Choice

### Option A: Implement Solution 1 (Switch Control)
**I need from you:**
1. What brand/model is your managed PoE switch?
2. Do you have admin access to the switch?
3. Which ports are your Pis connected to?

**I will:**
1. Research your switch's API documentation
2. Implement switch client in C#
3. Add port mapping configuration
4. Add Boot button to dashboard

### Option B: Implement Solution 3 (No Shutdown)
**I will:**
1. Add Reboot button (already planned for Phase 2)
2. Add "Stop Services" button instead of shutdown
3. Update UI to reflect "services stopped" vs "powered off"
4. Document power consumption expectations

### Option C: Research Solution 2 (GPIO Wake)
**If you want the ESP8266 option:**
1. I'll create detailed wiring diagrams
2. Provide ESP8266 firmware
3. Add dashboard wake controller support
4. Provide BOM (bill of materials)

**Which option do you prefer?** I recommend Option A if you can provide switch details!

---

## Technical References

- Raspberry Pi GPIO Wake: https://forums.raspberrypi.com/viewtopic.php?t=24682
- UniFi PoE Control: https://github.com/ep1cman/unifi_poe
- Waveshare PoE HAT (B) Wiki: https://www.waveshare.com/wiki/PoE_HAT_(B)
- Pi Power Button Tutorial: https://learn.sparkfun.com/tutorials/raspberry-pi-safe-reboot-and-shutdown-button

---

## Summary Table

| Solution | Reliability | Cost | Complexity | Remote Boot | Hard Power Cycle |
|----------|-------------|------|------------|-------------|------------------|
| **Switch Control** | ⭐⭐⭐⭐⭐ | $0 (have switch) | Medium | ✅ Yes | ✅ Yes |
| **GPIO Wake** | ⭐⭐⭐⭐ | ~$5/Pi | High | ✅ Yes | ❌ No |
| **Don't Shutdown** | ⭐⭐⭐⭐⭐ | ~$3/Pi/year | Low | N/A (always on) | N/A |

**Recommendation: Start with Switch Control (Solution 1)**
