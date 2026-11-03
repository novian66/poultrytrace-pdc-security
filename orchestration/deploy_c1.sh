#!/usr/bin/env bash
set -euo pipefail

CI="coder-novian66-ws-integrator"
PEERS=(
  "coder-novian66-ws-integrator"
  "coder-novian66-ws-hatchery"
  "coder-novian66-ws-farm"
  "coder-novian66-ws-rpa"
  "coder-novian66-ws-distributor"
  "coder-novian66-ws-retailer"
  "coder-novian66-ws-regulator"
)

echo "=== 1. Extracting C1 artifacts from ws-integrator ==="
TMP_DIR="$(mktemp -d /tmp/c1_deploy_XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

docker cp "$CI:/home/coder/poultrytrace/chaincode_src/c1/poultry-chaincode-c1" "$TMP_DIR/poultry-chaincode"
docker cp "$CI:/home/coder/poultrytrace/c1-package/poultrytrace_1.1.tgz" "$TMP_DIR/poultrytrace_1.1.tgz"
docker cp "$CI:/home/coder/poultrytrace/c1-package/package-id.txt" "$TMP_DIR/package-id.txt"
docker cp "$CI:/home/coder/poultrytrace/collections_c1/collections_config.json" "$TMP_DIR/collections_config.json"

BIN_HASH=$(sha256sum "$TMP_DIR/poultry-chaincode" | awk '{print $1}')
PKG_ID=$(cat "$TMP_DIR/package-id.txt" | tr -d '\r\n')
COLL_HASH=$(sha256sum "$TMP_DIR/collections_config.json" | awk '{print $1}')

echo "C1 Binary SHA256:     $BIN_HASH"
echo "C1 Package ID:        $PKG_ID"
echo "C1 Collection SHA256: $COLL_HASH"

echo "=== 2. Deploying to all 7 peer nodes ==="
for peer in "${PEERS[@]}"; do
  echo ">>> Processing $peer..."
  
  # A. Backup C0 artifacts if not already backed up
  docker exec "$peer" bash -c '
    ROOT="/home/coder/poultrytrace"
    if [ -f "$ROOT/chaincode/poultry-chaincode" ] && [ ! -f "$ROOT/chaincode/poultry-chaincode.c0" ]; then
      cp "$ROOT/chaincode/poultry-chaincode" "$ROOT/chaincode/poultry-chaincode.c0"
    fi
    if [ -f "$ROOT/stage10-package/package-id.txt" ] && [ ! -f "$ROOT/stage10-package/package-id.txt.c0" ]; then
      cp "$ROOT/stage10-package/package-id.txt" "$ROOT/stage10-package/package-id.txt.c0"
    fi
    if [ -f "$ROOT/collections/collections_config.json" ] && [ ! -f "$ROOT/collections/collections_config.json.c0" ]; then
      cp "$ROOT/collections/collections_config.json" "$ROOT/collections/collections_config.json.c0"
    fi
  '

  # B. Copy C1 artifacts
  docker cp "$TMP_DIR/poultry-chaincode" "$peer:/home/coder/poultrytrace/chaincode/poultry-chaincode"
  docker exec "$peer" chmod +x /home/coder/poultrytrace/chaincode/poultry-chaincode

  docker exec "$peer" mkdir -p /home/coder/poultrytrace/c1-package
  docker cp "$TMP_DIR/poultrytrace_1.1.tgz" "$peer:/home/coder/poultrytrace/c1-package/poultrytrace_1.1.tgz"
  docker cp "$TMP_DIR/package-id.txt" "$peer:/home/coder/poultrytrace/c1-package/package-id.txt"
  docker cp "$TMP_DIR/package-id.txt" "$peer:/home/coder/poultrytrace/stage10-package/package-id.txt"
  docker cp "$TMP_DIR/collections_config.json" "$peer:/home/coder/poultrytrace/collections/collections_config.json"

  # Fix ownership
  docker exec -u 0:0 "$peer" chown -R coder:coder \
    /home/coder/poultrytrace/chaincode \
    /home/coder/poultrytrace/c1-package \
    /home/coder/poultrytrace/stage10-package \
    /home/coder/poultrytrace/collections

  # C. Stop old CCaaS
  docker exec "$peer" bash -c '
    ROOT="/home/coder/poultrytrace"
    if [ -f "$ROOT/run/chaincode.pid" ]; then
      PID=$(cat "$ROOT/run/chaincode.pid")
      if kill -0 "$PID" 2>/dev/null; then
        kill -TERM "$PID" 2>/dev/null || true
        sleep 1
        kill -9 "$PID" 2>/dev/null || true
      fi
      rm -f "$ROOT/run/chaincode.pid"
    fi
  '

  # D. Start CCaaS
  docker exec -u coder:coder "$peer" bash -c '/home/coder/poultrytrace/scripts/start_ccaas.sh'

  # E. Verify CCaaS is running
  docker exec "$peer" bash -c '
    ROOT="/home/coder/poultrytrace"
    PID=$(cat "$ROOT/run/chaincode.pid")
    kill -0 "$PID" || { echo "CCaaS failed to run!"; exit 1; }
    echo "CCaaS active with PID $PID"
  '
done

echo "=== All 7 peers updated with C1 binary and CCaaS restarted successfully ==="
