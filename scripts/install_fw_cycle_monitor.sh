#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "This installer must be run with sudo or as root." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
INSTALL_USER="${SUDO_USER:-$(logname 2>/dev/null || id -un)}"
INSTALL_GROUP="$(id -gn "${INSTALL_USER}")"
INSTALL_HOME="$(eval echo "~${INSTALL_USER}")"
INSTALL_DIR="/opt/fw-cycle-monitor"
VENV_DIR="${INSTALL_DIR}/.venv"
VENV_BIN="${VENV_DIR}/bin"
ACTIVATE="${VENV_BIN}/activate"
DESKTOP_NAME="FW Cycle Monitor.desktop"
MOUNT_POINT="${INSTALL_HOME}/FWCycle"
CONFIG_HOME="${INSTALL_HOME}/.config/fw_cycle_monitor"
REMOTE_SUPERVISOR_CONFIG="${CONFIG_HOME}/remote_supervisor.json"
FSTAB_LINE="//192.168.0.249/Apps/FWCycle ${MOUNT_POINT} cifs _netdev,user=Operation1,password=Crows1991!,uid=${INSTALL_USER},gid=${INSTALL_GROUP},file_mode=0775,dir_mode=0775,noperm,vers=3.0 0 0"
APT_PACKAGES=(python3 python3-pip python3-venv python3-tk git cifs-utils rsync xdg-user-dirs)
INSTALL_EXTRAS="raspberrypi,remote_supervisor"

printf '\n=== FW Cycle Monitor Installer ===\n'
printf 'Detected user: %s\n' "${INSTALL_USER}"
printf 'Repository directory: %s\n' "${REPO_DIR}"
printf 'Target installation directory: %s\n\n' "${INSTALL_DIR}"

install_apt_packages() {
    echo "Installing required apt packages..."
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y "${APT_PACKAGES[@]}"
}

create_virtualenv() {
    if [[ -d "${VENV_DIR}" ]]; then
        echo "Existing virtual environment detected at ${VENV_DIR}."
    else
        echo "Creating Python virtual environment at ${VENV_DIR} (with system site packages)..."
        python3 -m venv --system-site-packages "${VENV_DIR}"
    fi

    if [[ ! -x "${VENV_BIN}/python" ]]; then
        echo "Error: virtual environment at ${VENV_DIR} is missing its Python interpreter." >&2
        exit 1
    fi
}

install_virtualenv_dependencies() {
    echo "Upgrading core Python tooling in the virtual environment..."
    "${VENV_BIN}/python" -m pip install --upgrade pip setuptools wheel

    echo "Installing GPIO backends (RPi.GPIO, lgpio, rpi-lgpio) inside the virtual environment..."
    "${VENV_BIN}/pip" install --upgrade RPi.GPIO lgpio rpi-lgpio

    echo "Verifying GPIO modules import correctly inside the virtual environment..."
    if ! "${VENV_BIN}/python" - <<'PY'
import importlib

required_modules = ("RPi.GPIO", "lgpio")
missing = []
for name in required_modules:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        missing.append(name)

if missing:
    raise ModuleNotFoundError(
        "Missing required GPIO modules inside the virtual environment: " + ", ".join(missing)
    )

try:
    importlib.import_module("rpi_lgpio")
except ModuleNotFoundError:
    print(
        "Warning: optional module 'rpi_lgpio' is not available. "
        "The fw-cycle-monitor package only requires RPi.GPIO for operation, "
        "but the installer attempted to provide the pip extras as well."
    )
PY
    then
        echo "Error: Failed to import GPIO dependencies inside the virtual environment." >&2
        exit 1
    fi
}

install_python_package() {
    echo "Installing FW Cycle Monitor into ${VENV_DIR}..."
    "${VENV_BIN}/pip" install --upgrade "${INSTALL_DIR}[${INSTALL_EXTRAS}]"
}

ensure_venv_launcher() {
    echo "Creating helper script to run commands inside the virtual environment..."
    cat > "${INSTALL_DIR}/run_in_venv.sh" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

ACTIVATE_PATH="__ACTIVATE__"
CONFIG_HOME="__CONFIG_HOME__"
INSTALL_DIR="__INSTALL_DIR__"
EXTRAS_SPEC="__INSTALL_EXTRAS__"

if [[ ! -f "${ACTIVATE_PATH}" ]]; then
    echo "Missing virtual environment activate script at ${ACTIVATE_PATH}" >&2
    exit 1
fi

# shellcheck disable=SC1090
source "${ACTIVATE_PATH}"

export FW_CYCLE_MONITOR_CONFIG_DIR="${CONFIG_HOME}"
export FW_CYCLE_MONITOR_REPO="${INSTALL_DIR}"

if [[ -n "${EXTRAS_SPEC}" ]]; then
    export FW_CYCLE_MONITOR_INSTALL_EXTRAS="${EXTRAS_SPEC}"
fi

if [[ -n "${PYTHONPATH:-}" ]]; then
    export PYTHONPATH="${INSTALL_DIR}/src:${PYTHONPATH}"
else
    export PYTHONPATH="${INSTALL_DIR}/src"
fi

if [[ $# -eq 0 ]]; then
    exec "$SHELL"
else
    exec "$@"
fi
SCRIPT

    sed -i \
        -e "s|__ACTIVATE__|${ACTIVATE}|g" \
        -e "s|__CONFIG_HOME__|${CONFIG_HOME}|g" \
        -e "s|__INSTALL_DIR__|${INSTALL_DIR}|g" \
        -e "s|__INSTALL_EXTRAS__|${INSTALL_EXTRAS}|g" \
        "${INSTALL_DIR}/run_in_venv.sh"
    chmod +x "${INSTALL_DIR}/run_in_venv.sh"
}

ensure_cli_shims() {
    echo "Creating command shims for virtual environment..."
    local shim_dir="/usr/local/bin"
    mkdir -p "${shim_dir}"

    cat > "${shim_dir}/fw-cycle-monitor" <<'SHIM'
#!/usr/bin/env bash
exec "__INSTALL_DIR__/run_in_venv.sh" python -m fw_cycle_monitor "$@"
SHIM

    cat > "${shim_dir}/fw-cycle-monitor-launcher" <<'SHIM'
#!/usr/bin/env bash
exec "__INSTALL_DIR__/run_in_venv.sh" python -m fw_cycle_monitor.launcher "$@"
SHIM

    cat > "${shim_dir}/fw-cycle-monitor-daemon" <<'SHIM'
#!/usr/bin/env bash
exec "__INSTALL_DIR__/run_in_venv.sh" python -m fw_cycle_monitor.service_runner "$@"
SHIM

    cat > "${shim_dir}/fw-remote-supervisor-cli" <<'SHIM'
#!/usr/bin/env bash
exec "__INSTALL_DIR__/run_in_venv.sh" python -m fw_cycle_monitor.remote_supervisor.cli "$@"
SHIM

    sed -i "s|__INSTALL_DIR__|${INSTALL_DIR}|g" \
        "${shim_dir}/fw-cycle-monitor" \
        "${shim_dir}/fw-cycle-monitor-launcher" \
        "${shim_dir}/fw-cycle-monitor-daemon" \
        "${shim_dir}/fw-remote-supervisor-cli"
    chmod +x \
        "${shim_dir}/fw-cycle-monitor" \
        "${shim_dir}/fw-cycle-monitor-launcher" \
        "${shim_dir}/fw-cycle-monitor-daemon" \
        "${shim_dir}/fw-remote-supervisor-cli"
}

deploy_repository() {
    echo "Copying project files to ${INSTALL_DIR}..."
    mkdir -p "${INSTALL_DIR}"
    rsync -a --delete \
        --exclude "__pycache__/" \
        --exclude ".venv/" \
        "${REPO_DIR}/" "${INSTALL_DIR}/"
}

configure_network_share() {
    echo "Configuring network share at ${MOUNT_POINT}..."
    mkdir -p "${MOUNT_POINT}"
    chown "${INSTALL_USER}:${INSTALL_GROUP}" "${MOUNT_POINT}"
    if ! grep -Fq "${FSTAB_LINE}" /etc/fstab; then
        echo "Adding network share to /etc/fstab..."
        printf '\n%s\n' "${FSTAB_LINE}" >> /etc/fstab
    else
        echo "Network share already present in /etc/fstab."
    fi
    if mountpoint -q "${MOUNT_POINT}"; then
        echo "Network share already mounted."
    else
        if mount "${MOUNT_POINT}"; then
            echo "Mounted network share at ${MOUNT_POINT}."
        else
            echo "Warning: failed to mount ${MOUNT_POINT}. Please check the network connection." >&2
        fi
    fi
}

create_desktop_entry() {
    local desktop_dir=""

    if command -v xdg-user-dir >/dev/null 2>&1; then
        if command -v sudo >/dev/null 2>&1; then
            desktop_dir="$(sudo -u "${INSTALL_USER}" xdg-user-dir DESKTOP 2>/dev/null || true)"
        else
            desktop_dir="$(su - "${INSTALL_USER}" -c 'xdg-user-dir DESKTOP' 2>/dev/null || true)"
        fi
    fi

    if [[ -z "${desktop_dir}" ]]; then
        desktop_dir="${INSTALL_HOME}/Desktop"
    fi

    echo "Using desktop directory: ${desktop_dir}"

    if [[ ! -d "${desktop_dir}" ]]; then
        echo "Desktop directory ${desktop_dir} not found; creating it."
        mkdir -p "${desktop_dir}"
        chown "${INSTALL_USER}:${INSTALL_GROUP}" "${desktop_dir}"
    fi

    local desktop_file="${desktop_dir}/${DESKTOP_NAME}"
    local icon_path="${INSTALL_DIR}/assets/fw-cycle-monitor.png"
    if [[ ! -f "${icon_path}" ]]; then
        icon_path="utilities-system-monitor"
    fi

    cat > "${desktop_file}" <<DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=FW Cycle Monitor
Comment=Launch the FW Cycle Monitor configuration GUI
Exec=${INSTALL_DIR}/run_in_venv.sh python -m fw_cycle_monitor.launcher
Icon=${icon_path}
Terminal=false
Categories=Utility;
Path=${INSTALL_DIR}
DESKTOP

    chmod +x "${desktop_file}"
    chown "${INSTALL_USER}:${INSTALL_GROUP}" "${desktop_file}"

    if [[ -f "${desktop_file}" ]]; then
        echo "Desktop shortcut created at ${desktop_file}."
    else
        echo "Warning: failed to create desktop shortcut at ${desktop_file}." >&2
    fi
}

configure_service() {
    echo "Configuring systemd service..."
    cat > /etc/systemd/system/fw-cycle-monitor.service <<SERVICE
[Unit]
Description=FW Cycle Time Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${INSTALL_USER}
WorkingDirectory=${INSTALL_DIR}
Environment=FW_CYCLE_MONITOR_REPO=${INSTALL_DIR}
Environment=FW_CYCLE_MONITOR_CONFIG_DIR=${CONFIG_HOME}
Environment=FW_CYCLE_MONITOR_INSTALL_EXTRAS=${INSTALL_EXTRAS}
Environment=PYTHONPATH=${INSTALL_DIR}/src
ExecStart=${VENV_BIN}/python -m fw_cycle_monitor.service_runner
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

    systemctl daemon-reload
    systemctl enable --now fw-cycle-monitor.service
    echo "systemd service enabled and started."
}

generate_remote_supervisor_api_key() {
    python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
}

detect_ip_address() {
    # Try to detect the primary IP address (preferring non-localhost)
    local ip_address

    # Try hostname -I first (most reliable on Raspberry Pi)
    if command -v hostname >/dev/null 2>&1; then
        ip_address=$(hostname -I 2>/dev/null | awk '{print $1}')
    fi

    # Fallback to ip command
    if [[ -z "${ip_address}" ]] && command -v ip >/dev/null 2>&1; then
        ip_address=$(ip route get 1.1.1.1 2>/dev/null | grep -oP 'src \K\S+')
    fi

    # Fallback to ifconfig
    if [[ -z "${ip_address}" ]] && command -v ifconfig >/dev/null 2>&1; then
        ip_address=$(ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1' | head -n1)
    fi

    # Final fallback to 0.0.0.0
    if [[ -z "${ip_address}" ]]; then
        ip_address="0.0.0.0"
    fi

    echo "${ip_address}"
}

ensure_remote_supervisor_config() {
    echo "Ensuring remote supervisor configuration at ${REMOTE_SUPERVISOR_CONFIG}..."
    mkdir -p "${CONFIG_HOME}"

    if [[ -f "${REMOTE_SUPERVISOR_CONFIG}" ]]; then
        echo "Remote supervisor config already exists; leaving in place."
        return
    fi

    local api_key
    api_key="$(generate_remote_supervisor_api_key)"

    local host_ip
    host_ip="$(detect_ip_address)"
    echo "Detected IP address: ${host_ip}"

    cat > "${REMOTE_SUPERVISOR_CONFIG}" <<CONFIG
{
  "host": "${host_ip}",
  "port": 8443,
  "unit_name": "fw-cycle-monitor.service",
  "api_keys": [
    "${api_key}"
  ],
  "certfile": null,
  "keyfile": null,
  "metrics_enabled": true,
  "stacklight": {
    "enabled": true,
    "mock_mode": false,
    "active_low": true,
    "startup_self_test": true,
    "pins": {
      "green": 26,
      "amber": 20,
      "red": 21
    }
  }
}
CONFIG

    chown "${INSTALL_USER}:${INSTALL_GROUP}" "${REMOTE_SUPERVISOR_CONFIG}"
    chmod 600 "${REMOTE_SUPERVISOR_CONFIG}"

    echo "Generated remote supervisor API key: ${api_key}"
    echo "Store this key securely. It is required for remote CLI access."
    echo ""
    echo "Stack light control is enabled in HARDWARE MODE by default."
    echo "A startup self-test will run when the service starts."
    echo "To disable hardware control, edit ${REMOTE_SUPERVISOR_CONFIG}"
    echo "and set 'mock_mode' to true under the 'stacklight' section."
}

configure_sudoers_for_remote_supervisor() {
    echo "Configuring sudo permissions for remote supervisor and GUI..."
    local sudoers_file="/etc/sudoers.d/fw-cycle-monitor"

    cat > "${sudoers_file}" <<SUDOERS
${INSTALL_USER} ALL=(ALL) NOPASSWD: /bin/systemctl start fw-cycle-monitor.service, /bin/systemctl stop fw-cycle-monitor.service, /bin/systemctl restart fw-cycle-monitor.service, /bin/systemctl status fw-cycle-monitor.service, /bin/systemctl start fw-remote-supervisor.service, /bin/systemctl stop fw-remote-supervisor.service, /bin/systemctl restart fw-remote-supervisor.service, /bin/systemctl status fw-remote-supervisor.service, /bin/systemctl is-active fw-remote-supervisor.service, /usr/sbin/shutdown
SUDOERS

    chmod 0440 "${sudoers_file}"

    if visudo -c -f "${sudoers_file}" >/dev/null 2>&1; then
        echo "Sudoers file created successfully at ${sudoers_file}"
    else
        echo "Error: sudoers file syntax validation failed" >&2
        rm -f "${sudoers_file}"
        exit 1
    fi
}

ensure_gpio_permissions() {
    echo "Ensuring ${INSTALL_USER} has GPIO permissions..."

    # Add user to gpio group if not already a member
    if ! groups "${INSTALL_USER}" | grep -q "\bgpio\b"; then
        echo "Adding ${INSTALL_USER} to gpio group..."
        usermod -a -G gpio "${INSTALL_USER}"
        echo "User ${INSTALL_USER} added to gpio group. GPIO access will be available after service restart."
    else
        echo "User ${INSTALL_USER} is already in gpio group."
    fi
}

configure_remote_supervisor_service() {
    echo "Configuring remote supervisor systemd service..."
    cat > /etc/systemd/system/fw-remote-supervisor.service <<SERVICE
[Unit]
Description=FW Cycle Monitor Remote Supervisor API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${INSTALL_USER}
Group=${INSTALL_GROUP}
SupplementaryGroups=gpio
Environment=FW_CYCLE_MONITOR_CONFIG_DIR=${CONFIG_HOME}
Environment=FW_CYCLE_MONITOR_REPO=${INSTALL_DIR}
Environment=FW_CYCLE_MONITOR_INSTALL_EXTRAS=${INSTALL_EXTRAS}
Environment=PYTHONPATH=${INSTALL_DIR}/src
WorkingDirectory=${INSTALL_DIR}
ExecStart=${VENV_BIN}/python -m fw_cycle_monitor.remote_supervisor.server --reload-settings
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

    systemctl daemon-reload
    systemctl enable --now fw-remote-supervisor.service
    echo "Remote supervisor service enabled and started."
}

install_apt_packages
deploy_repository
create_virtualenv
install_virtualenv_dependencies
install_python_package
ensure_venv_launcher
ensure_cli_shims
configure_network_share
create_desktop_entry

mkdir -p "${CONFIG_HOME}"
chown -R "${INSTALL_USER}:${INSTALL_GROUP}" "${CONFIG_HOME}"

chown -R "${INSTALL_USER}:${INSTALL_GROUP}" "${INSTALL_DIR}"

configure_service
ensure_remote_supervisor_config
configure_sudoers_for_remote_supervisor
ensure_gpio_permissions
configure_remote_supervisor_service

echo "\nInstallation complete!"
printf 'The FW Cycle Monitor GUI can be launched from the desktop shortcut or via "%s/.venv/bin/python -m fw_cycle_monitor".\n' "${INSTALL_DIR}"
printf 'Command shims (fw-cycle-monitor, fw-cycle-monitor-launcher, fw-cycle-monitor-daemon) invoke the virtual environment.\n'
printf 'The monitoring service is managed by systemd as "fw-cycle-monitor.service".\n'

