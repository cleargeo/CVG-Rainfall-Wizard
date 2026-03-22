<!--
  © Clearview Geographic LLC -- All Rights Reserved | Est. 2018
  CVG Rainfall Wizard — SECURITY
-->

# Security Policy — CVG Rainfall Wizard

> Proprietary Software | © Clearview Geographic LLC

---

## Supported Versions

| Version | Supported |
|---|---|
| 1.0.x | ✅ Active |
| < 1.0 | ❌ Not supported |

---

## Reporting a Vulnerability

**Do not open public GitHub issues for security vulnerabilities.**

Report directly to:
- **Email**: azelenski@clearviewgeographic.com
- **Subject**: `[SECURITY] CVG Rainfall Wizard — <Brief Description>`
- **Response time**: 48–72 business hours

---

## Security Practices

- No API keys are required (NOAA PFDS is a public unauthenticated API)
- All NOAA API calls use HTTPS
- Docker containers run as non-root user (`rfwiz`, UID 1001)
- No user-supplied input is executed as shell commands
- PFDS response data is validated before use

---

## Dependency Scanning

```bash
pip install pip-audit
pip-audit --requirement requirements-lock.txt
```

---

*© Clearview Geographic LLC — All Rights Reserved*
