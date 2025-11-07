# FW Cycle Time Monitor

A lightweight Raspberry Pi application that logs mold close events for injection molding machines. Each detected cycle writes the cycle number, machine identifier, and timestamp to a CSV file for production tracking.

## Features

- **Automatic updates**: Optional launcher checks the GitHub `main` branch for new commits and pulls them before starting the GUI.
- **Configurable logging**: Define machine number, GPIO input pin, and CSV storage directory. CSV files follow the `CM_<MachineID>.csv` naming pattern.
- **Simple GUI**: Tkinter-based interface to configure hardware settings, start/stop monitoring, and log test events without hardware.
- **Raspberry Pi ready**: Uses `RPi.GPIO` for hardware access and is packaged for straightforward installation.
- **Guided installation**: A one-command installer prepares dependencies, configures the network share, enables the boot service, and drops a desktop shortcut for the GUI.
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

   - Installs required APT packages (`python3`, `python3-tk`, `git`, `cifs-utils`, `rsync`, etc.).
   - Installs the `fw-cycle-monitor` Python package with Raspberry Pi GPIO extras.
   - Copies the repository to `/opt/fw-cycle-monitor` so the auto-updater has a stable working tree.
   - Adds the network share `//192.168.0.249/Apps` to `/etc/fstab`, mounting it at `${HOME}/Apps` with the provided credentials (`Operation1` / `Crows1991!`).
   - Enables and starts the `fw-cycle-monitor.service` systemd unit that launches the auto-updating monitor on boot.
   - Creates a “FW Cycle Monitor” desktop shortcut that runs the GUI (`fw-cycle-monitor`).

   > **Security note:** Credentials for the network share are stored in `/etc/fstab`. Review and adjust permissions according to your facility’s policies.

4. Confirm the share is mounted (`ls ${HOME}/Apps`) and that the desktop shortcut launches the GUI. The monitoring service will continue running in the background.

### Manual installation (for development)

Follow these steps if you prefer to manage the environment yourself (e.g., during development or when adapting the project for a different deployment workflow):

1. **Install system dependencies**

   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-tk git
   ```

2. **Clone (or extract) the repository**

   ```bash
   git clone https://github.com/<your-org>/FWCycleTimeMonitor-RPi.git
   cd FWCycleTimeMonitor-RPi
   ```

3. **Install the application**

   For editable/development mode:

   ```bash
   python3 -m pip install --user -e .
   ```

   Or install from a built wheel/sdist (produced via `python -m build`):

   ```bash
   python3 -m pip install fw-cycle-monitor-0.1.0-py3-none-any.whl
   ```

4. **Install Raspberry Pi GPIO support (when running on real hardware)**

   ```bash
   python3 -m pip install RPi.GPIO
   ```

### Customizing the installer

The installer uses the account that invokes `sudo` as the service user and mounts the network share at `${HOME}/Apps`. Adjust `scripts/install_fw_cycle_monitor.sh` before running it if you need to:

- Change the mount location, credentials, or SMB server information.
- Deploy the repository to a different directory than `/opt/fw-cycle-monitor`.
- Skip the desktop shortcut creation (comment out `create_desktop_entry`).

Re-run the installer after making modifications to propagate the changes.

## Usage

### Launch the GUI directly

```bash
python -m fw_cycle_monitor
```

You can also use the **FW Cycle Monitor** desktop shortcut that the installer places on the Raspberry Pi desktop. Internally it runs the same `fw-cycle-monitor` entry point.

### Launch with update checks

The launcher pulls the newest `main` branch revision before starting the GUI. By default it uses the repository that contains the scripts, but you can override it using the `FW_CYCLE_MONITOR_REPO` environment variable.

```bash
python -m fw_cycle_monitor.launcher
```

### Configuration fields

- **Machine ID**: Text identifier (e.g. `M201`). Used in the CSV file name and log entries.
- **GPIO Pin (BCM)**: Input pin that receives the 3.3 V mold close signal (BCM numbering).
- **CSV Directory**: Folder where CSV output is saved. Each machine logs to `CM_<MachineID>.csv` with headers `cycle_number,machine_id,timestamp`, and cycle numbers reset to 1 every day at 3 AM.

The application persists settings to `~/.config/fw_cycle_monitor/config.json`.

### Test events without hardware

Use the **Log Test Event** button to append a simulated timestamp to the configured CSV. This works even when running on a non-Raspberry Pi development machine.

## Auto-start with systemd

An example service file is provided under `systemd/fw-cycle-monitor.service`. Adjust the `User`, `WorkingDirectory`, and path to Python as needed, then install and enable it:

```bash
sudo cp systemd/fw-cycle-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable fw-cycle-monitor.service
sudo systemctl start fw-cycle-monitor.service
```

The service uses the update-aware launcher so the Pi automatically pulls the latest code before starting the GUI at boot.

> The automated installer already deploys and enables a tailored unit at `/etc/systemd/system/fw-cycle-monitor.service`. Use the steps above only if you need to perform a custom/manual deployment.

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
