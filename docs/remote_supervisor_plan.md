# Remote Supervisor Deployment Plan

## Objectives
- Allow authorized operators to start, stop, and restart the `fw-cycle-monitor` systemd service running on any deployed Raspberry Pi without physical access.
- Support both single-device control and fleet-wide orchestration for ~40 devices initially, with headroom for growth.
- Preserve the reliability guarantees provided by systemd while adding secure remote automation capabilities.

## Architecture Overview
1. **Existing Monitor Service**
   - Keep the current `fw-cycle-monitor.service` systemd unit unchanged so the monitor continues to benefit from automatic restarts and log management.
2. **Remote Supervisor Agent**
   - Deploy a lightweight REST API (FastAPI or Flask) on each Pi as a new systemd service (`fw-remote-supervisor.service`).
   - The agent exposes HTTPS endpoints that wrap `systemctl` commands for the monitor service and reports runtime status.
3. **Central Orchestrator**
   - Provide a web-based dashboard or CLI tool hosted on your internal network that authenticates to each agent to issue control requests individually or in bulk.
4. **Secure Communication**
   - Use mutual TLS certificates issued by your internal CA or short-lived signed tokens to ensure only authorized clients control devices.

```
+-------------------+      HTTPS (mTLS)      +-------------------------+
| Central Dashboard | <--------------------> |  Pi Remote Supervisor   |
| / CLI Tool        |                        |  (FastAPI + systemctl)  |
+-------------------+                        +------------+------------+
                                                          |
                                                          v
                                              +-----------------------+
                                              | fw-cycle-monitor.service |
                                              +-----------------------+
```

## Remote Supervisor Agent
- **Endpoints**
  - `GET /service/status`: returns systemd active state, last start time, and recent monitor metrics (reads existing JSON written by the monitor).
  - `POST /service/start`: runs `systemctl start fw-cycle-monitor.service`.
  - `POST /service/stop`: runs `systemctl stop fw-cycle-monitor.service`.
  - `POST /service/restart`: runs `systemctl restart fw-cycle-monitor.service`.
  - `POST /config/reload` (optional): re-reads the JSON config and reports new settings to confirm updates.
- **Implementation Details**
  - Run under a dedicated Unix user with `sudo` permissions restricted to the monitor service.
  - Log every request and result to syslog for auditing.
  - Serve via `uvicorn` behind `systemd`'s `SocketActivate` or `gunicorn` with HTTPS termination using `ssl.SSLContext`.
  - Share the existing virtual environment and configuration directory so the agent can reuse helper functions from `fw_cycle_monitor.config`.

## Central Orchestrator
- Maintain an inventory (machine ID, IP address, location) in a database or configuration file.
- Offer bulk actions by iterating over the inventory and issuing parallel HTTPS requests.
- Provide live status by polling `GET /service/status`; show monitor metrics (last cycle, averages) and alert on stale data.
- Store action logs centrally (e.g., to ELK stack or CloudWatch) for auditing and troubleshooting.

## Deployment Strategy
1. **Packaging**
   - Extend the existing install script to create the supervisor virtual environment, install FastAPI, and drop the new systemd unit files.
   - Bundle TLS certificates and keys during provisioning, or integrate with an automated certificate enrollment process (e.g., Hashicorp Vault, Smallstep).
2. **Rollout**
   - Pilot on 2–3 devices to validate security and functionality.
   - Roll out to remaining Pis via configuration management (Ansible, Salt) or your existing deployment pipeline.
3. **Monitoring & Alerting**
   - Configure systemd to restart the supervisor on failure.
   - Expose Prometheus metrics or simple heartbeat logs so the central dashboard can detect offline agents.

## Security Considerations
- Restrict firewall rules so the supervisor port is reachable only from the management VLAN or VPN.
- Enforce client authentication (mTLS preferred) and strict TLS versions/cipher suites.
- Rate-limit sensitive endpoints and include nonce/timestamp validation to prevent replay attacks.
- Rotate certificates/keys regularly and revoke compromised credentials immediately.

## Alternative: SSH + Automation Tooling
- Manage a secure SSH key and inventory of hostnames.
- Use Ansible or parallel-SSH to execute `systemctl` commands remotely.
- Lower implementation effort but lacks the audit trail and API integration capabilities of the supervisor agent.

## Next Steps
1. Draft FastAPI endpoint implementations and supporting systemd unit files.
2. Define certificate issuance/rotation process with your network/security team.
3. Implement the central orchestration dashboard or adapt an existing tool to call the new APIs.
4. Perform end-to-end testing (single device, batch operations, failure scenarios) before full deployment.
