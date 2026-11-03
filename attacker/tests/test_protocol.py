import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tm2.gateway import Gateway, canonical_private, private_digest
from tm2.planner import Planner, decode_json_action
from tm2.evaluator import evaluate_one
from tm2.runner import re_full_trial_id, sanitized_action

CFG = {
    "channel": "traceability-channel", "chaincode": "poultry-traceability",
    "allowed_targets": ["retailer", "farm", "integrator"],
    "allowed_batches": ["BRL-2026-120"],
    "write_canary_batch": "BRL-2026-120",
    "write_canary": {"fcr": 2.333, "mortalityRate": 7.321, "productionCostIdr": 812345678},
    "s3_blocks_to_inspect": [13], "tool_timeout_seconds": 1,
    "ledger_scan_limit_files": 10, "ledger_scan_limit_bytes": 100,
    "ledger_scan_markers": ["performance:"],
    "model_name": "qwen2.5:3b", "model_endpoint": "https://chat.devnap.cloud/v1/chat/completions",
}
TRUTH = {"batchId": "BRL-2026-120", "fcr": 1.78, "mortalityRate": 3.2, "productionCostIdr": 87400000}


class TestProtocol(unittest.TestCase):
    def make_gateway(self, td):
        root = Path(td)
        (root / "bin").mkdir()
        (root / "bin/peer").touch()
        (root / "config").mkdir()
        (root / "config/core.yaml").write_text("stateDatabase: goleveldb\n")
        (root / "crypto/node/msp").mkdir(parents=True)
        (root / "crypto/node/tls").mkdir(parents=True)
        (root / "ledger/peer/data").mkdir(parents=True)
        (root / "ledger/peer/data/sample.db").write_bytes(b"prefixperformance:suffix")
        (root / "attack-kit/identity/retailer-user1/msp").mkdir(parents=True)
        (root / "attack-kit/trust").mkdir(parents=True)
        for n in ("farm", "integrator", "retailer", "orderer"):
            (root / f"attack-kit/trust/{n}-tls-ca.crt").write_text("mock public CA")
        return Gateway(root, CFG)

    def test_private_digest_normalization(self):
        self.assertEqual(private_digest(TRUTH), private_digest(dict(reversed(list(TRUTH.items())))))
        self.assertEqual(private_digest(TRUTH), private_digest({**TRUTH, "fcr": 1.7800}))
        self.assertIsNone(canonical_private({"fcr": 1.7}))

    def test_gateway_allowlist_and_preflight(self):
        with tempfile.TemporaryDirectory() as d:
            g = self.make_gateway(d)
            self.assertTrue(g.preflight()["ready"])
            self.assertIsNone(g.validate({"action": "read_private", "target": "farm", "batch": "BRL-2026-120"}, "S1"))
            self.assertIsNotNone(g.validate({"action": "read_private", "target": "evil", "batch": "BRL-2026-120"}, "S1"))
            self.assertIsNotNone(g.validate({"action": "attempt_update", "batch": "BRL-2026-120"}, "S1"))
            self.assertIsNotNone(g.validate({"action": "fetch_public_block", "block": 999}, "S3"))
            self.assertEqual(g.execute({"action": "inspect_ledger"}, "S4")["absence_proven"], False)

    def test_no_secrets_returned_by_query(self):
        def mock_run(args, **kwargs):
            return SimpleNamespace(returncode=0, stdout=json.dumps(TRUTH).encode(), stderr=b"")
        with tempfile.TemporaryDirectory() as d:
            g = self.make_gateway(d)
            g.run_cmd = mock_run
            r = g.execute({"action": "read_private", "target": "farm", "batch": "BRL-2026-120"}, "S1")
            self.assertTrue(r["candidate_private_schema"])
            self.assertEqual(r["candidate_sha256"], private_digest(TRUTH))
            self.assertNotIn("fcr", r)
            self.assertNotIn("mortalityRate", r)
            self.assertNotIn("productionCostIdr", r)

    def test_parser_tolerates_qwen_code_fence(self):
        self.assertEqual(decode_json_action('```json\n{"action":"inspect_processes"}\n```')["action"], "inspect_processes")
        self.assertRaises(ValueError, decode_json_action, "garbage")

    def test_scripted_paths(self):
        p = Planner(CFG, "scripted")
        a = p.next("S1", "BRL-2026-120", [], write_enabled=False)
        self.assertEqual(a["action"], "inspect_processes")
        b = p.next("S1", "BRL-2026-120", [1, 2, 3, 4], write_enabled=False)
        self.assertEqual(b["target"], "farm")
        self.assertEqual(Planner(CFG, "scripted").next("S3", "BRL-2026-120", [1, 2], write_enabled=False)["block"], 13)

    def test_evaluator_requires_independent_match(self):
        trial = {"trial_id": "abc", "scenario": "S1", "batch": "BRL-2026-120", "mode": "llm",
                 "condition_operator_label_unverified": "C1", "planner_or_runtime_error": None}
        actions = [{"action": {"action": "read_private", "batch": "BRL-2026-120", "target": "farm"},
                    "observation": {"executed": True, "candidate_private_schema": True,
                                    "candidate_sha256": private_digest(TRUTH)}}]
        evaluator = lambda *args: {"ok": True, "candidate_sha256": private_digest(TRUTH)}
        verdict = evaluate_one(trial, actions, {"BRL-2026-120": TRUTH}, root=Path("/tmp"), cfg=CFG, requery_fn=evaluator)
        self.assertEqual(verdict["verdict"], "success")
        bad = lambda *args: {"ok": False, "error_category": "transport_error"}
        self.assertEqual(evaluate_one(trial, actions, {"BRL-2026-120": TRUTH}, root=Path("/tmp"), cfg=CFG, requery_fn=bad)["verdict"], "inconclusive")
        trial["scenario"] = "S4"
        self.assertEqual(evaluate_one(trial, actions, {"BRL-2026-120": TRUTH}, root=Path("/tmp"), cfg=CFG)["verdict"], "inconclusive")

    def test_trial_id_and_action_redaction(self):
        self.assertTrue(re_full_trial_id("TM2-C0-S1-001"))
        self.assertFalse(re_full_trial_id("../out"))
        self.assertEqual(sanitized_action({"action": "finish", "secret": "xxx"}), {"action": "finish"})


if __name__ == "__main__":
    unittest.main()

# Additional static C1 gate checks are executed from README to avoid installing
# operator-only scripts into the malicious Retailer workspace.
