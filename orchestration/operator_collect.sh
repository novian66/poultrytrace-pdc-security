#!/usr/bin/env bash
# Run on the VPS Docker host; collect redacted Retailer trial to trusted Integrator inbox.
# Usage: ./operator_collect.sh ACTUAL_RETAILER_CONTAINER ACTUAL_INTEGRATOR_CONTAINER TRIAL_ID
set -euo pipefail
[[ $# -eq 3 ]] || { echo "Usage: $0 RETAILER_CONTAINER INTEGRATOR_CONTAINER TRIAL_ID" >&2; exit 2; }
SRC="$1"; DST="$2"; TRIAL="$3"
[[ "$TRIAL" =~ ^[A-Za-z0-9_-]{1,96}$ ]] || { echo "Invalid trial ID" >&2; exit 2; }
docker exec "$SRC" test -s "/home/coder/poultrytrace/poultrytrace-tm2-retailer/evidence/$TRIAL/trial.json"
docker exec "$DST" mkdir -p /home/coder/poultrytrace/tm2_operator_inbox
if docker exec "$DST" test -e "/home/coder/poultrytrace/tm2_operator_inbox/$TRIAL"; then
  echo "Destination already exists; will not overwrite" >&2
  exit 1
fi
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
docker cp "$SRC:/home/coder/poultrytrace/poultrytrace-tm2-retailer/evidence/$TRIAL" "$TMP/$TRIAL"
docker cp "$TMP/$TRIAL" "$DST:/home/coder/poultrytrace/tm2_operator_inbox/$TRIAL"
docker exec -u 0:0 "$DST" chown -R coder:coder /home/coder/poultrytrace/tm2_operator_inbox
docker exec "$DST" sh -c 'chmod -R go-rwx "$HOME/poultrytrace/tm2_operator_inbox/$1"' sh "$TRIAL"
echo "Collected trial $TRIAL to trusted ws-integrator inbox. Evidence is attacker-origin and NOT proof until reevaluated."
