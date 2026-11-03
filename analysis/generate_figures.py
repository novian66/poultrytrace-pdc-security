#!/usr/bin/env python3
"""Generate publication-quality academic charts for TM2 PDC Security Evaluation (Decoupled & Consistent Metrics)."""
import os
import matplotlib.pyplot as plt
import numpy as np

# Configure matplotlib for academic publication
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['DejaVu Sans', 'Arial', 'Helvetica'],
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 11,
    'ytick.labelsize': 11,
    'legend.fontsize': 10.5,
    'figure.titlesize': 14,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight'
})

OUT_DIRS = [
    "/www/wwwroot/riset-blockchain-pdc/figures",
    "/root/.gemini/antigravity-cli/brain/4365535c-86e9-4982-99cb-ba3281252ff9/figures"
]
for d in OUT_DIRS:
    os.makedirs(d, exist_ok=True)

# ----------------------------------------------------------------------
# FIGURE 1: Decoupled Evaluation: Disclosure Rate (ASR) & Verdict Distribution
# ----------------------------------------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

categories = ['C0\nScripted', 'C0\nAgentic AI', 'C1\nScripted', 'C1\nAgentic AI']
x = np.arange(len(categories))

# (a) Factual Disclosure Attack Success Rate (Factual ASR %)
asr_values = [0.0, 0.0, 100.0, 30.0]
asr_colors = ['#2ca02c', '#2ca02c', '#d62728', '#e65100']

bars1 = ax1.bar(x, asr_values, color=asr_colors, width=0.55, edgecolor='black', linewidth=1.2)
ax1.set_ylabel('Verified Private Disclosure Rate (%)\n[Factual ASR]', fontweight='bold')
ax1.set_title('(a) Keberhasilan Pengungkapan Data Privat (Factual ASR)', fontweight='bold', pad=12)
ax1.set_xticks(x)
ax1.set_xticklabels(categories, fontweight='bold')
ax1.set_ylim(0, 120)
ax1.grid(axis='y', linestyle='--', alpha=0.5)

# Add text labels on bars with formal decidable ASR notes
ax1.text(bars1[0].get_x() + bars1[0].get_width()/2., 4, '0.0%\n(0/30)', ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#1b5e20')
ax1.text(bars1[1].get_x() + bars1[1].get_width()/2., 4, '0.0% (0/30)\n[Decidable: N/A*]', ha='center', va='bottom', fontsize=9, fontweight='bold', color='#1b5e20')
ax1.text(bars1[2].get_x() + bars1[2].get_width()/2., 103, '100.0%\n(30/30)', ha='center', va='bottom', fontsize=9.5, fontweight='bold', color='#b71c1c')
ax1.text(bars1[3].get_x() + bars1[3].get_width()/2., 33, '30.0% (9/30)\n[Decidable: N/A*]', ha='center', va='bottom', fontsize=9, fontweight='bold', color='#bf360c')

# (b) Breakdown of Decoupled Operator Verdicts (Stacked Bar)
success_counts = np.array([0, 0, 30, 9])
defended_counts = np.array([30, 9, 0, 0])
inconclusive_counts = np.array([0, 21, 0, 21])

width = 0.55
p1 = ax2.bar(x, defended_counts, width, label='Defended (Akses Ditolak PDC)', color='#2ca02c', edgecolor='black', linewidth=1.2)
p2 = ax2.bar(x, success_counts, width, bottom=defended_counts, label='Success (Data Privat Terbocorkan)', color='#d62728', edgecolor='black', linewidth=1.2)
p3 = ax2.bar(x, inconclusive_counts, width, bottom=defended_counts+success_counts, label='Inconclusive (Terhenti Sebelum Kueri)', color='#7f7f7f', edgecolor='black', linewidth=1.2)

ax2.set_ylabel('Jumlah Trial Terdaftar (n = 30 per grup)', fontweight='bold')
ax2.set_title('(b) Distribusi Status Pengungkapan (Decoupled Evaluator)', fontweight='bold', pad=12)
ax2.set_xticks(x)
ax2.set_xticklabels(categories, fontweight='bold')
ax2.set_ylim(0, 38)
ax2.legend(loc='upper right', framealpha=0.95)
ax2.grid(axis='y', linestyle='--', alpha=0.5)

# Value annotations on stacked bars
for i in range(len(categories)):
    if defended_counts[i] > 0:
        ax2.text(i, defended_counts[i]/2, f'{defended_counts[i]}', ha='center', va='center', color='white', fontweight='bold', fontsize=11)
    if success_counts[i] > 0:
        ax2.text(i, defended_counts[i] + success_counts[i]/2, f'{success_counts[i]}', ha='center', va='center', color='white', fontweight='bold', fontsize=11)
    if inconclusive_counts[i] > 0:
        ax2.text(i, defended_counts[i] + success_counts[i] + inconclusive_counts[i]/2, f'{inconclusive_counts[i]}', ha='center', va='center', color='white', fontweight='bold', fontsize=11)

plt.tight_layout()
for d in OUT_DIRS:
    plt.savefig(os.path.join(d, "fig1_tm2_asr_distribution.png"))
plt.close()

# ----------------------------------------------------------------------
# FIGURE 2: Operational Efficiency & Latency Comparison
# ----------------------------------------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

labels = ['C0 Scripted', 'C0 Agentic AI', 'C1 Scripted', 'C1 Agentic AI']
x = np.arange(len(labels))
w = 0.35

mean_tool_calls = [7.00, 2.83, 7.00, 2.73]
machine_inspections = [2.00, 2.13, 2.00, 2.03]

b1 = ax1.bar(x - w/2, mean_tool_calls, w, label='Rata-rata Langkah Tool', color='#1f77b4', edgecolor='black')
b2 = ax1.bar(x + w/2, machine_inspections, w, label='Rata-rata Inspeksi Mesin', color='#ff7f0e', edgecolor='black')

ax1.set_ylabel('Jumlah Langkah per Trial', fontweight='bold')
ax1.set_title('(a) Beban Langkah Interaksi dan Inspeksi Mesin', fontweight='bold', pad=12)
ax1.set_xticks(x)
ax1.set_xticklabels(labels, fontweight='bold', rotation=10)
ax1.set_ylim(0, 9)
ax1.legend(loc='upper right')
ax1.grid(axis='y', linestyle='--', alpha=0.5)

for bar in b1:
    h = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2., h + 0.15, f'{h:.2f}', ha='center', va='bottom', fontsize=9.5, fontweight='bold')
for bar in b2:
    h = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2., h + 0.15, f'{h:.2f}', ha='center', va='bottom', fontsize=9.5, fontweight='bold')

median_durations = [0.291, 14.971, 0.307, 14.061]
colors_lat = ['#2ca02c', '#9467bd', '#d62728', '#8c564b']

b_lat = ax2.bar(x, median_durations, width=0.5, color=colors_lat, edgecolor='black', linewidth=1.2)
ax2.set_ylabel('Median Durasi Eksekusi (Detik - Skala Logaritmik)', fontweight='bold')
ax2.set_title('(b) Perbandingan Kecepatan Eksekusi (Latensi)', fontweight='bold', pad=12)
ax2.set_xticks(x)
ax2.set_xticklabels(labels, fontweight='bold', rotation=10)
ax2.set_yscale('log')
ax2.set_ylim(0.08, 40)
ax2.grid(axis='y', linestyle='--', alpha=0.5)

for bar, val in zip(b_lat, median_durations):
    ax2.text(bar.get_x() + bar.get_width()/2., val * 1.25, f'{val:.3f} s', ha='center', va='bottom', fontsize=10, fontweight='bold')

plt.tight_layout()
for d in OUT_DIRS:
    plt.savefig(os.path.join(d, "fig2_tm2_operational_metrics.png"))
plt.close()

# ----------------------------------------------------------------------
# FIGURE 3: Agentic AI Action Breakdown & Token Utilization
# ----------------------------------------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

actions = ['inspect_peer_config\n(Inspeksi Simpul / Host)', 'read_private\n(Kueri Fabric PDC)', 'read_public\n(Kueri Ledger Publik)']
counts = [125, 30, 12]
colors_pie = ['#3366cc', '#dc3912', '#ff9900']
explode = (0.05, 0.05, 0.05)

wedges, texts, autotexts = ax1.pie(counts, explode=explode, labels=actions, autopct='%1.1f%%',
                                  startangle=140, colors=colors_pie, textprops=dict(fontweight='bold'))
for at in autotexts:
    at.set_color('white')
    at.set_fontsize(10)
ax1.set_title('(a) Distribusi Pemilihan Tool oleh Bounded AI (n = 167 aksi)', fontweight='bold', pad=12)

# Token counts for the 60 main registered trials:
token_groups = ['Kondisi C0\n(30 Trials LLM Utama)', 'Kondisi C1\n(30 Trials LLM Utama)']
prompt_toks = np.array([35031, 33783])
completion_toks = np.array([3954, 3631])

w = 0.45
p_bar1 = ax2.bar(token_groups, prompt_toks, w, label='Prompt Tokens (Input Observasi)', color='#3b528b', edgecolor='black')
p_bar2 = ax2.bar(token_groups, completion_toks, w, bottom=prompt_toks, label='Completion Tokens (Output Aksi)', color='#5dc863', edgecolor='black')

ax2.set_ylabel('Total Token Model (Qwen2.5:3B)', fontweight='bold')
ax2.set_title('(b) Utilisasi Token Komputasi 60 Trial Utama (Total: 76.399)', fontweight='bold', pad=12)
ax2.set_ylim(0, 46000)
ax2.legend(loc='upper right')
ax2.grid(axis='y', linestyle='--', alpha=0.5)

for i, (pt, ct) in enumerate(zip(prompt_toks, completion_toks)):
    total = pt + ct
    ax2.text(i, total + 800, f'Total: {total:,}\n(Prompt: {pt:,} | Compl: {ct:,})', ha='center', va='bottom', fontsize=9.5, fontweight='bold')

plt.tight_layout()
for d in OUT_DIRS:
    plt.savefig(os.path.join(d, "fig3_tm2_ai_action_and_tokens.png"))
plt.close()

print("Publication figures successfully re-generated.")
