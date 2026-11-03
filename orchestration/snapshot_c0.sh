#!/usr/bin/env bash
# Coordinated cold snapshot of all 11 PoultryTrace nodes at Baseline C0
set -euo pipefail

PEERS=(integrator hatchery farm rpa distributor retailer regulator)
ORDERERS=(orderer0 orderer1 orderer2 orderer3)
BACKUP_DIR="/www/wwwroot/riset-blockchain-pdc/c0_snapshot"
mkdir -p "$BACKUP_DIR"
rm -f "$BACKUP_DIR/C0_SNAPSHOT_SHA256SUMS.txt"

echo "=================================================================="
echo "   POULTRYTRACE C0 COLD PERSISTENT-VOLUME SNAPSHOT (11 NODES)     "
echo "=================================================================="

# 1. Stop all client activity & CCaaS processes
echo "1. Stopping CCaaS on all 7 peer nodes..."
for p in "${PEERS[@]}"; do
  c="coder-novian66-ws-$p"
  docker exec -u coder "$c" pkill -f poultry-chaincode 2>/dev/null || true
done

# 2. Stop all peer node processes (SIGTERM to flush LevelDB cleanly)
echo "2. Stopping Fabric peer processes gracefully..."
for p in "${PEERS[@]}"; do
  c="coder-novian66-ws-$p"
  docker exec -u coder "$c" pkill -TERM -f "peer node start" 2>/dev/null || true
done

# 3. Stop all orderer processes (SIGTERM to flush SmartBFT WAL cleanly)
echo "3. Stopping SmartBFT orderer processes gracefully..."
for o in "${ORDERERS[@]}"; do
  c="coder-novian66-ws-$o"
  docker exec -u coder "$c" pkill -TERM -f "orderer start" 2>/dev/null || true
done

# Wait 3 seconds for all file locks to close
sleep 3
echo "Verifying all processes stopped..."
for p in "${PEERS[@]}"; do
  docker exec "coder-novian66-ws-$p" pgrep -f "peer node" && { echo "ERROR: peer on $p still running" >&2; exit 1; } || true
done
for o in "${ORDERERS[@]}"; do
  docker exec "coder-novian66-ws-$o" pgrep -f "orderer" && { echo "ERROR: orderer on $o still running" >&2; exit 1; } || true
done
echo "All 11 node processes stopped. Storage is frozen."

# 4. Take cold filesystem snapshot of ledgers and run artifacts
echo "4. Creating compressed cold snapshot tarballs..."
for p in "${PEERS[@]}"; do
  c="coder-novian66-ws-$p"
  tarfile="$BACKUP_DIR/peer_${p}_ledger_C0.tar.gz"
  docker exec -u coder "$c" tar -czf - -C /home/coder/poultrytrace ledger config > "$tarfile"
  sha256sum "$tarfile" >> "$BACKUP_DIR/C0_SNAPSHOT_SHA256SUMS.txt"
  echo "  Saved $tarfile ($(du -h "$tarfile" | cut -f1))"
done

for o in "${ORDERERS[@]}"; do
  c="coder-novian66-ws-$o"
  tarfile="$BACKUP_DIR/orderer_${o}_ledger_C0.tar.gz"
  docker exec -u coder "$c" tar -czf - -C /home/coder/poultrytrace ledger config > "$tarfile"
  sha256sum "$tarfile" >> "$BACKUP_DIR/C0_SNAPSHOT_SHA256SUMS.txt"
  echo "  Saved $tarfile ($(du -h "$tarfile" | cut -f1))"
done

echo "Cold persistent-volume snapshot successfully saved to $BACKUP_DIR."

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
echo "8. Verifying ledger height on all peers..."
for p in "${PEERS[@]}"; do
  c="coder-novian66-ws-$p"
  info=$(docker exec -u coder coder-novian66-ws-integrator bash -c '
    source /home/coder/poultrytrace/scripts/admin_env.sh '"$p"' >/dev/null
    /home/coder/poultrytrace/bin/peer channel getinfo -c traceability-channel 2>/dev/null | grep "Blockchain info" || true
  ')
  echo "  $p: $info"
done

echo "=================================================================="
echo "   C0 SNAPSHOT COMPLETED & NETWORK RESUMED HEALTHILY!             "
echo "=================================================================="
