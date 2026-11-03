#!/usr/bin/env python3
"""Automated executor for TM2 C0 60 registered trials."""
import csv
import io
import json
import subprocess
import sys
import time

CI = "coder-novian66-ws-integrator"
CR = "coder-novian66-ws-retailer"
COLLECT_SCRIPT = "/root/poultrytrace-tm2-host-tools/operator_collect.sh"
GROUND_TRUTH = "/home/coder/poultrytrace/stage11/dataset/farm_performance_private.jsonl"

def sh(cmd, check=True):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"Command failed (rc={r.returncode}): {cmd}\nSTDERR: {r.stderr}\nSTDOUT: {r.stdout}")
    return r

def main():
    print("=" * 70)
    print("   POULTRYTRACE TM2 — FULL-SCALE C0 RUNNER (60 REGISTERED TRIALS)   ")
    print("=" * 70)

    # 1. Read schedule from ws-integrator
    res = sh(f"docker exec {CI} cat /home/coder/poultrytrace/poultrytrace-tm2-retailer/schedule_tm2_s1.csv")
    reader = csv.DictReader(io.StringIO(res.stdout))
    c0_trials = [r for r in reader if r["condition"] == "C0"]
    print(f"Loaded {len(c0_trials)} C0 trials from schedule.")

    # 2. Check inbox in ws-integrator to identify already evaluated trials
    res_inbox = sh(f"docker exec {CI} ls -1 /home/coder/poultrytrace/tm2_operator_inbox 2>/dev/null || true", check=False)
    existing_inbox = set(res_inbox.stdout.split())

    completed = 0
    start_all = time.time()

    for idx, t in enumerate(c0_trials, 1):
        tid = t["trial_id"]
        mode = t["mode"]
        batch = t["batch"]
        scenario = t["scenario"]

        # Check if already evaluated in inbox
        if tid in existing_inbox:
            verdict_check = sh(f"docker exec {CI} test -f /home/coder/poultrytrace/tm2_operator_inbox/{tid}/operator_verdict.json", check=False)
            if verdict_check.returncode == 0:
                print(f"[{idx:02d}/60] {tid} already evaluated. Skipping.")
                completed += 1
                continue

        print(f"[{idx:02d}/60] Running {tid} (mode={mode}, batch={batch})... ", end="", flush=True)
        t0 = time.time()

        # Step A: Run in ws-retailer (exit code 0 or 3 are expected trial outcomes)
        run_cmd = (
            f"docker exec -u coder {CR} bash -c '"
            f"cd /home/coder/poultrytrace/poultrytrace-tm2-retailer && "
            f"python3 -m tm2.runner --scenario {scenario} --condition C0 --mode {mode} "
            f"--batch {batch} --trial-id {tid}'"
        )
        r_run = sh(run_cmd, check=False)
        if r_run.returncode not in (0, 3):
            print(f"FAILED (rc={r_run.returncode})")
            print("STDERR:", r_run.stderr)
            sys.exit(1)

        # Step B: Collect from ws-retailer to ws-integrator
        collect_cmd = f"{COLLECT_SCRIPT} {CR} {CI} {tid}"
        r_col = sh(collect_cmd, check=True)

        # Step C: Evaluate in ws-integrator
        eval_cmd = (
            f"docker exec -u coder {CI} bash -c '"
            f"cd /home/coder/poultrytrace/poultrytrace-tm2-retailer && "
            f"python3 -m tm2.evaluator "
            f"--trial-dir /home/coder/poultrytrace/tm2_operator_inbox/{tid} "
            f"--truth {GROUND_TRUTH}'"
        )
        r_eval = sh(eval_cmd, check=True)
        try:
            verdict_data = json.loads(r_eval.stdout)
            verdict = verdict_data.get("verdict", "unknown")
            reason = verdict_data.get("reason", "")
        except Exception:
            verdict = "parse_err"
            reason = ""

        dt = time.time() - t0
        print(f"DONE in {dt:.1f}s | verdict={verdict} ({reason})")
        completed += 1

    total_time = time.time() - start_all
    print("=" * 70)
    print(f"All 60 C0 trials completed in {total_time:.1f} seconds (~{total_time/60:.1f} minutes).")

    # 3. Generate summary report in ws-integrator
    print("Generating aggregate report in ws-integrator...")
    rep_cmd = (
        f"docker exec -u coder {CI} bash -c '"
        f"cd /home/coder/poultrytrace/poultrytrace-tm2-retailer && "
        f"python3 -m tm2.report "
        f"--evidence /home/coder/poultrytrace/tm2_operator_inbox "
        f"--output reports_tm2_s1.csv && "
        f"cat reports_tm2_s1.csv'"
    )
    r_rep = sh(rep_cmd, check=True)
    print(r_rep.stdout)

    # 4. Sync reports to host
    sh("mkdir -p /www/wwwroot/riset-blockchain-pdc/tm2_reports")
    sh(f"docker cp {CI}:/home/coder/poultrytrace/poultrytrace-tm2-retailer/reports_tm2_s1.csv /www/wwwroot/riset-blockchain-pdc/tm2_reports/reports_tm2_s1.csv")
    sh(f"docker cp {CI}:/home/coder/poultrytrace/tm2_operator_inbox/ /www/wwwroot/riset-blockchain-pdc/tm2_reports/")
    print("Reports synchronized to host: /www/wwwroot/riset-blockchain-pdc/tm2_reports/")
    print("=" * 70)

if __name__ == "__main__":
    main()
