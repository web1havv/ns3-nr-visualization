#!/usr/bin/env python3
"""
Task 1: Flow-ID / UE Filter Engine
─────────────────────────────────
Mentor Biljana Bojovic explicitly requested (March 4, 2026 mailing list):
  "possibility of using such a visualizer for debugging/inspecting,
   generation of specific logs/traces based on flow id/packet id"

This module provides a filtering API over ns-3 NR trace data so users can
isolate any individual UE, flow, or cell for deep inspection.

Usage:
  filter = NRFlowFilter(dl_rlc, dl_sinr)
  ue3_data = filter.by_ue(3)
  cell2_data = filter.by_cell(2)
  handover_window = filter.by_time(2.3, 2.7)
  combined = filter.by_ue(3).by_time(2.3, 2.7).get()
"""

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from ns3_nr_parser import load_rlc_stats, load_sinr_stats


class NRFlowFilter:
    """
    Chainable filter for ns-3 NR trace data.
    Supports filtering by UE (IMSI), Cell ID, RNTI, LCID, and time window.
    """

    def __init__(self, rlc_df: pd.DataFrame, sinr_df: pd.DataFrame = None):
        self._rlc  = rlc_df.copy()
        self._sinr = sinr_df.copy() if sinr_df is not None else pd.DataFrame()

    def by_ue(self, imsi: int) -> "NRFlowFilter":
        """Filter to a single UE by IMSI."""
        f = NRFlowFilter(self._rlc[self._rlc["IMSI"] == imsi],
                         self._sinr[self._sinr["IMSI"] == imsi] if not self._sinr.empty else self._sinr)
        return f

    def by_cell(self, cell_id: int) -> "NRFlowFilter":
        """Filter to a single cell."""
        f = NRFlowFilter(self._rlc[self._rlc["cellId"] == cell_id],
                         self._sinr[self._sinr["cellId"] == cell_id] if not self._sinr.empty else self._sinr)
        return f

    def by_time(self, t_start: float, t_end: float) -> "NRFlowFilter":
        """Filter to a specific time window [t_start, t_end] seconds."""
        rlc  = self._rlc[(self._rlc["start_time"] >= t_start) & (self._rlc["end_time"] <= t_end)]
        sinr = self._sinr[(self._sinr["time"] >= t_start) & (self._sinr["time"] <= t_end)] \
               if not self._sinr.empty else self._sinr
        return NRFlowFilter(rlc, sinr)

    def by_lcid(self, lcid: int) -> "NRFlowFilter":
        """Filter to a specific Logical Channel ID (bearer)."""
        return NRFlowFilter(self._rlc[self._rlc["LCID"] == lcid], self._sinr)

    def get_rlc(self) -> pd.DataFrame:
        return self._rlc.copy()

    def get_sinr(self) -> pd.DataFrame:
        return self._sinr.copy()

    def summary(self) -> dict:
        """Return a summary dict for the filtered data."""
        if self._rlc.empty:
            return {"warning": "No data matches the filter"}
        return {
            "ues":          sorted(self._rlc["IMSI"].unique().tolist()),
            "cells":        sorted(self._rlc["cellId"].unique().tolist()),
            "time_range":   [self._rlc["start_time"].min(), self._rlc["end_time"].max()],
            "mean_dl_tput": round(self._rlc["DL_throughput_mbps"].mean(), 2),
            "mean_delay_ms": round(self._rlc["delay_ms"].mean(), 3),
            "mean_loss_pct": round(self._rlc["packet_loss_pct"].mean(), 3),
            "rows":          len(self._rlc),
        }

    def plot_ue_deep_dive(self, imsi: int, output: str = None):
        """
        Generate a per-UE deep-dive plot with:
          - Throughput timeline
          - SINR timeline
          - Delay timeline
          - Packet loss timeline
        """
        ue_rlc  = self._rlc[self._rlc["IMSI"] == imsi]
        ue_sinr = self._sinr[self._sinr["IMSI"] == imsi] if not self._sinr.empty else pd.DataFrame()

        fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
        fig.suptitle(f"Deep-Dive: UE {imsi} (IMSI={imsi})", fontweight="bold", fontsize=14)

        # Throughput
        axes[0].plot(ue_rlc["start_time"], ue_rlc["DL_throughput_mbps"],
                     color="#E63946", linewidth=2)
        axes[0].set_ylabel("DL Tput [Mbps]")
        axes[0].grid(True, alpha=0.3)
        axes[0].fill_between(ue_rlc["start_time"], ue_rlc["DL_throughput_mbps"],
                              alpha=0.15, color="#E63946")

        # SINR
        if not ue_sinr.empty:
            axes[1].plot(ue_sinr["time"], ue_sinr["sinr_dB"],
                         color="#457B9D", linewidth=1.5)
            axes[1].axhline(y=0, color="red", linestyle=":", alpha=0.5)
            axes[1].set_ylabel("SINR [dB]")
            axes[1].grid(True, alpha=0.3)

        # Delay
        axes[2].plot(ue_rlc["start_time"], ue_rlc["delay_ms"],
                     color="#2A9D8F", linewidth=2)
        axes[2].set_ylabel("Delay [ms]")
        axes[2].grid(True, alpha=0.3)

        # Packet loss
        axes[3].bar(ue_rlc["start_time"], ue_rlc["packet_loss_pct"],
                    width=0.08, color="#E9C46A", alpha=0.8)
        axes[3].set_ylabel("Loss [%]")
        axes[3].set_xlabel("Time [s]")
        axes[3].grid(True, alpha=0.3)

        plt.tight_layout()
        out = output or f"figures/ue{imsi}_deepdive.png"
        fig.savefig(out, dpi=120, bbox_inches="tight")
        plt.close(fig)
        print(f"  ✓ Deep-dive plot → {out}")
        return out


def demo():
    data_dir = Path("data")
    dl_rlc  = load_rlc_stats(data_dir / "DlRlcStats.txt")
    dl_sinr = load_sinr_stats(data_dir / "DlPhySinr.txt")

    filt = NRFlowFilter(dl_rlc, dl_sinr)

    print("=== Flow Filter Demo ===")

    # UE-level filter
    ue3 = filt.by_ue(3)
    print(f"\nUE 3 overall: {ue3.summary()}")

    # Time window around handover
    ho_window = filt.by_ue(3).by_time(2.0, 3.0)
    print(f"UE 3 handover window [2.0–3.0 s]: {ho_window.summary()}")

    # Cell-level filter
    cell1 = filt.by_cell(1)
    print(f"\nCell 1 overall: {cell1.summary()}")

    # Generate deep-dive plots for all UEs
    print("\nGenerating UE deep-dive plots...")
    Path("figures").mkdir(exist_ok=True)
    for imsi in [1, 3, 7]:
        filt.plot_ue_deep_dive(imsi)


if __name__ == "__main__":
    demo()
