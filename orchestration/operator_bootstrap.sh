#!/usr/bin/env bash
# Run on the VPS DOCKER HOST, not inside any Coder container.
# Usage: ./operator_bootstrap.sh ACTUAL_INTEGRATOR_CONTAINER ACTUAL_RETAILER_CONTAINER
set -euo pipefail
[[ $# -eq 2 ]] || { echo "Usage: $0 INTEGRATOR_CONTAINER RETAILER_CONTAINER" >&2; exit 2; }
SRC="$1"; DST="$2"
[[ "$SRC" != "$DST" ]] || { echo "Source and destination must differ" >&2; exit 2; }
docker inspect "$SRC" >/dev/null
docker inspect "$DST" >/dev/null

docker exec "$DST" sh -c '
  set -eu
  BASE="$HOME/poultrytrace/attack-kit"
  test ! -e "$BASE/identity/retailer-user1/msp" || { echo "Retailer User1 MSP exists: no overwrite"; exit 1; }
  mkdir -p "$BASE/identity/retailer-user1" "$BASE/trust"
  chmod 700 "$BASE" "$BASE/identity" "$BASE/identity/retailer-user1"
'

# Stream *only* Retailer User1 client identity (never CA signing keys or other admin identities).
docker exec "$SRC" sh -c '
  set -eu
  SRC="$HOME/poultrytrace/crypto/peerOrganizations/retailer.poultrytrace.test/users/User1@retailer.poultrytrace.test"
  test -d "$SRC/msp" || { echo "User1 MSP not found" >&2; exit 1; }
  tar -C "$SRC" -cf - msp
' | docker exec -i "$DST" sh -c 'tar -C "$HOME/poultrytrace/attack-kit/identity/retailer-user1" -xf -'

for org in retailer farm integrator; do
  docker exec "$SRC" sh -c '
    org="$1"
    file="$HOME/poultrytrace/crypto/peerOrganizations/$org.poultrytrace.test/peers/peer0.$org.poultrytrace.test/tls/ca.crt"
    test -s "$file" && cat "$file"
  ' sh "$org" | docker exec -i "$DST" sh -c 'cat > "$HOME/poultrytrace/attack-kit/trust/'"$org"'-tls-ca.crt"'
done

docker exec "$SRC" sh -c '
  file="$HOME/poultrytrace/crypto/ordererOrganizations/orderer.poultrytrace.test/tlsca/tlsca.orderer.poultrytrace.test-cert.pem"
  test -s "$file" && cat "$file"
' | docker exec -i "$DST" sh -c 'cat > "$HOME/poultrytrace/attack-kit/trust/orderer-tls-ca.crt"'

docker exec "$DST" sh -c '
  chmod -R go-rwx "$HOME/poultrytrace/attack-kit/identity"
  chmod 600 "$HOME/poultrytrace/attack-kit/identity/retailer-user1/msp/keystore/"* 2>/dev/null || true
  echo "Bootstrap complete: User1 MSP and public TLS CAs, no external CA private key"
'
