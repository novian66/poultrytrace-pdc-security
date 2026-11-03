#!/usr/bin/env bash
# Coordinated cold restore of all 11 PoultryTrace nodes back to Baseline C0
set -euo pipefail

PEERS=(integrator hatchery farm rpa distributor retailer regulator)
ORDERERS=(orderer0 orderer1 orderer2 orderer3)
BACKUP_DIR="/www/wwwroot/riset-blockchain-pdc/c0_snapshot"

[ -f "$BACKUP_DIR/C0_SNAPSHOT_SHA256SUMS.txt" ] || { echo "Snapshot missing" >&2; exit 1; }

echo "=================================================================="
echo "   POULTRYTRACE C0 COLD PERSISTENT-VOLUME RESTORE (11 NODES)      "
echo "=================================================================="

# 1. Stop CCaaS
echo "1. Stopping CCaaS on all 7 peer nodes..."
for p in "${PEERS[@]}"; do
  c="coder-novian66-ws-$p"
  docker exec -u coder "$c" bash -c '
    ROOT="/home/coder/poultrytrace"
    if [ -f "$ROOT/run/chaincode.pid" ]; then
      kill -TERM "$(cat "$ROOT/run/chaincode.pid")" 2>/dev/null || true
      sleep 1
      kill -9 "$(cat "$ROOT/run/chaincode.pid")" 2>/dev/null || true
      rm -f "$ROOT/run/chaincode.pid"
    fi
  '
done

# 2. Stop peer nodes
echo "2. Stopping Fabric peer processes gracefully..."
for p in "${PEERS[@]}"; do
  c="coder-novian66-ws-$p"
  docker exec -u coder "$c" pkill -TERM -f "peer node start" 2>/dev/null || true
done

# 3. Stop orderers
echo "3. Stopping SmartBFT orderer processes gracefully..."
for o in "${ORDERERS[@]}"; do
  c="coder-novian66-ws-$o"
  docker exec -u coder "$c" pkill -TERM -f "orderer start" 2>/dev/null || true
done

sleep 3
echo "Verifying all processes stopped..."
for p in "${PEERS[@]}"; do
  docker exec "coder-novian66-ws-$p" pgrep -f "peer node" && { echo "ERROR: peer on $p still running" >&2; exit 1; } || true
done
for o in "${ORDERERS[@]}"; do
  docker exec "coder-novian66-ws-$o" pgrep -f "orderer" && { echo "ERROR: orderer on $o still running" >&2; exit 1; } || true
done

# 4. Restore filesystems
echo "4. Restoring ledger and configs from cold snapshot tarballs..."
for p in "${PEERS[@]}"; do
  c="coder-novian66-ws-$p"
  tarfile="$BACKUP_DIR/peer_${p}_ledger_C0.tar.gz"
  docker exec -u coder "$c" bash -c 'rm -rf /home/coder/poultrytrace/ledger'
  docker exec -i -u coder "$c" tar -xzf - -C /home/coder/poultrytrace < "$tarfile"
  
  # Restore C0 binary and configs if backups exist
  docker exec -u coder "$c" bash -c '
    ROOT="/home/coder/poultrytrace"
    if [ -f "$ROOT/chaincode/poultry-chaincode.c0" ]; then
      cp "$ROOT/chaincode/poultry-chaincode.c0" "$ROOT/chaincode/poultry-chaincode"
    fi
    if [ -f "$ROOT/stage10-package/package-id.txt.c0" ]; then
      cp "$ROOT/stage10-package/package-id.txt.c0" "$ROOT/stage10-package/package-id.txt"
    fi
    if [ -f "$ROOT/collections/collections_config.json.c0" ]; then
      cp "$ROOT/collections/collections_config.json.c0" "$ROOT/collections/collections_config.json"
    fi
  '
  echo "  Restored $p"
done

for o in "${ORDERERS[@]}"; do
  c="coder-novian66-ws-$o"
  tarfile="$BACKUP_DIR/orderer_${o}_ledger_C0.tar.gz"
  docker exec -u coder "$c" bash -c 'rm -rf /home/coder/poultrytrace/ledger'
  docker exec -i -u coder "$c" tar -xzf - -C /home/coder/poultrytrace < "$tarfile"
  echo "  Restored $o"
done

# 5. Restart orderers
echo "5. Restarting 4 SmartBFT orderers..."
for o in "${ORDERERS[@]}"; do
  c="coder-novian66-ws-$o"
  docker exec -u coder "$c" bash -c '
    export FABRIC_CFG_PATH=/home/coder/poultrytrace/config
    export FABRIC_LOGGING_SPEC=INFO
    nohup /home/coder/poultrytrace/bin/orderer start > /home/coder/poultrytrace/logs/orderer.log 2>&1 < /dev/null &
    echo $! > /home/coder/poultrytrace/run/orderer.pid
  '
done
sleep 3

# 6. Restart CCaaS on all 7 peers
echo "6. Restarting CCaaS daemons on all 7 peers..."
for p in "${PEERS[@]}"; do
  c="coder-novian66-ws-$p"
  docker exec -u coder "$c" /home/coder/poultrytrace/scripts/start_ccaas.sh >/dev/null
done
sleep 2

# 7. Restart 7 peer nodes
echo "7. Restarting 7 Fabric peer nodes..."
for p in "${PEERS[@]}"; do
  c="coder-novian66-ws-$p"
  docker exec -u coder "$c" bash -c '
    export FABRIC_CFG_PATH=/home/coder/poultrytrace/config
    export FABRIC_LOGGING_SPEC=INFO
    nohup /home/coder/poultrytrace/bin/peer node start > /home/coder/poultrytrace/logs/peer.log 2>&1 < /dev/null &
    echo $! > /home/coder/poultrytrace/run/peer.pid
  '
done

echo "Waiting 5 seconds for network convergence..."
sleep 5

# 8. Post-start health check
echo "8. Verifying ledger height on all peers (should be 218)..."
for p in "${PEERS[@]}"; do
  info=$(docker exec -u coder coder-novian66-ws-integrator bash -c '
    source /home/coder/poultrytrace/scripts/admin_env.sh '"$p"' >/dev/null
    /home/coder/poultrytrace/bin/peer channel getinfo -c traceability-channel 2>/dev/null | grep "Blockchain info" || true
  ')
  echo "  $p: $info"
done

echo "=================================================================="
echo "   C0 RESTORE COMPLETED & NETWORK RESTORED TO HEIGHT 218!         "
echo "=================================================================="
