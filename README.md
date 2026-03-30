# ns-3 NR Visualization Toolkit

**GSoC 2026 Proof-of-Concept** | [The ns-3 Network Simulator Project](https://www.nsnam.org)  
**Project:** Enabling 5G NR Examples Visualization  
**Contributor:** Vaibhav Sharma (web1havv) | BITS Pilani

---

## Design Philosophy

This toolkit was designed with four explicit constraints raised by past ns-3 visualization efforts that failed to be maintained:

### 1. Minimal dependencies — core runs on 3 packages

```
matplotlib   (BSD)  — the only plotting library; already used in ns-3 docs
numpy        (BSD)  — standard scientific baseline
pandas       (BSD)  — standard data analysis baseline
```

`plotly`, `ipywidgets`, and `jupyterlab` are **optional extras** — the entire toolkit works without them. No Qt. No Electron. No compiled extensions.

Install only what you need:
```bash
pip install matplotlib numpy pandas           # core
pip install ipywidgets jupyterlab             # optional: interactive notebook
pip install pillow                            # optional: animated GIF output
```

### 2. Reusable across all ns-3 modules — not NR-only

The parser is built on a generic base class (`ns3_trace_parser.py`) that handles any ns-3 tab-separated trace file. Adding a new module means adding ~10 lines:

```python
class WifiEdcaStatsParser(Ns3TraceParser):
    COLUMNS = [
        ColDef("time",       float, "s"),
        ColDef("node_id",    int),
        ColDef("queue_size", int,   "pkts"),
        # ... add columns from the .cc source
    ]
```

The same visualization functions then work unchanged for WiFi, CSMA, LTE, or any future module.

### 3. Survives ns-3 changes — column schema is isolated

If ns-3 adds or renames a column in a trace file, **only the `COLUMNS` list in one class changes**. No parsing logic changes. No visualization code changes. This is a direct response to how past ns-3 visualizers broke every release.

The column definitions live in one place and are the single source of truth for column names, types, units, and documentation.

### 4. Modular — each script does one thing

| Script | Does exactly one thing |
|--------|----------------------|
| `ns3_trace_parser.py` | Reads trace files → typed DataFrames |
| `ns3_nr_parser.py` | NR-specific derived metrics (throughput, SINR dB, MCS) |
| `flow_filter.py` | Filters DataFrames by UE/cell/time |
| `visualize_nr.py` | Static 8-panel dashboard |
| `animate_handover.py` | Handover animation |
| `json_exporter.py` | JSON export for web/AI |
| `kpi_dashboard.py` | Advanced KPI panels |
| `report_generator.py` | HTML report + AI agent interface |
| `realtime_dashboard.py` | Live file-watch dashboard |
| `sem_integration.py` | SEM parameter sweep integration |
| `multi_run_ci.py` | Multi-run statistical analysis |
| `netanim_parser.py` | NetAnim XML + NR overlay |
| `run_all.py` | CLI runner for the full pipeline |

Each script can be used independently. Nothing is hard-coded to NR. The parser, filter, and statistics modules work for any ns-3 trace format.

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

## Quick Start

```bash
# 1. Install core dependencies (3 packages)
pip install matplotlib numpy pandas

# 2. Generate synthetic trace data (matches real ns-3 NR output format)
python3 generate_traces.py

# 3. Run the full pipeline
python3 run_all.py --skip-generate

# 4. Or run individual scripts
python3 visualize_nr.py          # static 8-panel dashboard
python3 animate_handover.py      # handover animation GIF
python3 flow_filter.py           # per-UE deep-dive
python3 json_exporter.py         # structured JSON output
```

### Using Real ns-3 NR Output

```bash
# In your ns-3 build directory
./ns3 run "cttc-nr-demo --enableTraces=true"

# Copy trace files
cp DlRlcStats.txt UlRlcStats.txt DlPhySinr.txt UlPhySinr.txt ns3-viz/data/

# Run visualizations on real data
python3 run_all.py --skip-generate
```

---

## Generic Parser API

```python
from ns3_trace_parser import NrRlcStatsParser, NrPhySinrParser, auto_parse

# Explicit parser
dl = NrRlcStatsParser.from_file("data/DlRlcStats.txt")

# Auto-detect from filename
sinr = auto_parse("data/DlPhySinr.txt")

# Works identically for LTE (same trace format)
from ns3_trace_parser import LteRlcStatsParser
lte_dl = LteRlcStatsParser.from_file("data/DlRlcStats.txt")
```

---

## File Structure

```
ns3-viz/
├── ns3_trace_parser.py    # Generic base parser — reusable for all ns-3 modules
├── ns3_nr_parser.py       # NR-specific derived metrics (wraps base parser)
├── generate_traces.py     # Synthetic trace generator (matches real ns-3 format)
├── visualize_nr.py        # 8-panel static KPI dashboard
├── animate_handover.py    # Handover animation (GIF/MP4)
├── flow_filter.py         # Flow-ID / UE filter engine
├── json_exporter.py       # Structured JSON export
├── kpi_dashboard.py       # Advanced KPI panels (PRB, CQI, HARQ, comparison)
├── netsimulyzer_bridge.py # NetSimulyzer 3D visualizer JSON bridge
├── report_generator.py    # HTML report + AI agent observation interface
├── realtime_dashboard.py  # Real-time file-watch dashboard
├── netanim_parser.py      # NetAnim XML parser + NR-KPI overlay
├── multi_run_ci.py        # Multi-run statistical CI + Welch t-test
├── sem_integration.py     # SEM parameter sweep integration
├── style_checker.py       # ns-3 clang-format config + PEP-8 checker
├── run_all.py             # One-command CLI runner
├── ns3_nr_dashboard.ipynb # Interactive Jupyter notebook
├── requirements.txt       # Core: matplotlib, numpy, pandas only
├── tests/
│   └── test_parser.py     # pytest suite (parser, filter, statistics)
├── data/
│   ├── DlRlcStats.txt
│   ├── UlRlcStats.txt
│   ├── DlPhySinr.txt
│   ├── UlPhySinr.txt
│   ├── topology.json
│   └── flow_monitor.json
└── figures/               # Generated outputs (gitignored)
```

---

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

Tests cover: column presence, type correctness, SINR unit conversion, MCS monotonicity, packet loss bounds, filter correctness, Jain's Fairness Index bounds.

---

## GSoC 2026 Project Scope

The full GSoC project extends this proof-of-concept into mergeable, documented, tested ns-3 code:

1. **Hardened parser library** — production-quality, fully documented column semantics
2. **Interactive Jupyter dashboard** — ipywidgets sliders, no re-run required
3. **Handover analysis** — automatic detection from RRC trace files
4. **C++ NrVisualizationHelper** — optional convenience class in ns-3-nr
5. **SEM campaign integration** — parameter sweep → visualization pipeline
6. **ns-3 wiki page** — milestone tracking per contributor guide

**What this project will NOT do:** Attempt to visualize everything for every ns-3 module in one shot. The generic base parser makes future extension straightforward, but the GSoC scope is deliberately focused on the NR module first.

---

## References

- [ns-3 NR module (5G-LENA)](https://gitlab.com/cttc-lena/nr)
- [ns-3 documentation](https://www.nsnam.org/documentation/)
- [GSoC 2026 project idea](https://www.nsnam.org/wiki/GSOC2026Projects#Enabling_5G_NR_examples_visualization)
- [NrBearerStatsCalculator source](https://gitlab.com/cttc-lena/nr/-/blob/master/helper/nr-bearer-stats-calculator.cc)
- [PhyStatsCalculator source](https://gitlab.com/cttc-lena/nr/-/blob/master/helper/phy-stats-calculator.cc)
