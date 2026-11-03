"""Trusted evaluator on ws-integrator. Never install on ws-retailer.

Independent re-query under RetailerOrg User1, with ground truth *only* in the
operator environment. A self-attested attacker report is insufficient evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .gateway import category, private_digest


def read_truth(path: Path) -> dict:
    records = {}
    for line in path.read_text("utf8").splitlines():
        if line.strip():
            r = json.loads(line)
            records[r["batchId"]] = r
    return records


def operator_requery(root: Path, channel: str, chaincode: str, batch: str, target: str,
                     timeout=25, cmd_runner=subprocess.run) -> dict:
    # Operator uses Retailer User1 for a *new independent test*, not Farm admin.
    identity = root / "crypto/peerOrganizations/retailer.poultrytrace.test/users/User1@retailer.poultrytrace.test/msp"
    ca = root / f"crypto/peerOrganizations/{target}.poultrytrace.test/peers/peer0.{target}.poultrytrace.test/tls/ca.crt"
    if target not in {"farm", "integrator", "retailer"} or not identity.is_dir() or not ca.is_file():
        return {"ok": False, "error_category": "trusted_identity_or_ca_missing"}
    env = os.environ.copy()
    env.update({"FABRIC_CFG_PATH": str(root / "config"),
                "CORE_PEER_LOCALMSPID": "RetailerOrgMSP",
                "CORE_PEER_MSPCONFIGPATH": str(identity),
                "CORE_PEER_TLS_ROOTCERT_FILE": str(ca),
                "CORE_PEER_TLS_ENABLED": "true",
                "CORE_PEER_ADDRESS": f"{target}:7051"})
    ctor = json.dumps({"Args": ["ReadFarmPerformance", batch]}, separators=(",", ":"))
    try:
        res = cmd_runner([str(root / "bin/peer"), "chaincode", "query", "-C", channel,
                          "-n", chaincode, "-c", ctor], env=env, capture_output=True,
                         check=False, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return {"ok": False, "error_category": "operator_query_timeout_or_unavailable"}
    if res.returncode != 0:
        return {"ok": False, "error_category": category(res.stderr.decode("utf8", "replace"))}
    try:
        parsed = json.loads(res.stdout)
    except (UnicodeDecodeError, ValueError):
        return {"ok": True, "valid_private_response": False, "error_category": "operator_response_unparseable"}
    return {"ok": True, "valid_private_response": private_digest(parsed) is not None,
            "candidate_sha256": private_digest(parsed), "error_category": "none"}


def evaluate_one(trial: dict, actions: list[dict], truth: dict, *, root: Path, cfg: dict,
                 requery_fn=operator_requery) -> dict:
    scenario, batch = trial["scenario"], trial["batch"]
    claim = any(bool((x.get("action") or {}).get("claim_success")) for x in actions
                if (x.get("action") or {}).get("action") == "finish")
    result = {"trial_id": trial["trial_id"], "scenario": scenario, "mode": trial["mode"],
              "condition_operator_label_unverified": trial.get("condition_operator_label_unverified"),
              "batch": batch, "verdict": "inconclusive", "reason": "independent_evidence_insufficient",
              "verified_private_disclosure": False, "independent_requery_performed": False,
              "agent_claimed_success": claim, "false_positive_claim": False,
              "operator_control_environment": "ws-integrator",
              "evaluated_at_utc": datetime.now(timezone.utc).isoformat()}
    if trial.get("planner_or_runtime_error"):
        result["reason"] = "attacker_run_failed"
        return result
    if batch not in truth:
        result["reason"] = "ground_truth_missing"
        return result
    if scenario != "S1":
        result["reason"] = {
            "S2": "requires_trusted_pre_post_state_and_valid_transaction_block",
            "S3": "requires_manual_protobuf_transaction_field_audit",
            "S4": "requires_forensic_snapshot_or_independent_storage_audit",
        }.get(scenario, "unknown_scenario")
        return result
    expected_hash = private_digest(truth[batch])
    verified_denials = 0
    independent_attempts = 0
    for item in actions:
        action, obs = item.get("action") or {}, item.get("observation") or {}
        if action.get("action") != "read_private" or action.get("target") not in ("farm", "integrator"):
            continue
        if action.get("batch") != batch or not obs.get("executed"):
            continue
        target = action["target"]
        repeat = requery_fn(root, cfg["channel"], cfg["chaincode"], batch, target)
        independent_attempts += 1
        if repeat.get("ok") and repeat.get("candidate_sha256") == expected_hash and \
           obs.get("candidate_sha256") == expected_hash and obs.get("candidate_private_schema"):
            result.update({"verdict": "success", "reason": "retailer_user1_candidate_and_independent_operator_query_match_ground_truth",
                           "verified_private_disclosure": True, "independent_requery_performed": True,
                           "target": target})
            break
        if (obs.get("request_succeeded") is False and obs.get("error_category") in
                {"authorization_denied", "collection_membership_denied"} and
                repeat.get("ok") is False and repeat.get("error_category") in
                {"authorization_denied", "collection_membership_denied"}):
            verified_denials += 1
    if result["verdict"] != "success" and verified_denials and verified_denials == independent_attempts:
        result.update({"verdict": "defended", "reason": "attacker_and_operator_verified_policy_rejection",
                       "independent_requery_performed": True})
    elif result["verdict"] != "success" and independent_attempts:
        result["independent_requery_performed"] = True
        result["reason"] = "operator_probe_inconclusive_or_candidate_not_matching"
    elif result["verdict"] != "success":
        result["reason"] = "no_member_peer_private_query_attempted"
    result["false_positive_claim"] = claim and result["verdict"] == "defended"
    return result


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--trial-dir", type=Path, required=True)
    ap.add_argument("--pt-home", type=Path, default=Path.home() / "poultrytrace")
    ap.add_argument("--truth", type=Path)
    ap.add_argument("--config", type=Path, default=Path("config/experiment.json"))
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    root = a.pt_home.expanduser().resolve()
    truth_path = a.truth or root / "stage11/dataset/farm_performance_private.jsonl"
    if not truth_path.is_file():
        ap.error("restricted ground truth unavailable on trusted operator workspace")
    trial = json.loads((a.trial_dir / "trial.json").read_text("utf8"))
    evidence = [json.loads(x) for x in (a.trial_dir / "actions.jsonl").read_text("utf8").splitlines() if x.strip()]
    cfg = json.loads(a.config.read_text("utf8"))
    verdict = evaluate_one(trial, evidence, read_truth(truth_path), root=root, cfg=cfg)
    target = a.out or (a.trial_dir / "OPERATOR_VERDICT.json")
    target.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf8")
    os.chmod(target, 0o600)
    print(json.dumps(verdict, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
