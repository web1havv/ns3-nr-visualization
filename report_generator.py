#!/usr/bin/env python3
"""
Tasks 9–10: Automated Report Generator + AI Agent Interface
─────────────────────────────────────────────────────────────
Task 9: One-command PDF/HTML report from any ns-3 NR example output.
Task 10: Structured AI-agent interface (Biljana's mention of Nvidia
         agentic AI blueprint — mailing list, March 4, 2026).

Task 9 — Automated Report:
  Generates a self-contained HTML report with all charts embedded as
  base64 PNG, simulation summary table, and KPI analysis.
  Run: python3 report_generator.py

Task 10 — AI Agent Interface:
  Exports a clean JSON "observation" dict that can be fed to an LLM
  or agentic AI system for automated network analysis.
  Example prompt chain: simulation → analyze KPIs → suggest parameter tuning
"""

import base64
import json
import subprocess
from datetime import datetime
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ns3_nr_parser import (
    load_rlc_stats, load_sinr_stats, load_topology,
    load_flow_monitor, print_summary,
)
from json_exporter import export_simulation_json, NpEncoder


# ─── Task 9: Automated HTML Report ───────────────────────────────────────────

def img_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def build_html_report(dl_rlc, ul_rlc, dl_sinr, topo, flows, output: str = "report.html"):
    """Generate a complete standalone HTML simulation report."""

    # Run all visualizations first
    from visualize_nr import build_dashboard
    from kpi_dashboard import build_kpi_dashboard
    build_dashboard()
    build_kpi_dashboard()

    dashboard_b64 = img_to_base64("figures/nr_dashboard.png")
    kpi_b64       = img_to_base64("figures/kpi_dashboard.png")
    anim_b64      = img_to_base64("figures/handover_animation.gif")

    # Per-UE summary table rows
    ue_rows = ""
    for imsi in sorted(dl_rlc["IMSI"].unique()):
        ue = dl_rlc[dl_rlc["IMSI"] == imsi]
        s_dl = dl_sinr[dl_sinr["IMSI"] == imsi]
        ue_rows += f"""
        <tr>
          <td>{imsi}</td>
          <td>{int(ue['cellId'].mode()[0])}</td>
          <td>{ue['DL_throughput_mbps'].mean():.1f}</td>
          <td>{ul_rlc[ul_rlc['IMSI']==imsi]['DL_throughput_mbps'].mean():.1f}</td>
          <td>{s_dl['sinr_dB'].mean():.1f}</td>
          <td>{ue['delay_ms'].mean():.2f}</td>
          <td>{ue['packet_loss_pct'].mean():.2f}%</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>ns-3 5G NR Simulation Report</title>
  <style>
    body  {{ font-family: 'Segoe UI', sans-serif; margin: 40px; background: #f8f9fa; }}
    h1    {{ color: #1a1a2e; border-bottom: 3px solid #E63946; padding-bottom: 10px; }}
    h2    {{ color: #457B9D; margin-top: 30px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
    th    {{ background: #1a1a2e; color: white; padding: 10px 15px; }}
    td    {{ border: 1px solid #ddd; padding: 8px 15px; text-align: center; }}
    tr:nth-child(even) {{ background: #f2f2f2; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }}
    .kpi-card {{ background: white; border-radius: 8px; padding: 15px;
                 box-shadow: 0 2px 8px rgba(0,0,0,0.1); text-align: center; }}
    .kpi-val  {{ font-size: 2em; font-weight: bold; color: #E63946; }}
    .kpi-lbl  {{ color: #666; font-size: 0.85em; }}
    img {{ max-width: 100%; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }}
    .footer {{ color: #999; font-size: 0.8em; margin-top: 40px; border-top: 1px solid #ddd; }}
  </style>
</head>
<body>
  <h1>ns-3 5G NR Simulation Report</h1>
  <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 
     GSoC 2026 PoC — Enabling 5G NR Examples Visualization</p>

  <h2>Simulation Configuration</h2>
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-val">{topo['n_gnb']}</div>
      <div class="kpi-lbl">gNBs</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">{topo['n_ue']}</div>
      <div class="kpi-lbl">UEs</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">{topo['freq_ghz']:.1f} GHz</div>
      <div class="kpi-lbl">Frequency</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">{topo['bw_mhz']:.0f} MHz</div>
      <div class="kpi-lbl">Bandwidth</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">{dl_rlc['DL_throughput_mbps'].mean():.1f}</div>
      <div class="kpi-lbl">Avg DL Tput [Mbps]</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">{dl_sinr['sinr_dB'].mean():.1f}</div>
      <div class="kpi-lbl">Avg SINR [dB]</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">{dl_rlc['delay_ms'].mean():.1f}</div>
      <div class="kpi-lbl">Avg Delay [ms]</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">{topo['sim_time']:.0f} s</div>
      <div class="kpi-lbl">Simulation Time</div>
    </div>
  </div>

  <h2>Per-UE Performance Summary</h2>
  <table>
    <tr>
      <th>IMSI</th><th>Cell</th><th>DL Tput (Mbps)</th><th>UL Tput (Mbps)</th>
      <th>SINR (dB)</th><th>Delay (ms)</th><th>Loss</th>
    </tr>
    {ue_rows}
  </table>

  <h2>Full Dashboard</h2>
  <img src="data:image/png;base64,{dashboard_b64}" alt="NR Dashboard">

  <h2>Advanced KPI Analysis</h2>
  <img src="data:image/png;base64,{kpi_b64}" alt="KPI Dashboard">

  <h2>Live Handover Animation</h2>
  <img src="data:image/gif;base64,{anim_b64}" alt="Handover Animation">

  <div class="footer">
    <p>Generated by ns3-nr-visualization | 
       <a href="https://github.com/web1havv/ns3-nr-visualization">GitHub</a> | 
       GSoC 2026 — The ns-3 Network Simulator Project</p>
  </div>
</body>
</html>"""

    with open(output, "w") as f:
        f.write(html)

    size_kb = Path(output).stat().st_size / 1024
    print(f"  ✓ HTML report → {output}  ({size_kb:.0f} KB, self-contained)")


# ─── Task 10: AI Agent Interface ─────────────────────────────────────────────

def build_ai_agent_observation(dl_rlc, ul_rlc, dl_sinr, topo) -> dict:
    """
    Build a structured observation dict for AI/LLM agents.

    Biljana Bojovic (March 4, 2026):
    "We like this json/xml generic approach. Such API opens many
    different possibilities, e.g., ns-3 for agentic AI."

    This follows the Nvidia AI Blueprint telco agent structure:
    https://blogs.nvidia.com/blog/nvidia-agentic-ai-blueprints-telco-reasoning-models/

    The observation can be fed to GPT-4/Claude/Llama to:
      - Identify performance bottlenecks
      - Suggest parameter changes (scheduler, power, bandwidth)
      - Predict handover timing
      - Generate natural-language simulation summaries
    """
    obs = {
        "task": "5G NR network performance analysis",
        "simulation_config": {
            "n_gnbs":   topo["n_gnb"],
            "n_ues":    topo["n_ue"],
            "freq_ghz": topo["freq_ghz"],
            "bw_mhz":   topo["bw_mhz"],
            "sim_time": topo["sim_time"],
        },
        "network_kpis": {
            "mean_dl_throughput_mbps": round(float(dl_rlc["DL_throughput_mbps"].mean()), 2),
            "mean_ul_throughput_mbps": round(float(ul_rlc["DL_throughput_mbps"].mean()), 2),
            "mean_sinr_db":            round(float(dl_sinr["sinr_dB"].mean()), 2),
            "mean_delay_ms":           round(float(dl_rlc["delay_ms"].mean()), 3),
            "mean_packet_loss_pct":    round(float(dl_rlc["packet_loss_pct"].mean()), 3),
            "p5_dl_throughput_mbps":   round(float(np.percentile(dl_rlc["DL_throughput_mbps"], 5)), 2),
            "p95_dl_throughput_mbps":  round(float(np.percentile(dl_rlc["DL_throughput_mbps"], 95)), 2),
        },
        "per_cell_summary": {},
        "alerts": [],
        "suggested_actions": [],
    }

    # Per-cell KPIs
    for cell_id in sorted(dl_rlc["cellId"].unique()):
        c = dl_rlc[dl_rlc["cellId"] == cell_id]
        obs["per_cell_summary"][f"cell_{int(cell_id)}"] = {
            "n_ues":          int(c["IMSI"].nunique()),
            "mean_tput_mbps": round(float(c["DL_throughput_mbps"].mean()), 2),
            "mean_sinr_db":   round(float(dl_sinr[dl_sinr["cellId"]==cell_id]["sinr_dB"].mean()), 2),
        }

    # Auto-generate alerts based on thresholds
    if obs["network_kpis"]["mean_delay_ms"] > 10:
        obs["alerts"].append({
            "severity": "WARNING",
            "message":  f"Mean delay {obs['network_kpis']['mean_delay_ms']} ms exceeds 10 ms threshold",
        })
    if obs["network_kpis"]["mean_packet_loss_pct"] > 2:
        obs["alerts"].append({
            "severity": "WARNING",
            "message":  f"Packet loss {obs['network_kpis']['mean_packet_loss_pct']}% exceeds 2% threshold",
        })
    for cell_id, stats in obs["per_cell_summary"].items():
        if stats["mean_sinr_db"] < 5:
            obs["alerts"].append({
                "severity": "CRITICAL",
                "message":  f"{cell_id}: Mean SINR {stats['mean_sinr_db']} dB below 5 dB — coverage hole",
            })

    # Example AI-suggested actions (would come from LLM in full system)
    obs["suggested_actions"] = [
        "Increase transmit power by 3 dB on cells with SINR < 10 dB",
        "Enable carrier aggregation for UEs with DL throughput < 50 Mbps",
        "Trigger early handover threshold reduction from -3 to -5 dB",
        "Consider frequency reuse to reduce inter-cell interference",
    ]

    return obs


if __name__ == "__main__":
    data_dir = Path("data")
    dl_rlc  = load_rlc_stats(data_dir / "DlRlcStats.txt")
    ul_rlc  = load_rlc_stats(data_dir / "UlRlcStats.txt")
    dl_sinr = load_sinr_stats(data_dir / "DlPhySinr.txt")
    topo    = load_topology(data_dir / "topology.json")
    flows   = load_flow_monitor(data_dir / "flow_monitor.json")

    print("=== Task 9: Automated Report ===")
    build_html_report(dl_rlc, ul_rlc, dl_sinr, topo, flows)

    print("\n=== Task 10: AI Agent Interface ===")
    obs = build_ai_agent_observation(dl_rlc, ul_rlc, dl_sinr, topo)
    out_path = "data/ai_agent_observation.json"
    with open(out_path, "w") as f:
        json.dump(obs, f, indent=2, cls=NpEncoder)
    print(f"  ✓ AI observation → {out_path}")
    print(f"    Alerts: {len(obs['alerts'])}")
    print(f"    Suggested actions: {len(obs['suggested_actions'])}")
    if obs["alerts"]:
        for alert in obs["alerts"]:
            print(f"    [{alert['severity']}] {alert['message']}")
