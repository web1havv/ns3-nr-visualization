# ns-3 5G NR Visualization Toolkit

**GSoC 2026 Proof-of-Concept** | [The ns-3 Network Simulator Project](https://www.nsnam.org)  
**Project:** Enabling 5G NR Examples Visualization  
**Contributor:** Vaibhav (web1havv)

---

## Overview

This repository is a proof-of-concept for the GSoC 2026 project
**"Enabling 5G NR examples visualization"** under the ns-3 Network Simulator.

It demonstrates a Python-based visualization toolkit that parses **real ns-3 NR
trace files** (produced by `NrBearerStatsCalculator` and `PhyStatsCalculator`)
and generates:

- A comprehensive **8-panel simulation dashboard** (static PNG)
- A **50-frame animated GIF** showing live handover events and per-UE throughput
- A **Jupyter Notebook** for interactive exploration of simulation results

The trace file format is taken directly from the ns-3 NR source:
[`helper/nr-bearer-stats-calculator.cc`](https://gitlab.com/cttc-lena/nr/-/blob/master/helper/nr-bearer-stats-calculator.cc)

---

## Simulation Setup

| Parameter | Value |
|-----------|-------|
| gNBs | 3 (hexagonal layout) |
| UEs | 10 (mobile) |
| Central frequency | 3.5 GHz (sub-6 NR) |
| Channel bandwidth | 100 MHz |
| Simulation time | 5 s |
| Handover event | UE 3: Cell 1 → Cell 2 at t = 2.5 s |
| Epoch (stats interval) | 100 ms |

---

## Dashboard Preview

![NR Dashboard](figures/nr_dashboard.png)

**Panels:**
1. Network topology — gNB/UE positions with coverage areas
2. Per-UE DL throughput over time (handover dip visible)
3. Per-UE DL SINR (dB) over time
4. Cell-aggregate DL throughput
5. CDF of DL throughput (per cell + overall)
6. Jain's Fairness Index over time
7. Delay vs. Throughput scatter (averaged per UE)
8. Estimated MCS distribution (from SINR → 3GPP CQI mapping)

---

## Animated Handover Visualization

![Handover Animation](figures/handover_animation.gif)

Shows real-time UE positions, SINR-based color coding, live throughput bars,
and the handover event where UE 3 switches its serving cell at t = 2.5 s.

---

## Files

```
ns3-viz/
├── generate_traces.py     # Generates realistic ns-3 NR trace files
├── ns3_nr_parser.py       # Parser for NrBearerStatsCalculator output
├── visualize_nr.py        # 8-panel dashboard generator
├── animate_handover.py    # Animated handover GIF
├── ns3_nr_dashboard.ipynb # Interactive Jupyter notebook
├── data/
│   ├── DlRlcStats.txt     # Downlink RLC stats (ns-3 format)
│   ├── UlRlcStats.txt     # Uplink RLC stats
│   ├── DlPhySinr.txt      # Downlink PHY SINR traces
│   ├── UlPhySinr.txt      # Uplink PHY SINR traces
│   ├── topology.json      # Node positions
│   └── flow_monitor.json  # FlowMonitor summary
└── figures/
    ├── nr_dashboard.png
    └── handover_animation.gif
```

---

## Installation & Usage

```bash
# Install dependencies
pip install pandas matplotlib numpy plotly ipywidgets jupyterlab pillow

# Generate trace data (or use real ns-3 output)
python3 generate_traces.py

# Static 8-panel dashboard
python3 visualize_nr.py

# Animated handover visualization
python3 animate_handover.py

# Interactive Jupyter notebook
jupyter lab ns3_nr_dashboard.ipynb
```

### Using Real ns-3 NR Output

Replace the generated files in `data/` with the actual output from running
an ns-3 5G-LENA simulation. The parser reads the exact format produced by
`NrBearerStatsCalculator`:

```bash
# In your ns-3 build directory, run the NR demo
./ns3 run "cttc-nr-demo --enableTraces=true"

# Then copy the output files
cp DlRlcStats.txt UlRlcStats.txt DlPhySinr.txt UlPhySinr.txt ns3-viz/data/

# Regenerate visualizations
python3 visualize_nr.py
```

---

## GSoC 2026 Project Scope

The full GSoC project would extend this proof-of-concept to:

1. **Jupyter Widget Dashboard** — Interactive ipywidgets sliders to filter by
   UE, cell, time range; toggle between DL/UL; select metrics
2. **NetAnim Integration** — Python wrapper to launch NetAnim from Jupyter
3. **Automated Report Generation** — One-command PDF report from any NR example
4. **More NR-Specific Metrics** — HARQ retransmission rate, CQI distribution,
   beamforming gain, PRB utilization
5. **Handover Analysis** — Automatic detection and annotation of handover events
   from RRC trace files

---

## References

- [ns-3 NR module (5G-LENA)](https://gitlab.com/cttc-lena/nr)
- [ns-3 documentation](https://www.nsnam.org/documentation/)
- [GSoC 2026 project idea](https://www.nsnam.org/wiki/GSOC2026Projects#Enabling_5G_NR_examples_visualization)
- [NrBearerStatsCalculator source](https://gitlab.com/cttc-lena/nr/-/blob/master/helper/nr-bearer-stats-calculator.cc)
