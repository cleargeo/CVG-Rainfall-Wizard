#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# CVG Rainfall Wizard — Production Deployment Bootstrap
# Target: VM 452 (cvg-rainfall-01) — 10.10.10.201 — rainfall.cleargeo.tech
# Proxmox: CVG-QUEEN-11-PROXMOX (10.10.10.56)
#
# USAGE (from DFORGE-100 workstation Git Bash):
#   cd "G:/07_APPLICATIONS_TOOLS/CVG_Rainfall Wizard"
#   bash deploy_production.sh
#
# WHAT THIS DOES:
#   1. Creates VM 452 on Proxmox via SSH (Ubuntu 22.04 cloud-init)
#   2. Waits for VM SSH availability
#   3. Bootstraps VM: Docker CE, CIFS tools
#   4. Mounts TrueNAS CGPS + CGDP
#   5. rsyncs this project to /opt/cvg/CVG_Rainfall_Wizard on VM
#   6. Builds + launches docker-compose.prod.yml (Rainfall API + Caddy)
#   7. Health-checks /health endpoint
# ══════════════════════════════════════════════════════════════════════════════

set -euo pipefail
IFS=$'\n\t'

# ── Config ─────────────────────────────────────────────────────────────────
PROXMOX_HOST="10.10.10.56"
PROXMOX_NODE="CVG-QUEEN-11-PROXMOX"
VMID=452
VM_STATIC_IP="10.10.10.201"
VM_HOSTNAME="cvg-rainfall-01"
VM_GW="10.10.10.1"
VM_DNS="8.8.8.8 1.1.1.1"
VM_RAM=16384     # 16 GB
VM_CORES=4
VM_DISK_SIZE=60  # GB
DISK_POOL="PE-Enclosure1"

CI_USER="ubuntu"
CI_PASS="CVGadmin2026!"

# TrueNAS CGPS/CGDP
TRUENAS_CGPS_SHARE="//10.10.10.100/cgps"
TRUENAS_CGDP_SHARE="//10.10.10.100/cgdp"
SMB_USER="ProcessingVM1"
SMB_PASS="CVGproc1!2026"
SMB_DOMAIN="WORKGROUP"

# Project paths (note: source dir has a space in the name)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DEST="/opt/cvg/CVG_Rainfall_Wizard"

# Domain
SUBDOMAIN="rainfall"
DOMAIN="cleargeo.tech"
PUBLIC_IP="131.148.52.225"
APP_PORT="8020"

# SSH
SSH_KEY="${HOME}/.ssh/cvg_neuron_proxmox"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=30 -o ServerAliveInterval=15"

# Proxmox API
PVE_TOKEN="PVEAPIToken=root@pam!fulltoken=d0af97b6-36df-49e7-82dc-ed37a8c4f3ff"

# Ubuntu 22.04 cloud-init image
CLOUD_IMG="jammy-server-cloudimg-amd64.img"
CLOUD_IMG_URL="https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
TEMPLATE_VMID=9000

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*"; }
info() { echo -e "${BLUE}[i]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }
step() { echo -e "\n${CYAN}══ Step $1: $2 ══${NC}"; }

# ══════════════════════════════════════════════════════════════════════════════
# STEP 0: Pre-flight
# ══════════════════════════════════════════════════════════════════════════════

step 0 "Pre-flight checks"

[ -f "${SSH_KEY}" ]                            || err "SSH key not found: ${SSH_KEY}"
[ -f "${SCRIPT_DIR}/Dockerfile" ]              || err "Dockerfile not found in ${SCRIPT_DIR}"
[ -f "${SCRIPT_DIR}/docker-compose.prod.yml" ] || err "docker-compose.prod.yml not found"
[ -f "${SCRIPT_DIR}/caddy/Caddyfile" ]         || err "caddy/Caddyfile not found"

log "Script dir:  ${SCRIPT_DIR}"
log "Target VM:   ${VMID} (${VM_HOSTNAME}) @ ${VM_STATIC_IP}"
log "Public URL:  https://${SUBDOMAIN}.${DOMAIN}"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: Create VM on Proxmox
# ══════════════════════════════════════════════════════════════════════════════

step 1 "Provision VM ${VMID} on Proxmox ${PROXMOX_HOST}"

VM_STATUS=$(curl -sk -H "Authorization: ${PVE_TOKEN}" \
    "https://${PROXMOX_HOST}:8006/api2/json/nodes/${PROXMOX_NODE}/qemu/${VMID}/status/current" \
    2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(d.get('data',{}).get('status','missing'))
except:
    print('missing')
" 2>/dev/null || echo "missing")

info "VM ${VMID} status: ${VM_STATUS}"

if [[ "${VM_STATUS}" == "missing" ]] || [[ -z "${VM_STATUS}" ]]; then

    if [ -f "${SSH_KEY}.pub" ]; then
        log "Uploading SSH public key to Proxmox..."
        scp ${SSH_OPTS} -i "${SSH_KEY}" "${SSH_KEY}.pub" "root@${PROXMOX_HOST}:/tmp/cvg_deploy_key_${VMID}.pub" 2>/dev/null || true
    fi

    ssh ${SSH_OPTS} -i "${SSH_KEY}" "root@${PROXMOX_HOST}" /bin/bash << PROXMOX_EOF

set -euo pipefail
VMID="${VMID}"
VM_NAME="${VM_HOSTNAME}"
VM_IP="${VM_STATIC_IP}"
VM_GW="${VM_GW}"
VM_DNS="${VM_DNS}"
VM_RAM="${VM_RAM}"
VM_CORES="${VM_CORES}"
VM_DISK="${VM_DISK_SIZE}"
DISK_POOL="${DISK_POOL}"
TEMPLATE="${TEMPLATE_VMID}"
CLOUD_IMG="${CLOUD_IMG}"
CLOUD_IMG_URL="${CLOUD_IMG_URL}"
CI_USER="${CI_USER}"
CI_PASS="${CI_PASS}"
PUB_KEY_FILE="/tmp/cvg_deploy_key_${VMID}.pub"

echo "[proxmox] === CVG Rainfall Wizard VM \$VMID ==="

if ! qm status \$TEMPLATE &>/dev/null; then
    echo "[proxmox] Creating cloud-init template \$TEMPLATE..."
    IMG_PATH="/var/lib/vz/template/iso/\${CLOUD_IMG}"
    if [ ! -f "\$IMG_PATH" ]; then
        CGPS_IMG=""
        mountpoint -q /mnt/cgps 2>/dev/null && CGPS_IMG=\$(find /mnt/cgps -name "\$CLOUD_IMG" 2>/dev/null | head -1) || true
        if [ -n "\$CGPS_IMG" ]; then cp "\$CGPS_IMG" "\$IMG_PATH"
        else wget -q --show-progress -O "\$IMG_PATH" "\$CLOUD_IMG_URL"; fi
    fi
    qm create \$TEMPLATE --name ubuntu-2204-template \
        --memory 2048 --cores 2 --net0 virtio,bridge=vmbr0 \
        --ostype l26 --scsihw virtio-scsi-single --serial0 socket --vga serial0
    DISK_FILE=\$(qm importdisk \$TEMPLATE "\$IMG_PATH" "\$DISK_POOL" 2>&1 | grep -o "vm-\${TEMPLATE}-disk-[0-9]*" | head -1)
    [ -z "\$DISK_FILE" ] && DISK_FILE="vm-\${TEMPLATE}-disk-0"
    qm set \$TEMPLATE \
        --scsi0 \${DISK_POOL}:\${DISK_FILE} --ide2 \${DISK_POOL}:cloudinit \
        --boot c --bootdisk scsi0 --agent enabled=1
    qm template \$TEMPLATE
    echo "[proxmox] Template \$TEMPLATE ready"
fi

qm clone \$TEMPLATE \$VMID --name "\$VM_NAME" --full
qm set \$VMID --memory \$VM_RAM --balloon 0 --cores \$VM_CORES --sockets 1 --cpu host
qm resize \$VMID scsi0 \${VM_DISK}G
qm set \$VMID \
    --ipconfig0 "ip=\${VM_IP}/24,gw=\${VM_GW}" \
    --nameserver "\$VM_DNS" \
    --ciuser "\$CI_USER" \
    --cipassword "\$(openssl passwd -6 "\$CI_PASS")"
[ -f "\$PUB_KEY_FILE" ] && qm set \$VMID --sshkeys "\$PUB_KEY_FILE" && rm -f "\$PUB_KEY_FILE"
qm set \$VMID --description "CVG Rainfall Wizard — FastAPI / NOAA Atlas 14
URL: https://rainfall.cleargeo.tech | Port: ${APP_PORT}
Created: \$(date -u +%Y-%m-%dT%H:%M:%SZ)"
qm start \$VMID
echo "[proxmox] VM \$VMID started"

PROXMOX_EOF

    log "VM ${VMID} created — waiting 90s for cloud-init..."
    sleep 90

elif [[ "${VM_STATUS}" == "stopped" ]]; then
    curl -sk -X POST -H "Authorization: ${PVE_TOKEN}" \
        "https://${PROXMOX_HOST}:8006/api2/json/nodes/${PROXMOX_NODE}/qemu/${VMID}/status/start" > /dev/null
    sleep 30
else
    log "VM ${VMID} already running"
fi

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: Wait for VM SSH
# ══════════════════════════════════════════════════════════════════════════════

step 2 "Wait for VM SSH (${CI_USER}@${VM_STATIC_IP})"

MAX_WAIT=300; ELAPSED=0
until ssh ${SSH_OPTS} -i "${SSH_KEY}" "${CI_USER}@${VM_STATIC_IP}" "echo ok" 2>/dev/null; do
    [ $ELAPSED -ge $MAX_WAIT ] && err "SSH timeout — check https://${PROXMOX_HOST}:8006"
    printf "  waiting... (%ds/%ds)\r" "$ELAPSED" "$MAX_WAIT"
    sleep 10; ELAPSED=$((ELAPSED + 10))
done
echo ""; log "SSH OK: ${CI_USER}@${VM_STATIC_IP}"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: Bootstrap VM
# ══════════════════════════════════════════════════════════════════════════════

step 3 "Bootstrap Docker + CIFS on VM ${VM_STATIC_IP}"

ssh ${SSH_OPTS} -i "${SSH_KEY}" "${CI_USER}@${VM_STATIC_IP}" /bin/bash << 'VM_BOOTSTRAP'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq && sudo apt-get upgrade -yq 2>/dev/null
sudo apt-get install -yq curl wget git htop vim tmux rsync jq unzip cifs-utils nfs-common ca-certificates
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker ubuntu && sudo systemctl enable --now docker
fi
docker compose version &>/dev/null || sudo apt-get install -yq docker-compose-plugin
sudo mkdir -p /opt/cvg /opt/cvg/.secrets /mnt/cgps /mnt/cgdp /var/log/caddy
sudo chown -R ubuntu:ubuntu /opt/cvg
echo "[vm] Bootstrap: Docker $(docker --version | cut -d' ' -f3)"
VM_BOOTSTRAP

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: Mount TrueNAS shares
# ══════════════════════════════════════════════════════════════════════════════

step 4 "Mount TrueNAS CGPS + CGDP"

ssh ${SSH_OPTS} -i "${SSH_KEY}" "${CI_USER}@${VM_STATIC_IP}" /bin/bash << MOUNT_SCRIPT
set -euo pipefail
sudo mkdir -p /etc/smbcredentials
sudo tee /etc/smbcredentials/cgps > /dev/null << 'EOF'
username=${SMB_USER}
password=${SMB_PASS}
domain=${SMB_DOMAIN}
EOF
sudo chmod 600 /etc/smbcredentials/cgps && sudo chown root:root /etc/smbcredentials/cgps

mountpoint -q /mnt/cgps || sudo mount -t cifs "${TRUENAS_CGPS_SHARE}" /mnt/cgps \
    -o credentials=/etc/smbcredentials/cgps,vers=3.0,uid=1000,gid=1000,file_mode=0664,dir_mode=0775,_netdev \
    && echo "[vm] CGPS mounted" || echo "[vm] WARN: CGPS mount failed"

mountpoint -q /mnt/cgdp || sudo mount -t cifs "${TRUENAS_CGDP_SHARE}" /mnt/cgdp \
    -o credentials=/etc/smbcredentials/cgps,vers=3.0,uid=1000,gid=1000,file_mode=0664,dir_mode=0775,_netdev \
    && echo "[vm] CGDP mounted" || echo "[vm] WARN: CGDP mount failed"

grep -q "cgps" /etc/fstab || sudo tee -a /etc/fstab > /dev/null << 'EOF'

# CVG TrueNAS shares
${TRUENAS_CGPS_SHARE} /mnt/cgps cifs credentials=/etc/smbcredentials/cgps,vers=3.0,uid=1000,gid=1000,file_mode=0664,dir_mode=0775,soft,_netdev 0 0
${TRUENAS_CGDP_SHARE} /mnt/cgdp cifs credentials=/etc/smbcredentials/cgps,vers=3.0,uid=1000,gid=1000,file_mode=0664,dir_mode=0775,soft,_netdev 0 0
EOF
MOUNT_SCRIPT

log "Shares configured"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: Sync project files
# ══════════════════════════════════════════════════════════════════════════════

step 5 "Sync project to ${PROJECT_DEST}"

log "rsyncing '${SCRIPT_DIR}' → ${CI_USER}@${VM_STATIC_IP}:${PROJECT_DEST}"

rsync -avz --progress \
    --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.pytest_cache' --exclude='htmlcov' --exclude='.coverage' \
    -e "ssh ${SSH_OPTS} -i ${SSH_KEY}" \
    "${SCRIPT_DIR}/" "${CI_USER}@${VM_STATIC_IP}:${PROJECT_DEST}/"

log "Project synced"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: Build + launch Docker stack
# ══════════════════════════════════════════════════════════════════════════════

step 6 "Build + launch production Docker stack"

ssh ${SSH_OPTS} -i "${SSH_KEY}" "${CI_USER}@${VM_STATIC_IP}" /bin/bash << 'DOCKER_SCRIPT'
set -euo pipefail
cd /opt/cvg/CVG_Rainfall_Wizard

docker compose -f docker-compose.prod.yml pull --ignore-pull-failures 2>/dev/null || true
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
docker compose -f docker-compose.prod.yml up -d

echo "[vm] Waiting 45s for Rainfall API to start..."
sleep 45

docker compose -f docker-compose.prod.yml ps
echo ""
echo "[vm] API health check:"
curl -fsS "http://localhost:8020/health" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "(not yet ready)"
DOCKER_SCRIPT

log "Docker stack launched"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 7: Health check + Summary
# ══════════════════════════════════════════════════════════════════════════════

step 7 "Health verification"

check_svc() {
    local code
    code=$(curl -sk --connect-timeout 15 -o /dev/null -w "%{http_code}" "$2" 2>/dev/null || echo "000")
    [[ "$code" =~ ^(200|301|302)$ ]] && log "✓ $1: HTTP $code" || warn "✗ $1: HTTP $code"
}

check_svc "Rainfall API /health" "http://${VM_STATIC_IP}:${APP_PORT}/health"
check_svc "Caddy HTTP"           "http://${VM_STATIC_IP}:80/"

cat << SUMMARY

${GREEN}══════════════════════════════════════════════════════════════${NC}
${GREEN}  CVG Rainfall Wizard — Deployed Successfully!                ${NC}
${GREEN}══════════════════════════════════════════════════════════════${NC}

  VM ${VMID}:     ${VM_HOSTNAME} @ ${VM_STATIC_IP}
  Public URL:   https://${SUBDOMAIN}.${DOMAIN}

  Internal endpoints:
    API health  → http://${VM_STATIC_IP}:${APP_PORT}/health
    API docs    → http://${VM_STATIC_IP}:${APP_PORT}/docs

  Required manual steps:
    1. DNS A record:  ${SUBDOMAIN}.${DOMAIN}  →  ${PUBLIC_IP}
    2. FortiGate VIP: ${PUBLIC_IP}:80+443  →  ${VM_STATIC_IP}:80+443

${CYAN}  Proxmox: https://${PROXMOX_HOST}:8006 → VM ${VMID}${NC}

SUMMARY
