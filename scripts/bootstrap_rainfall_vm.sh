#!/usr/bin/env bash
# =============================================================================
# CVG Rainfall Wizard — VM Bootstrap Script (Ubuntu 22.04 LTS)
# Clearview Geographic LLC — Proprietary and Confidential
# =============================================================================
# Run inside a fresh Ubuntu 22.04 VM after OS install.
# Mounts the CVG CGPS SMB share from TrueNAS (10.10.10.100), rsyncs
# the Rainfall Wizard repo, creates a virtualenv, and installs dependencies.
#
# Usage:
#   chmod +x bootstrap_rainfall_vm.sh
#   sudo ./bootstrap_rainfall_vm.sh
# =============================================================================
set -euo pipefail

CGPS_SMB="//10.10.10.100/cgps"
CGPS_MOUNT="/mnt/cgps"
SMB_USER="${SMB_USER:-azelenski}"
SMB_PASS="${SMB_PASS:-}"

REPO_SRC="${CGPS_MOUNT}/07_APPLICATIONS_TOOLS/CVG_Rainfall Wizard"
REPO_DST="/opt/cvg/CVG_Rainfall_Wizard"
VENV_DIR="${REPO_DST}/.venv"
SERVICE_PORT=8020

echo "============================================================"
echo "  CVG Rainfall Wizard — VM Bootstrap"
echo "  Target: ${REPO_DST}"
echo "============================================================"

# ── System packages ──────────────────────────────────────────────────────────
apt-get update -q
apt-get install -y -q \
    python3.11 python3.11-venv python3.11-dev \
    python3-pip git build-essential \
    gdal-bin libgdal-dev libproj-dev \
    cifs-utils curl jq

# ── Mount CGPS share ─────────────────────────────────────────────────────────
mkdir -p "${CGPS_MOUNT}"
if ! mountpoint -q "${CGPS_MOUNT}"; then
    if [[ -z "${SMB_PASS}" ]]; then
        read -rsp "SMB password for ${SMB_USER}: " SMB_PASS
        echo
    fi
    mount -t cifs "${CGPS_SMB}" "${CGPS_MOUNT}" \
        -o "username=${SMB_USER},password=${SMB_PASS},uid=$(id -u),gid=$(id -g),vers=3.0"
    echo "  [OK] CGPS share mounted at ${CGPS_MOUNT}"
else
    echo "  [OK] CGPS share already mounted"
fi

# ── Sync repo ────────────────────────────────────────────────────────────────
mkdir -p "${REPO_DST}"
rsync -av --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.egg-info' \
    --exclude='.venv' \
    --exclude='htmlcov' \
    "${REPO_SRC}/" "${REPO_DST}/"
echo "  [OK] Repo synced to ${REPO_DST}"

# ── Python virtualenv ─────────────────────────────────────────────────────────
python3.11 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip wheel
"${VENV_DIR}/bin/pip" install -r "${REPO_DST}/requirements-lock.txt"
"${VENV_DIR}/bin/pip" install -e "${REPO_DST}"
echo "  [OK] Virtualenv created and packages installed"

# ── Systemd service ───────────────────────────────────────────────────────────
cat > /etc/systemd/system/cvg-rainfall-wizard.service <<EOF
[Unit]
Description=CVG Rainfall Wizard API
After=network.target

[Service]
Type=simple
User=cvg
WorkingDirectory=${REPO_DST}
ExecStart=${VENV_DIR}/bin/uvicorn rainfall_wizard.web_api:app --host 0.0.0.0 --port ${SERVICE_PORT} --workers 2
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

id cvg &>/dev/null || useradd -r -s /bin/false cvg
chown -R cvg:cvg "${REPO_DST}"

systemctl daemon-reload
systemctl enable cvg-rainfall-wizard.service
systemctl start cvg-rainfall-wizard.service

echo ""
echo "============================================================"
echo "  Bootstrap complete!"
echo "  CVG Rainfall Wizard running on http://0.0.0.0:${SERVICE_PORT}"
echo "  Service: cvg-rainfall-wizard.service"
echo "============================================================"
