#!/usr/bin/env python3
"""
Task 15: Multi-Run Statistical Confidence Intervals
─────────────────────────────────────────────────────
ns-3 simulations are stochastic — a single run is meaningless.
Mentor Tom Henderson (ns-3 lead, mailing list Feb 2026) highlighted this:
  "ns-3 decided to focus on parallelization via MPI and on using
   multiple cores to run experiments in parallel"

This module:
  1. Simulates N independent runs with different random seeds
  2. Aggregates per-UE throughput across runs
  3. Plots mean ± 95% confidence interval ribbons (proper statistical analysis)
  4. Computes Welch's t-test to compare two configurations

This is directly what researchers need: not just one trace, but a
statistically valid comparison between parameter choices.
"""

import numpy as np
import pandas as pd
import scipy.stats as stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path


N_RUNS = 10
N_UES  = 10
T_MAX  = 5.0
DT     = 0.2


def simulate_run(seed: int, config: dict) -> pd.DataFrame:
    """
    Simulate one ns-3 run (deterministic per seed) returning per-UE throughput.
    In the real project this would call ns-3 via subprocess/SEM.
    """
    rng = np.random.default_rng(seed)
    rows = []
    t = 0.0
    while t < T_MAX:
        t_end = round(t + DT, 4)
        for imsi in range(1, N_UES + 1):
            base = config["base_tput"] / N_UES
            noise = rng.normal(0, 0.05 * base)
            tput = max(0, base * config["efficiency"] + noise)
            rows.append({
                "run": seed, "t": t, "IMSI": imsi,
                "tput_mbps": tput,
                "delay_ms": max(0.1, rng.normal(config["base_delay"], 2)),
            })
        t = round(t_end, 4)
    return pd.DataFrame(rows)


def aggregate_runs(config: dict, n_runs: int = N_RUNS) -> pd.DataFrame:
    """Aggregate N runs into mean ± CI per time step per UE."""
    all_runs = pd.concat([simulate_run(seed, config)
                          for seed in range(n_runs)], ignore_index=True)
    return all_runs


def compute_ci(data: pd.Series, confidence: float = 0.95) -> tuple[float, float]:
    """Compute confidence interval using scipy t-distribution."""
    n = len(data)
    if n < 2:
        return float(data.mean()), 0.0
    se = stats.sem(data)
    margin = se * stats.t.ppf((1 + confidence) / 2, df=n - 1)
    return float(data.mean()), float(margin)


def welch_t_test(df1: pd.DataFrame, df2: pd.DataFrame,
                 column: str = "tput_mbps") -> dict:
    """Welch's t-test (unequal variance) between two configurations."""
    t_stat, p_val = stats.ttest_ind(df1[column], df2[column], equal_var=False)
    return {
        "t_statistic": float(t_stat),
        "p_value": float(p_val),
        "significant_at_5pct": bool(p_val < 0.05),
        "config1_mean": float(df1[column].mean()),
        "config2_mean": float(df2[column].mean()),
    }


def plot_multi_run_ci(output: str = "figures/multi_run_ci.png"):
    """
    Plot mean ± 95% CI for two configurations across time.
    Config A: μ=0 numerology (lower efficiency, lower delay)
    Config B: μ=2 numerology (higher efficiency, higher delay)
    """
    Path("figures").mkdir(exist_ok=True)

    cfg_a = {"base_tput": 120, "efficiency": 1.00, "base_delay": 10.0,
             "label": "Numerology 0 (15 kHz)", "color": "#E63946"}
    cfg_b = {"base_tput": 120, "efficiency": 0.88, "base_delay":  4.0,
             "label": "Numerology 2 (60 kHz)", "color": "#2A9D8F"}

    df_a = aggregate_runs(cfg_a)
    df_b = aggregate_runs(cfg_b)

    t_test = welch_t_test(df_a, df_b)

    # Aggregate over runs and UEs per time step
    def agg_by_time(df: pd.DataFrame) -> pd.DataFrame:
        out = []
        for t, grp in df.groupby("t"):
            m, ci = compute_ci(grp["tput_mbps"])
            out.append({"t": t, "mean": m, "ci": ci})
        return pd.DataFrame(out)

    agg_a = agg_by_time(df_a)
    agg_b = agg_by_time(df_b)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Multi-Run Statistical Analysis (N=10 runs, 95% CI)\n"
                 "Demonstrates: Same codebase, different numerology → measurable difference",
                 fontweight="bold", fontsize=12)

    # Panel 1: Throughput ribbons
    for agg, cfg in [(agg_a, cfg_a), (agg_b, cfg_b)]:
        ax1.plot(agg["t"], agg["mean"], color=cfg["color"],
                 label=cfg["label"], linewidth=2)
        ax1.fill_between(agg["t"], agg["mean"] - agg["ci"],
                         agg["mean"] + agg["ci"],
                         alpha=0.25, color=cfg["color"])

    ax1.set_xlabel("Simulation Time [s]")
    ax1.set_ylabel("Mean Per-UE Throughput [Mbps]")
    ax1.set_title("Per-UE Throughput: Mean ± 95% CI")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Panel 2: Welch t-test summary box
    y_a = df_a.groupby("run")["tput_mbps"].mean()
    y_b = df_b.groupby("run")["tput_mbps"].mean()
    ax2.boxplot([y_a, y_b], labels=["Numerology 0", "Numerology 2"],
                patch_artist=True,
                boxprops=dict(facecolor="lightblue"),
                medianprops=dict(color="darkred", linewidth=2))
    ax2.set_ylabel("Mean Per-Run Throughput [Mbps]")
    ax2.set_title(
        f"Welch T-Test (n={N_RUNS} runs each)\n"
        f"t={t_test['t_statistic']:.2f}, p={t_test['p_value']:.4f}, "
        f"{'SIGNIFICANT' if t_test['significant_at_5pct'] else 'NOT significant'} at α=0.05"
    )
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output, dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  ✓ Multi-run CI → {output}")
    print(f"  t-test: p={t_test['p_value']:.4f}, "
          f"significant={t_test['significant_at_5pct']}")


if __name__ == "__main__":
    print("=== Task 15: Multi-Run Statistical CI ===")
    plot_multi_run_ci()
