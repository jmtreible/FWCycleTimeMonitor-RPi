# Stack Light Control System - Implementation Plan

## Overview
Add stack light control functionality to the existing fw-remote-supervisor service on the Raspberry Pi, with integration points for the FWCycleDashboard and external ERP system.

## Light State Definitions
- **Green**: Machine actively cycling, cycle time ≤ expected
- **Amber**: Machine actively cycling, cycle time > expected
- **Red**: Machine on, but no cycle detected in (expected cycle time + 2 minutes)

---

## Phase 1: Raspberry Pi Service Extension (fw-remote-supervisor)

### 1.1 Hardware Setup Requirements
- GPIO pins configuration (3 pins needed for 3 lights)
- Relay module compatible with Pi GPIO (to switch 24V stack lights)
- Suggested pin mapping:
  - GPIO 17 → Green light relay
  - GPIO 27 → Amber light relay
  - GPIO 22 → Red light relay
- Add to configuration file for easy changes

### 1.2 Python Dependencies
- Add `RPi.GPIO` or `gpiozero` library to requirements.txt
- Mock GPIO library for testing without hardware

### 1.3 New Python Module: `stacklight_controller.py`
**Purpose**: Manage GPIO pin control and light state management

**Key Functions**:
- `initialize_gpio()` - Setup GPIO pins on service start
- `set_light_state(green, amber, red)` - Set all three lights
- `get_light_state()` - Return current state of all lights
- `test_sequence()` - Cycle through all lights for testing (2 sec each)
- `cleanup_gpio()` - Safely cleanup on service shutdown
- Mock mode toggle for development/testing without hardware

### 1.4 New API Endpoints in `supervisor.py`

#### `POST /stacklight/set`
**Purpose**: Set specific light states (main control endpoint)

**Request Body**:
```json
{
  "green": true,
  "amber": false,
  "red": false
}
```

**Response**:
```json
{
  "success": true,
  "state": {
    "green": true,
    "amber": false,
    "red": false
  },
  "timestamp": "2025-11-11T10:30:00Z"
}
```

**Authentication**: X-API-Key header (existing mechanism)

---

#### `GET /stacklight/status`
**Purpose**: Query current light states

**Response**:
```json
{
  "green": true,
  "amber": false,
  "red": false,
  "last_updated": "2025-11-11T10:30:00Z"
}
```

---

#### `POST /stacklight/test`
**Purpose**: Test all lights in sequence (Green → Amber → Red → All Off)

**Request Body**: None

**Response**:
```json
{
  "success": true,
  "message": "Test sequence completed",
  "duration_seconds": 8
}
```

---

#### `POST /stacklight/off`
**Purpose**: Turn all lights off (convenience endpoint)

**Response**:
```json
{
  "success": true,
  "state": {
    "green": false,
    "amber": false,
    "red": false
  }
}
```

### 1.5 Configuration Updates
Add to `config.json`:
```json
{
  "stacklight": {
    "enabled": true,
    "mock_mode": false,
    "pins": {
      "green": 17,
      "amber": 27,
      "red": 22
    }
  }
}
```

### 1.6 Service Lifecycle Integration
- Initialize GPIO on service startup
- Cleanup GPIO on shutdown
- Handle errors gracefully (GPIO not available, etc.)
- All lights off on service stop

---

## Phase 2: FWCycleDashboard Integration

### 2.1 Update `Services/RemoteSupervisorModels.cs`
Add new response models:
```csharp
public class StackLightState
{
    public bool Green { get; set; }
    public bool Amber { get; set; }
    public bool Red { get; set; }
    public DateTime? LastUpdated { get; set; }
}

public class StackLightResponse
{
    public bool Success { get; set; }
    public StackLightState? State { get; set; }
    public string? Message { get; set; }
}
```

### 2.2 Update `Services/RemoteSupervisorClient.cs`
Add new methods:

```csharp
public async Task<(bool Success, string? Error)> SetStackLightAsync(
    Machine machine,
    bool green,
    bool amber,
    bool red)

public async Task<StackLightState?> GetStackLightStatusAsync(Machine machine)

public async Task<(bool Success, string? Error)> TestStackLightAsync(Machine machine)

public async Task<(bool Success, string? Error)> TurnOffStackLightAsync(Machine machine)
```

### 2.3 UI Updates - Machine Management Page
Add new section for Stack Light Control:
- Display current light states (colored indicators)
- Individual toggle buttons for each light (manual override)
- "Test Lights" button (runs test sequence)
- "All Off" button
- Show last updated timestamp
- Error display if API call fails

### 2.4 UI Location
Add to existing machine detail/management view alongside:
- Service Start/Stop/Restart buttons
- Current service status display
- Keep consistent with existing UI patterns

---

## Phase 3: ERP System Integration Documentation

### 3.1 API Endpoint Reference for ERP Team

**Base URL Format**: `http(s)://{machine-ip}:{port}`
- Example: `https://192.168.1.100:8443`

**Authentication**:
- Header: `X-API-Key: {api-key-from-machine-config}`

**Primary Control Endpoint**:
```
POST /stacklight/set
Content-Type: application/json
X-API-Key: your-api-key-here

Body:
{
  "green": false,
  "amber": true,
  "red": false
}
```

### 3.2 ERP Integration Logic Flow

**When ERP reads CSV and analyzes cycle time:**

1. **Parse CSV** (existing ERP functionality)
2. **Compare actual vs expected cycle time**
3. **Determine light state**:
   - If actively cycling AND actual ≤ expected → Green ON, others OFF
   - If actively cycling AND actual > expected → Amber ON, others OFF
   - If no cycle in (expected + 2 min) → Red ON, others OFF
4. **Send HTTP POST** to Pi's `/stacklight/set` endpoint
5. **Handle response** (log success/failure)

### 3.3 Sample ERP Pseudocode

```
expected_cycle = 40  // seconds, from ERP job data
actual_cycle = 50    // seconds, from CSV
last_cycle_time = parse_timestamp_from_csv()
time_since_last = now() - last_cycle_time

if time_since_last > (expected_cycle + 120):
    set_lights(green=false, amber=false, red=true)
elif actual_cycle > expected_cycle:
    set_lights(green=false, amber=true, red=false)
else:
    set_lights(green=true, amber=false, red=false)
```

### 3.4 Network Requirements
- ERP system must have network access to Raspberry Pi IP/Port
- Firewall rules may need adjustment
- API key must be securely stored in ERP configuration
- Consider HTTPS with self-signed cert handling (same as dashboard)

### 3.5 Error Handling Recommendations
- Timeout: 10 seconds
- Retry logic: 2-3 attempts with exponential backoff
- Log all API calls and responses
- Alert if Pi becomes unreachable
- Don't block ERP operations if stack light API fails

---

## Phase 4: Testing Plan

### 4.1 Unit Testing (Pi Service)
- Test GPIO initialization (mock and real)
- Test each API endpoint
- Test authentication
- Test error handling (invalid GPIO pins, etc.)

### 4.2 Integration Testing (Dashboard)
- Test light control from dashboard UI
- Test "Test" function sequence
- Verify status display updates
- Test error messages on failure

### 4.3 Hardware Testing
- Verify GPIO pin outputs with multimeter
- Test relay switching
- Test actual stack lights
- Verify light sequence timing
- Test multiple rapid state changes

### 4.4 ERP Integration Testing
- Mock ERP calls to API
- Test different cycle time scenarios
- Verify light states match logic
- Load test (multiple rapid updates)

---

## File Changes Summary

### Files to Modify (in FWCycleTimeMonitor-RPi):
- `requirements.txt` - Add GPIO library
- `supervisor.py` - Add new API endpoints
- `config.json` - Add stacklight configuration

### Files to Create (in FWCycleTimeMonitor-RPi):
- `stacklight_controller.py` - New module for GPIO control

### Files to Modify (in FWCycleDashboard):
- `Services/RemoteSupervisorModels.cs` - Add response models
- `Services/RemoteSupervisorClient.cs` - Add client methods
- Machine management Razor component - Add UI controls

---

## Configuration Data Needed

1. **GPIO Pin Numbers** (Pi side)
2. **Machine-to-Pi mapping** (already in dashboard DB)
3. **API Keys** (already configured)
4. **Expected cycle times per machine** (ERP system has this)

---

## Implementation Sequence

1. ✅ Create `stacklight_controller.py` with mock mode enabled
2. ✅ Add API endpoints to `supervisor.py`
3. ✅ Test API endpoints with mock GPIO
4. ✅ Update dashboard models and client
5. ✅ Add dashboard UI controls
6. ✅ Test dashboard → Pi communication
7. ✅ Connect real hardware and test GPIO
8. ✅ Document ERP integration
9. ✅ Provide ERP team with API specs and test environment

---

## Deliverables for Next Session

When you're ready to implement, I will:
1. **Add stack light control to fw-remote-supervisor** (GPIO + API)
2. **Extend FWCycleDashboard** (client methods + UI)
3. **Create ERP integration document** (API specs, examples, sample code)
4. **Add configuration templates** (GPIO pins, settings)
5. **Create testing guide** (hardware setup, verification steps)

---

## Architecture Notes

This keeps the monitor/supervisor focused on cycle time data collection, while the stack light system operates independently based on external commands from your ERP system.

**Key Design Principles**:
- Separation of concerns: Monitor collects data, ERP analyzes and controls lights
- Reuse existing API infrastructure and authentication
- Dashboard provides manual override and testing capabilities
- Mock mode allows development and testing without hardware
