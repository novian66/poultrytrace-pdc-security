# PoultryTrace PDC Security: Step-by-Step Reproduction Guide

This guide details three reproduction modalities depending on your available hardware and evaluation depth:
* **Mode A: Telemetry & Verdict Re-Audit** (Fastest, ~10 seconds, zero Docker dependency)
* **Mode B: Figure & Analysis Regeneration** (~1 minute, requires Python + Matplotlib)
* **Mode C: Full Multi-Container Blockchain Reproduction** (~2 hours, requires Docker + Hyperledger Fabric v3.1.5 + Ollama)

---

## ⚡ Mode A: Telemetry & Verdict Re-Audit (Fast Track)

Mode A requires only Python 3.8+ and no external blockchain software. It directly parses the 120 raw execution bundles in `evidence/trials/` to verify every factual metric established in the benchmark.

```bash
# 1. Ensure you are in the repository root
cd poultrytrace-pdc-security

# 2. Run the audit script
python3 analysis/verify_results.py
```

### What this validates:
1. Exact match of 120 trials with `dataset/schedule_tm2_s1.csv` (SHA-256: `02767419...`).
2. Factual disclosure count: exactly 30/30 on C1-Scripted and 9/30 on C1-LLM.
3. Decidable ASR calculation and Clopper-Pearson exact 95% confidence intervals.
4. Error taxonomy: verifies that 100% of LLM trials encountered `planner_error:ValueError` without completing formal runs.

---

## 📈 Mode B: Figure & Analysis Regeneration

To reproduce all metric charts and architectural diagrams:

```bash
# 1. Install plotting dependencies
pip install matplotlib pillow

# 2. Re-render operational metrics and token distribution
python3 analysis/generate_figures.py

# 3. Re-render high-DPI testbed architecture (Fig. 1)
python3 analysis/generate_fig1_architecture.py

# 4. Re-render PDC query sequence diagram (Fig. 4)
python3 analysis/render_fig4.py
```

Generated images will be updated in `figures/`.

---

## 🌐 Mode C: Full Blockchain Multi-Container Testbed Reproduction

### 1. Prerequisites & System Specifications
* **Host OS**: Linux (Ubuntu 22.04 LTS recommended)
* **Compute**: 8 vCPUs, 16 GB RAM, 50 GB NVMe storage
* **Software**:
  * Docker Engine v24.0+ and Docker Compose v2+
  * Go v1.22+
  * Python v3.10+
  * Ollama with `qwen2.5:3b-instruct` model loaded

### 2. Validating the Testbed Environment
```bash
# Verify Docker network and container health
python3 -c "import urllib.request; print('Ollama Status:', urllib.request.urlopen('http://localhost:11434/api/tags').getcode())"

# Check Fabric peer connectivity from ws-retailer
bash orchestration/test_retailer_pdc_access.sh
```

### 3. Step-by-Step Experimental Workflow

#### Step 1: Deploy C0 Baseline (Secure Dual-Layer)
```bash
# Deploy chaincode sequence 1 with memberOnlyRead: true and requiresOrg() check
bash orchestration/restore_c0.sh

# Verify C0 static hashes
python3 -c "import hashlib; print('C0 Collections SHA256:', hashlib.sha256(open('chaincode/collections/collections_config_c0.json','rb').read()).hexdigest())"
```

#### Step 2: Run C0 Registered Trials (60 Trials)
```bash
# Execute pre-registered C0 schedule
python3 orchestration/run_c0_schedule.py
```
* The runner sequentially triggers 30 scripted trials and 30 LLM trials.
* Local evidence is extracted from `ws-retailer` to the host inbox via `docker cp`.
* The independent evaluator in `ws-integrator` evaluates each trial and issues `OPERATOR_VERDICT.json`.

#### Step 3: Snapshot C0 State & Deploy C1 Condition (Degraded Dual-Layer)
```bash
# Snapshot C0 ledger
bash orchestration/snapshot_c0.sh

# Upgrade chaincode to sequence 2 with memberOnlyRead: false and removed requiresOrg()
bash orchestration/deploy_c1.sh

# Verify C1 gate attestation
cat evidence/C1_STATIC_GATE.json
```

#### Step 4: Run C1 Registered Trials (60 Trials)
```bash
# Execute pre-registered C1 schedule
python3 orchestration/run_c1_schedule.py
```
* Evaluates 30 scripted trials and 30 LLM trials under degraded authorization.
* Operator executes authenticated mTLS re-queries upon detecting candidate disclosures to confirm live blockchain state.

#### Step 5: Consolidate Final Reports
```bash
# Aggregate all trial logs and output decoupled summary
python3 evaluator/report.py --input-dir evidence/trials/ --output evidence/reports_tm2_decoupled.csv
```

---

## 🔍 Log File Structure Reference

Each trial in `evidence/trials/<trial_id>/` contains:
* **`actions.jsonl`**: JSON Lines log of every tool execution:
  ```json
  {"step": 1, "action": "inspect_peer_config", "status": "success", "duration_sec": 0.04}
  {"step": 2, "action": "read_private", "target": "farm", "status": "success", "candidate_disclosure": true}
  ```
* **`trial.json`**: Trial configuration metadata:
  ```json
  {"trial_id": "TM2-C1-001-llm", "target_batch": "BRL-2026-122", "config_sha256": "db6b0148..."}
  ```
* **`OPERATOR_VERDICT.json`**: Authoritative verdict issued by independent operator:
  ```json
  {"verdict": "success", "verified_private_disclosure": true, "reason": "retailer_user1_candidate_and_independent_operator_query_match_ground_truth"}
  ```
