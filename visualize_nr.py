#!/usr/bin/env python3
"""
visualize_nr.py — 5G NR Simulation Visualization Dashboard

Generates a comprehensive multi-panel visualization of ns-3 5G NR simulation
results. This is the proof-of-concept for the GSoC 2026 project:
  "Enabling 5G NR Examples Visualization" (ns-3 / CTTC 5G-LENA)

Produces:
  1. Network topology (gNB + UE positions, coverage areas)
  2. Per-UE DL throughput over time (with handover event marked)
  3. Per-UE SINR over time (DL)
  4. Cell-aggregate throughput comparison
  5. CDF of throughput across all UEs
  6. Jain's Fairness Index over time
  7. Delay vs. Throughput scatter plot
  8. MCS distribution per cell (estimated from SINR)

Output: figures/nr_dashboard.png  (high-resolution, ready for report)
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.cm as cm
from matplotlib.gridspec import GridSpec
import numpy as np
import pandas as pd
from pathlib import Path

from ns3_nr_parser import (
    load_rlc_stats, load_sinr_stats, load_topology,
    load_flow_monitor, compute_cell_stats, compute_jains_fairness,
)

# ─── Color palette per cell ──────────────────────────────────────────────────
CELL_COLORS = {1: "#E63946", 2: "#457B9D", 3: "#2A9D8F"}
UE_CMAP = matplotlib.colormaps.get_cmap("tab10")

Path("figures").mkdir(exist_ok=True)
data_dir = Path("data")


def load_all():
    dl_rlc  = load_rlc_stats(data_dir / "DlRlcStats.txt")
    ul_rlc  = load_rlc_stats(data_dir / "UlRlcStats.txt")
    dl_sinr = load_sinr_stats(data_dir / "DlPhySinr.txt")
    topo    = load_topology(data_dir / "topology.json")
    flows   = load_flow_monitor(data_dir / "flow_monitor.json")
    return dl_rlc, ul_rlc, dl_sinr, topo, flows


def plot_topology(ax, topo):
    """Panel 1: Network topology with coverage circles."""
    gnbs = topo["gnbs"]
    ues  = topo["ues"]

    # Draw coverage circles
    for gnb in gnbs:
        circle = plt.Circle(
            (gnb["x"], gnb["y"]), 220,
            color=CELL_COLORS[gnb["id"]], alpha=0.08, zorder=0
        )
        ax.add_patch(circle)

    # Plot gNBs
    for gnb in gnbs:
        ax.scatter(gnb["x"], gnb["y"], s=300, marker="^",
                   color=CELL_COLORS[gnb["id"]], zorder=5,
                   edgecolors="black", linewidth=1.5, label=f"gNB {gnb['id']}")
        ax.annotate(f"gNB {gnb['id']}", (gnb["x"], gnb["y"]),
                    textcoords="offset points", xytext=(8, 8),
                    fontsize=9, fontweight="bold",
                    color=CELL_COLORS[gnb["id"]])

    # Plot UEs with connection lines to serving gNB
    gnb_pos = {g["id"]: (g["x"], g["y"]) for g in gnbs}
    for ue in ues:
        gx, gy = gnb_pos[ue["serving_gnb"]]
        ax.plot([ue["x"], gx], [ue["y"], gy],
                color=CELL_COLORS[ue["serving_gnb"]],
                alpha=0.3, linewidth=0.8, zorder=1)
        ax.scatter(ue["x"], ue["y"], s=80, marker="o",
                   color=CELL_COLORS[ue["serving_gnb"]],
                   zorder=4, edgecolors="white", linewidth=0.8)
        ax.annotate(f"UE{ue['id']}", (ue["x"], ue["y"]),
                    textcoords="offset points", xytext=(4, 4),
                    fontsize=7, color="gray")

    ax.set_title("Network Topology", fontweight="bold")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_aspect("equal")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3, linestyle="--")

    # Annotate frequency
    freq = topo["freq_ghz"]
    bw   = topo["bw_mhz"]
    ax.text(0.02, 0.02, f"f = {freq:.1f} GHz | BW = {bw:.0f} MHz",
            transform=ax.transAxes, fontsize=8, color="gray")


def plot_dl_throughput(ax, dl_rlc):
    """Panel 2: Per-UE DL throughput over time."""
    imsis = sorted(dl_rlc["IMSI"].unique())
    for idx, imsi in enumerate(imsis):
        ue_data = dl_rlc[dl_rlc["IMSI"] == imsi]
        cell = ue_data["cellId"].mode()[0]
        ax.plot(ue_data["start_time"], ue_data["DL_throughput_mbps"],
                label=f"UE {imsi}", alpha=0.8, linewidth=1.2,
                color=UE_CMAP(idx / len(imsis)))

    # Mark handover event
    ax.axvline(x=2.5, color="black", linestyle="--",
               linewidth=1.5, alpha=0.7, label="Handover (UE 3)")
    ax.text(2.52, ax.get_ylim()[1] * 0.92 if ax.get_ylim()[1] > 0 else 10,
            "HO", fontsize=8, color="black")

    ax.set_title("DL Throughput per UE", fontweight="bold")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Throughput [Mbps]")
    ax.legend(loc="upper right", fontsize=6, ncol=2)
    ax.grid(True, alpha=0.3)


def plot_sinr(ax, dl_sinr):
    """Panel 3: Per-UE DL SINR over time."""
    imsis = sorted(dl_sinr["IMSI"].unique())
    for idx, imsi in enumerate(imsis):
        ue_data = dl_sinr[dl_sinr["IMSI"] == imsi]
        ax.plot(ue_data["time"], ue_data["sinr_dB"],
                alpha=0.6, linewidth=0.8,
                color=UE_CMAP(idx / len(imsis)))

    ax.axhline(y=0, color="red", linestyle=":", linewidth=1, alpha=0.5, label="SINR = 0 dB")
    ax.axvline(x=2.5, color="black", linestyle="--", linewidth=1.5, alpha=0.7)
    ax.set_title("DL SINR per UE", fontweight="bold")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("SINR [dB]")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


def plot_cell_aggregate(ax, dl_rlc):
    """Panel 4: Per-cell aggregate throughput over time."""
    cell_stats = compute_cell_stats(dl_rlc)
    for cell_id, color in CELL_COLORS.items():
        cdata = cell_stats[cell_stats["cellId"] == cell_id]
        if cdata.empty:
            continue
        ax.plot(cdata["start_time"], cdata["total_tput_mbps"],
                label=f"Cell {cell_id}", color=color, linewidth=2)

    ax.set_title("Cell-Aggregate DL Throughput", fontweight="bold")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Aggregate Throughput [Mbps]")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)


def plot_cdf(ax, dl_rlc):
    """Panel 5: CDF of DL throughput across UEs."""
    all_tput = dl_rlc["DL_throughput_mbps"].values
    all_tput_sorted = np.sort(all_tput)
    cdf = np.arange(1, len(all_tput_sorted) + 1) / len(all_tput_sorted)

    # Per-cell CDFs
    for cell_id, color in CELL_COLORS.items():
        cell_data = dl_rlc[dl_rlc["cellId"] == cell_id]["DL_throughput_mbps"].values
        if len(cell_data) == 0:
            continue
        x = np.sort(cell_data)
        y = np.arange(1, len(x)+1) / len(x)
        ax.plot(x, y, color=color, alpha=0.6, linewidth=1.5,
                label=f"Cell {cell_id}")

    ax.plot(all_tput_sorted, cdf, color="black",
            linewidth=2.5, label="Overall", linestyle="--")

    # Annotate median
    median = np.percentile(all_tput, 50)
    ax.axvline(x=median, color="gray", linestyle=":", linewidth=1)
    ax.text(median * 1.05, 0.5, f"P50={median:.0f}", fontsize=8, color="gray")

    ax.set_title("CDF of DL Throughput", fontweight="bold")
    ax.set_xlabel("Throughput [Mbps]")
    ax.set_ylabel("CDF")
    ax.set_ylim(0, 1)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


def plot_fairness(ax, dl_rlc):
    """Panel 6: Jain's Fairness Index over time."""
    jfi_series = compute_jains_fairness(dl_rlc)
    ax.plot(jfi_series.index, jfi_series.values,
            color="#6A4C93", linewidth=2, label="JFI")
    ax.fill_between(jfi_series.index, jfi_series.values,
                    alpha=0.15, color="#6A4C93")
    ax.axhline(y=1.0, color="green", linestyle="--", linewidth=1,
               alpha=0.7, label="Perfect fairness")
    ax.axvline(x=2.5, color="black", linestyle="--", linewidth=1.5, alpha=0.7)
    ax.set_ylim(0, 1.1)
    ax.set_title("Jain's Fairness Index", fontweight="bold")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("JFI")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


def plot_delay_tput_scatter(ax, dl_rlc):
    """Panel 7: Delay vs. Throughput scatter (per UE, averaged)."""
    ue_avg = dl_rlc.groupby("IMSI").agg(
        mean_tput=("DL_throughput_mbps", "mean"),
        mean_delay=("delay_ms", "mean"),
        cell=("cellId", lambda x: x.mode()[0]),
    ).reset_index()

    for _, row in ue_avg.iterrows():
        ax.scatter(row["mean_tput"], row["mean_delay"],
                   s=120, color=CELL_COLORS.get(row["cell"], "gray"),
                   edgecolors="white", linewidth=0.8, zorder=3)
        ax.annotate(f"UE{int(row['IMSI'])}", (row["mean_tput"], row["mean_delay"]),
                    textcoords="offset points", xytext=(4, 3), fontsize=7)

    patches = [mpatches.Patch(color=c, label=f"Cell {k}") for k, c in CELL_COLORS.items()]
    ax.legend(handles=patches, fontsize=8)
    ax.set_title("Delay vs. Throughput (avg/UE)", fontweight="bold")
    ax.set_xlabel("Mean DL Throughput [Mbps]")
    ax.set_ylabel("Mean Delay [ms]")
    ax.grid(True, alpha=0.3)


def plot_mcs_distribution(ax, dl_sinr):
    """Panel 8: MCS distribution per cell (estimated from SINR)."""
    for cell_id, color in CELL_COLORS.items():
        cell_data = dl_sinr[dl_sinr["cellId"] == cell_id]["mcs"]
        if cell_data.empty:
            continue
        mcs_counts = cell_data.value_counts().sort_index()
        mcs_pct = mcs_counts / mcs_counts.sum() * 100
        ax.bar(mcs_counts.index + (cell_id - 2) * 0.25,
               mcs_pct.values, width=0.25,
               color=color, alpha=0.8, label=f"Cell {cell_id}")

    ax.set_title("Estimated MCS Distribution", fontweight="bold")
    ax.set_xlabel("MCS Index")
    ax.set_ylabel("Frequency [%]")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")


def build_dashboard():
    """Build full 8-panel dashboard."""
    dl_rlc, ul_rlc, dl_sinr, topo, flows = load_all()

    fig = plt.figure(figsize=(20, 22))
    fig.suptitle(
        "5G NR Simulation Dashboard  ·  ns-3 + CTTC 5G-LENA\n"
        f"3 gNBs · 10 UEs · 5 s · 3.5 GHz · 100 MHz BW",
        fontsize=16, fontweight="bold", y=0.98
    )

    gs = GridSpec(4, 2, figure=fig, hspace=0.45, wspace=0.35)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, 0])
    ax4 = fig.add_subplot(gs[1, 1])
    ax5 = fig.add_subplot(gs[2, 0])
    ax6 = fig.add_subplot(gs[2, 1])
    ax7 = fig.add_subplot(gs[3, 0])
    ax8 = fig.add_subplot(gs[3, 1])

    print("Plotting topology...")
    plot_topology(ax1, topo)
    print("Plotting DL throughput...")
    plot_dl_throughput(ax2, dl_rlc)
    print("Plotting SINR...")
    plot_sinr(ax3, dl_sinr)
    print("Plotting cell aggregate...")
    plot_cell_aggregate(ax4, dl_rlc)
    print("Plotting CDF...")
    plot_cdf(ax5, dl_rlc)
    print("Plotting fairness...")
    plot_fairness(ax6, dl_rlc)
    print("Plotting delay vs throughput...")
    plot_delay_tput_scatter(ax7, dl_rlc)
    print("Plotting MCS distribution...")
    plot_mcs_distribution(ax8, dl_sinr)

    output = "figures/nr_dashboard.png"
    fig.savefig(output, dpi=150, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    print(f"\n✓ Dashboard saved → {output}")
    plt.close(fig)


if __name__ == "__main__":
    build_dashboard()
