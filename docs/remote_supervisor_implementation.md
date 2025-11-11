# Remote Supervisor Implementation Guide

This document describes how to deploy the Remote Supervisor agent on each Raspberry Pi and how to operate it from a Windows workstation using the provided CLI. It complements the high-level architecture in `remote_supervisor_plan.md`.

## 1. Install or upgrade with the deployment script

Run the repository installer to deploy both the monitor and the remote supervisor:

```bash
cd FWCycleTimeMonitor-RPi/scripts
sudo ./install_fw_cycle_monitor.sh
```

The script now:

- copies the repository to `/opt/fw-cycle-monitor` and upgrades the virtual environment
- installs the `fw-cycle-monitor` package with both the `raspberrypi` and `remote_supervisor` extras so FastAPI, Uvicorn, and the CLI are present
- provisions `fw-remote-supervisor.service` alongside the existing monitor unit and enables it immediately
- generates `/home/<user>/.config/fw_cycle_monitor/remote_supervisor.json` with a random API key (printed at the end of the install) and restrictive permissions
- creates `/etc/sudoers.d/fw-cycle-monitor` with passwordless sudo permissions for the remote supervisor to control the monitor service
- configures the remote supervisor service to run independently of the monitor service, allowing remote start/stop/restart operations

Make sure to store the generated API key securely—you will need it for every remote command. If you rerun the installer, the script leaves an existing config untouched, so your API keys and TLS settings persist.

### Optional: enable TLS

For encrypted traffic create a certificate/key pair and update the generated settings file:

```bash
sudo mkdir -p /home/<user>/.config/fw_cycle_monitor/certs
sudo openssl req -x509 -newkey rsa:4096 \
  -keyout /home/<user>/.config/fw_cycle_monitor/certs/remote.key \
  -out /home/<user>/.config/fw_cycle_monitor/certs/remote.crt \
  -sha256 -days 365 -nodes \
  -subj "/CN=fw-remote-supervisor"
sudo chown <user>:<group> /home/<user>/.config/fw_cycle_monitor/certs/remote.*
chmod 600 /home/<user>/.config/fw_cycle_monitor/certs/remote.key
```

Then edit `remote_supervisor.json` to reference the new files:

```json
{
  "certfile": "/home/<user>/.config/fw_cycle_monitor/certs/remote.crt",
  "keyfile": "/home/<user>/.config/fw_cycle_monitor/certs/remote.key"
}
```

Restart the service to pick up the change:

```bash
sudo systemctl restart fw-remote-supervisor.service
```

## 2. Verify the remote supervisor service

Confirm the service is running and listening on the configured port:

```bash
sudo systemctl status fw-remote-supervisor.service
sudo ss -tlnp | grep 8443
```

## 3. Operating from Windows

### 3.1 Install the CLI

1. Install Python 3.10+ from [python.org](https://www.python.org/downloads/windows/).
2. Open **PowerShell** and install the CLI package (you can either clone the repository or copy the wheel/zip produced by `pip wheel`). Assuming you copy the source tree:

   ```powershell
   cd C:\Tools\FWCycleMonitor-RPi
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install --upgrade pip
   pip install .[remote_supervisor]
   ```

3. The setup script installs the `fw-remote-supervisor-cli` console entry point. Verify it is available:

   ```powershell
   fw-remote-supervisor-cli --help
   ```

### 3.2 Use the CLI

All commands default to `https://localhost:8443`. Override `--base-url` with each Pi’s hostname or IP. Provide the API key configured on the Pi.

```powershell
# Check service status on a single Pi
fw-remote-supervisor-cli --base-url https://10.10.4.21:8443 --api-key YOUR_TOKEN status

# Restart the monitor service
fw-remote-supervisor-cli --base-url https://10.10.4.21:8443 --api-key YOUR_TOKEN restart

# Retrieve current configuration and metrics
fw-remote-supervisor-cli --base-url https://10.10.4.21:8443 --api-key YOUR_TOKEN config
fw-remote-supervisor-cli --base-url https://10.10.4.21:8443 --api-key YOUR_TOKEN metrics
```

If you use self-signed certificates, supply the CA bundle with `--ca-cert C:\path\to\ca.pem` or temporarily trust the certificate on Windows. For ad-hoc testing you can append `--insecure`, but do not disable TLS in production.

### 3.3 Bulk operations

Create a simple PowerShell script (`Start-All.ps1`) to iterate over every Pi:

```powershell
$apiKey = "YOUR_TOKEN"
$machines = @("10.10.4.21", "10.10.4.22", "10.10.4.23")
foreach ($machine in $machines) {
  Write-Host "Restarting $machine"
  fw-remote-supervisor-cli --base-url "https://$machine:8443" --api-key $apiKey restart
}
```

You can schedule these scripts via Windows Task Scheduler for routine maintenance or integrate them into a richer dashboard (e.g., a .NET or Power BI front-end) using the same REST endpoints.

## 4. Building a dashboard

Any web or desktop application that can issue HTTPS requests can serve as your dashboard. The key endpoints are:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/service/status` | GET | Returns systemd state, PID, and uptime. |
| `/service/start` | POST | Starts the monitor service. |
| `/service/stop` | POST | Stops the monitor service. |
| `/service/restart` | POST | Restarts the monitor service. |
| `/config` | GET | Returns machine ID, GPIO pin, CSV path, and reset hour. |
| `/metrics/summary` | GET | Returns last-cycle duration and rolling averages for 5/15/30/60 minutes. |

Authenticate by sending the `X-API-Key` header. Use the TLS certificate you generated earlier to encrypt traffic. Common dashboard options include:

- **PowerShell/Power BI**: call the API and visualize uptime and metrics.
- **.NET (WPF/WinUI)**: use `HttpClient` to call the endpoints and render controls to start/stop or restart each Pi.
- **Web dashboard**: Build a React or Blazor UI that loops through all machine IPs, calling the endpoints above and aggregating their responses.

## 5. Troubleshooting

### Remote commands return 500 errors

If you receive HTTP 500 errors when trying to stop, start, or restart the monitor service, check the following:

1. **Verify sudoers configuration**:
   ```bash
   sudo cat /etc/sudoers.d/fw-cycle-monitor
   ```

   The file must contain a single line (no line breaks) granting passwordless sudo access to the user running the remote supervisor service:
   ```
   <user> ALL=(ALL) NOPASSWD: /bin/systemctl start fw-cycle-monitor.service, /bin/systemctl stop fw-cycle-monitor.service, /bin/systemctl restart fw-cycle-monitor.service, /bin/systemctl status fw-cycle-monitor.service
   ```

2. **Check which user is running the remote supervisor**:
   ```bash
   ps aux | grep fw-remote-supervisor
   ```

   The user shown must match the user in the sudoers file.

3. **Test sudo access manually**:
   ```bash
   sudo systemctl stop fw-cycle-monitor.service
   sudo systemctl status fw-cycle-monitor.service
   ```

   If prompted for a password, the sudoers configuration is incorrect.

4. **Check the remote supervisor logs**:
   ```bash
   sudo journalctl -u fw-remote-supervisor.service -n 50
   ```

   Look for "systemctl failed with code 1" errors or permission denied messages.

### Remote supervisor stops when monitor service is stopped

If stopping the monitor service also stops the remote supervisor, the service dependency needs to be removed:

1. **Check the remote supervisor service file**:
   ```bash
   sudo systemctl cat fw-remote-supervisor.service
   ```

2. **Verify it does NOT contain** `Requires=fw-cycle-monitor.service` in the `[Unit]` section.

3. **If it does, reinstall with the latest version**:
   ```bash
   cd FWCycleTimeMonitor-RPi/scripts
   sudo ./install_fw_cycle_monitor.sh
   ```

The remote supervisor should run independently so you can start the monitor remotely after stopping it.

## 6. Maintenance tips

- Rotate API keys regularly and update the `remote_supervisor.json` file on each Pi.
- Use firewall rules to limit access to the supervisor port to trusted management workstations or VPN subnets.
- Monitor `fw-remote-supervisor.service` logs (`journalctl -u fw-remote-supervisor.service`) to audit remote operations.
- Keep the virtual environment patched (`pip install --upgrade fw-cycle-monitor[remote_supervisor]`).

With these steps complete, you can remotely observe, start, stop, or restart any monitor instance from a Windows PC.
