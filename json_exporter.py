#!/usr/bin/env python3
"""
Task 2: JSON Trace Exporter
───────────────────────────
Tom Henderson (ns-3 lead) and Biljana Bojovic both endorsed the
"json/xml generic approach" (mailing list, Feb–Mar 2026).

Tom: "Using JSON as the representation may also make sense...
      it might be time to try to upgrade ConfigStore to use JSON"
Biljana: "We like this json/xml generic approach. Such API opens
          many different possibilities, e.g., ns-3 for agentic AI."

This module exports parsed ns-3 NR traces into a structured JSON
format that can be consumed by:
  - Web dashboards (React, Vue)
  - AI/LLM agents (Nvidia Blueprint, LangChain)
  - Other ns-3 tools (NetSimulyzer, SEM)
  - REST APIs for remote visualization
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from ns3_nr_parser import (
    load_rlc_stats, load_sinr_stats, load_topology,
    compute_cell_stats, compute_jains_fairness,
)


class NpEncoder(json.JSONEncoder):
    """Handle numpy types for JSON serialization."""
    def default(self, obj):
        if isinstance(obj, (np.integer,)):  return int(obj)
        if isinstance(obj, (np.floating,)): return round(float(obj), 6)
        if isinstance(obj, np.ndarray):     return obj.tolist()
        return super().default(obj)


def export_simulation_json(dl_rlc, ul_rlc, dl_sinr, topo, output_path: str) -> dict:
    """
    Export full simulation results to structured JSON.

    Schema:
      simulation_meta: { n_gnbs, n_ues, sim_time, freq_ghz, bw_mhz }
      topology: { gnbs: [...], ues: [...] }
      per_ue: { <imsi>: { dl_timeline, ul_timeline, sinr_timeline, summary } }
      per_cell: { <cell_id>: { aggregate_tput_timeline, n_ues, summary } }
      global: { jains_fairness_timeline, mean_dl_tput, mean_sinr_db, ... }
    """

    def df_to_records(df: pd.DataFrame, cols: list) -> list:
        return df[cols].round(6).to_dict(orient="records")

    # Per-UE data
    per_ue = {}
    for imsi in sorted(dl_rlc["IMSI"].unique()):
        ue_dl   = dl_rlc[dl_rlc["IMSI"] == imsi]
        ue_ul   = ul_rlc[ul_rlc["IMSI"] == imsi]
        ue_sinr = dl_sinr[dl_sinr["IMSI"] == imsi]

        per_ue[int(imsi)] = {
            "serving_cell": int(ue_dl["cellId"].mode()[0]),
            "dl_timeline": df_to_records(ue_dl, [
                "start_time", "DL_throughput_mbps", "delay_ms", "packet_loss_pct"
            ]),
            "ul_timeline": df_to_records(ue_ul, [
                "start_time", "DL_throughput_mbps"
            ]),
            "sinr_timeline": df_to_records(ue_sinr, [
                "time", "sinr_dB", "mcs"
            ]),
            "summary": {
                "mean_dl_tput_mbps": round(float(ue_dl["DL_throughput_mbps"].mean()), 2),
                "mean_ul_tput_mbps": round(float(ue_ul["DL_throughput_mbps"].mean()), 2),
                "mean_sinr_db":      round(float(ue_sinr["sinr_dB"].mean()), 2),
                "mean_delay_ms":     round(float(ue_dl["delay_ms"].mean()), 3),
                "mean_loss_pct":     round(float(ue_dl["packet_loss_pct"].mean()), 3),
                "p5_dl_tput":        round(float(np.percentile(ue_dl["DL_throughput_mbps"], 5)), 2),
                "p95_dl_tput":       round(float(np.percentile(ue_dl["DL_throughput_mbps"], 95)), 2),
            }
        }

    # Per-cell data
    cell_stats = compute_cell_stats(dl_rlc)
    per_cell = {}
    for cell_id in sorted(dl_rlc["cellId"].unique()):
        cs = cell_stats[cell_stats["cellId"] == cell_id]
        per_cell[int(cell_id)] = {
            "aggregate_timeline": df_to_records(cs, [
                "start_time", "total_tput_mbps", "n_ues", "mean_delay_ms"
            ]),
            "summary": {
                "mean_total_tput_mbps": round(float(cs["total_tput_mbps"].mean()), 2),
                "mean_ue_count":        round(float(cs["n_ues"].mean()), 1),
                "mean_delay_ms":        round(float(cs["mean_delay_ms"].mean()), 3),
            }
        }

    # Global stats
    jfi = compute_jains_fairness(dl_rlc)
    global_stats = {
        "mean_dl_tput_mbps":   round(float(dl_rlc["DL_throughput_mbps"].mean()), 2),
        "mean_ul_tput_mbps":   round(float(ul_rlc["DL_throughput_mbps"].mean()), 2),
        "mean_sinr_db":        round(float(dl_sinr["sinr_dB"].mean()), 2),
        "mean_delay_ms":       round(float(dl_rlc["delay_ms"].mean()), 3),
        "mean_loss_pct":       round(float(dl_rlc["packet_loss_pct"].mean()), 3),
        "mean_jains_fi":       round(float(jfi.mean()), 4),
        "jains_fi_timeline":   [
            {"time": round(float(t), 3), "jfi": round(float(v), 4)}
            for t, v in jfi.items() if not np.isnan(v)
        ],
    }

    output = {
        "schema_version": "1.0",
        "generator": "ns3-nr-visualization (GSoC 2026 PoC)",
        "simulation_meta": {
            "n_gnbs":   topo["n_gnb"],
            "n_ues":    topo["n_ue"],
            "sim_time": topo["sim_time"],
            "freq_ghz": topo["freq_ghz"],
            "bw_mhz":   topo["bw_mhz"],
        },
        "topology": topo,
        "per_ue":   per_ue,
        "per_cell": per_cell,
        "global":   global_stats,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, cls=NpEncoder)

    size_kb = Path(output_path).stat().st_size / 1024
    print(f"  ✓ JSON export → {output_path}  ({size_kb:.1f} KB)")
    print(f"    Contains: {topo['n_ue']} UEs, {topo['n_gnb']} cells")
    print(f"    Global mean DL: {global_stats['mean_dl_tput_mbps']} Mbps, "
          f"SINR: {global_stats['mean_sinr_db']} dB, "
          f"JFI: {global_stats['mean_jains_fi']}")
    return output


if __name__ == "__main__":
    data_dir = Path("data")
    dl_rlc  = load_rlc_stats(data_dir / "DlRlcStats.txt")
    ul_rlc  = load_rlc_stats(data_dir / "UlRlcStats.txt")
    dl_sinr = load_sinr_stats(data_dir / "DlPhySinr.txt")
    topo    = load_topology(data_dir / "topology.json")

    Path("data").mkdir(exist_ok=True)
    export_simulation_json(dl_rlc, ul_rlc, dl_sinr, topo, "data/simulation_results.json")
