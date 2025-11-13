# ERP System Stack Light API Integration Guide

This document provides detailed HTTP POST examples for controlling stack lights on Raspberry Pi machines from your ERP system.

---

## API Overview

**Base URL:** `https://{machine-ip}:{port}/stacklight/`
**Default Port:** `8443`
**Authentication:** API Key via `X-API-Key` header
**Protocol:** HTTPS (self-signed certificate)

---

## Prerequisites

### 1. Get Machine Configuration

For each Raspberry Pi machine, you'll need:
- **IP Address:** The machine's network IP (e.g., `192.168.1.100`)
- **Port:** API port (default: `8443`)
- **API Key:** Authentication token (configured in machine's `config.json`)

### 2. SSL Certificate Handling

The Raspberry Pis use self-signed SSL certificates. Your ERP system must:
- Disable SSL certificate verification, OR
- Import and trust the self-signed certificates

---

## API Endpoints

### 1. Set Light State
Control individual lights (Green, Amber, Red) independently.

**Endpoint:** `POST /stacklight/set`

**Request Body:**
```json
{
  "green": true,
  "amber": false,
  "red": false
}
```

**Response (Success):**
```json
{
  "success": true,
  "state": {
    "green": true,
    "amber": false,
    "red": false
  }
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "Stack lights are not enabled in configuration"
}
```

---

### 2. Set Preset Pattern
Use predefined patterns for common states.

**Endpoint:** `POST /stacklight/preset`

**Request Body:**
```json
{
  "preset": "running"
}
```

**Available Presets:**
- `off` - All lights off
- `running` - Green only (machine operating normally)
- `idle` - Amber only (machine idle/waiting)
- `error` - Red only (machine error/stopped)
- `warning` - Amber + Red (warning state)
- `startup` - All lights on (machine starting)

**Response (Success):**
```json
{
  "success": true,
  "preset": "running",
  "state": {
    "green": true,
    "amber": false,
    "red": false
  }
}
```

---

### 3. Get Current State
Query the current stack light state.

**Endpoint:** `GET /stacklight/status`

**Response:**
```json
{
  "enabled": true,
  "green": true,
  "amber": false,
  "red": false,
  "timestamp": "2025-11-13T19:00:00Z"
}
```

---

## HTTP Request Examples

### Example 1: Python (Using requests library)

```python
import requests
import urllib3

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
MACHINE_IP = "192.168.1.100"
PORT = 8443
API_KEY = "your-api-key-here"
BASE_URL = f"https://{MACHINE_IP}:{PORT}/stacklight"

# Headers
headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# Example 1: Turn on green light (machine running)
response = requests.post(
    f"{BASE_URL}/set",
    json={
        "green": True,
        "amber": False,
        "red": False
    },
    headers=headers,
    verify=False  # Ignore SSL certificate verification
)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")

# Example 2: Use preset pattern
response = requests.post(
    f"{BASE_URL}/preset",
    json={"preset": "running"},
    headers=headers,
    verify=False
)

print(f"Response: {response.json()}")

# Example 3: Get current status
response = requests.get(
    f"{BASE_URL}/status",
    headers=headers,
    verify=False
)

print(f"Current State: {response.json()}")
```

---

### Example 2: curl (Command Line)

```bash
# Configuration
MACHINE_IP="192.168.1.100"
PORT="8443"
API_KEY="your-api-key-here"

# Turn on green light
curl -X POST \
  "https://${MACHINE_IP}:${PORT}/stacklight/set" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"green": true, "amber": false, "red": false}' \
  -k  # Ignore SSL certificate

# Use preset pattern
curl -X POST \
  "https://${MACHINE_IP}:${PORT}/stacklight/preset" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"preset": "running"}' \
  -k

# Get current status
curl -X GET \
  "https://${MACHINE_IP}:${PORT}/stacklight/status" \
  -H "X-API-Key: ${API_KEY}" \
  -k
```

---

### Example 3: C# (.NET)

```csharp
using System;
using System.Net.Http;
using System.Net.Http.Json;
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;
using System.Text.Json;
using System.Threading.Tasks;

public class StackLightController
{
    private readonly HttpClient _httpClient;
    private readonly string _baseUrl;
    private readonly string _apiKey;

    public StackLightController(string machineIp, int port, string apiKey)
    {
        _baseUrl = $"https://{machineIp}:{port}/stacklight";
        _apiKey = apiKey;

        // Create HttpClient that ignores SSL certificate errors
        var handler = new HttpClientHandler
        {
            ServerCertificateCustomValidationCallback =
                (message, cert, chain, errors) => true
        };

        _httpClient = new HttpClient(handler);
        _httpClient.DefaultRequestHeaders.Add("X-API-Key", apiKey);
    }

    public async Task<bool> SetLightState(bool green, bool amber, bool red)
    {
        var data = new
        {
            green = green,
            amber = amber,
            red = red
        };

        var response = await _httpClient.PostAsJsonAsync(
            $"{_baseUrl}/set",
            data
        );

        if (response.IsSuccessStatusCode)
        {
            var result = await response.Content.ReadFromJsonAsync<StackLightResponse>();
            Console.WriteLine($"Success: {result?.Success}");
            return result?.Success ?? false;
        }

        return false;
    }

    public async Task<bool> SetPreset(string preset)
    {
        var data = new { preset = preset };

        var response = await _httpClient.PostAsJsonAsync(
            $"{_baseUrl}/preset",
            data
        );

        if (response.IsSuccessStatusCode)
        {
            var result = await response.Content.ReadFromJsonAsync<StackLightResponse>();
            return result?.Success ?? false;
        }

        return false;
    }

    public async Task<StackLightStatus> GetStatus()
    {
        var response = await _httpClient.GetAsync($"{_baseUrl}/status");

        if (response.IsSuccessStatusCode)
        {
            return await response.Content.ReadFromJsonAsync<StackLightStatus>();
        }

        return null;
    }
}

public class StackLightResponse
{
    public bool Success { get; set; }
    public string? Error { get; set; }
    public LightState? State { get; set; }
}

public class LightState
{
    public bool Green { get; set; }
    public bool Amber { get; set; }
    public bool Red { get; set; }
}

public class StackLightStatus
{
    public bool Enabled { get; set; }
    public bool Green { get; set; }
    public bool Amber { get; set; }
    public bool Red { get; set; }
    public DateTime Timestamp { get; set; }
}

// Usage Example
class Program
{
    static async Task Main(string[] args)
    {
        var controller = new StackLightController(
            machineIp: "192.168.1.100",
            port: 8443,
            apiKey: "your-api-key-here"
        );

        // Turn on green light
        await controller.SetLightState(green: true, amber: false, red: false);

        // Use preset
        await controller.SetPreset("running");

        // Get status
        var status = await controller.GetStatus();
        Console.WriteLine($"Green: {status?.Green}, Amber: {status?.Amber}, Red: {status?.Red}");
    }
}
```

---

### Example 4: JavaScript/Node.js

```javascript
const https = require('https');
const axios = require('axios');

// Configuration
const MACHINE_IP = '192.168.1.100';
const PORT = 8443;
const API_KEY = 'your-api-key-here';
const BASE_URL = `https://${MACHINE_IP}:${PORT}/stacklight`;

// Create axios instance that ignores SSL errors
const client = axios.create({
  httpsAgent: new https.Agent({
    rejectUnauthorized: false
  }),
  headers: {
    'X-API-Key': API_KEY,
    'Content-Type': 'application/json'
  }
});

// Set light state
async function setLightState(green, amber, red) {
  try {
    const response = await client.post(`${BASE_URL}/set`, {
      green: green,
      amber: amber,
      red: red
    });
    console.log('Success:', response.data);
    return response.data;
  } catch (error) {
    console.error('Error:', error.message);
    return null;
  }
}

// Use preset pattern
async function setPreset(preset) {
  try {
    const response = await client.post(`${BASE_URL}/preset`, {
      preset: preset
    });
    console.log('Success:', response.data);
    return response.data;
  } catch (error) {
    console.error('Error:', error.message);
    return null;
  }
}

// Get current status
async function getStatus() {
  try {
    const response = await client.get(`${BASE_URL}/status`);
    console.log('Status:', response.data);
    return response.data;
  } catch (error) {
    console.error('Error:', error.message);
    return null;
  }
}

// Usage examples
(async () => {
  // Turn on green light
  await setLightState(true, false, false);

  // Use preset
  await setPreset('running');

  // Get status
  await getStatus();
})();
```

---

## Controlling Multiple Machines

### Sequential Control (One at a time)

```python
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# List of machines
machines = [
    {"ip": "192.168.1.100", "port": 8443, "api_key": "key1"},
    {"ip": "192.168.1.101", "port": 8443, "api_key": "key2"},
    {"ip": "192.168.1.102", "port": 8443, "api_key": "key3"},
]

def set_machine_light(machine, green, amber, red):
    """Set stack light for a single machine"""
    url = f"https://{machine['ip']}:{machine['port']}/stacklight/set"
    headers = {
        "X-API-Key": machine['api_key'],
        "Content-Type": "application/json"
    }
    data = {
        "green": green,
        "amber": amber,
        "red": red
    }

    try:
        response = requests.post(url, json=data, headers=headers, verify=False, timeout=5)
        return response.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

# Set all machines to green (running)
for machine in machines:
    result = set_machine_light(machine, green=True, amber=False, red=False)
    print(f"Machine {machine['ip']}: {result}")
```

---

### Parallel Control (All at once)

```python
import requests
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

machines = [
    {"ip": "192.168.1.100", "port": 8443, "api_key": "key1", "name": "Press-01"},
    {"ip": "192.168.1.101", "port": 8443, "api_key": "key2", "name": "Press-02"},
    {"ip": "192.168.1.102", "port": 8443, "api_key": "key3", "name": "Press-03"},
]

def set_machine_light(machine, green, amber, red):
    """Set stack light for a single machine"""
    url = f"https://{machine['ip']}:{machine['port']}/stacklight/set"
    headers = {
        "X-API-Key": machine['api_key'],
        "Content-Type": "application/json"
    }
    data = {
        "green": green,
        "amber": amber,
        "red": red
    }

    try:
        response = requests.post(url, json=data, headers=headers, verify=False, timeout=5)
        return {
            "machine": machine['name'],
            "success": True,
            "data": response.json()
        }
    except Exception as e:
        return {
            "machine": machine['name'],
            "success": False,
            "error": str(e)
        }

def set_all_machines_parallel(machines, green, amber, red, max_workers=10):
    """Set stack lights on multiple machines in parallel"""
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(set_machine_light, machine, green, amber, red): machine
            for machine in machines
        }

        # Collect results as they complete
        for future in as_completed(futures):
            machine = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(f"✓ {result['machine']}: {'Success' if result['success'] else 'Failed'}")
            except Exception as e:
                print(f"✗ {machine['name']}: Exception - {e}")
                results.append({
                    "machine": machine['name'],
                    "success": False,
                    "error": str(e)
                })

    return results

# Usage: Set all machines to green
results = set_all_machines_parallel(machines, green=True, amber=False, red=False)

# Summary
success_count = sum(1 for r in results if r['success'])
print(f"\nTotal: {len(results)} machines, {success_count} successful")
```

---

### Parallel Control with Presets

```python
def set_machine_preset(machine, preset):
    """Set stack light preset for a single machine"""
    url = f"https://{machine['ip']}:{machine['port']}/stacklight/preset"
    headers = {
        "X-API-Key": machine['api_key'],
        "Content-Type": "application/json"
    }
    data = {"preset": preset}

    try:
        response = requests.post(url, json=data, headers=headers, verify=False, timeout=5)
        return {
            "machine": machine['name'],
            "success": True,
            "data": response.json()
        }
    except Exception as e:
        return {
            "machine": machine['name'],
            "success": False,
            "error": str(e)
        }

def set_all_presets_parallel(machines, preset, max_workers=10):
    """Set preset on multiple machines in parallel"""
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(set_machine_preset, machine, preset): machine
            for machine in machines
        }

        for future in as_completed(futures):
            machine = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(f"✓ {result['machine']}: {preset}")
            except Exception as e:
                print(f"✗ {machine['name']}: {e}")

    return results

# Usage: Set all machines to "running" preset
results = set_all_presets_parallel(machines, preset="running")
```

---

## Error Handling

### Common HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| `200` | Success | Request completed successfully |
| `400` | Bad Request | Check request body format |
| `401` | Unauthorized | Verify API key is correct |
| `404` | Not Found | Check endpoint URL |
| `500` | Server Error | Check Pi logs, may need restart |
| `503` | Service Unavailable | Stack lights disabled in config |

### Example Error Handling

```python
def set_light_with_retry(machine, green, amber, red, max_retries=3):
    """Set light with automatic retry on failure"""
    url = f"https://{machine['ip']}:{machine['port']}/stacklight/set"
    headers = {
        "X-API-Key": machine['api_key'],
        "Content-Type": "application/json"
    }
    data = {
        "green": green,
        "amber": amber,
        "red": red
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(
                url,
                json=data,
                headers=headers,
                verify=False,
                timeout=5
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                return {"success": False, "error": "Invalid API key"}
            elif response.status_code == 503:
                return {"success": False, "error": "Stack lights disabled"}
            else:
                # Retry on other errors
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return {"success": False, "error": f"HTTP {response.status_code}"}

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return {"success": False, "error": str(e)}

    return {"success": False, "error": "Max retries exceeded"}
```

---

## Integration Patterns

### Pattern 1: Event-Driven Control

```python
# When machine starts a cycle
set_light_with_retry(machine, green=True, amber=False, red=False)

# When machine is idle/waiting
set_light_with_retry(machine, green=False, amber=True, red=False)

# When machine errors
set_light_with_retry(machine, green=False, amber=False, red=True)

# When machine completes cycle
set_light_with_retry(machine, green=True, amber=False, red=False)
```

### Pattern 2: State-Based Control

```python
def update_stack_light_from_state(machine, state):
    """Update stack light based on machine state"""
    presets = {
        "running": "running",
        "idle": "idle",
        "error": "error",
        "warning": "warning",
        "off": "off",
        "startup": "startup"
    }

    preset = presets.get(state, "off")
    return set_machine_preset(machine, preset)
```

### Pattern 3: Scheduled Polling

```python
import time

def monitor_and_update_lights(machines, check_interval=30):
    """Continuously monitor machines and update lights"""
    while True:
        for machine in machines:
            # Get machine state from your ERP database
            state = get_machine_state_from_erp(machine['name'])

            # Update stack light
            update_stack_light_from_state(machine, state)

        time.sleep(check_interval)
```

---

## Testing

### Quick Test Script

```python
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MACHINE_IP = "192.168.1.100"
PORT = 8443
API_KEY = "your-api-key-here"

def test_machine(ip, port, api_key):
    """Test all stack light functions"""
    base_url = f"https://{ip}:{port}/stacklight"
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    print(f"Testing machine at {ip}:{port}")

    # Test 1: Get status
    try:
        response = requests.get(f"{base_url}/status", headers=headers, verify=False, timeout=5)
        print(f"✓ Status check: {response.status_code}")
        print(f"  {response.json()}")
    except Exception as e:
        print(f"✗ Status check failed: {e}")
        return False

    # Test 2: Green light
    try:
        response = requests.post(
            f"{base_url}/set",
            json={"green": True, "amber": False, "red": False},
            headers=headers,
            verify=False,
            timeout=5
        )
        print(f"✓ Green light: {response.status_code}")
    except Exception as e:
        print(f"✗ Green light failed: {e}")

    # Test 3: Preset
    try:
        response = requests.post(
            f"{base_url}/preset",
            json={"preset": "running"},
            headers=headers,
            verify=False,
            timeout=5
        )
        print(f"✓ Preset 'running': {response.status_code}")
    except Exception as e:
        print(f"✗ Preset failed: {e}")

    print("Testing complete!\n")
    return True

# Run test
test_machine(MACHINE_IP, PORT, API_KEY)
```

---

## Security Considerations

### 1. API Key Management
- Store API keys securely in your ERP configuration
- Don't hardcode keys in source code
- Rotate keys periodically
- Use environment variables or secure vaults

### 2. Network Security
- Keep stack light control on internal network only
- Use firewall rules to restrict access to port 8443
- Consider VPN for remote access
- Monitor API access logs

### 3. SSL Certificates
- For production, consider using proper SSL certificates
- Or import self-signed certs into ERP trust store
- Don't disable SSL verification in production without understanding risks

---

## Troubleshooting

### Connection Issues

```python
def diagnose_connection(machine):
    """Diagnose connection issues"""
    import socket

    print(f"Diagnosing {machine['ip']}:{machine['port']}")

    # Test 1: Ping/socket connection
    try:
        sock = socket.create_connection((machine['ip'], machine['port']), timeout=5)
        sock.close()
        print("✓ Port is open and reachable")
    except Exception as e:
        print(f"✗ Cannot connect to port: {e}")
        return

    # Test 2: HTTPS connection
    try:
        url = f"https://{machine['ip']}:{machine['port']}/stacklight/status"
        response = requests.get(url, verify=False, timeout=5)
        print(f"✓ HTTPS connection successful: {response.status_code}")
    except Exception as e:
        print(f"✗ HTTPS connection failed: {e}")
        return

    # Test 3: Authentication
    headers = {"X-API-Key": machine['api_key']}
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=5)
        if response.status_code == 200:
            print("✓ API key is valid")
        elif response.status_code == 401:
            print("✗ API key is invalid")
        else:
            print(f"? Unexpected status: {response.status_code}")
    except Exception as e:
        print(f"✗ Auth test failed: {e}")
```

---

## Summary

### Quick Reference

**Set individual lights:**
```bash
POST /stacklight/set
{"green": true, "amber": false, "red": false}
```

**Use preset:**
```bash
POST /stacklight/preset
{"preset": "running"}
```

**Get status:**
```bash
GET /stacklight/status
```

**Authentication:**
```
Header: X-API-Key: your-api-key-here
```

**Multiple machines:**
Use Python's `ThreadPoolExecutor` or equivalent for parallel control.

---

## Support

For additional help:
1. Check remote supervisor logs on Pi: `/var/log/fw-cycle-monitor/`
2. Test API manually with curl first
3. Verify network connectivity and firewall rules
4. Confirm API key matches configuration

---

**Last Updated:** 2025-11-13
**API Version:** 1.0
**Compatible with:** FW Cycle Monitor Remote Supervisor v1.0+
