# Security Audit VM - 2026-03-03

## Findings (high to low)

1. SSH root login with password is enabled.
   - Evidence: `sshd -T` shows `permitrootlogin yes` and `passwordauthentication yes`.
   - Risk: brute-force and credential compromise on privileged account.

2. Multiple public listening ports are exposed on `0.0.0.0`.
   - Evidence: `ss -tulpn` shows exposed `22`, `53`, `80`, `3000`, `3002`, `8081`, `8100`, `8123`.
   - Risk: larger attack surface and unauthenticated probing.

3. Secrets are stored in plain `.env` files on disk.
   - Evidence: `.env.keys.local`, `.env.local`, `/mascarade/.env` include API keys/password fields.
   - Risk: local disclosure via mis-permissions, backups, or command output leaks.

4. `docker` group grants effective root-level host access.
   - Evidence: `getent group docker` includes non-root users (`zacus`, `cils`).
   - Risk: container/socket access can escalate to root-equivalent control.

## Mitigations applied now

- Added container-state observability with systemd timer:
  - `container-observability.service`
  - `container-observability.timer`
  - alerts in `/var/log/container-observability-alerts.log` and journald
- Standardized compose runtime env generation (`.env.runtime`) and wrapper usage.
- Applied collaborative permissions policy with group `users` + setgid on project roots.

## Recommended next hardening

1. Restrict SSH:
   - Prefer `PermitRootLogin prohibit-password`.
   - Keep root password only for console recovery.
   - Add IP allowlist or fail2ban.

2. Reduce exposure:
   - Bind non-public services to `127.0.0.1`.
   - Put public entrypoints behind a reverse proxy with auth/TLS.

3. Secret handling:
   - Keep `*.env` at `600` and owned by root where possible.
   - Rotate currently configured API tokens.
   - Avoid printing env values in shell history/logs.

4. Docker access model:
   - Keep `docker` group minimal.
   - Use audited operational accounts for deployment actions.
