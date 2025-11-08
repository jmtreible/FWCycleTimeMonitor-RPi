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
DESKTOP_NAME="FW Cycle Monitor.desktop"
MOUNT_POINT="${INSTALL_HOME}/FWCycle"
FSTAB_LINE="//192.168.0.249/Apps/FWCycle ${MOUNT_POINT} cifs _netdev,user=Operation1,password=Crows1991!,uid=${INSTALL_USER},gid=${INSTALL_GROUP},file_mode=0775,dir_mode=0775,noperm,vers=3.0 0 0"
APT_PACKAGES=(python3 python3-pip python3-venv python3-tk git cifs-utils rsync)

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
        echo "Creating Python virtual environment at ${VENV_DIR}..."
        python3 -m venv "${VENV_DIR}"
    fi

    if [[ ! -x "${VENV_BIN}/python" ]]; then
        echo "Error: virtual environment at ${VENV_DIR} is missing its Python interpreter." >&2
        exit 1
    fi
}

install_python_package() {
    echo "Installing Python package into ${VENV_DIR}..."
    "${VENV_BIN}/python" -m pip install --upgrade pip wheel
    "${VENV_BIN}/pip" install --upgrade "${INSTALL_DIR}[raspberrypi]"
}

ensure_cli_shims() {
    echo "Creating command shims for virtual environment..."
    local shim_dir="/usr/local/bin"
    mkdir -p "${shim_dir}"

    cat > "${shim_dir}/fw-cycle-monitor" <<'SHIM'
#!/usr/bin/env bash
exec "__VENV_BIN__/python" -m fw_cycle_monitor "$@"
SHIM

    cat > "${shim_dir}/fw-cycle-monitor-launcher" <<'SHIM'
#!/usr/bin/env bash
exec "__VENV_BIN__/python" -m fw_cycle_monitor.launcher "$@"
SHIM

    sed -i "s|__VENV_BIN__|${VENV_BIN}|g" "${shim_dir}/fw-cycle-monitor" "${shim_dir}/fw-cycle-monitor-launcher"
    chmod +x "${shim_dir}/fw-cycle-monitor" "${shim_dir}/fw-cycle-monitor-launcher"
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
    local desktop_dir="${INSTALL_HOME}/Desktop"
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
Exec=${VENV_BIN}/python -m fw_cycle_monitor
Icon=${icon_path}
Terminal=false
Categories=Utility;
Path=${INSTALL_DIR}
DESKTOP

    chmod +x "${desktop_file}"
    chown "${INSTALL_USER}:${INSTALL_GROUP}" "${desktop_file}"
    echo "Desktop shortcut created at ${desktop_file}."
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
Environment=PATH=${VENV_BIN}:/usr/bin:/bin
ExecStart=${VENV_BIN}/python -m fw_cycle_monitor.launcher
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

    systemctl daemon-reload
    systemctl enable --now fw-cycle-monitor.service
    echo "systemd service enabled and started."
}

install_apt_packages
deploy_repository
create_virtualenv
install_python_package
ensure_cli_shims
configure_network_share
create_desktop_entry

chown -R "${INSTALL_USER}:${INSTALL_GROUP}" "${INSTALL_DIR}"

configure_service

echo "\nInstallation complete!"
printf 'The FW Cycle Monitor GUI can be launched from the desktop shortcut or via "%s/.venv/bin/python -m fw_cycle_monitor".\n' "${INSTALL_DIR}"
printf 'Command shims (fw-cycle-monitor, fw-cycle-monitor-launcher) invoke the virtual environment.\n'
printf 'The monitoring service is managed by systemd as "fw-cycle-monitor.service".\n'

