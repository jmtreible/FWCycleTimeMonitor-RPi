# Stack Light Testing Notes

## Important: After Changing Config

When you edit `~/.config/fw_cycle_monitor/remote_supervisor.json`, you need to:

### For the GUI:
- Click the "Reload Config" button in the Stack Light Control section
- The status line should update to show the new mode

### For the Remote Supervisor Service (API):
```bash
sudo systemctl restart fw-remote-supervisor
```
The service caches the config, so it needs a restart to pick up changes.

### For the Dashboard:
- No action needed - it connects to the remote supervisor API
- Just make sure the remote supervisor service was restarted

## Testing Checklist

### 1. Test API (after restart)
```bash
export API_KEY="36Wn0_9r-VLziYeXMM1aiZmW0kROuDMa2YlL8-m_CB4"
curl -H "X-API-Key: $API_KEY" http://192.168.0.170:8443/stacklight/status
```

### 2. Test GUI
- Launch: `fw-cycle-monitor-gui`
- Check status line shows correct mode
- Click checkboxes to test lights
- Click "Test Sequence" to run full cycle

### 3. Test Dashboard
- Add machine with IP: 192.168.0.170
- Add API key: 36Wn0_9r-VLziYeXMM1aiZmW0kROuDMa2YlL8-m_CB4
- Control lights from dashboard

## Current Configuration
Based on your config file at `/home/pi1/.config/fw_cycle_monitor/remote_supervisor.json`:
- Host: 192.168.0.170
- Port: 8443
- Mock Mode: **false** (hardware mode)
- Active Low: **false** (active-high for your breadboard)
- Pins: Green=26, Amber=20, Red=21
