#!/usr/bin/env python3
"""
animate_handover.py — Animated Handover & SINR Visualization

Creates an animated GIF showing:
  - UE positions moving over time
  - SINR color-coded per UE
  - Handover event (UE 3 switching from cell 1 → cell 2)
  - Real-time throughput bar chart

This demonstrates the kind of dynamic visualization the GSoC project
would produce as a Jupyter widget or standalone animation.

Output: figures/handover_animation.gif
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.patches as mpatches
import numpy as np
import json
from pathlib import Path

from ns3_nr_parser import load_rlc_stats, load_sinr_stats, load_topology

CELL_COLORS = {1: "#E63946", 2: "#457B9D", 3: "#2A9D8F"}
data_dir = Path("data")
Path("figures").mkdir(exist_ok=True)


def build_animation():
    dl_rlc  = load_rlc_stats(data_dir / "DlRlcStats.txt")
    dl_sinr = load_sinr_stats(data_dir / "DlPhySinr.txt")
    topo    = load_topology(data_dir / "topology.json")

    gnb_pos = {g["id"]: (g["x"], g["y"]) for g in topo["gnbs"]}
    ue_base_pos = {u["id"]: (u["x"], u["y"]) for u in topo["ues"]}

    sim_time = topo["sim_time"]
    time_steps = np.arange(0, sim_time, 0.1)
    n_ues = topo["n_ue"]
    n_gnbs = topo["n_gnb"]

    fig, (ax_topo, ax_bar) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor("#1a1a2e")

    def style_ax(ax):
        ax.set_facecolor("#16213e")
        ax.tick_params(colors="white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#0f3460")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.title.set_color("white")

    style_ax(ax_topo)
    style_ax(ax_bar)

    time_text = fig.text(0.5, 0.96, "", ha="center", color="white",
                         fontsize=13, fontweight="bold")

    def get_ue_pos(ue_id, t):
        """Simulate slow UE movement."""
        bx, by = ue_base_pos[ue_id]
        speed = 3.0   # m/s (pedestrian)
        angle = np.pi / 4 * ue_id  # each UE moves in different direction
        dx = speed * t * np.cos(angle)
        dy = speed * t * np.sin(angle)
        # UE 3 moves toward cell 2 gNB
        if ue_id == 3:
            gx, gy = gnb_pos[2]
            frac = min(t / sim_time, 1.0)
            dx = (gx - bx) * frac * 0.5
            dy = (gy - by) * frac * 0.5
        return bx + dx, by + dy

    def get_sinr_at(ue_id, t):
        t_idx = dl_sinr["time"].sub(t).abs().idxmin()
        row = dl_sinr[(dl_sinr["IMSI"] == ue_id) &
                      (dl_sinr.index <= t_idx)].tail(1)
        if row.empty:
            return 10.0
        return float(row["sinr_dB"].values[0])

    def get_tput_at(ue_id, t):
        row = dl_rlc[(dl_rlc["IMSI"] == ue_id) &
                     (dl_rlc["start_time"] <= t) &
                     (dl_rlc["end_time"] > t)]
        if row.empty:
            return 0.0
        return float(row["DL_throughput_mbps"].values[0])

    def draw_frame(t):
        ax_topo.clear()
        ax_bar.clear()
        style_ax(ax_topo)
        style_ax(ax_bar)

        # ── Topology panel ──────────────────────────────────────────
        # Coverage circles
        for gnb_id, (gx, gy) in gnb_pos.items():
            circle = plt.Circle((gx, gy), 220,
                                 color=CELL_COLORS[gnb_id], alpha=0.12)
            ax_topo.add_patch(circle)
            ax_topo.scatter(gx, gy, s=300, marker="^",
                            color=CELL_COLORS[gnb_id],
                            edgecolors="white", linewidth=1.5, zorder=5)
            ax_topo.annotate(f"gNB {gnb_id}", (gx, gy),
                             textcoords="offset points", xytext=(8, 8),
                             fontsize=9, fontweight="bold",
                             color=CELL_COLORS[gnb_id])

        # UEs with SINR-based color intensity
        for ue_id in range(1, n_ues + 1):
            ux, uy = get_ue_pos(ue_id, t)
            sinr = get_sinr_at(ue_id, t)

            # Determine serving cell
            cell = ((ue_id - 1) % n_gnbs) + 1
            if ue_id == 3 and t >= 2.5:
                cell = 2

            # SINR → color intensity
            sinr_norm = np.clip((sinr + 5) / 35, 0, 1)
            color = CELL_COLORS[cell]

            ax_topo.scatter(ux, uy, s=100, color=color,
                            alpha=0.5 + 0.5 * sinr_norm,
                            edgecolors="white", linewidth=0.8, zorder=4)
            ax_topo.annotate(f"{ue_id}", (ux, uy),
                             textcoords="offset points", xytext=(4, 3),
                             fontsize=7, color="white")

            # Draw connection line to serving gNB
            gx, gy = gnb_pos[cell]
            ax_topo.plot([ux, gx], [uy, gy],
                         color=color, alpha=0.3, linewidth=0.8)

        # Mark handover
        if t >= 2.5:
            ax_topo.text(0.02, 0.06, "⚡ Handover: UE 3 → Cell 2",
                         transform=ax_topo.transAxes,
                         fontsize=9, color="#FFD166", fontweight="bold")

        ax_topo.set_xlim(-300, 850)
        ax_topo.set_ylim(-300, 800)
        ax_topo.set_title("Network Topology (live)", color="white", fontweight="bold")
        ax_topo.set_xlabel("x [m]")
        ax_topo.set_ylabel("y [m]")

        # ── Throughput bar chart ─────────────────────────────────────
        ue_ids  = list(range(1, n_ues + 1))
        tputs   = [get_tput_at(uid, t) for uid in ue_ids]
        cells   = [((uid-1) % n_gnbs)+1 for uid in ue_ids]
        # Handover
        for i, uid in enumerate(ue_ids):
            if uid == 3 and t >= 2.5:
                cells[i] = 2
        bar_colors = [CELL_COLORS[c] for c in cells]

        bars = ax_bar.bar(ue_ids, tputs, color=bar_colors, alpha=0.85,
                          edgecolor="white", linewidth=0.5)
        ax_bar.set_ylim(0, 200)
        ax_bar.set_title("DL Throughput per UE", color="white", fontweight="bold")
        ax_bar.set_xlabel("UE ID")
        ax_bar.set_ylabel("Throughput [Mbps]")
        ax_bar.set_xticks(ue_ids)

        # Value labels on bars
        for bar, tput in zip(bars, tputs):
            if tput > 5:
                ax_bar.text(bar.get_x() + bar.get_width()/2,
                            bar.get_height() + 2,
                            f"{tput:.0f}", ha="center", va="bottom",
                            fontsize=7, color="white")

        patches = [mpatches.Patch(color=c, label=f"Cell {k}")
                   for k, c in CELL_COLORS.items()]
        ax_bar.legend(handles=patches, fontsize=8,
                      facecolor="#16213e", labelcolor="white")

        time_text.set_text(f"Simulation Time: {t:.1f} s")
        return []

    # Build animation
    print(f"Building animation ({len(time_steps)} frames)...")
    anim = animation.FuncAnimation(
        fig, draw_frame, frames=time_steps,
        interval=100, blit=False, repeat=False
    )

    output = "figures/handover_animation.gif"
    writer = animation.PillowWriter(fps=10)
    anim.save(output, writer=writer, dpi=80)
    print(f"✓ Animation saved → {output}")
    plt.close(fig)


if __name__ == "__main__":
    build_animation()
