#!/usr/bin/env python3
"""Script to extract and render the Testbed Architecture Flowchart to PNG and JPG."""
import os
import json
import base64
import urllib.request
from PIL import Image

OUT_DIRS = [
    "/www/wwwroot/riset-blockchain-pdc/figures",
    "/root/.gemini/antigravity-cli/brain/4365535c-86e9-4982-99cb-ba3281252ff9/figures"
]
for d in OUT_DIRS:
    os.makedirs(d, exist_ok=True)

diagram = '''flowchart TD
    subgraph Host["Host Docker Environment (Isolated VPS)"]
        Runner["Host Runner Script (run_c0/c1_schedule.py)"]
        Schedule["Pre-registered Schedule (120 Trials)"]
        Collector["Operator Collector (operator_collect.sh)"]
    end

    subgraph WSRetailer["Untrusted Attacker Workspace (ws-retailer)"]
        Attacker["Attacker Process (tm2.runner)"]
        AgentAI["Bounded Agent (Qwen 2.5:3B via Ollama)"]
        ScriptedAttacker["Deterministic Scripted Agent"]
        RetailerMSP["RetailerOrgMSP / User1 Credentials"]
        LocalTools["Local OS Tools (inspect_processes, core.yaml)"]
        Evidence["Local Evidence Bundle (actions.jsonl, trial.json)"]
    end

    subgraph BlockchainNetwork["Permissioned Consortium Network (poultrytrace-net)"]
        Orderers["4 SmartBFT Orderers (orderer0..orderer3)"]
        PeerRetailer["peer0.retailer:7051"]
        PeerFarm["peer0.farm:7051 (Stores pdc_farm_integrator)"]
        PeerIntegrator["peer0.integrator:7051 (Stores pdc_farm_integrator)"]
        OtherPeers["4 Other Peer Nodes (Hatchery, RPA, Dist, Reg)"]
    end

    subgraph WSIntegrator["Trusted Operator Workspace (ws-integrator)"]
        Inbox["Isolated Operator Inbox (/tm2_operator_inbox/)"]
        Evaluator["Independent Evaluator (tm2.evaluator)"]
        GroundTruth["Ground Truth (farm_performance_private.jsonl)"]
        Verdict["Official Verdict (OPERATOR_VERDICT.json)"]
    end

    Schedule --> Runner
    Runner -->|Trigger Trial| Attacker
    Attacker --> AgentAI
    Attacker --> ScriptedAttacker
    AgentAI -->|mTLS Query| PeerFarm
    ScriptedAttacker -->|mTLS Query| PeerFarm
    Attacker --> Evidence
    Runner -->|Collect Evidence| Collector
    Collector -->|"Copy via Host (Docker cp)"| Inbox
    Runner -->|Trigger Evaluation| Evaluator
    Evaluator --> Inbox
    Evaluator --> GroundTruth
    Evaluator --> Verdict
'''

payload = json.dumps({'code': diagram, 'mermaid': {'theme': 'default'}})
encoded = base64.urlsafe_b64encode(payload.encode('utf-8')).decode('ascii')
url = f'https://mermaid.ink/img/{encoded}?type=png'

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=20) as resp:
    data = resp.read()

png_temp = "/tmp/flowchart_rendered.png"
with open(png_temp, "wb") as f:
    f.write(data)

im = Image.open(png_temp)
if im.mode == "RGBA":
    bg = Image.new("RGB", im.size, (255, 255, 255))
    bg.paste(im, mask=im.split()[3])
    rgb_im = bg
else:
    rgb_im = im.convert("RGB")

filenames = ["flowchart_tm2_testbed_architecture", "fig0_tm2_testbed_architecture"]

for d in OUT_DIRS:
    for name in filenames:
        p_png = os.path.join(d, f"{name}.png")
        p_jpg = os.path.join(d, f"{name}.jpg")
        im.save(p_png, "PNG", optimize=True)
        rgb_im.save(p_jpg, "JPEG", quality=95, optimize=True)

print("Flowchart rendering completed successfully.")
