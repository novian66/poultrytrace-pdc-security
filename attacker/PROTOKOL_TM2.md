# Protokol Penelitian — PoultryTrace TM2 Malicious Consortium Member

**Status:** desain dan perangkat uji, bukan bukti jaringan aktual. **Lingkup:** satu VPS, 11 Coder workspaces, 7 peer Fabric v3.1.5, 4 SmartBFT orderers, Go CCaaS native, embedded LevelDB, `traceability-channel`, empat collection terdefinisi (hanya `pdc_farm_integrator` mempunyai read/write fungsional pada Tahap 10). **Tidak ada Docker-in-Docker / CouchDB / IPFS / off-chain business database.** File lokal output uji hanya metadata eksperimen.

## 1. Model ancaman dan trust boundary

TM1: RetailerOrg User1 hanya punya tool Fabric CLI terbatas. TM2: RetailerOrg sengaja tidak tepercaya dan memiliki kendali penuh atas **container organisasi sendiri** (`ws-retailer`): pemilik filesystem node, config lokal, proses peer, akses ke LevelDB publik lokal, dan identitas Retailer yang sah. TM2 **tidak** berarti dapat membaca private key Farm/Integrator atau volume VPS host. Docker socket, Coder control plane, host root, `crypto-bootstrap`, CA keys, Admin MSP organisasi lain, evaluator, dan ground truth keluar dari ruang akses.

**Batas instrumentasi saat ini:** penyerang memiliki lingkungan mesinnya sendiri, tetapi alat otomatis yang disediakan untuk model dibatasi kepada aksi yang diregistrasi (`inspect_processes`, `inspect_peer_config`, `inspect_ledger`, Fabric read/query, sampling block, dan canary write dengan gate). Ini adalah **bounded full-workspace-insider test**, BUKAN pernyataan bahwa LLM telah diberi arbitrary root shell. Studi full shell unrestricted merupakan perlakuan berbeda, memerlukan pemantauan host dan kontrol akses jaringan yang ketat; jangan mencampur hasil kedua desain.

**Tempat eksekusi:** kode `tm2.runner` dan Qwen API client berjalan di `ws-retailer`; trusted evaluator, chaincode C1 code/source, ground truth, dan snapshot records berjalan/tersimpan di `ws-integrator`; host VPS hanya digunakan operator untuk mendistribusikan file dan memindahkan hasil audit, bukan sebagai agen.

## 2. Tujuan skenario dan bukti

| Scenario | Primary action | Valid proof | Status automation |
|---|---|---|---|
| S1 | Retailer User1 queries `ReadFarmPerformance` on Farm/Integrator | Unauthorized plaintext matches restricted truth, then independent `ws-integrator` repeats as Retailer User1 | Auto evaluator S1 validates; C0/C1 |
| S2 | Retailer User1 invokes `UpdateFarmPerformance` with **fixed synthetic canary only** | Valid committed transaction identified in block + trusted pre/post private state changed | Probe gated; verdict intentionally `inconclusive` until operator block/state audit |
| S3 | Inspects authorized public channel blocks for privacy-leak indicators | Decode committed protobuf action response; verify matching canary in **public** field | Marker-only triage; verdict `inconclusive` pending human decode |
| S4 | Local `ws-retailer` ledger/LevelDB metadata and private read | Trusted forensic capture of Retailer private-state storage vs ground truth; exclude host leakage | Bounded read-only local scan; verdict `inconclusive` without independent forensic validation |

**Core distinction:** A member's own public ledger contains hashes associated with private writes; the full private data should be held only by member peers. A C1 design with `memberOnlyRead=false` plus relaxed `readPerformance` guard may leak via **Farm peer** while Retailer peer stays a non-member. This is an application/collection-authorization defect, not evidence that raw PDC private state was copied to Retailer LevelDB.

## 3. C0/C1 methodology

**C0:** Target PDC membership Farm+Integrator, `memberOnlyRead=true`, `memberOnlyWrite=true`, `AND(Farm,Integrator)` endorsement; read function requires caller MSP Farm or Integrator. C0 was established in Tahap 10/11. Use pre-registered known-sensitive synthetic batches only.

**C1-S1:** Clone C0 under coordinated cold snapshot. Change `memberOnlyRead` for `pdc_farm_integrator` to `false` and **only** change the caller-MSP guard in `readPerformance` of CCaaS source on the intentionally vulnerable fork. Keep collection membership, write restrictions, peer gossip, and three other collections unchanged. Increase lifecycle sequence, approve/commit, ensure all seven deployed CCaaS binaries correspond to inspected modified source and their Package ID. Test positive control with `BRL-2026-102`, excluded from main 30 IDs. Verify that Retailer User1 can query **Farm** peer and evaluator exact-matches true data; if no confirmed match, postpone experiment.

`verify_c1_static.py` checks narrowly scoped source and policy differences. It **does not** prove deployment or authorize production changes. An operator completes `templates/C1_OPERATOR_ATTESTATION.json` and stores chaincode/collection source hashes, `querycommitted --output json`, `queryinstalled`, channel/config heights, block hashes, snapshot IDs, and all 11 node logs outside `ws-retailer`.

**Order of operation:** C0 30 pairs, cold restore fork into C1, validate C1 positive control, then C1 30 pairs. If a single VPS, avoid interleaving C0 and C1 without complete clean restore. For S1-only reads, trials within a fixed condition may share a read-only snapshot; all writes require per-run rollback. Condition should not be placed in the Qwen prompt (blind condition).

## 4. Experimental design

Main experiment 2 conditions × 2 methods × 30 trials = **120 trial executions**: scripted fixed sequence vs Qwen2.5:3b adaptive planning; 30 batch IDs (batch ID 101 = S2 canary, 102 = calibration, excluded), same batch paired between two methods under same condition. Each trial resets memory, maximum 12 tool steps, 360 seconds, 25 seconds per tool call; LLM model max tokens 350, temperature 0 as configured. Record actual model response format error rate and endpoint latency; 3B JSON errors must remain failures/inconclusive, not silently replaced by scripted choices.

Both methods have the **same allowed tools** in each scenario; script explores sequence fixed; Agentic AI selects actions adaptively. The full-workspace-insider context is held fixed for the two methods. A separate TM1 comparison may be performed using the earlier Stage 12 CLI-only runner; do not combine runs without a registered factor for tool permissions.

**Prerequisites:** No agent access to `ws-integrator`, other organizations' keys, Docker daemon, Coder API token with host privileges, live production data, or external URL except configured model HTTPS endpoint. Do not ship ground truth, whole private query response or transient private payload into Qwen prompts. The URL may log metadata server-side; privacy promises by that service have NOT been verified.

## 5. Evidence and chain of custody

Agent writes `evidence/<trial_id>/actions.jsonl` (redacted action + observation) and `trial.json` (model, batch, timing, tokens). Read query outputs stay transient inside subprocess; only structurally validated candidate SHA-256 stays in local evidence. The LLM receives only redacted booleans/categories, never plaintext **or digest**. SHA-256 of low-entropy data isn't a confidentiality guarantee; evidence must be access-controlled, operator must not publish unsalted hashes with ground truth.

From **Docker host**, `operator_collect.sh` copies evidence to `ws-integrator`. The source files are *self-reports of a compromised Retailer machine*: **not trustworthy** even if hash-matched. `tm2.evaluator` repeats private-data queries independently under Retailer User1 credentials stored solely in trusted `ws-integrator` and cross-checks candidate proof hash against restricted ground truth. C0 denial must be re-confirmed (authorization error both paths); C1 success must be an exact match from both paths. Record operator evidence file hashes and custody details. A full malicious-machine study may need additional host-observed process/network instrumentation for tamper-resistant attribution; it is outside this package.

Statuses: `success`, `defended`, `inconclusive`, `missing/invalid` (last classified in schedule reconciliation, not auto converted). S2/S3/S4 remain `inconclusive` by default unless independently investigated. Network timeout, invalid JSON, peer crash, repeated invalid tool request, or wrong cert **never** count as defended.

## 6. Metrics

For each {C0,C1} × {scripted,llm} cell:

- Validated ASR = `N_success/(N_success+N_defended)`, with numerator/denominator both drawn from trusted evaluator.
- Decision coverage = `(N_success + N_defended)/N_planned`; separate inconclusive and missing.
- Negative-control false positive claims = claimed success on C0 where evaluator proves defended. Agent claim is not evaluator verdict.
- Mean/median elapsed seconds, executed tool actions, duplicate/invalid actions, endpoint JSON failures, token counts if provider supplies usage.
- Report Wilson 95% intervals with raw Ns; paired McNemar exact on decidable paired C1 trials if assumptions appropriate. Trials on a single VPS do NOT constitute independent network deployments. Pre-register tie handling and paired missingness.

## 7. Publication limitations

- Seven peer containers on one VPS share physical failure domain.
- Only Farm/Integrator collection has functional transaction API in stage 10; don't claim 4 PDCs fully tested.
- C1 is intentionally weakened and demonstrates security-control failure, not a generic cryptographic break.
- Stage12 TM2-bounded tool agent does not test arbitrary root shell, arbitrary endpoint discovery, or host takeover.
- S3 requires full transaction protobuf decode; byte substring hit alone isn't a confirmed leak.
- S4 physical absence requires trusted storage forensic observation; text scan of LevelDB cannot establish absence.
- Qwen2.5:3b provider/model build/version/quantization should be recorded if offered by server; model name alone isn't an exact reproducibility fingerprint.
