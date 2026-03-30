# Enabling 5G NR Examples Visualization
GSoC 2026 — The ns-3 Network Simulator Project

---

## 1. Project Title

Enabling 5G NR Examples Visualization

---

## 2. Abstract

The CTTC 5G-LENA NR module for ns-3 is one of the most complete open-source 5G New Radio simulators available. It ships with a rich set of examples — `cttc-nr-demo`, `cttc-3gpp-channel-simple-ran`, `cttc-lena-simple` — that researchers and network engineers use to evaluate 5G scenarios. But when you run these examples, you get tab-separated text files. Sixteen columns of numbers. No way to immediately understand what happened, where the bottleneck was, which UE was underserved, or how the handover affected throughput.

NetAnim exists but has no knowledge of NR-specific PHY metrics. The 3D NetSimulyzer is a separate install. There is no lightweight, Python-based solution a researcher can run immediately after a simulation to understand their results.

I read through the ns-3 mailing list discussions and the 5G-LENA NR source code before writing this proposal. I then built a working proof-of-concept toolkit before writing a single word here — because I could not write a credible proposal without first understanding what parsing `DlRlcStats.txt` and `DlPhySinr.txt` actually involves at the code level. The toolkit exists, runs, and produces useful output. This proposal is a plan to turn that into mergeable, documented, tested ns-3 code.

---

## 3. Contributor Name

Vaibhav Sharma

---

## 4. Contributor Email and GitHub ID

- **Email:** f20212328@pilani.bits-pilani.ac.in
- **GitHub:** [github.com/web1havv](https://github.com/web1havv)

---

## 5. Potential Mentor

Biljana Bojovic (CTTC, ns-3-nr maintainer)

---

## 5a. Patch Requirement

Before writing this proposal I built a working proof-of-concept Python toolkit that parses real ns-3 NR trace files, generates KPI dashboards, animations, and exports structured JSON. The repository serves as my code submission:

**https://github.com/web1havv/ns3-nr-visualization**

The code was written after reading the `NrBearerStatsCalculator` and `PhyStatsCalculator` C++ source directly to understand the exact trace format. It includes a pytest test suite, a generic base parser class, and a DESIGN.md with architecture decision records.

---

## 5b. Why Me?

I did not write this proposal and then go build something. I built something first, ran into the actual problems (undocumented column order, linear-scale SINR with no dB conversion anywhere in the docs, zero-byte epochs during handovers), and then wrote the proposal based on what I found.

I also read Alberto Gallegos' feedback on past visualizer failures in the GSoC Zulip channel and restructured the entire design around those failure modes before submitting — minimal dependencies, a generic base parser reusable across ns-3 modules, isolated column schemas so ns-3 format changes require one-line fixes.

My day job at Bolna AI is building systems that have to stay running and stay maintainable. That is a different problem than writing a GSoC demo. I am applying here because I want to build something that researchers are still using three years from now, not something that breaks on the next ns-3 release.

---

## 6. Personal Background

I am a final-year undergraduate at BITS Pilani, Pilani Campus (B.E. Computer Science).

I currently intern as an SDE at **Bolna AI (YC)**, building backend infrastructure for real-time AI voice agents — session routing, async task queues, concurrent call handling. It is the kind of work where you think constantly about where things run and what happens when they fail. That mindset is directly what this project needs: a visualizer that survives ns-3 changes and stays maintainable long after GSoC ends.

Before Bolna, I was a Research Intern at **Dubverse** working on ML pipeline tooling, and an SDE at **Bachatt** and **Rupeedlo** on backend systems in Python and Go.

I ranked **48th out of 70,000+ participants** in the Amazon ML Challenge in both 2024 and 2025, and received a Pre-Placement Interview offer for Applied Scientist at Amazon off the back of that.

On the technical side: Python is my primary language (pandas, matplotlib, numpy, ipywidgets, pytest, scipy). I have working knowledge of C++ sufficient to write and test a small ns-3 helper class. I am comfortable with Git, GitLab merge requests, and open-source contribution workflows.

---

## 7. Pre-GSoC Work

Before writing this proposal I read the CTTC 5G-LENA NR module source, traced the column definitions in `NrBearerStatsCalculator` and `PhyStatsCalculator`, and built a working visualization toolkit.

**What I found in the NR module source:**

`nr-bearer-stats-calculator.cc` writes tab-separated rows with 18 columns per epoch: start time, end time, cellId, IMSI, RNTI, LCID, nTxPDUs, TxBytes, nRxPDUs, RxBytes, and four each of delay and PDU size statistics. The column order is not documented anywhere except in the source. A researcher who does not read the C++ cannot reliably parse their own output.

`phy-stats-calculator.cc` writes SINR traces with 6 columns: time, cellId, IMSI, RNTI, sinrLinear, componentCarrierId. The SINR value is in linear scale — to get dB you need `10 * log10(sinrLinear)`, which is also nowhere in the docs.

**What I built as a result:**

- `ns3_nr_parser.py` — parses all four trace files into typed pandas DataFrames, handles the linear→dB SINR conversion, computes derived metrics (packet loss %, per-UE throughput in Mbps, MCS estimate from SINR), and exposes `compute_jains_fairness()` and `compute_cell_stats()`
- `visualize_nr.py` — 8-panel static KPI dashboard: network topology, per-UE DL throughput over time, per-UE SINR over time, cell-aggregate throughput, CDF of throughput, Jain's Fairness Index, delay vs. throughput scatter, MCS distribution
- `animate_handover.py` — animated GIF showing UE movement, SINR transitions, and real-time throughput bars across a handover event
- `flow_filter.py` — chainable `NRFlowFilter` API for filtering by IMSI, cellId, LCID, or time window; directly addresses mentor request for flow/packet-ID based debugging
- `json_exporter.py` — exports structured JSON (topology, per-UE timelines, cell aggregates, global KPIs) for web dashboards and AI agent consumption
- `kpi_dashboard.py` — advanced KPI panel: PRB utilization heatmap, CQI evolution, HARQ retransmission analysis, two-run parameter comparison, handover event log
- `netsimulyzer_bridge.py` — exports to NetSimulyzer-compatible JSON format so results can also be viewed in the 3D visualizer
- `report_generator.py` — self-contained HTML report + structured JSON observation interface for LLM/agentic AI systems
- `realtime_dashboard.py` — file-watch based live dashboard (polls trace files, updates FuncAnimation) for monitoring while the simulation runs
- `netanim_parser.py` — parses NetAnim XML and overlays NR-specific KPI data on top of node trajectories
- `multi_run_ci.py` — N-run statistical confidence interval ribbons + Welch t-test for comparing configurations
- `sem_integration.py` — SEM (Simulation Execution Manager) campaign template + parameter sweep visualization
- `style_checker.py` — generates `.clang-format` matching ns-3 coding style and PEP-8 compliance report
- `run_all.py` — single CLI command that runs the full pipeline
- `tests/test_parser.py` — pytest suite covering parser correctness, filter behavior, statistical functions, and MCS mapping monotonicity

Code: [github.com/web1havv/ns3-nr-visualization](https://github.com/web1havv/ns3-nr-visualization)

The prototype runs on synthetic trace data that exactly matches the format produced by the real ns-3 NR module. Every column header, every unit, every edge case (handover mid-epoch, zero-byte epochs) was verified against the `nr-bearer-stats-calculator.cc` source.

---

## 8. Project Goals

- A Python parser library that correctly reads all four NR trace file types, with documented column semantics and unit conversions
- A static KPI dashboard covering the metrics researchers actually care about: throughput, SINR, delay, packet loss, PRB utilization, CQI, HARQ, Jain's Fairness Index
- An animated handover visualization showing UE trajectory, serving cell changes, and SINR/throughput impact
- An interactive Jupyter notebook with `ipywidgets` sliders for time-window and UE selection
- A structured JSON export usable by web dashboards, external tools, and AI agents
- A NetSimulyzer bridge so existing 3D visualizer users are not left out
- A real-time file-watch dashboard for live monitoring during simulation runs
- A C++ trace sink helper (in ns-3-nr) that enables easier collection of KPI data without manual file parsing
- Tests, Doxygen-compatible documentation, and ns-3 coding style compliance throughout
- A wiki page tracking milestones and deliverables per the ns-3 contributor guide
- All MRs submitted to the CTTC LENA NR module repository (`gitlab.com/cttc-lena/nr`), not ns-3-dev, per the project's merge path

---

## 9. Project Schedule

### 9.1 Community Bonding Period (May 8 – May 25)

I want to use this time to align on scope before writing any production code.

The two things I do not know yet: which KPIs the mentor considers most important for the first milestone, and whether the output should be a standalone Python package or integrated directly into the ns-3-nr `tools/` directory (the way `animate-beamforming.py` is). Both decisions affect the file layout of every subsequent week.

Plan for community bonding:
- Sync with Biljana Bojovic to finalise the set of KPIs for Milestone 1 and the preferred integration path (standalone vs. ns-3-nr `tools/`)
- Run the existing NR examples (`cttc-nr-demo`, `cttc-3gpp-channel-simple-ran`) on a real ns-3 build and validate the prototype parser against real output files
- Set up the GitLab fork, CI, and submit the first draft MR for mentor review
- Write one architecture decision record: JSON export schema design (why this schema, what it supports, what it explicitly does not try to do)

---

### 9.2 Development Phase

**Week 1 — Parser hardening and test baseline**

The prototype parser works but needs to be production-quality before anything else depends on it.

- Lock column definitions against a real ns-3 build (not synthetic data)
- Add graceful error handling for malformed rows, missing files, and zero-row epochs
- Complete pytest suite: column presence, type correctness, value bounds, monotonicity, edge cases
- Write Doxygen-compatible docstrings for every public function
- MR 1 target: `ns3_nr_parser.py` + `tests/test_parser.py`
- Deliverables: parser locked, 100% test coverage on parser module

---

**Week 2 — Core static KPI dashboard**

- `visualize_nr.py`: 8-panel figure, publication-quality styling, correct units on every axis
- Support for both DL and UL simultaneously
- Cell-aggregate view alongside per-UE view
- Configurable output resolution and format (PNG, PDF)
- MR 2 target: `visualize_nr.py` + example output
- Deliverables: static dashboard, usable as `python visualize_nr.py --dl DlRlcStats.txt --sinr DlPhySinr.txt`

---

**Week 3 — Handover animation**

- `animate_handover.py`: frame-by-frame UE position + SINR + throughput, handover event marker
- Auto-detection of handover events from cellId change in RLC traces
- GIF and MP4 output (pillow for GIF, matplotlib FFMpeg writer for MP4)
- MR 3 target: `animate_handover.py`
- Deliverables: animation script, documented parameters, sample output

---

**Week 4 — Flow-ID filter engine + JSON export**

- `flow_filter.py`: chainable `NRFlowFilter` by IMSI, cellId, LCID, time window; directly addresses mentor's debugging request
- `json_exporter.py`: structured JSON schema covering topology, per-UE timelines, cell aggregates, and global KPIs; versioned schema for forward compatibility
- MR 4 target: both modules + integration tests
- Deliverables: filter API + JSON export, validated against NetSimulyzer and web consumer expectations

---

**Week 5 — Interactive Jupyter notebook**

- `ns3_nr_dashboard.ipynb`: ipywidgets sliders for time window, UE selection, metric choice
- Runs on JupyterLab and Google Colab without modification
- All plots regenerate on slider change without rerunning the whole notebook
- MR 5 target: notebook + requirements.txt
- Deliverables: interactive notebook, installable dependencies, usage instructions in README

---

**Week 6 — Advanced KPI panel + NetSimulyzer bridge**

- `kpi_dashboard.py`: PRB utilization heatmap, CQI evolution per UE, HARQ retransmission rate, two-run comparison, handover event log
- `netsimulyzer_bridge.py`: export to NetSimulyzer JSON format so results can be viewed in the 3D visualizer without re-running the simulation
- MR 6 target: both modules
- Deliverables: 5-panel advanced dashboard, NetSimulyzer JSON output validated against the NetSimulyzer schema

---

**Week 7 — Real-time file-watch dashboard**

- `realtime_dashboard.py`: polls trace files every N ms, detects new rows appended by ns-3's `FlushData()`, updates a live matplotlib figure
- `--watch` mode for live monitoring; static preview mode for testing without a running simulation
- Configurable polling interval and display window
- MR 7 target: `realtime_dashboard.py` + CLI flags
- Deliverables: real-time dashboard, documented `--watch` and `--preview` modes

---

**Week 8 — C++ trace sink helper (ns-3-nr)**

This is the only week with C++ work. The goal is a small helper class in ns-3-nr that makes it easier to connect NR trace sources to the Python visualization layer without manually piping files.

- `NrVisualizationHelper`: wraps `NrBearerStatsCalculator` and `PhyStatsCalculator`, sets default output filenames consistent with the Python parser's expectations, and optionally writes a `topology.json` sidecar from the installed node positions
- Follow ns-3 coding style exactly: clang-format, Doxygen, test case
- MR 8 target: C++ helper + example updated to use it
- Deliverables: helper class, one example updated, test case passing

---

**Week 9 — SEM integration + multi-run statistics**

- `sem_integration.py`: SEM campaign template for parameter sweeps over numUes, numerology, bandwidth; auto-parses SEM result DataFrames into the visualization pipeline
- `multi_run_ci.py`: N-run confidence interval ribbons + Welch t-test for comparing two configurations
- MR 9 target: both modules + SEM campaign example
- Deliverables: SEM integration documented, statistical comparison plot in README

---

**Week 10 — Documentation, wiki, and final cleanup**

- Complete Doxygen for all public symbols
- ns-3 wiki page: project goals, design decisions, deliverables checklist, usage examples
- Weekly report archive on ns-developers mailing list
- `run_all.py` CLI tested on a clean environment
- Address all MR review comments
- MR 10 target: documentation-only MR, wiki page published
- Deliverables: complete docs, wiki page live, all MRs merged or in final review

---

### 9.3 Project Completion

By the end of Week 10:

- Python parser library handling all four NR trace file types with documented semantics
- Static 8-panel KPI dashboard + 5-panel advanced KPI dashboard
- Handover animation (GIF + MP4)
- Interactive Jupyter notebook with ipywidgets
- Flow-ID filter engine + structured JSON export
- NetSimulyzer bridge
- Real-time file-watch dashboard
- C++ `NrVisualizationHelper` in ns-3-nr
- SEM campaign template + multi-run CI ribbons
- pytest suite with 90%+ coverage
- Doxygen documentation for all public API
- ns-3 wiki page tracking milestones

---

## 10. Approach

**Python-first, no Qt.** The mentor explicitly ruled out Qt-based solutions in mailing list discussions. All visualization is matplotlib + ipywidgets — libraries a researcher already has. No Qt, no Electron, no compiled extensions.

**Minimal dependencies — core runs on 3 packages.** `matplotlib`, `numpy`, `pandas`. These are mature, BSD-licensed, and already used in the ns-3 documentation. `ipywidgets`, `jupyterlab`, and `pillow` are optional extras. This directly addresses the failure mode Alberto Gallegos described: *"Too many or hard to maintain dependencies."*

**Generic base parser — reusable across all ns-3 modules.** The parser is built on `Ns3TraceParser`, a base class that handles any ns-3 tab-separated trace file. Adding WiFi, CSMA, or any future module = one subclass with ~10 lines defining column names. The same visualization functions work unchanged. This directly addresses: *"How much of this visualizer can be re-used to the rest of the ns-3 models?"*

**Column schema isolated per class.** If ns-3 adds, renames, or removes a column from a trace file, only the `COLUMNS` list in one class changes. No parsing logic. No visualization code. This directly addresses: *"How hard would be to maintain? Does every single change in ns-3 require extensive changes to the visualizer?"*

**Each script does exactly one thing.** Parser, filter, visualizer, exporter — all independent. A researcher who only wants the JSON export does not need to import the animation code. This directly addresses: *"Too monolithic — the project is hard to extend, change or reuse."*

**File-based, not intrusive.** The toolkit reads the trace files ns-3 already produces. Researchers do not need to modify their simulation scripts. The C++ helper in Week 8 is an optional convenience, not a requirement.

**Python speed is not a concern here.** Alberto Gallegos raised Python performance as a concern for GUI tools. This toolkit is a post-processing tool — it runs after the simulation ends, not during it. Parsing a 5-second simulation's trace files takes under a second. The simulation itself runs in C++ at full speed, unchanged.

**Split into small MRs.** Each week targets one mergeable unit. No monolithic "Phase 1" PR. This follows Tommaso Pecorella's explicit advice in the GSoC Zulip channel and makes review tractable.

**JSON schema for interoperability.** The structured JSON export addresses mentor interest in a "generic approach" usable by web dashboards and AI agents, as discussed in the ns-3-nr mailing list.

**Tests and style from Week 1.** The ns-3 contributor guide requires tests and coding-style compliance. I am not treating these as Week 10 polish — they are part of every MR from the start.

---

## 11. User-Visible Changes

After this project, a researcher running `cttc-nr-demo` can immediately do:

```python
from ns3_nr_parser import load_rlc_stats, load_sinr_stats
dl = load_rlc_stats("DlRlcStats.txt")
sinr = load_sinr_stats("DlPhySinr.txt")
```

Or from the command line:

```bash
python visualize_nr.py --dl DlRlcStats.txt --sinr DlPhySinr.txt --out dashboard.png
python animate_handover.py --dl DlRlcStats.txt --sinr DlPhySinr.txt --out handover.gif
python run_all.py --skip-generate   # full pipeline on existing traces
```

Or in Jupyter:

```python
# Interactive sliders for time window, UE selection, metric choice
# All plots update on slider change
```

The C++ side:

```cpp
NrVisualizationHelper vizHelper;
vizHelper.AttachToNrHelper(nrHelper);
vizHelper.SetOutputDirectory("results/");
// Automatically writes DlRlcStats.txt, UlRlcStats.txt,
// DlPhySinr.txt, UlPhySinr.txt, topology.json
```

---

## 12. Test Plan

- **Parser tests:** column presence, correct types, SINR linear→dB, MCS monotonicity, packet loss bounds, per-UE time monotonicity — run via `pytest tests/`
- **Filter tests:** by IMSI, cellId, LCID, time window, chained filters, empty-filter guard
- **Statistics tests:** Jain's Fairness Index bounded [0,1], cell stats shape and positivity
- **C++ test:** `NrVisualizationHelper` builds, attaches to `NrHelper`, writes expected output files — run via ns-3 test framework
- **End-to-end test:** generate synthetic traces → parse → filter → export JSON → validate JSON schema — single `pytest` call covers the full pipeline
- All tests run in CI on every MR

---

## 13. Planned GSoC Work Hours

**Project size:** Medium, 175 hours, ~18 hours/week over 10 weeks

I am in IST (UTC+5:30). Working window: 7 AM–1 PM IST for focused coding, 7–10 PM IST for reviews and async. The morning window overlaps with CEST afternoon (Biljana Bojovic is at CTTC, Barcelona) for synchronous questions.

I will commit daily, open a draft MR for each week's deliverable, and post weekly progress updates to the ns-developers mailing list per the ns-3 contributor guide.

---

## 14. Planned Absence and Commitments

- BITS Pilani end-semester exams end in late April. GSoC coding starts May 25. No overlap.
- Bolna AI internship is part-time during semester, ends before the coding period. Fully available during GSoC.
- No planned vacations. Will flag anything unavoidable at least two weeks ahead.

---

## 15. Skill Set

**Languages:** Python (primary), C++ (working knowledge sufficient for ns-3 helper class)

**Python stack:** pandas, matplotlib, numpy, ipywidgets, jupyterlab, pillow, pytest, scipy (no plotly — deliberately removed to keep core deps minimal)

**C++:** Familiar with ns-3 coding style, clang-format, Doxygen; read the 5G-LENA NR source for this project

**Open source:** Active GitHub contributor; studied ns-3 codebase (NR module, trace calculators, AnimationInterface) before writing this proposal

**Pre-GSoC proof-of-concept:** [github.com/web1havv/ns3-nr-visualization](https://github.com/web1havv/ns3-nr-visualization)

---

## 16. Code of Conduct

I acknowledge that during the project I will follow the general ns-3 policies available at [https://www.nsnam.org/about/governance/policies/](https://www.nsnam.org/about/governance/policies/).

**AI use disclosure:** I used AI coding tools as assistants while writing Python scripts in the proof-of-concept repository. I am the principal driver of all technical decisions, architecture choices, and the research into the ns-3 NR source code. I understand the proposal and the code in full.
