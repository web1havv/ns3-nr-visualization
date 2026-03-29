#!/usr/bin/env python3
"""
Task 16: Real-Time Dashboard via File-Watch (Matplotlib Animation)
──────────────────────────────────────────────────────────────────
Mentor Biljana Bojovic (CTTC/ns-3-nr lead) stated explicitly:
  "The ideal solution would allow monitoring while the simulation is
   still running, not only post-processing."

This module implements a file-watch based real-time dashboard:
  1. Polls the trace file directory every POLL_MS milliseconds
  2. Detects new rows appended by ns-3's FlushData() calls
  3. Updates a live matplotlib figure via FuncAnimation
  4. Can be used with a running ns-3 simulation in a parallel terminal

Usage:
  # In one terminal: run ns-3 (appends to trace files)
  # In another terminal: python realtime_dashboard.py --watch data/

  The static mode (default when data already exists) shows what the
  real-time view would look like, outputting a 30-frame GIF.
"""

import time
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from ns3_nr_parser import load_rlc_stats, load_sinr_stats


POLL_INTERVAL_MS = 500  # Polling interval in milliseconds
N_FRAMES         = 30   # Number of frames for static preview


def _rolling_window(df: pd.DataFrame, t_max: float,
                    window: float = 1.0) -> pd.DataFrame:
    """Return rows within the last `window` seconds of `t_max`."""
    return df[df["end_time"] >= t_max - window]


class RealTimeDashboard:
    """
    Real-time NR KPI dashboard.
    In static mode: renders N_FRAMES to produce a preview GIF.
    In watch mode : polls trace files and updates live.
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self._last_dl_mtime = 0
        self._last_sinr_mtime = 0
        self._dl   = pd.DataFrame()
        self._sinr  = pd.DataFrame()
        self._load_data()

        self.fig, self.axes = plt.subplots(2, 2, figsize=(12, 8))
        self.fig.suptitle("ns-3 NR Real-Time Dashboard (file-watch mode)",
                          fontweight="bold", fontsize=12)
        plt.tight_layout(rect=[0, 0, 1, 0.95])

    def _load_data(self):
        dl_path   = self.data_dir / "DlRlcStats.txt"
        sinr_path = self.data_dir / "DlPhySinr.txt"

        if dl_path.exists():
            new_mtime = dl_path.stat().st_mtime
            if new_mtime != self._last_dl_mtime:
                self._dl = load_rlc_stats(dl_path)
                self._last_dl_mtime = new_mtime

        if sinr_path.exists():
            new_mtime = sinr_path.stat().st_mtime
            if new_mtime != self._last_sinr_mtime:
                self._sinr = load_sinr_stats(sinr_path)
                self._last_sinr_mtime = new_mtime

    def _update(self, frame: int):
        """Called by FuncAnimation for each frame."""
        # Simulate data being "streamed" by slicing up to t = frame * dt
        dt = self._dl["end_time"].max() / N_FRAMES if len(self._dl) > 0 else 1
        t_now = (frame + 1) * dt

        dl_now   = self._dl[self._dl["end_time"] <= t_now]
        sinr_now = self._sinr[self._sinr["time"] <= t_now]

        for ax in self.axes.flat:
            ax.cla()

        # Panel 1: Cumulative throughput per UE (line chart)
        ax = self.axes[0, 0]
        if not dl_now.empty:
            for imsi, grp in dl_now.groupby("IMSI"):
                ax.plot(grp["end_time"], grp["DL_throughput_mbps"],
                        label=f"UE{imsi}", alpha=0.8, linewidth=1.5)
        ax.set_title(f"Live DL Throughput [t={t_now:.2f}s]")
        ax.set_xlabel("Time [s]"); ax.set_ylabel("Throughput [Mbps]")
        ax.legend(fontsize=7, ncol=2)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, self._dl["end_time"].max() if not self._dl.empty else 5)

        # Panel 2: SINR over time per UE (heatmap-style scatter)
        ax = self.axes[0, 1]
        if not sinr_now.empty:
            sc = ax.scatter(sinr_now["time"], sinr_now["IMSI"],
                            c=sinr_now["sinr_dB"], cmap="RdYlGn",
                            s=15, vmin=0, vmax=30)
            self.fig.colorbar(sc, ax=ax, label="SINR [dB]")
        ax.set_title("Live SINR per UE")
        ax.set_xlabel("Time [s]"); ax.set_ylabel("UE (IMSI)")
        ax.grid(True, alpha=0.3)

        # Panel 3: Cell-aggregate throughput bar
        ax = self.axes[1, 0]
        if not dl_now.empty:
            cell_tput = (dl_now.groupby("cellId")["DL_throughput_mbps"]
                         .mean().reset_index())
            ax.bar(cell_tput["cellId"].astype(str),
                   cell_tput["DL_throughput_mbps"],
                   color=["#E63946", "#457B9D", "#2A9D8F"])
        ax.set_title("Cell-Aggregate Throughput")
        ax.set_xlabel("Cell ID"); ax.set_ylabel("Mean Tput [Mbps]")
        ax.grid(True, alpha=0.3)

        # Panel 4: Delay histogram (live)
        ax = self.axes[1, 1]
        if not dl_now.empty:
            ax.hist(dl_now["delay_ms"], bins=30, color="#E9C46A",
                    edgecolor="k", alpha=0.8)
        ax.set_title("Live Delay Distribution")
        ax.set_xlabel("Delay [ms]"); ax.set_ylabel("Count")
        ax.grid(True, alpha=0.3)

        return self.axes.flat

    def render_preview_gif(self, output: str = "figures/realtime_preview.gif"):
        """Save a static preview GIF showing what the real-time dashboard looks like."""
        Path("figures").mkdir(exist_ok=True)
        anim = animation.FuncAnimation(
            self.fig, self._update, frames=N_FRAMES,
            interval=100, blit=False,
        )
        anim.save(output, writer="pillow", fps=8, dpi=90)
        plt.close(self.fig)
        print(f"  ✓ Real-time preview GIF → {output}")

    def watch(self, poll_ms: int = POLL_INTERVAL_MS):
        """Poll trace files and update live (blocks; run in terminal)."""
        plt.ion()
        print(f"  Watching {self.data_dir} every {poll_ms}ms ... (Ctrl-C to stop)")
        try:
            while True:
                self._load_data()
                self._update(frame=N_FRAMES - 1)  # always show latest
                plt.pause(poll_ms / 1000.0)
        except KeyboardInterrupt:
            print("  Stopped.")
        finally:
            plt.ioff()


def main():
    parser = argparse.ArgumentParser(description="ns-3 NR Real-Time Dashboard")
    parser.add_argument("--watch", action="store_true",
                        help="Watch mode: poll files live (requires running ns-3)")
    parser.add_argument("--data", default="data",
                        help="Directory containing ns-3 trace files")
    parser.add_argument("--output", default="figures/realtime_preview.gif",
                        help="Output GIF path (static preview mode)")
    args = parser.parse_args()

    dash = RealTimeDashboard(data_dir=args.data)
    if args.watch:
        dash.watch()
    else:
        dash.render_preview_gif(output=args.output)


if __name__ == "__main__":
    print("=== Task 16: Real-Time Dashboard (file-watch) ===")
    dash = RealTimeDashboard()
    dash.render_preview_gif()
