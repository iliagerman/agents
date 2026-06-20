#!/usr/bin/env bash
set -euo pipefail

# ----------------------------------------------------------------
# Template: deploy-homeserver.sh
# Replace the CONFIG block below for the project you're deploying.
# Builds a self-contained image locally, ships it to the homeserver
# via the `homeserver` SSH alias, and brings the compose stack up.
# NPM forwards https://__DOMAIN__ to __CONTAINER__:__PORT__ over
# the shared `system_default` docker network.
# ----------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- CONFIG (replace these) ----------------------------------------------
IMAGE_NAME="__CONTAINER__"
IMAGE_TAG="latest"
DOCKERFILE="Dockerfile.__SERVICE__"        # at repo root
COMPOSE_FILE="docker-compose.homeserver.yml"
SSH_ALIAS="homeserver"
DEPLOY_DIR="~/__SERVICE_DIR__"             # remote dir under $HOME
DOMAIN="__DOMAIN__"
CONTAINER_NAME="__CONTAINER__"
FORWARD_PORT="__PORT__"
EXTERNAL_NETWORK="system_default"
# -------------------------------------------------------------------------

CLEAN_VOLUME=false

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --clean-volume) CLEAN_VOLUME=true; shift ;;
    -h|--help)
      echo "Usage: $0 [--clean-volume]"
      echo ""
      echo "Deploys __SERVICE__ to the homeserver via SSH alias '${SSH_ALIAS}'."
      echo ""
      echo "Options:"
      echo "  --clean-volume   Remove the persistent docker volume before deploying"
      exit 0
      ;;
    *) log_error "Unknown argument: $1"; exit 1 ;;
  esac
done

echo ""
log_info "Deployment configuration:"
echo "  SSH alias:   ${SSH_ALIAS}"
echo "  Domain:      ${DOMAIN}"
echo "  Remote dir:  ${DEPLOY_DIR}"
echo "  Image:       ${IMAGE_NAME}:${IMAGE_TAG}"
echo "  Clean vol:   ${CLEAN_VOLUME}"
echo ""

# Local docker
log_info "Checking local prerequisites..."
command -v docker >/dev/null || { log_error "Docker not installed locally."; exit 1; }
docker info >/dev/null 2>&1 || { log_error "Docker daemon is not running."; exit 1; }
log_success "Local prerequisites OK"

# SSH connectivity
log_info "Testing SSH connection to ${SSH_ALIAS}..."
if ! ssh ${SSH_ALIAS} "echo ok" &>/dev/null; then
  log_error "Cannot connect via SSH alias '${SSH_ALIAS}'."
  log_error "Add a 'Host ${SSH_ALIAS}' entry to ~/.ssh/config (HostName + User + IdentityFile)."
  exit 1
fi
log_success "SSH connection OK"

# Remote architecture
log_info "Detecting remote architecture..."
REMOTE_ARCH=$(ssh ${SSH_ALIAS} "uname -m")
case "$REMOTE_ARCH" in
  x86_64)  PLATFORM="linux/amd64" ;;
  aarch64) PLATFORM="linux/arm64" ;;
  *)
    log_error "Unsupported remote architecture: $REMOTE_ARCH"
    exit 1
    ;;
esac
log_success "Remote architecture: ${REMOTE_ARCH} (building for ${PLATFORM})"

# Docker on homeserver
log_info "Checking Docker on homeserver..."
if ! ssh ${SSH_ALIAS} "command -v docker &>/dev/null && docker info &>/dev/null"; then
  log_error "Docker is not installed or not running on the homeserver."
  exit 1
fi
log_success "Docker is ready on homeserver"

# NPM network presence
log_info "Checking external network '${EXTERNAL_NETWORK}' on homeserver..."
if ! ssh ${SSH_ALIAS} "docker network inspect ${EXTERNAL_NETWORK}" >/dev/null 2>&1; then
  log_error "Docker network '${EXTERNAL_NETWORK}' does not exist on the homeserver."
  log_error "NPM (Nginx Proxy Manager) typically owns this network."
  log_error "Start NPM first, or create the network: docker network create ${EXTERNAL_NETWORK}"
  exit 1
fi
log_success "External network '${EXTERNAL_NETWORK}' present"

# Build image
log_info "Building ${IMAGE_NAME}:${IMAGE_TAG} for ${PLATFORM}..."
docker build --platform ${PLATFORM} \
  -f "$ROOT_DIR/${DOCKERFILE}" \
  -t "${IMAGE_NAME}:${IMAGE_TAG}" \
  "$ROOT_DIR"
log_success "Image built"

# Save image
log_info "Saving image as tar.gz..."
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT
docker save "${IMAGE_NAME}:${IMAGE_TAG}" | gzip > "$TMPDIR/${IMAGE_NAME}.tar.gz"
IMAGE_SIZE=$(du -h "$TMPDIR/${IMAGE_NAME}.tar.gz" | cut -f1)
log_success "Image saved (${IMAGE_SIZE})"

# Deploy package — preserve deployments/homeserver/ so env_file paths match
log_info "Preparing deploy package..."
DEPLOY_PKG="$TMPDIR/deploy-pkg"
mkdir -p "$DEPLOY_PKG/deployments/homeserver"
cp "$ROOT_DIR/${COMPOSE_FILE}" "$DEPLOY_PKG/docker-compose.yml"
cp "$ROOT_DIR/deployments/homeserver/env.homeserver" "$DEPLOY_PKG/deployments/homeserver/env.homeserver"
cat > "$DEPLOY_PKG/.env" <<EOF
DEPLOY_DOMAIN=${DOMAIN}
EOF
log_success "Deploy package ready"

# Copy files
log_info "Copying deploy package to homeserver..."
ssh ${SSH_ALIAS} "mkdir -p ${DEPLOY_DIR}/deployments/homeserver"
scp -q \
  "$DEPLOY_PKG/docker-compose.yml" \
  "$DEPLOY_PKG/.env" \
  "${SSH_ALIAS}:${DEPLOY_DIR}/"
scp -q \
  "$DEPLOY_PKG/deployments/homeserver/env.homeserver" \
  "${SSH_ALIAS}:${DEPLOY_DIR}/deployments/homeserver/env.homeserver"
log_success "Config files copied"

# Stop existing + optional volume wipe
log_info "Preparing homeserver for deployment..."
ssh ${SSH_ALIAS} bash <<REMOTE_PREPARE
set -euo pipefail
cd ${DEPLOY_DIR}

if [ "${CLEAN_VOLUME}" = "true" ]; then
  echo "[WARN] Removing data volume (--clean-volume). All persistent state will be lost!"
  docker compose down --remove-orphans --volumes 2>/dev/null || true
else
  echo "[INFO] Stopping existing deployment (preserving volumes)..."
  docker compose down --remove-orphans 2>/dev/null || true
fi

echo "[INFO] Pruning dangling images to free disk space..."
docker image prune -af 2>/dev/null || true

echo "[INFO] Disk space available:"
df -h / | tail -1
REMOTE_PREPARE

# Ship image
log_info "Transferring image to homeserver..."
scp -q "$TMPDIR/${IMAGE_NAME}.tar.gz" "${SSH_ALIAS}:${DEPLOY_DIR}/${IMAGE_NAME}.tar.gz"
log_info "Loading image on homeserver..."
ssh ${SSH_ALIAS} "sync && docker load -i ${DEPLOY_DIR}/${IMAGE_NAME}.tar.gz && rm -f ${DEPLOY_DIR}/${IMAGE_NAME}.tar.gz"
log_success "Image loaded"

# Start
log_info "Starting services on homeserver..."
ssh ${SSH_ALIAS} bash <<REMOTE_DEPLOY
set -euo pipefail
cd ${DEPLOY_DIR}

echo "[INFO] Starting __SERVICE__..."
docker compose up -d

echo "[INFO] Waiting for the service to become healthy..."
for i in \$(seq 1 60); do
  if docker exec ${CONTAINER_NAME} curl -fsS http://127.0.0.1:${FORWARD_PORT}/ >/dev/null 2>&1; then
    echo "[OK] Service is responding"
    break
  fi
  if [ \$i -eq 60 ]; then
    echo "[WARN] Health check timed out after 120s"
    echo "[INFO] Check logs: cd ${DEPLOY_DIR} && docker compose logs"
  fi
  sleep 2
done

echo ""
echo "[INFO] Container status:"
docker compose ps
REMOTE_DEPLOY

echo ""
echo "============================================"
log_success "Deployment complete!"
echo ""
echo "  URL:        https://${DOMAIN}"
echo ""
echo "  NPM (Nginx Proxy Manager) configuration:"
echo "    Domain:           ${DOMAIN}"
echo "    Scheme:           http"
echo "    Forward Hostname: ${CONTAINER_NAME}"
echo "    Forward Port:     ${FORWARD_PORT}"
echo "    Websockets:       ON"
echo ""
echo "  SSH into homeserver:"
echo "    ssh ${SSH_ALIAS}"
echo "============================================"
