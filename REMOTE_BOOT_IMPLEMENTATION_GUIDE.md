# Remote Boot Implementation Guide

This guide explains how to set up and configure remote boot functionality for your Raspberry Pis using PoE switch control.

## Overview

The dashboard now includes a framework for controlling PoE switch ports to enable remote power cycling (boot) of Raspberry Pis after shutdown.

**Status:** Framework prepared, awaiting switch purchase and configuration.

---

## What's Been Implemented

### 1. Database Schema
- Added `PoESwitchIp` field to Machine table (switch IP address)
- Added `PoESwitchPort` field to Machine table (port number on switch)

### 2. PoE Switch Client Interface
- `IPoESwitchClient` - Generic interface for any managed switch
- Methods: `PowerCyclePortAsync`, `EnablePortAsync`, `DisablePortAsync`, `GetPortStatusAsync`

### 3. TP-Link JetStream Client (Placeholder)
- `TPLinkJetStreamClient` - Implementation framework for TP-Link switches
- Ready to be configured once switch model is known
- Includes authentication, session management, error handling

### 4. Documentation
- `POE_SWITCH_RECOMMENDATIONS.md` - Switch purchasing guide
- `REMOTE_BOOT_SOLUTIONS.md` - Technical research and alternatives
- This file - Implementation guide

---

## Configuration Steps (After Switch Purchase)

### Step 1: Update appsettings.json

Add PoE switch configuration:

```json
{
  "PoESwitch": {
    "Type": "TPLink",
    "Username": "admin",
    "Password": "your-switch-password",
    "BaseUrl": "https://192.168.1.10",
    "Enabled": true
  }
}
```

### Step 2: Configure Machine Port Mappings

For each machine in the database, set:
- `PoESwitchIp` - IP address of the switch that machine is connected to
- `PoESwitchPort` - Port number on that switch

**Via SQL:**
```sql
UPDATE Machines
SET PoESwitchIp = '192.168.1.10',
    PoESwitchPort = 1
WHERE MachineId = 'Press-01';

UPDATE Machines
SET PoESwitchIp = '192.168.1.10',
    PoESwitchPort = 2
WHERE MachineId = 'Press-02';
```

**Or via Dashboard UI** (to be added in Phase 2):
- Machine edit form will have fields for switch IP and port

### Step 3: Implement Switch-Specific API

Once you have the switch model, update `TPLinkJetStreamClient.cs`:

#### For TP-Link JetStream with Web GUI:

Replace the TODO sections with actual API calls:

```csharp
private async Task<string?> AuthenticateAsync(string switchIp)
{
    var loginData = new
    {
        username = _username,
        password = _password
    };

    var response = await _httpClient.PostAsJsonAsync(
        $"https://{switchIp}/login",
        loginData
    );

    // Parse session cookie or token
    // Store in _sessionTokens[switchIp]
}

private async Task<(bool success, string? error)> SetPortPoEStateAsync(
    string switchIp,
    int portNumber,
    bool enabled)
{
    var token = await AuthenticateAsync(switchIp);

    var data = new
    {
        port = portNumber,
        poeMode = enabled ? "auto" : "off"
    };

    var response = await _httpClient.PostAsJsonAsync(
        $"https://{switchIp}/api/poe/port/{portNumber}",
        data
    );

    return (response.IsSuccessStatusCode, null);
}
```

#### For TP-Link with Omada SDN:

```csharp
// Authenticate to Omada Controller
private async Task<string?> AuthenticateAsync(string switchIp)
{
    var response = await _httpClient.PostAsJsonAsync(
        $"https://omada-controller:8043/api/v2/login",
        new { username = _username, password = _password }
    );

    var result = await response.Content.ReadFromJsonAsync<OmadaLoginResponse>();
    return result?.Token;
}

// Control via Omada API
private async Task<(bool success, string? error)> SetPortPoEStateAsync(
    string switchIp,
    int portNumber,
    bool enabled)
{
    // Get switch device ID first
    var deviceId = await GetDeviceIdAsync(switchIp);

    var request = new HttpRequestMessage(HttpMethod.Patch,
        $"https://omada-controller:8043/api/v2/sites/default/devices/{deviceId}/ports/{portNumber}");

    request.Headers.Add("Csrf-Token", _token);
    request.Content = JsonContent.Create(new { poeMode = enabled ? "auto" : "off" });

    var response = await _httpClient.SendAsync(request);
    return (response.IsSuccessStatusCode, null);
}
```

#### For SNMP-Based Control:

Install SNMP library:
```bash
dotnet add package Lextm.SharpSnmpLib
```

```csharp
using Lextm.SharpSnmpLib;
using Lextm.SharpSnmpLib.Messaging;

private async Task<(bool success, string? error)> SetPortPoEStateAsync(
    string switchIp,
    int portNumber,
    bool enabled)
{
    try
    {
        // PoE port control OID (varies by manufacturer)
        // Example for TP-Link: 1.3.6.1.4.1.11863.6.56.1.1.2.1.1.3.{port}
        var oid = new ObjectIdentifier($"1.3.6.1.4.1.11863.6.56.1.1.2.1.1.3.{portNumber}");
        var value = new Integer32(enabled ? 1 : 0);

        var endpoint = new IPEndPoint(IPAddress.Parse(switchIp), 161);
        var community = new OctetString("private"); // SNMP community string

        var result = Messenger.Set(
            VersionCode.V2,
            endpoint,
            community,
            new List<Variable> { new Variable(oid, value) },
            timeout: 5000
        );

        return (true, null);
    }
    catch (Exception ex)
    {
        return (false, ex.Message);
    }
}
```

### Step 4: Add Boot Button to Dashboard UI

Update `Home.razor` to add a Boot button:

```razor
@* In the machine card footer, alongside Start/Restart/Stop buttons *@
<div class="btn-group btn-group-sm mb-2" role="group">
    <button class="btn btn-outline-primary"
            @onclick="() => BootMachine(machine)"
            disabled="@(status.IsOnline || machine.PoESwitchPort == null)"
            title="@(machine.PoESwitchPort == null ? "PoE port not configured" : "Power cycle to boot")">
        Boot
    </button>
    <button class="btn btn-sm btn-success" @onclick="() => StartService(machine)" disabled="@(!status.IsOnline)">
        Start
    </button>
    <button class="btn btn-sm btn-warning" @onclick="() => RestartService(machine)" disabled="@(!status.IsOnline)">
        Restart
    </button>
    <button class="btn btn-sm btn-danger" @onclick="() => StopService(machine)" disabled="@(!status.IsOnline)">
        Stop
    </button>
</div>

@code {
    private async Task BootMachine(Machine machine)
    {
        if (machine.PoESwitchPort == null || string.IsNullOrEmpty(machine.PoESwitchIp))
        {
            // Show error
            return;
        }

        var confirmed = await JSRuntime.InvokeAsync<bool>(
            "confirm",
            $"Power cycle {machine.MachineId}? This will cut power and reboot the Pi."
        );

        if (!confirmed) return;

        // Call PoE switch client
        var result = await PoESwitchClient.PowerCyclePortAsync(
            machine.PoESwitchIp,
            machine.PoESwitchPort.Value
        );

        // Log to command history
        DbContext.CommandHistory.Add(new CommandHistory
        {
            MachineId = machine.Id,
            Command = $"boot: power cycle port {machine.PoESwitchPort}",
            Success = result.success,
            Error = result.error
        });
        await DbContext.SaveChangesAsync();

        // Wait for boot (30 seconds)
        await Task.Delay(30000);
        await RefreshAll();
    }
}
```

### Step 5: Register Service in Program.cs

```csharp
// Add PoE switch client
builder.Services.AddHttpClient<IPoESwitchClient, TPLinkJetStreamClient>();
builder.Services.AddScoped<IPoESwitchClient, TPLinkJetStreamClient>();
```

---

## Testing Checklist

Once configured:

- [ ] PoE switch accessible from dashboard server
- [ ] Switch credentials configured in appsettings.json
- [ ] Machine port mappings configured in database
- [ ] Boot button appears on dashboard for machines with PoE port configured
- [ ] Boot button disabled when machine is online
- [ ] Boot button triggers confirmation dialog
- [ ] Power cycle actually disables PoE on switch
- [ ] Power cycle actually re-enables PoE on switch
- [ ] Pi boots after power cycle
- [ ] Command logged to history
- [ ] Dashboard refreshes after boot delay

---

## Switch-Specific Implementation Guides

### TP-Link TL-SG3428MP

**API Type:** Web GUI + SNMP

**SNMP OIDs for PoE Control:**
```
# Get PoE status for port
GET: 1.3.6.1.4.1.11863.6.56.1.1.2.1.1.2.{port}

# Set PoE enable/disable
SET: 1.3.6.1.4.1.11863.6.56.1.1.2.1.1.3.{port}
Values: 1 = enable, 0 = disable
```

**SNMP Community Strings:**
- Read: `public` (default)
- Write: `private` (default, should be changed)

**Web GUI Endpoints:**
- Login: `https://{switchIp}/logon.html`
- PoE Control: `https://{switchIp}/PoEPortConfig.html`

### TP-Link with Omada Controller

**API Documentation:**
https://www.tp-link.com/us/omada-sdn/product-guide/omada-api/

**Base URL:**
```
https://{omada-controller}:8043/api/v2/
```

**Key Endpoints:**
- Login: `POST /api/v2/login`
- Get Sites: `GET /api/v2/sites`
- Get Devices: `GET /api/v2/sites/{site}/devices`
- Control Port: `PATCH /api/v2/sites/{site}/devices/{deviceId}/ports/{portId}`

---

## Troubleshooting

### Boot button not appearing
- Check `PoESwitchPort` is set for machine
- Check `PoESwitchIp` is set for machine
- Verify button HTML is added to Home.razor

### Button does nothing when clicked
- Check browser console for JavaScript errors
- Check server logs for exceptions
- Verify PoESwitchClient is registered in DI container

### "Failed to authenticate with switch"
- Verify switch IP is correct and accessible
- Verify username/password in appsettings.json
- Check switch allows API/SNMP access
- Try accessing switch web GUI manually

### PoE doesn't disable
- Check SNMP community string is correct
- Verify write access is enabled on switch
- Check firewall isn't blocking SNMP port 161
- Try SNMP command manually with snmpset tool

### PoE disables but Pi doesn't boot when re-enabled
- Check PoE HAT is working (LED on HAT)
- Verify Pi isn't in a hung state (SD card corruption)
- Try manual power cycle at switch
- Check PoE budget on switch (enough power available?)

### Pi boots but takes too long
- Increase wait delay in PowerCyclePortAsync
- Check Pi boot time (SD card speed, network wait, etc.)
- Consider adding progress indicator to dashboard

---

## Security Considerations

### Switch Credentials
- Store in appsettings.json (server-side only)
- Use environment variables for production
- Rotate passwords regularly
- Use read-only credentials if possible (SNMP)

### Network Access
- Switches should be on management VLAN
- Firewall rules to restrict access
- Use HTTPS for web-based APIs
- Consider VPN for remote access

### Audit Trail
- All power cycles logged to CommandHistory
- Include timestamp, user, machine, result
- Monitor for unusual activity
- Set up alerts for failed power cycles

---

## Future Enhancements

### Phase 3 (Future)
- [ ] Bulk operations (boot multiple machines)
- [ ] Scheduled power cycles
- [ ] Auto-boot on detection (if machine offline > X minutes)
- [ ] Power cycle retry on boot failure
- [ ] Health monitoring (PoE current draw, voltage)
- [ ] Email/SMS alerts on power events
- [ ] Integration with monitoring systems

---

## API Reference

### IPoESwitchClient Interface

```csharp
public interface IPoESwitchClient
{
    Task<(bool success, string? error)> PowerCyclePortAsync(
        string switchIp,
        int portNumber,
        int waitSeconds = 3);

    Task<(bool success, string? error)> EnablePortAsync(
        string switchIp,
        int portNumber);

    Task<(bool success, string? error)> DisablePortAsync(
        string switchIp,
        int portNumber);

    Task<(bool? enabled, string? error)> GetPortStatusAsync(
        string switchIp,
        int portNumber);
}
```

### Usage Example

```csharp
// Inject the client
private readonly IPoESwitchClient _switchClient;

// Power cycle a port
var (success, error) = await _switchClient.PowerCyclePortAsync(
    switchIp: "192.168.1.10",
    portNumber: 5,
    waitSeconds: 3
);

if (success)
{
    _logger.LogInformation("Successfully power cycled port 5");
}
else
{
    _logger.LogError("Failed to power cycle: {Error}", error);
}
```

---

## Support

For implementation questions or issues:

1. Check switch manufacturer documentation
2. Review `POE_SWITCH_RECOMMENDATIONS.md` for switch details
3. Review `REMOTE_BOOT_SOLUTIONS.md` for alternatives
4. Test SNMP/API access manually first
5. Check logs for detailed error messages

---

## Summary

**Current Status:** Framework ready, awaiting switch purchase

**Next Steps:**
1. Purchase PoE switches (see POE_SWITCH_RECOMMENDATIONS.md)
2. Configure switches on network
3. Update TPLinkJetStreamClient with actual API calls
4. Configure machine port mappings
5. Test power cycle functionality
6. Deploy to production

The framework is designed to be flexible and work with any managed PoE switch that supports API or SNMP control.
