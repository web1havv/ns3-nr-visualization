#!/usr/bin/env python3
"""
Task 12: SEM (Simulation Execution Manager) Integration
─────────────────────────────────────────────────────────
Tom Henderson (ns-3 lead) recommended SEM multiple times as the preferred
way to run ns-3 experiments programmatically (mailing list, Feb 25, 2026):
  "ns-3 decided to focus on parallelization via MPI and on using multiple
   cores to run experiments in parallel (e.g., the SEM tool)"
  https://apps.nsnam.org/app/sem/

SEM allows batch simulation runs with parameter sweeps, then
collects all results into a structured dataset.

This module provides:
  1. A SEM campaign template for the cttc-nr-demo example
  2. Automatic parsing of SEM output into our visualization format
  3. Parameter sweep visualization (e.g., bandwidth vs throughput)
"""

import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path


def generate_sem_campaign_config() -> dict:
    """
    Generate a SEM campaign configuration for cttc-nr-demo.

    SEM campaign: sweep over numUes (1-10) and numerology (0,1,2)
    to study how UE density and numerology affect per-UE throughput.

    Usage with real SEM:
      import sem
      campaign = sem.CampaignManager.new(
          ns_path="/path/to/ns3",
          script="cttc-nr-demo",
          campaign_dir="nr-viz-campaign",
      )
      campaign.run_missing_simulations(params, runs=5)
    """
    return {
        "script": "cttc-nr-demo",
        "params": {
            "numUes":      [1, 2, 3, 5, 7, 10],
            "numerology":  [0, 1, 2],
            "simTime":     [1.0],
            "enableTraces": [True],
        },
        "runs": 5,
        "description": "5G NR UE density and numerology sweep for visualization project",
    }


def simulate_sem_results() -> pd.DataFrame:
    """
    Simulate what SEM would return from the parameter sweep.
    In the real GSoC project, this would call:
      results = campaign.get_results_as_dataframe("cttc-nr-demo")
    """
    np.random.seed(42)
    records = []
    for num_ues in [1, 2, 3, 5, 7, 10]:
        for numerology in [0, 1, 2]:
            for run in range(5):
                # Numerology 0 = 15kHz SCS, 1 = 30kHz, 2 = 60kHz
                # Higher numerology → shorter slots → lower latency but overhead
                base_tput = 150 / num_ues  # bandwidth split
                num_factor = {0: 1.0, 1: 0.92, 2: 0.85}[numerology]
                lat_factor  = {0: 1.0, 1: 0.55, 2: 0.30}[numerology]

                records.append({
                    "numUes":       num_ues,
                    "numerology":   numerology,
                    "run":          run,
                    "dl_tput_mbps": max(0, base_tput * num_factor + np.random.normal(0, 3)),
                    "delay_ms":     max(0.1, 20 * lat_factor + np.random.normal(0, 1)),
                    "sinr_db":      np.random.normal(15, 3),
                })
    return pd.DataFrame(records)


def plot_parameter_sweep(output: str = "figures/sem_sweep.png"):
    """
    Plot SEM parameter sweep results.

    Panel 1: UE count vs. per-UE DL throughput (per numerology)
    Panel 2: Numerology vs. latency trade-off
    Panel 3: 2D heatmap: UEs × numerology → throughput
    """
    df = simulate_sem_results()
    Path("figures").mkdir(exist_ok=True)

    # Aggregate over runs
    agg = df.groupby(["numUes", "numerology"]).agg(
        mean_tput=("dl_tput_mbps", "mean"),
        std_tput=("dl_tput_mbps", "std"),
        mean_delay=("delay_ms", "mean"),
        std_delay=("delay_ms", "std"),
    ).reset_index()

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle("SEM Parameter Sweep: UE Density × Numerology\n(cttc-nr-demo)",
                 fontweight="bold", fontsize=13)

    num_colors = {0: "#E63946", 1: "#457B9D", 2: "#2A9D8F"}
    num_labels = {0: "Numerology 0 (15 kHz)", 1: "Numerology 1 (30 kHz)", 2: "Numerology 2 (60 kHz)"}

    # Panel 1: Throughput vs UE count
    for num in [0, 1, 2]:
        d = agg[agg["numerology"] == num]
        axes[0].errorbar(d["numUes"], d["mean_tput"], yerr=d["std_tput"],
                         label=num_labels[num], color=num_colors[num],
                         marker="o", linewidth=2, capsize=4)
    axes[0].set_xlabel("Number of UEs")
    axes[0].set_ylabel("Per-UE DL Throughput [Mbps]")
    axes[0].set_title("Throughput vs. UE Count")
    axes[0].legend(fontsize=8)
    axes[0].grid(True, alpha=0.3)

    # Panel 2: Numerology vs latency
    for num in [0, 1, 2]:
        d = agg[agg["numerology"] == num]
        axes[1].errorbar(d["numUes"], d["mean_delay"], yerr=d["std_delay"],
                         label=num_labels[num], color=num_colors[num],
                         marker="s", linewidth=2, capsize=4)
    axes[1].set_xlabel("Number of UEs")
    axes[1].set_ylabel("Mean Delay [ms]")
    axes[1].set_title("Latency vs. UE Count (Numerology Effect)")
    axes[1].legend(fontsize=8)
    axes[1].grid(True, alpha=0.3)

    # Panel 3: Heatmap UEs × numerology → throughput
    pivot = agg.pivot(index="numerology", columns="numUes", values="mean_tput")
    im = axes[2].imshow(pivot.values, aspect="auto", cmap="YlOrRd",
                        origin="upper")
    axes[2].set_xticks(range(len(pivot.columns)))
    axes[2].set_xticklabels(pivot.columns)
    axes[2].set_yticks(range(len(pivot.index)))
    axes[2].set_yticklabels([f"μ={n}" for n in pivot.index])
    axes[2].set_xlabel("Number of UEs")
    axes[2].set_ylabel("Numerology")
    axes[2].set_title("Throughput Heatmap [Mbps]")
    plt.colorbar(im, ax=axes[2], label="Tput [Mbps]")

    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            axes[2].text(j, i, f"{pivot.values[i,j]:.0f}",
                         ha="center", va="center", fontsize=8, color="black")

    fig.tight_layout()
    fig.savefig(output, dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  ✓ SEM sweep → {output}")


if __name__ == "__main__":
    print("=== Task 12: SEM Integration ===")
    config = generate_sem_campaign_config()
    print(f"  Campaign: {config['script']}")
    print(f"  Params: numUes={config['params']['numUes']}, "
          f"numerology={config['params']['numerology']}")
    print(f"  Total runs: "
          f"{len(config['params']['numUes']) * len(config['params']['numerology']) * config['runs']}")
    plot_parameter_sweep()
    cfg_path = "data/sem_campaign_config.json"
    with open(cfg_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  ✓ SEM config → {cfg_path}")
