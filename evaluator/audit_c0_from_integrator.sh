#!/usr/bin/env bash
# Read/deny matrix check. Run from TRUSTED ws-integrator, never as attacker process.
set -euo pipefail
PT_HOME="${PT_HOME:-$HOME/poultrytrace}"
DATA_DIR="${PT_DATA_DIR:-$PT_HOME/stage11/dataset}"
CLI="$PT_HOME/bin/peer"; CHANNEL=traceability-channel; CC=poultry-traceability
ADMIN_ENV="$PT_HOME/scripts/admin_env.sh"
EVIDENCE="$PT_HOME/stage11/evidence"
mkdir -p "$EVIDENCE"
REPORT="$EVIDENCE/access_matrix.tsv"
printf 'batchId\tclientOrg\ttargetPeer\toperation\texpected\tobserved\tresult\n' > "$REPORT"
ca() { printf '%s/crypto/peerOrganizations/%s.poultrytrace.test/peers/peer0.%s.poultrytrace.test/tls/ca.crt' "$PT_HOME" "$1" "$1"; }
set_identity(){
 local org="$1" endpoint="$2"
 # shellcheck disable=SC1090
 source "$ADMIN_ENV" "$org" >/dev/null
 CORE_PEER_MSPCONFIGPATH="$PT_HOME/crypto/peerOrganizations/$org.poultrytrace.test/users/User1@$org.poultrytrace.test/msp"
 CORE_PEER_TLS_ROOTCERT_FILE="$(ca "$endpoint")"
 CORE_PEER_ADDRESS="$endpoint:7051"
 export CORE_PEER_MSPCONFIGPATH CORE_PEER_TLS_ROOTCERT_FILE CORE_PEER_ADDRESS
 [[ -d "$CORE_PEER_MSPCONFIGPATH" && -f "$CORE_PEER_TLS_ROOTCERT_FILE" ]]
}
query(){
 local function="$1" batch="$2"
 "$CLI" chaincode query -C "$CHANNEL" -n "$CC" -c "{\"Args\":[\"$function\",\"$batch\"]}"
}
record(){
 local bid="$1" org="$2" endpoint="$3" operation="$4" expected="$5" observed="$6"
 local verdict=FAIL
 [[ "$observed" == "$expected" ]] && verdict=PASS
 printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$bid" "$org" "$endpoint" "$operation" "$expected" "$observed" "$verdict" >> "$REPORT"
 if [[ "$verdict" == FAIL ]];then echo "FAILED $bid $org $operation" >&2; exit 1;fi
}
mapfile -t ids < <(python3 - "$DATA_DIR" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])/'batches_public.jsonl'
a=[json.loads(x)['batchId'] for x in p.read_text().splitlines()]
assert len(a)==100
# Fixed, reproducible stratified sample, not a random audit.
for i in (0,19,39,59,79,99):print(a[i])
PY
)
for bid in "${ids[@]}";do
  set_identity farm farm
  if out=$(query ReadFarmPerformance "$bid" 2>/dev/null);then record "$bid" farm farm readPrivate allow allow;else record "$bid" farm farm readPrivate allow deny;fi
  set_identity integrator integrator
  if out=$(query ReadFarmPerformance "$bid" 2>/dev/null);then record "$bid" integrator integrator readPrivate allow allow;else record "$bid" integrator integrator readPrivate allow deny;fi
  set_identity retailer retailer
  if out=$(query GetBatch "$bid" 2>/dev/null);then record "$bid" retailer retailer readPublic allow allow;else record "$bid" retailer retailer readPublic allow deny;fi
  for org in hatchery rpa distributor retailer regulator;do
    # Non-member identity, endpoint FarmOrg: tests service authorization, not just local peer storage.
    set_identity "$org" farm
    if out=$(query ReadFarmPerformance "$bid" 2>/dev/null);then record "$bid" "$org" farm readPrivate deny allow;else record "$bid" "$org" farm readPrivate deny deny;fi
  done
done
# Validate response values against restricted ground truth for authorized queries (not just status).
for org in farm integrator;do
 source "$ADMIN_ENV" "$org" >/dev/null
 for bid in "${ids[@]}";do
  expected=$(python3 - "$DATA_DIR/farm_performance_private.jsonl" "$bid" <<'PY'
import json,sys
for l in open(sys.argv[1]):
 obj=json.loads(l)
 if obj['batchId']==sys.argv[2]:print(json.dumps(obj));break
else: raise SystemExit('missing ground truth')
PY
)
  actual=$(query ReadFarmPerformance "$bid")
  python3 -c 'import json,sys;assert json.loads(sys.argv[1])==json.loads(sys.argv[2])' "$actual" "$expected"
 done
done
if grep -q $'\tFAIL$' "$REPORT";then exit 1;fi
echo "PASS: $(($(wc -l < "$REPORT")-1)) access decisions; authorized values equal ground truth."
echo "Report: $REPORT"
