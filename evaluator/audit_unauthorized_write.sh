#!/usr/bin/env bash
# Negative test: legitimate RetailerOrg User1 without Farm-Integrator PDC permissions.
# Does not change C0 if chaincode and collection ACL are correct.
set -euo pipefail
PT_HOME="${PT_HOME:-$HOME/poultrytrace}"
CLI="$PT_HOME/bin/peer"; CHANNEL=traceability-channel; CC=poultry-traceability
source "$PT_HOME/scripts/admin_env.sh" retailer >/dev/null
export CORE_PEER_MSPCONFIGPATH="$PT_HOME/crypto/peerOrganizations/retailer.poultrytrace.test/users/User1@retailer.poultrytrace.test/msp"
[[ -d "$CORE_PEER_MSPCONFIGPATH" ]] || { echo 'Missing Retailer User1 identity' >&2; exit 1; }
base="$PT_HOME/crypto/peerOrganizations"
ca(){ printf '%s/%s.poultrytrace.test/peers/peer0.%s.poultrytrace.test/tls/ca.crt' "$base" "$1" "$1"; }
bid='BRL-2026-101'
# Deliberately fabricated test value, NOT the ground-truth private record.
private='{"batchId":"BRL-2026-101","fcr":1.95,"mortalityRate":4.75,"productionCostIdr":100000000}'
transient=$(python3 -c 'import base64,json,sys; print(json.dumps({"performance":base64.b64encode(sys.stdin.buffer.read().strip()).decode()}))' <<< "$private")
result_file="$(mktemp)"
trap 'rm -f "$result_file"' EXIT
if "$CLI" chaincode invoke -o orderer0:7050 --tls \
  --cafile "$PT_HOME/crypto-admin/orderer-tlsca.crt" \
  -C "$CHANNEL" -n "$CC" -c "{\"Args\":[\"UpdateFarmPerformance\",\"$bid\"]}" \
  --transient "$transient" \
  --peerAddresses farm:7051 --tlsRootCertFiles "$(ca farm)" \
  --peerAddresses integrator:7051 --tlsRootCertFiles "$(ca integrator)" \
  --waitForEvent >"$result_file" 2>&1; then
  echo 'FAIL: unauthorized update appears accepted; check ledger validity and state' >&2
  exit 1
else
  echo 'Expected rejection: unauthorized RetailerOrg update failed.'
fi
# Negative invoke alone is insufficient; a trusted evaluator must confirm state unchanged.
source "$PT_HOME/scripts/admin_env.sh" farm >/dev/null
actual=$("$CLI" chaincode query -C "$CHANNEL" -n "$CC" -c "{\"Args\":[\"ReadFarmPerformance\",\"$bid\"]}")
python3 - "$PT_HOME/stage11/dataset/farm_performance_private.jsonl" "$bid" "$actual" <<'PY'
import json,sys
path,bid,result=sys.argv[1:]
actual=json.loads(result)
for ln in open(path,encoding='utf-8'):
    expected=json.loads(ln)
    if expected['batchId']==bid:
        assert actual==expected, 'FAIL: state changed despite rejected write'
        print('PASS: FarmOrg ground truth unchanged after rejected write')
        break
else:raise SystemExit('Ground truth missing')
PY
mkdir -p "$PT_HOME/stage11/evidence"
printf '%s\t%s\t%s\t%s\n' 'BRL-2026-101' 'RetailerOrgMSP User1' 'UpdateFarmPerformance' 'REJECTED_STATE_UNCHANGED' > "$PT_HOME/stage11/evidence/unauthorized_write.tsv"
