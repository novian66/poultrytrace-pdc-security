#!/usr/bin/env bash
# Run on VPS Docker host. Transfers ONLY attacker runtime files and configuration.
# Usage: ./operator_deploy.sh ACTUAL_INTEGRATOR_CONTAINER ACTUAL_RETAILER_CONTAINER
set -euo pipefail
[[ $# -eq 2 ]] || { echo "Usage: $0 INTEGRATOR_CONTAINER RETAILER_CONTAINER" >&2; exit 2; }
SRC="$1"; DST="$2"
docker exec "$DST" sh -c '
  dir="$HOME/poultrytrace/poultrytrace-tm2-retailer"
  test ! -e "$dir" || { echo "TM2 runtime exists: no overwrite" >&2; exit 1; }
  mkdir -p "$dir"; chmod 700 "$dir"
'
docker exec "$SRC" sh -c '
  d="$HOME/poultrytrace/poultrytrace-tm2-retailer"
  test -d "$d/tm2" && test -f "$d/config/experiment.json"
  tar -C "$d" -cf - tm2/__init__.py tm2/gateway.py tm2/planner.py tm2/runner.py config/experiment.json scripts/check_model.py scripts/validate_tm2_environment.py
' | docker exec -i "$DST" sh -c 'tar -C "$HOME/poultrytrace/poultrytrace-tm2-retailer" -xf -'
docker exec "$DST" sh -c 'chmod -R go-rwx "$HOME/poultrytrace/poultrytrace-tm2-retailer"'
echo "Agent runtime deployed to Retailer only. Evaluator, ground truth, and operator reports remain in Integrator."
