import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
import os
from PIL import Image

plt.rcParams["font.family"] = "DejaVu Sans"

# Canvas dimensions
FIG_W, FIG_H = 15.0, 10.5
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H), dpi=300)
ax.set_xlim(0, 148)
ax.set_ylim(0, 108)
ax.axis("off")

# Professional Color Palette
C_HOST_BG = "#F1F5F9"
C_HOST_BORDER = "#475569"
C_HOST_HEADER = "#0F172A"

C_ATK_BG = "#FFF5F5"
C_ATK_BORDER = "#DC2626"
C_ATK_HEADER = "#7F1D1D"

C_OP_BG = "#F0FDF4"
C_OP_BORDER = "#059669"
C_OP_HEADER = "#064E3B"

C_NET_BG = "#EFF6FF"
C_NET_BORDER = "#2563EB"
C_NET_HEADER = "#1E3A8A"

BOX_BG = "#FFFFFF"
TXT_MAIN = "#0F172A"
TXT_MUTED = "#334155"

def draw_group(x, y, w, h, title, bg_col, border_col, title_col, badge=""):
    patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=2.0",
                           fc=bg_col, ec=border_col, lw=2.2, zorder=1)
    ax.add_patch(patch)
    # Header title
    ax.text(x + 2.4, y + h - 2.4, title, ha="left", va="top",
            fontsize=12.5, fontweight="bold", color=title_col, zorder=2)
    if badge:
        ax.text(x + w - 2.4, y + h - 2.4, badge, ha="right", va="top",
                fontsize=9.5, fontweight="bold", color=border_col,
                bbox=dict(boxstyle="round,pad=0.35,rounding_size=0.6", fc="#FFFFFF", ec=border_col, lw=1.3), zorder=2)

def draw_box(x, y, w, h, title, subtext="", fc=BOX_BG, ec="#94A3B8", lw=1.3,
             title_col=TXT_MAIN, sub_col=TXT_MUTED, title_fs=10, sub_fs=8.5, title_y_off=1.5):
    patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.35,rounding_size=1.0",
                           fc=fc, ec=ec, lw=lw, zorder=3)
    ax.add_patch(patch)
    if subtext:
        ax.text(x + w/2, y + h - title_y_off, title, ha="center", va="top",
                fontsize=title_fs, fontweight="bold", color=title_col, zorder=4)
        ax.text(x + w/2, y + 1.2, subtext, ha="center", va="bottom",
                fontsize=sub_fs, color=sub_col, zorder=4, linespacing=1.22)
    else:
        ax.text(x + w/2, y + h/2, title, ha="center", va="center",
                fontsize=title_fs, fontweight="bold", color=title_col, zorder=4)
    return (x + w/2, y + h/2, x, y, w, h)

def draw_arrow(p1, p2, label="", color="#334155", lw=1.8, rad=0.0, loff=(0, 0),
               step_num=None, style="-|>", linestyle="solid"):
    arrow = FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=16,
                            lw=lw, color=color, linestyle=linestyle,
                            connectionstyle=f"arc3,rad={rad}", zorder=5)
    ax.add_patch(arrow)
    if label or step_num:
        mx = (p1[0] + p2[0]) / 2 + loff[0]
        my = (p1[1] + p2[1]) / 2 + loff[1]
        txt = f" {step_num}  {label} " if step_num else f" {label} "
        ax.text(mx, my, txt, ha="center", va="center", fontsize=8.8, fontweight="bold",
                color=color, zorder=6,
                bbox=dict(boxstyle="round,pad=0.3,rounding_size=0.6", fc="#FFFFFF", ec=color, lw=1.3, alpha=0.98))

# ==================== 1. HOST ENVIRONMENT (TOP: y in 86..105) ====================
draw_group(4, 86, 140, 18, "Host Docker Environment (Isolated VPS Testbed Host)",
           C_HOST_BG, C_HOST_BORDER, C_HOST_HEADER, badge="HOST / ORCHESTRATION LAYER")

b_sched = draw_box(7, 88.5, 38, 12, "Pre-registered Schedule",
                   "schedule_tm2_s1.csv (120 Trials)\nSHA-256: 02767419... (Frozen)\nRandomized Pair Order (LLM / Scripted)",
                   ec="#475569", lw=1.4)

b_runner = draw_box(51, 88.5, 44, 12, "Host Runner Script",
                    "run_c0_schedule.py / run_c1_schedule.py\nSequential trial orchestration & timeouts\nEnforces zero cross-trial contamination",
                    ec="#2563EB", lw=1.8)

b_collector = draw_box(101, 88.5, 40, 12, "Host Operator Collector",
                       "operator_collect.sh (Host script)\nTransfers trial logs via docker cp\nZero network route to Operator Inbox",
                       ec="#0D9488", lw=1.6)

draw_arrow((b_sched[2]+b_sched[4], b_sched[1]), (b_runner[2], b_runner[1]), lw=1.6, color="#475569")

# ==================== 2. UNTRUSTED ATTACKER WORKSPACE (MIDDLE-LEFT: y in 33..76) ====================
draw_group(4, 33, 67, 43, "Untrusted Attacker Workspace (Docker: ws-retailer)",
           C_ATK_BG, C_ATK_BORDER, C_ATK_HEADER, badge="UNTRUSTED ZONE")

b_atk_proc = draw_box(7, 67, 61, 6.2, "Attacker Process (tm2.runner)",
                      "Security Context: RetailerOrgMSP / User1 Credentials (Valid Consortium Member)",
                      fc="#FFFFFF", ec="#DC2626", lw=1.6, title_fs=10.5, sub_fs=8.5, title_y_off=1.3)

b_scripted = draw_box(7, 52.5, 29, 12.5, "Deterministic Scripted",
                      "Fixed 7-step sequence:\n1-2: inspect_processes/config\n3: read_public (Retailer)\n4-6: read_private (Ret, Farm, Int)\n7: finish",
                      fc="#FFF8F8", ec="#DC2626", lw=1.4, title_fs=9.8, sub_fs=8.0)

b_agent = draw_box(39, 52.5, 29, 12.5, "Bounded Agent (LLM)",
                   "Qwen 2.5:3B via Ollama\nLocal inference (chat.devnap.cloud)\n12-step budget, schema allowlist\nFailure mode: planner_error",
                   fc="#FFF8F8", ec="#DC2626", lw=1.4, title_fs=9.8, sub_fs=8.0)

b_tools = draw_box(7, 35.5, 29, 14.5, "Local OS Tools & Storage",
                   "inspect_processes (procfs scan)\ninspect_peer_config (core.yaml)\nLocal LevelDB state inspect\nRetailer TLS certs & keystore",
                   ec="#94A3B8", lw=1.2, title_fs=9.8, sub_fs=8.0)

b_evid = draw_box(39, 35.5, 29, 14.5, "Local Evidence Bundle",
                  "actions.jsonl (step telemetry)\ntrial.json (config_sha256: db6b0148)\nExtracted candidate records\nLocal execution error traces",
                  fc="#FFF5F5", ec="#E11D48", lw=1.5, title_fs=9.8, sub_fs=8.0)

draw_arrow((b_atk_proc[0]-14, b_atk_proc[3]), (b_scripted[0], b_scripted[3]+b_scripted[5]), lw=1.3, color="#DC2626")
draw_arrow((b_atk_proc[0]+14, b_atk_proc[3]), (b_agent[0], b_agent[3]+b_agent[5]), lw=1.3, color="#DC2626")
draw_arrow((b_scripted[0], b_scripted[3]), (b_evid[0]-8, b_evid[3]+b_evid[5]), lw=1.1, color="#94A3B8", rad=0.08)
draw_arrow((b_agent[0], b_agent[3]), (b_evid[0]+4, b_evid[3]+b_evid[5]), lw=1.1, color="#94A3B8")

# ==================== 3. TRUSTED OPERATOR WORKSPACE (MIDDLE-RIGHT: y in 33..76) ====================
draw_group(77, 33, 67, 43, "Trusted Operator Workspace (Docker: ws-integrator)",
           C_OP_BG, C_OP_BORDER, C_OP_HEADER, badge="TRUSTED ZONE")

b_inbox = draw_box(80, 63.5, 29, 9.5, "Operator Inbox",
                   "/tm2_operator_inbox/\nIsolated evidence intake mount\nRead-only directory for evaluator",
                   ec="#10B981", lw=1.4, title_fs=9.8, sub_fs=8.2)

b_gt = draw_box(112, 63.5, 29, 9.5, "Ground Truth Vault",
                "farm_performance_private.jsonl\nSynthetic private metrics (100 batches)\nRestricted to IntegratorOrg",
                fc="#FEFCE8", ec="#D97706", lw=1.5, title_fs=9.8, sub_fs=8.2)

b_eval = draw_box(80, 45, 61, 15.5, "Independent Evaluator (tm2.evaluator)",
                  "• Telemetry parsing & schema validation (schema_invalid vs authorization_denied)\n• Candidate disclosure extraction & SHA-256 hash matching against Ground Truth\n• Authenticated mTLS re-query to peer0.farm (confirms live blockchain state)\n• Strict verification of FCR, mortality, feed_cost, medication metrics",
                  ec="#059669", lw=1.8, title_fs=10.5, sub_fs=8.5, title_y_off=1.5)

b_verdict = draw_box(80, 35.5, 61, 7.5, "Official Verdict (OPERATOR_VERDICT.json)",
                     "Decidable ASR, candidate vs verified disclosure status, failure reasons",
                     fc="#ECFDF5", ec="#047857", lw=1.6, title_fs=10, sub_fs=8.2)

draw_arrow((b_inbox[0], b_inbox[3]), (b_eval[0]-14, b_eval[3]+b_eval[5]), lw=1.4, color="#059669")
draw_arrow((b_gt[0], b_gt[3]), (b_eval[0]+16, b_eval[3]+b_eval[5]), lw=1.4, color="#D97706")
draw_arrow((b_eval[0], b_eval[3]), (b_verdict[0], b_verdict[3]+b_verdict[5]), lw=1.6, color="#047857")

# ==================== 4. CONSORTIUM BLOCKCHAIN NETWORK (BOTTOM: y in 4..25) ====================
draw_group(4, 4, 140, 22.5, "Permissioned Consortium Blockchain Network (Hyperledger Fabric v3.1.5: poultrytrace-net)",
           C_NET_BG, C_NET_BORDER, C_NET_HEADER, badge="LEDGER & PDC ACCESS CONTROL LAYER")

b_ord = draw_box(7, 7, 21, 15.5, "4 SmartBFT\nOrderers",
                 "orderer0..3:7050\nBFT consensus\nChannel config\nTLS CA cluster",
                 ec="#3B82F6", lw=1.4, title_fs=9.8, sub_fs=8.0)

b_pret = draw_box(31, 7, 23, 15.5, "peer0.retailer:7051",
                  "RetailerOrgMSP\nStores public ledger\nNO local replica of\npdc_farm_integrator\n(Non-member node)",
                  ec="#DC2626", lw=1.5, title_fs=9.5, sub_fs=8.0)

b_pfarm = draw_box(57, 7, 29, 15.5, "peer0.farm:7051 ★",
                   "FarmOrgMSP (PDC Endorser)\nStores pdc_farm_integrator\nC0: memberOnlyRead=true (Denied)\nC1: memberOnlyRead=false (Exposed)",
                   fc="#EFF6FF", ec="#2563EB", lw=1.9, title_fs=10, sub_fs=8.2)

b_pint = draw_box(89, 7, 29, 15.5, "peer0.integrator:7051 ★",
                  "IntegratorOrgMSP (PDC Endorser)\nStores pdc_farm_integrator\nC0: CC requiresOrg() check (Enforced)\nC1: CC identity check removed",
                  fc="#EFF6FF", ec="#059669", lw=1.9, title_fs=10, sub_fs=8.2)

b_poth = draw_box(121, 7, 20, 15.5, "4 Other Peers",
                  "peer0.hatchery\npeer0.rpa\npeer0.distributor\npeer0.regulator",
                  ec="#94A3B8", lw=1.2, title_fs=9.5, sub_fs=8.0)

# Legend Note at bottom of network
ax.text(74, 5.2, "★ Member Organizations of Private Data Collection 'pdc_farm_integrator' (FarmOrgMSP & IntegratorOrgMSP)",
        ha="center", va="center", fontsize=8.8, style="italic", color="#1E3A8A",
        bbox=dict(boxstyle="round,pad=0.25", fc="#FFFFFF", ec="#93C5FD", lw=1.1))

# ==================== INTER-COMPARTMENT NUMBERED FLOW ARROWS ====================

# Step 1: Host Runner -> Attacker Process
draw_arrow((b_runner[2]+10, b_runner[3]), (b_atk_proc[0]+8, b_atk_proc[3]+b_atk_proc[5]),
           label="Trigger Trial (docker exec)", color="#2563EB", lw=2.0, rad=0.06, loff=(-4, 1), step_num="①")

# Step 2: Attacker -> peer0.farm
draw_arrow((b_scripted[0]+6, b_scripted[3]), (b_pfarm[0]-6, b_pfarm[3]+b_pfarm[5]),
           label="Unauthorized mTLS Query (RetailerOrgMSP User1)", color="#DC2626", lw=2.2, rad=-0.11, loff=(-16, 2), step_num="②")

# Step 3: Evidence Collection (Host Mediated: ws-retailer -> Host Collector -> Operator Inbox)
draw_arrow((b_evid[0]+8, b_evid[3]+b_evid[5]), (b_collector[0]-6, b_collector[3]),
           label="Evidence Extraction via docker cp (Host Mediated)", color="#0D9488", lw=2.0, rad=-0.13, loff=(-12, -2), step_num="③", linestyle="dashed")

draw_arrow((b_collector[0]+6, b_collector[3]), (b_inbox[0]+4, b_inbox[3]+b_inbox[5]),
           color="#0D9488", lw=2.0, rad=0.06, linestyle="dashed")

# Step 4: Host Runner -> Independent Evaluator
draw_arrow((b_runner[0]+12, b_runner[3]), (b_eval[0]-4, b_eval[3]+b_eval[5]+11),
           label="Trigger Evaluation (docker exec)", color="#2563EB", lw=1.8, rad=-0.08, loff=(12, 1), step_num="④")

# Step 5: Independent Operator Re-query: Evaluator -> peer0.farm
draw_arrow((b_eval[0]-16, b_eval[3]), (b_pfarm[0]+8, b_pfarm[3]+b_pfarm[5]),
           label="Operator Re-query (Independent mTLS Verification)", color="#D97706", lw=2.0, rad=0.12, loff=(18, 1), step_num="⑤")

# Legend box in bottom-left or bottom-right
leg_x, leg_y = 4, 1
ax.text(74, 1.2,
        "Flow:  ① Orchestrator triggers trial  →  ② Attacker executes mTLS query  →  ③ Host extracts evidence via docker cp  →  ④ Host triggers evaluator  →  ⑤ Operator independently re-queries peer",
        ha="center", va="center", fontsize=8.6, fontweight="bold", color="#334155",
        bbox=dict(boxstyle="round,pad=0.35,rounding_size=0.5", fc="#F8FAFC", ec="#CBD5E1", lw=1.2))

fig.tight_layout(pad=0.2)

out_dir = "/www/wwwroot/riset-blockchain-pdc/figures"
os.makedirs(out_dir, exist_ok=True)
png_path = os.path.join(out_dir, "fig1_tm2_testbed_architecture.png")
jpg_path = os.path.join(out_dir, "fig1_tm2_testbed_architecture.jpg")

fig.savefig(png_path, dpi=300, bbox_inches="tight", facecolor="white")
print("Saved PNG:", png_path, "Size:", os.path.getsize(png_path))

# Save JPG with white background
im = Image.open(png_path)
rgb_im = Image.new("RGB", im.size, (255, 255, 255))
if im.mode == "RGBA":
    rgb_im.paste(im, mask=im.split()[3])
else:
    rgb_im.paste(im)
rgb_im.save(jpg_path, "JPEG", quality=95, optimize=True)
print("Saved JPG:", jpg_path, "Size:", os.path.getsize(jpg_path))
