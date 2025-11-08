#!/usr/bin/env bash
set -euo pipefail

SERVICE_FILE="${1:-/etc/systemd/system/fw-cycle-monitor.service}"

if [[ ${EUID} -ne 0 ]]; then
    echo "This diagnostic helper must be run with sudo or as root." >&2
    exit 1
fi

if [[ ! -f "${SERVICE_FILE}" ]]; then
    echo "Service file not found at ${SERVICE_FILE}." >&2
    exit 1
fi

service_user="$(awk -F= '/^User=/ {print $2}' "${SERVICE_FILE}" | tail -n 1)"
if [[ -z "${service_user}" ]]; then
    service_user="root"
fi

working_dir="$(awk -F= '/^WorkingDirectory=/ {print $2}' "${SERVICE_FILE}" | tail -n 1)"
exec_cmd="$(awk -F= '/^ExecStart=/ {print substr($0, index($0,$2))}' "${SERVICE_FILE}" | tail -n 1)"

if [[ -z "${exec_cmd}" ]]; then
    echo "ExecStart command not found in ${SERVICE_FILE}." >&2
    exit 1
fi

mapfile -t env_lines < <(grep '^Environment=' "${SERVICE_FILE}" || true)

declare -a env_exports=()
for line in "${env_lines[@]}"; do
    kv="${line#Environment=}"
    env_exports+=("${kv}")
    export "${kv}"
done

if [[ -n "${working_dir}" ]]; then
    if [[ ! -d "${working_dir}" ]]; then
        echo "Working directory ${working_dir} does not exist." >&2
        exit 1
    fi
    cd "${working_dir}"
fi

printf 'Starting service command as %s...\n' "${service_user}"
printf 'Command: %s\n' "${exec_cmd}"

# If the ExecStart command references an absolute script path, make sure it exists
read -r -a exec_parts <<< "${exec_cmd}"
cmd_path="${exec_parts[0]:-}"
if [[ "${cmd_path}" == /* ]]; then
    if [[ ! -e "${cmd_path}" ]]; then
        echo "Executable referenced in ExecStart is missing: ${cmd_path}" >&2
        echo "Re-run the installer or restore the helper script before testing the service." >&2
        exit 1
    fi
fi

if command -v sudo >/dev/null 2>&1; then
    exec sudo -u "${service_user}" bash -lc "${exec_cmd}"
else
    exec su - "${service_user}" -c "${exec_cmd}"
fi
