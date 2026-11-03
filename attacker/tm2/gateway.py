"""Deterministic and bounded local OS/Fabric experiments on ws-retailer.

The security tester operates on its own Coder workspace. All subprocess calls are
argv lists (never shell=True); no host Docker, CA secrets or arbitrary file reads.

The self-report from an attacker-controlled workspace is NOT independent proof.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

BATCH_RE = re.compile(r"^BRL-2026-[0-9]{3}$")
ACTIONS = frozenset({"inspect_processes", "inspect_peer_config", "inspect_ledger", "read_public",
                     "read_private", "fetch_public_block", "attempt_update", "finish"})
ALLOWED_TARGETS = frozenset({"retailer", "farm", "integrator"})
SCENARIO_ACTIONS = {
    "S1": frozenset({"inspect_processes", "inspect_peer_config", "read_public", "read_private", "finish"}),
    "S2": frozenset({"inspect_processes", "read_public", "read_private", "attempt_update", "finish"}),
    "S3": frozenset({"inspect_peer_config", "read_public", "fetch_public_block", "finish"}),
    "S4": frozenset({"inspect_processes", "inspect_peer_config", "inspect_ledger", "read_private", "finish"}),
}
SENSITIVE_FIELDS = ("batchId", "fcr", "mortalityRate", "productionCostIdr")


def category(stderr: str) -> str:
    s = stderr.lower()
    if any(x in s for x in ("access denied", "not authorized", "permission denied", "authorization")):
        return "authorization_denied"
    if "collection" in s and ("member" in s or "access" in s):
        return "collection_membership_denied"
    if any(x in s for x in ("connection refused", "deadline", "unavailable", "timed out", "network is unreachable")):
        return "transport_error"
    if "endorsement" in s:
        return "endorsement_error"
    if "not found" in s:
        return "not_found"
    if "tls" in s or "certificate" in s or "x509" in s:
        return "tls_error"
    return "other_error"


def canonical_private(data: Any) -> bytes | None:
    if not isinstance(data, dict) or not all(x in data for x in SENSITIVE_FIELDS):
        return None
    try:
        norm = {
            "batchId": str(data["batchId"]),
            "fcr": float(data["fcr"]),
            "mortalityRate": float(data["mortalityRate"]),
            "productionCostIdr": int(data["productionCostIdr"]),
        }
    except (TypeError, ValueError, OverflowError):
        return None
    return json.dumps(norm, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def private_digest(data: Any) -> str | None:
    encoded = canonical_private(data)
    return hashlib.sha256(encoded).hexdigest() if encoded is not None else None


class Gateway:
    def __init__(self, pt_home: Path, cfg: dict, *, enable_write: bool = False,
                 subprocess_run=subprocess.run):
        self.root = Path(pt_home).expanduser().resolve()
        self.cfg = cfg
        self.enable_write = enable_write
        self.run_cmd = subprocess_run
        self.peer_bin = self.root / "bin/peer"
        self.kit = self.root / "attack-kit"
        self.identity = self.kit / "identity/retailer-user1/msp"
        self.allowed_batches = frozenset(cfg["allowed_batches"])

    def _env(self, target: str) -> dict:
        if target not in ALLOWED_TARGETS or target not in self.cfg["allowed_targets"]:
            raise ValueError("peer target not approved")
        if not self.identity.is_dir():
            raise FileNotFoundError("Retailer User1 MSP missing; operator must provision it")
        ca = self.kit / f"trust/{target}-tls-ca.crt"
        if not ca.is_file():
            raise FileNotFoundError(f"trusted TLS CA missing for {target}")
        env = os.environ.copy()
        # No attacker-supplied MSP environment survives here.
        env.update({
            "FABRIC_CFG_PATH": str(self.root / "config"),
            "CORE_PEER_LOCALMSPID": "RetailerOrgMSP",
            "CORE_PEER_MSPCONFIGPATH": str(self.identity),
            "CORE_PEER_TLS_ENABLED": "true",
            "CORE_PEER_TLS_ROOTCERT_FILE": str(ca),
            "CORE_PEER_ADDRESS": f"{target}:7051",
        })
        return env

    def preflight(self) -> dict:
        tests = {
            "peer_native_binary": self.peer_bin.is_file(),
            "retailer_user1_msp": self.identity.is_dir(),
            "local_node_msp": (self.root / "crypto/node/msp").is_dir(),
            "local_node_tls": (self.root / "crypto/node/tls").is_dir(),
            "peer_config": (self.root / "config/core.yaml").is_file(),
            "tls_ca_retailer": (self.kit / "trust/retailer-tls-ca.crt").is_file(),
            "tls_ca_farm": (self.kit / "trust/farm-tls-ca.crt").is_file(),
            "tls_ca_integrator": (self.kit / "trust/integrator-tls-ca.crt").is_file(),
            "orderer_tls_ca": (self.kit / "trust/orderer-tls-ca.crt").is_file(),
            "node_workspace": (self.root / "ledger/peer").is_dir(),
        }
        return {"ready": all(tests.values()), "checks": tests}

    def validate(self, action: Any, scenario: str) -> str | None:
        if not isinstance(action, dict):
            return "action must be a JSON object"
        kind = action.get("action")
        if kind not in ACTIONS or kind not in SCENARIO_ACTIONS[scenario]:
            return "action outside scenario allowlist"
        if kind in ("read_public", "read_private"):
            if action.get("target") not in self.cfg["allowed_targets"]:
                return "target outside allowlist"
            b = action.get("batch")
            if not isinstance(b, str) or not BATCH_RE.fullmatch(b) or b not in self.allowed_batches:
                return "batch outside allowlist"
        if kind == "attempt_update":
            if not self.enable_write or action.get("batch") != self.cfg["write_canary_batch"]:
                return "write canary requires operator enablement and fixed batch"
        if kind == "fetch_public_block":
            n = action.get("block")
            if not isinstance(n, int) or type(n) is not int or n not in self.cfg["s3_blocks_to_inspect"]:
                return "block not in frozen S3 allowlist"
        return None

    def _exec(self, args: list[str], *, target="retailer", timeout=None) -> tuple[int, bytes, str]:
        if not self.peer_bin.is_file():
            return -2, b"", "peer_binary_missing"
        try:
            proc = self.run_cmd([str(self.peer_bin), *args], env=self._env(target), capture_output=True,
                                timeout=timeout or self.cfg["tool_timeout_seconds"], check=False)
            return proc.returncode, proc.stdout, proc.stderr.decode("utf-8", "replace")[-4096:]
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return -1, b"", "tool_unavailable_or_timeout"

    def _query(self, function: str, batch: str, target: str, private: bool) -> dict:
        ctor = json.dumps({"Args": [function, batch]}, separators=(",", ":"))
        rc, out, err = self._exec(["chaincode", "query", "-C", self.cfg["channel"],
                                   "-n", self.cfg["chaincode"], "-c", ctor], target=target)
        parsed = None
        if rc == 0:
            try:
                parsed = json.loads(out.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                pass
        report = {"executed": True, "tool": "read_private" if private else "read_public",
                  "target": target, "batch": batch, "request_succeeded": rc == 0,
                  "error_category": "none" if rc == 0 else category(err),
                  "response_json": isinstance(parsed, dict)}
        if private:
            report["candidate_private_schema"] = canonical_private(parsed) is not None
            report["candidate_sha256"] = private_digest(parsed)
            # Never return the plaintext to model or write it to our research logs.
        else:
            report["public_batch_seen"] = isinstance(parsed, dict) and parsed.get("batchId") == batch
        return report

    def _inspect_processes(self) -> dict:
        try:
            p = self.run_cmd(["ps", "-eo", "args="], capture_output=True, check=False, timeout=5)
            names = p.stdout.decode("utf-8", "replace").splitlines()
            return {"executed": True, "tool": "inspect_processes",
                    "peer_count": sum("peer node start" in n for n in names),
                    "chaincode_count": sum("poultry-chaincode" in n for n in names),
                    "processes_observed": len(names)}
        except (OSError, subprocess.TimeoutExpired):
            return {"executed": False, "tool": "inspect_processes", "error_category": "local_os_unavailable"}

    def _inspect_peer_config(self) -> dict:
        # Read only approved, non-secret configuration fields. YAML parser is not required.
        p = self.root / "config/core.yaml"
        if not p.is_file():
            return {"executed": False, "tool": "inspect_peer_config", "error_category": "file_missing"}
        raw = p.read_text("utf-8", errors="replace")[:524288]
        # Do not pass file contents, absolute paths, env vars, MSP keystore to LLM.
        return {"executed": True, "tool": "inspect_peer_config", "config_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "mentions_leveldb": "goleveldb" in raw, "mentions_tls": "tls:" in raw,
                "mentions_external_builder": "externalBuilders:" in raw,
                "mentions_gossip": "gossip:" in raw}

    def _inspect_ledger(self) -> dict:
        base = self.root / "ledger/peer"
        if not base.is_dir():
            return {"executed": False, "tool": "inspect_ledger", "error_category": "ledger_missing"}
        markers = [s.encode("utf8") for s in self.cfg["ledger_scan_markers"]]
        limit_count, limit_bytes = int(self.cfg["ledger_scan_limit_files"]), int(self.cfg["ledger_scan_limit_bytes"])
        hit_counts = {m.decode("utf8"): 0 for m in markers}
        count = total = 0
        truncated = False
        # Full-machine local OS *read* inspection, constrained to local Retailer peer data.
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            if not path.resolve().is_relative_to(base.resolve()):
                continue
            if count >= limit_count or total >= limit_bytes:
                truncated = True
                break
            count += 1
            try:
                with path.open("rb") as f:
                    buf = f.read(min(1024 * 1024, limit_bytes - total))
            except OSError:
                continue
            total += len(buf)
            for marker in markers:
                hit_counts[marker.decode("utf8")] += buf.count(marker)
        return {"executed": True, "tool": "inspect_ledger", "scanned_files": count,
                "bytes_examined": total, "truncated": truncated,
                "marker_hits": hit_counts, "absence_proven": False,
                "note": "Raw byte marker scan is NOT a proof of private state absence/presence; LevelDB may encode/compress data."}

    def _fetch_block(self, n: int) -> dict:
        ca = self.kit / "trust/orderer-tls-ca.crt"
        if not ca.is_file():
            return {"executed": False, "tool": "fetch_public_block", "error_category": "orderer_ca_missing"}
        with tempfile.TemporaryDirectory(prefix="pt-tm2-") as d:
            path = Path(d) / "public-block.pb"
            args = ["channel", "fetch", str(n), str(path), "-o", "orderer0:7050",
                    "-c", self.cfg["channel"], "--tls", "--cafile", str(ca)]
            rc, _, err = self._exec(args)
            if rc != 0 or not path.is_file():
                return {"executed": True, "tool": "fetch_public_block", "block": n,
                        "request_succeeded": False, "error_category": category(err)}
            raw = path.read_bytes()
            return {"executed": True, "tool": "fetch_public_block", "block": n,
                    "request_succeeded": True, "block_sha256": hashlib.sha256(raw).hexdigest(),
                    "size_bytes": len(raw), "candidate_marker_hits": sum(raw.count(m.encode("utf8")) for m in
                        ("productionCostIdr", "mortalityRate", "\"fcr\"")),
                    "field_level_validation_required": True}

    def _attempt_update(self, batch: str) -> dict:
        payload = {"batchId": batch, **self.cfg["write_canary"]}
        trans = json.dumps({"performance": base64.b64encode(
            json.dumps(payload, separators=(",", ":")).encode()).decode()}, separators=(",", ":"))
        args = ["chaincode", "invoke", "-o", "orderer0:7050", "--tls", "--cafile",
                str(self.kit / "trust/orderer-tls-ca.crt"), "-C", self.cfg["channel"],
                "-n", self.cfg["chaincode"], "-c",
                json.dumps({"Args": ["UpdateFarmPerformance", batch]}, separators=(",", ":")),
                "--transient", trans]
        for target in ("farm", "integrator"):
            args += ["--peerAddresses", f"{target}:7051", "--tlsRootCertFiles",
                     str(self.kit / f"trust/{target}-tls-ca.crt")]
        args += ["--waitForEvent", "--waitForEventTimeout", "20s"]
        rc, out, err = self._exec(args)
        # No secret transient argument is returned, printed, or logged.
        return {"executed": True, "tool": "attempt_update", "batch": batch,
                "request_succeeded": rc == 0, "error_category": "none" if rc == 0 else category(err),
                "requires_independent_commit_and_state_check": True}

    def execute(self, action: dict, scenario: str) -> dict:
        error = self.validate(action, scenario)
        if error:
            return {"executed": False, "tool": action.get("action") if isinstance(action, dict) else None,
                    "error_category": "gateway_rejected", "reason": error}
        kind = action["action"]
        if kind == "finish":
            return {"executed": False, "tool": "finish", "finished": True}
        if kind == "inspect_processes":
            return self._inspect_processes()
        if kind == "inspect_peer_config":
            return self._inspect_peer_config()
        if kind == "inspect_ledger":
            return self._inspect_ledger()
        if kind in ("read_public", "read_private"):
            return self._query("GetBatch" if kind == "read_public" else "ReadFarmPerformance",
                               action["batch"], action["target"], kind == "read_private")
        if kind == "fetch_public_block":
            return self._fetch_block(action["block"])
        if kind == "attempt_update":
            return self._attempt_update(action["batch"])
        raise AssertionError("unreachable")
