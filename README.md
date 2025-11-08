# FW Cycle Time Monitor

A lightweight Raspberry Pi application that logs mold close events for injection molding machines. Each detected cycle writes the cycle number, machine identifier, and timestamp to a CSV file for production tracking.

## Features

- **Automatic updates**: Optional launcher checks the GitHub `main` branch for new commits and pulls them before starting the GUI.
- **Configurable logging**: Define machine number, GPIO input pin, and CSV storage directory. CSV files follow the `CM_<MachineID>.csv` naming pattern.
- **Simple GUI**: Tkinter-based interface to configure hardware settings, start/stop monitoring, and log test events without hardware.
- **Raspberry Pi ready**: Uses `RPi.GPIO` (with the modern `lgpio` backend) for hardware access and is packaged for straightforward installation.
- **Isolated runtime**: The installer provisions a dedicated Python virtual environment so GPIO dependencies remain consistent across Raspberry Pi OS releases.
- **Cycle counter support**: Every event updates a per-machine counter that persists across restarts and resets to 1 at a configurable time (3 AM by default).
- **Resilient logging**: If a CSV is temporarily locked (e.g., opened from another workstation), events are queued locally and flushed once access is restored.
- **Guided installation**: A one-command installer prepares dependencies, configures the network share, enables the boot service, and drops a desktop shortcut for the GUI that auto-activates the managed virtual environment.
- **Auto-start support**: Example `systemd` unit file for launching on boot.

## Project layout

```
.
├── pyproject.toml            # Packaging metadata
├── README.md                 # Project documentation
├── scripts/install_fw_cycle_monitor.sh  # Automated Raspberry Pi installer
├── src/fw_cycle_monitor/     # Application source code
│   ├── __init__.py
│   ├── __main__.py           # Allows `python -m fw_cycle_monitor`
│   ├── config.py             # Load/save user configuration
│   ├── gpio_monitor.py       # GPIO edge detection and CSV logging
│   ├── gui.py                # Tkinter configuration and control UI
│   ├── launcher.py           # Update-aware entry point
│   └── updater.py            # Git utilities for self-update
└── systemd/fw-cycle-monitor.service  # Example unit file
```

## Installation

### Automated setup (recommended)

1. Download or clone the repository onto the Raspberry Pi:

   ```bash
   git clone https://github.com/<your-org>/FWCycleTimeMonitor-RPi.git
   cd FWCycleTimeMonitor-RPi
   ```

2. Make the installer executable (first run only):

   ```bash
   chmod +x scripts/install_fw_cycle_monitor.sh
   ```

3. Run the installer with `sudo`:

   ```bash
   sudo ./scripts/install_fw_cycle_monitor.sh
   ```

   The script performs the following actions:

   - Installs required APT packages (`python3`, `python3-venv`, `python3-tk`, `git`, `cifs-utils`, `rsync`, `xdg-user-dirs`, etc.).
   - Copies the repository to `/opt/fw-cycle-monitor` so the auto-updater has a stable working tree.
   - Provisions a Python virtual environment at `/opt/fw-cycle-monitor/.venv`, shares system GPIO bindings, and installs `fw-cycle-monitor[raspberrypi]` (including `RPi.GPIO`, `lgpio`, and `rpi-lgpio`).
   - Verifies the GPIO libraries import successfully inside the managed environment so edge detection is ready immediately after install.
   - Creates command shims (`/usr/local/bin/fw-cycle-monitor*`) that activate the virtual environment automatically via the bundled `run_in_venv.sh` helper.
   - Adds the network share `//192.168.0.249/Apps/FWCycle` to `/etc/fstab`, mounting it at `${HOME}/FWCycle` with the provided credentials (`Operation1` / `Crows1991!`).
   - Enables and starts the `fw-cycle-monitor.service` systemd unit that launches the auto-updating monitor on boot.
   - Creates a “FW Cycle Monitor” desktop shortcut that runs the GUI inside the managed environment.

   > **Security note:** Credentials for the network share are stored in `/etc/fstab`. Review and adjust permissions according to your facility’s policies.

4. Confirm the share is mounted (`ls ${HOME}/FWCycle`) and that the desktop shortcut launches the GUI. The monitoring service will continue running in the background.

### Manual installation (for development)

Follow these steps if you prefer to manage the environment yourself (e.g., during development or when adapting the project for a different deployment workflow):

1. **Install system dependencies**

   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-venv python3-tk git
   ```

2. **Clone (or extract) the repository**

   ```bash
   git clone https://github.com/<your-org>/FWCycleTimeMonitor-RPi.git
   cd FWCycleTimeMonitor-RPi
   ```

3. **Create (optional) virtual environment and install the application**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e '.[raspberrypi]'
   ```

   > If you prefer not to create a virtual environment, use `python3 -m pip install --user -e '.[raspberrypi]'` to install the same dependencies into your user site-packages directory.

   To install from a built wheel/sdist (produced via `python -m build`):

   ```bash
   pip install 'fw-cycle-monitor-0.1.0-py3-none-any.whl[raspberrypi]'
   ```

### Customizing the installer

The installer uses the account that invokes `sudo` as the service user and mounts the network share at `${HOME}/FWCycle`. Adjust `scripts/install_fw_cycle_monitor.sh` before running it if you need to:

- Change the mount location, credentials, or SMB server information.
- Deploy the repository to a different directory than `/opt/fw-cycle-monitor`.
- Skip the desktop shortcut creation (comment out `create_desktop_entry`).

Re-run the installer after making modifications to propagate the changes.

## Usage

### Launch the GUI directly

When running inside the managed installation on the Raspberry Pi, use one of the following methods—each one sources the virtual environment before launching the GUI so GPIO dependencies (`lgpio`, `RPi.GPIO`) are always available:

```bash
fw-cycle-monitor
# or explicitly:
/opt/fw-cycle-monitor/run_in_venv.sh python -m fw_cycle_monitor
# or interactively:
source /opt/fw-cycle-monitor/.venv/bin/activate
python -m fw_cycle_monitor
```

You can also use the **FW Cycle Monitor** desktop shortcut that the installer places on the Raspberry Pi desktop. Internally it calls `run_in_venv.sh` with the GUI entry point.

> The `fw-cycle-monitor`, `fw-cycle-monitor-launcher`, and `fw-cycle-monitor-daemon` command shims, along with the systemd unit and the desktop shortcut, all activate the virtual environment automatically before executing Python modules.

When the GUI is running on an installed system, the **Start Service** and **Stop Service** buttons issue `systemctl start/stop fw-cycle-monitor.service` so you can manage the background daemon without opening a terminal. If the current user lacks permission to control the unit, a dialog explains that elevated rights (for example via `sudo` or a policykit rule) are required.

### Launch with update checks

The launcher pulls the newest `main` branch revision before starting the GUI. By default it uses the repository that contains the scripts, but you can override it using the `FW_CYCLE_MONITOR_REPO` environment variable.

```bash
fw-cycle-monitor-launcher
# or
/opt/fw-cycle-monitor/run_in_venv.sh python -m fw_cycle_monitor.launcher
```

### Configuration fields

- **Machine ID**: Text identifier (e.g. `M201`). Used in the CSV file name and log entries.
- **GPIO Pin (BCM)**: Input pin that receives the 3.3 V mold close signal (BCM numbering).
- **CSV Directory**: Folder where CSV output is saved. Each machine logs to `CM_<MachineID>.csv` with headers `cycle_number,machine_id,timestamp`.
-   When you change the machine ID or move the CSV directory, the application clears any pending queue/state files tied to the previous machine so retired identifiers (for example `M201`) no longer reappear with locked CSVs. Existing CSV logs are left intact so you can archive or delete them manually.
- **Reset Hour (0–23)**: Local hour when the cycle counter resets back to 1. The default is `3`, meaning the first cycle logged on or after 3 AM becomes cycle 1.

The application persists settings to `~/.config/fw_cycle_monitor/config.json` and stores the live per-machine cycle counters in `~/.config/fw_cycle_monitor/state.json`. A mirrored copy of the latest counter is also written beside each CSV as `CM_<MachineID>.csv.state.json` so the monitor can recover even if the configuration directory is reset or the service and GUI momentarily disagree on their storage paths. During automated installations the helper script exports `FW_CYCLE_MONITOR_CONFIG_DIR` so both the GUI and the systemd service share the same directory (for example `/home/pi1/.config/fw_cycle_monitor`), which keeps the persisted cycle numbers aligned after reboots.

To inspect the stored cycle numbers manually, open the `state.json` file in that directory (or the per-machine `*.csv.state.json` sidecar). Each machine ID retains the `last_cycle` that was written along with the timestamp of the most recent event. When debugging persistence, confirm that:

1. The `fw-cycle-monitor.service` systemd unit is running as the same user recorded in the installer output (or adjust the `User=` field to the correct account and run `sudo systemctl daemon-reload`).
2. The `FW_CYCLE_MONITOR_CONFIG_DIR` environment variable in the unit file points to the same directory the GUI uses. After editing, restart the service and monitor the logs with `journalctl -u fw-cycle-monitor.service` to verify that the monitor reports the restored `last_cycle` number on startup.
3. The CSV directory contains the matching `CM_<MachineID>.csv.state.json` sidecar. If a maintenance process clears old CSV logs, leave the sidecar file in place so the next monitor session can resume from the most recent counter.

> If a CSV file is opened elsewhere (for example in Excel over the network share), new events are stored in a local queue. A dedicated background writer periodically opens the CSV, appends the queued rows, and closes it immediately so other clients retain read access. The monitor also normalizes file permissions to `rw-rw-r--` so other users can read the logs while the Raspberry Pi retains write access.

### Test events without hardware

Use the **Log Test Event** button to append a simulated timestamp directly to the configured CSV. This works even when running on a non-Raspberry Pi development machine and does not require the service to be running.

## Auto-start with systemd

An example service file is provided under `systemd/fw-cycle-monitor.service`. Adjust the `User` (default `pi`) and the paths to match your deployment (the template assumes the project lives in `/opt/fw-cycle-monitor` and runs the headless service runner with the managed virtual environment’s Python interpreter), then install and enable it:

```bash
sudo cp systemd/fw-cycle-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable fw-cycle-monitor.service
sudo systemctl start fw-cycle-monitor.service
```

The service uses the headless `fw_cycle_monitor.service_runner` module so it can operate without a desktop session while still honouring the GUI-managed configuration.

> The automated installer already deploys and enables a tailored unit at `/etc/systemd/system/fw-cycle-monitor.service`. Use the steps above only if you need to perform a custom/manual deployment.

### Diagnosing the systemd service

If the unit fails to stay running after installation, you can reproduce the exact command that the service executes by using the `scripts/test_service_exec.sh` helper. The script parses the installed unit file, exports any `Environment=` variables, switches to the declared `WorkingDirectory`, and finally launches the `ExecStart` command as the configured service user. Run it with `sudo` so it can impersonate the target account:

```bash
sudo ./scripts/test_service_exec.sh
```

The helper streams the launcher’s output directly to your terminal so you can spot missing dependencies or display issues. Once the command exits, review the traditional systemd logs as well:

```bash
sudo systemctl status fw-cycle-monitor.service
sudo journalctl -u fw-cycle-monitor.service
```

If the helper reports a missing user, update the `User=` line in `/etc/systemd/system/fw-cycle-monitor.service` to match the account that should own the monitor (for example, `pi1` instead of the default `pi`), run `sudo systemctl daemon-reload`, and start the service again.

## Packaging

The project uses `pyproject.toml` with setuptools. Build distributables with:

```bash
python -m build
```

This produces a wheel and sdist in the `dist/` directory for distribution to additional machines.

## Development

- Run the GUI in development mode: `python -m fw_cycle_monitor`.
- Simulate GPIO events via the GUI when running off-device.
- Configure logging verbosity by setting the `PYTHONLOGLEVEL` environment variable (e.g., `PYTHONLOGLEVEL=DEBUG`).

Contributions and improvements are welcome!
