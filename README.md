# FW Cycle Time Monitor

A lightweight Raspberry Pi application that logs mold close events for injection molding machines. Each detected cycle writes the machine identifier and timestamp to a CSV file for production tracking.

## Features

- **Automatic updates**: Optional launcher checks the GitHub `main` branch for new commits and pulls them before starting the GUI.
- **Configurable logging**: Define machine number, GPIO input pin, and CSV storage directory. CSV files follow the `CM_<MachineID>.csv` naming pattern.
- **Simple GUI**: Tkinter-based interface to configure hardware settings, start/stop monitoring, and log test events without hardware.
- **Raspberry Pi ready**: Uses `RPi.GPIO` for hardware access and is packaged for straightforward installation.
- **Auto-start support**: Example `systemd` unit file for launching on boot.

## Project layout

```
.
├── pyproject.toml            # Packaging metadata
├── README.md                 # Project documentation
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

1. **Install system dependencies**

   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-tk git
   sudo pip3 install RPi.GPIO  # already available on Raspberry Pi OS, if missing
   ```

2. **Clone the repository** (or copy the packaged distribution):

   ```bash
   git clone https://github.com/<your-org>/FWCycleTimeMonitor-RPi.git
   cd FWCycleTimeMonitor-RPi
   ```

3. **Install the application** (editable/development mode shown):

   ```bash
   pip install -e .
   ```

   For regular installation from a package wheel or sdist:

   ```bash
   pip install fw-cycle-monitor-0.1.0-py3-none-any.whl
   ```

## Usage

### Launch the GUI directly

```bash
python -m fw_cycle_monitor
```

### Launch with update checks

The launcher pulls the newest `main` branch revision before starting the GUI. By default it uses the repository that contains the scripts, but you can override it using the `FW_CYCLE_MONITOR_REPO` environment variable.

```bash
python -m fw_cycle_monitor.launcher
```

### Configuration fields

- **Machine ID**: Text identifier (e.g. `M201`). Used in the CSV file name and log entries.
- **GPIO Pin (BCM)**: Input pin that receives the 3.3 V mold close signal (BCM numbering).
- **CSV Directory**: Folder where CSV output is saved. Each machine logs to `CM_<MachineID>.csv` with headers `machine_id,timestamp`.

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
