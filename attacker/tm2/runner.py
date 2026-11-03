"""TM2 in-workspace agent runner. It cannot independently attest its own observations."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .gateway import Gateway, SCENARIO_ACTIONS
from .planner import Planner


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, obj):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n", encoding="utf8")
    os.replace(temp, path)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path("config/experiment.json"))
    p.add_argument("--pt-home", type=Path, default=Path.home() / "poultrytrace")
    p.add_argument("--scenario", choices=sorted(SCENARIO_ACTIONS), default="S1")
    p.add_argument("--mode", choices=("scripted", "llm"), default="scripted")
    p.add_argument("--condition", choices=("C0", "C1"), default="C0")
    p.add_argument("--batch")
    p.add_argument("--trial-id", required=True)
    p.add_argument("--outroot", type=Path, default=Path("evidence"))
    p.add_argument("--preflight-only", action="store_true")
    p.add_argument("--enable-write", action="store_true")
    p.add_argument("--snapshot-attested", action="store_true")
    args = p.parse_args(argv)
    config = json.loads(args.config.read_text("utf8"))
    batch = args.batch or config["default_batch"]
    if batch not in config["allowed_batches"]:
        p.error("batch not in dataset allowlist")
    if not re_full_trial_id(args.trial_id):
        p.error("trial-id must contain only letters, digits, hyphens, underscores (max 96)")
    if args.enable_write and (args.scenario != "S2" or not args.snapshot_attested):
        p.error("write requires S2 and explicit snapshot attestation")
    gw = Gateway(args.pt_home, config, enable_write=args.enable_write)
    preflight = gw.preflight()
    if args.preflight_only:
        print(json.dumps({"experiment": "TM2", "mode": args.mode, "preflight": preflight}, indent=2))
        return 0 if preflight["ready"] else 2
    if not preflight["ready"]:
        print(json.dumps({"error": "preflight_failed", "checks": preflight["checks"]}, indent=2), file=sys.stderr)
        return 2
    trial_dir = args.outroot.resolve() / args.trial_id
    # Exclusive creation; no overwrite.
    trial_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.chmod(trial_dir, 0o700)
    planner = Planner(config, args.mode)
    history = []
    steps = []
    started = time.monotonic()
    error = None
    seen = {}
    with (trial_dir / "actions.jsonl").open("x", encoding="utf8") as log:
        os.chmod(trial_dir / "actions.jsonl", 0o600)
        for i in range(int(config["max_steps"])):
            if time.monotonic() - started > int(config["max_run_seconds"]):
                error = "run_timeout"
                break
            try:
                action = planner.next(args.scenario, batch, history, write_enabled=args.enable_write)
            except Exception as exc:
                error = "planner_error:" + type(exc).__name__
                break
            sig = json.dumps(action, sort_keys=True)
            seen[sig] = seen.get(sig, 0) + 1
            if seen[sig] > 2:
                obs = {"executed": False, "tool": action.get("action"), "error_category": "duplicate_action_limit"}
            else:
                try:
                    obs = gw.execute(action, args.scenario)
                except Exception as exc:
                    obs = {"executed": False, "tool": action.get("action"), "error_category": "gateway_exception:" + type(exc).__name__}
            item = {"step": i + 1, "timestamp_utc": utc_now(), "action": sanitized_action(action), "observation": obs}
            log.write(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n")
            log.flush()
            history.append(item)
            steps.append(item)
            if action.get("action") == "finish":
                break
    duration = time.monotonic() - started
    potential = [s for s in steps if s["observation"].get("candidate_private_schema")]
    trial = {"trial_id": args.trial_id, "timestamp_utc": utc_now(), "mode": args.mode,
             "scenario": args.scenario, "condition_operator_label_unverified": args.condition,
             "batch": batch, "model_name": config["model_name"] if args.mode == "llm" else None,
             "model_endpoint": config["model_endpoint"] if args.mode == "llm" else None,
             "attacker_identity": "RetailerOrgMSP/User1", "tool_calls": len(steps),
             "duration_seconds": round(duration, 3), "prompt_tokens": planner.tokens_in,
             "completion_tokens": planner.tokens_out, "planner_or_runtime_error": error,
             "candidate_private_responses": len(potential),
             "self_report_only": True, "independent_verification_required": True,
             "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest()}
    atomic_json(trial_dir / "trial.json", trial)
    for f in (trial_dir / "trial.json", trial_dir / "actions.jsonl"):
        os.chmod(f, 0o600)
    print(json.dumps({"trial_dir": str(trial_dir), "trial": trial}, indent=2))
    return 0 if error is None else 3


def sanitized_action(action: dict) -> dict:
    # Model can produce arbitrary extraneous keys; only record approved metadata.
    return {k: action[k] for k in ("action", "target", "batch", "block", "claim_success") if k in action}


def re_full_trial_id(name: str) -> bool:
    import re
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{1,96}", name))


if __name__ == "__main__":
    raise SystemExit(main())
