#!/bin/bash
# Quick diagnostic script for self-test at boot

echo "=== FW Cycle Monitor Self-Test Boot Diagnostic ==="
echo ""

echo "1. Checking configuration file..."
echo "---"
if [ -f ~/.config/fw_cycle_monitor/remote_supervisor.json ]; then
    echo "Config file exists at: ~/.config/fw_cycle_monitor/remote_supervisor.json"
    echo ""
    echo "Stack light section:"
    cat ~/.config/fw_cycle_monitor/remote_supervisor.json | grep -A 10 '"stacklight"'
else
    echo "ERROR: Config file not found at ~/.config/fw_cycle_monitor/remote_supervisor.json"
fi
echo ""

echo "2. Checking if service is enabled..."
echo "---"
if systemctl is-enabled fw-remote-supervisor.service >/dev/null 2>&1; then
    echo "✓ Service is enabled (will start at boot)"
else
    echo "✗ Service is NOT enabled (will not start at boot)"
    echo "  Run: sudo systemctl enable fw-remote-supervisor.service"
fi
echo ""

echo "3. Checking if service is running..."
echo "---"
if systemctl is-active fw-remote-supervisor.service >/dev/null 2>&1; then
    echo "✓ Service is currently running"
    systemctl status fw-remote-supervisor.service | grep "Active:"
else
    echo "✗ Service is NOT running"
    echo "  Run: sudo systemctl start fw-remote-supervisor.service"
fi
echo ""

echo "4. Checking recent service logs for self-test..."
echo "---"
echo "Looking for self-test messages in last startup:"
sudo journalctl -u fw-remote-supervisor.service -b | grep -i "self-test" | tail -10
if [ $? -ne 0 ]; then
    echo "No self-test messages found in current boot logs"
    echo ""
    echo "Full startup sequence:"
    sudo journalctl -u fw-remote-supervisor.service -b | grep -i "startup\|stacklight" | tail -20
fi
echo ""

echo "5. Testing Python configuration loading..."
echo "---"
python3 << 'PYEOF'
import sys
import os

# Set up paths
config_dir = os.path.expanduser("~/.config/fw_cycle_monitor")
sys.path.insert(0, '/opt/fw-cycle-monitor/src')
os.environ['FW_CYCLE_MONITOR_CONFIG_DIR'] = config_dir

try:
    from fw_cycle_monitor.remote_supervisor.settings import get_settings

    settings = get_settings()
    print(f"✓ Settings loaded successfully")
    print(f"  Stack light enabled: {settings.stacklight.enabled}")
    print(f"  Startup self-test: {settings.stacklight.startup_self_test}")
    print(f"  Mock mode: {settings.stacklight.mock_mode}")
    print(f"  Active low: {settings.stacklight.active_low}")
    print(f"  Pins: Green={settings.stacklight.green_pin}, Amber={settings.stacklight.amber_pin}, Red={settings.stacklight.red_pin}")

    if not settings.stacklight.enabled:
        print("\n⚠ WARNING: Stack lights are DISABLED in configuration!")
    if not settings.stacklight.startup_self_test:
        print("\n⚠ WARNING: Startup self-test is DISABLED in configuration!")

except Exception as e:
    print(f"✗ Error loading settings: {e}")
    import traceback
    traceback.print_exc()
PYEOF
echo ""

echo "6. Recommendations:"
echo "---"

# Check if startup_self_test exists in config
if grep -q "startup_self_test" ~/.config/fw_cycle_monitor/remote_supervisor.json 2>/dev/null; then
    if grep -q '"startup_self_test": true' ~/.config/fw_cycle_monitor/remote_supervisor.json 2>/dev/null; then
        echo "✓ startup_self_test is set to true"
    else
        echo "⚠ startup_self_test is set to false"
        echo "  To enable: Edit ~/.config/fw_cycle_monitor/remote_supervisor.json"
        echo "  Set: \"startup_self_test\": true"
    fi
else
    echo "⚠ startup_self_test not found in config"
    echo "  To add: Edit ~/.config/fw_cycle_monitor/remote_supervisor.json"
    echo "  Add \"startup_self_test\": true to the stacklight section"
fi

echo ""
echo "To manually test the self-test:"
echo "  sudo systemctl restart fw-remote-supervisor.service"
echo "  sudo journalctl -u fw-remote-supervisor.service -f"
echo ""
echo "To reboot and test at boot:"
echo "  sudo reboot"
echo "  (After reboot) sudo journalctl -u fw-remote-supervisor.service -b | grep self-test"
