# Architecture Decision Records

This document records the key design decisions for the ns-3 NR Visualization
Toolkit (GSoC 2026). Each decision documents what was chosen, what was
rejected, and why — so future maintainers can challenge or update them.

---

## ADR-1: Core Dependencies — matplotlib + numpy + pandas only

**Decision:** The core toolkit requires exactly three libraries.

**Rejected alternatives:**
- **plotly** — richer interactivity but adds a 30 MB dependency with frequent
  breaking API changes between major versions. Replaced with matplotlib for
  all static output. Available as an optional extra for users who want it.
- **Qt / PyQt5** — mentioned by mentor Biljana Bojovic as explicitly out of
  scope. Requires compiled binaries, breaks on headless servers.
- **bokeh / altair** — beautiful but obscure in the ns-3 community. Adds
  maintenance burden for whoever has to review PRs.

**Rationale:** A researcher who just ran `cttc-nr-demo` can get a dashboard
with `pip install matplotlib numpy pandas`. Three stable, BSD-licensed
libraries with no known compatibility issues among them.

---

## ADR-2: Generic Base Parser — not NR-specific

**Decision:** `Ns3TraceParser` is a base class that any ns-3 module can
subclass to get a working parser with ~10 lines.

**Rejected alternatives:**
- **NR-only hard-coded parser** — fast to write, impossible to maintain or
  reuse. Every new module needs a new parser from scratch.
- **Auto-detect columns from file headers** — ns-3 trace files use `%`
  comment headers with inconsistent formatting. Parsing them reliably is
  harder than maintaining a `COLUMNS` list.

**Rationale:** Alberto Gallegos raised "how much of this can be reused across
ns-3 models?" as an explicit requirement. The base class answers this. The
NR parsers are 10-line subclasses. LTE parsers are aliases (same format).
Future WiFi/CSMA parsers need one class each.

---

## ADR-3: Column Schema Isolation

**Decision:** Each parser class has a `COLUMNS` list as the single source of
truth for column names, types, units, and descriptions.

**Rejected alternatives:**
- **Positional parsing with magic indices** — `parts[7]` means nothing to
  a reviewer. Breaks silently if ns-3 inserts a new column.
- **Regex-based header parsing** — fragile against whitespace changes in
  ns-3's comment headers.

**Rationale:** When ns-3 changes a trace format (it does, every few
releases), only the `COLUMNS` list changes. The parsing loop, the DataFrame
construction, and the visualization functions are unchanged. This was the
specific failure mode of past ns-3 visualizers.

---

## ADR-4: File-Based, Not Simulation-Coupled

**Decision:** The toolkit reads files ns-3 already produces. It does not
hook into ns-3's C++ event system or require modifying simulation scripts.

**Rejected alternatives:**
- **ns-3 Python binding hooks** — would require the toolkit to be compiled
  with ns-3, breaking on every ns-3 API change.
- **Named pipes / sockets** — complex setup, requires a running simulation.
  Researchers often want to visualize old results.

**Rationale:** A researcher can run `cttc-nr-demo`, then run
`python visualize_nr.py` on the output files, with no coupling between the
two. The optional C++ `NrVisualizationHelper` (Week 8 deliverable) is a
convenience wrapper, not a requirement.

**Exception:** `realtime_dashboard.py` polls files every N ms for live
monitoring. This is file-based too — it does not connect to the simulation
process.

---

## ADR-5: One Script, One Responsibility

**Decision:** Each Python file does exactly one thing. No script imports
more than the files it directly depends on.

**Rejected alternatives:**
- **Single monolithic `visualize.py`** — easier for a demo, impossible to
  extend. A researcher who only wants JSON export should not need to install
  animation dependencies.

**Rationale:** Tommaso Pecorella's advice in GSoC Zulip: *"Split your planned
contributions in multiple, self-included steps, each leading to a MR."*
Applied to code structure as well: each script is independently reviewable,
testable, and mergeable.

---

## ADR-6: pytest, Not ns-3 Test Framework

**Decision:** The Python toolkit uses `pytest` for its tests. The C++
`NrVisualizationHelper` uses the ns-3 test framework.

**Rationale:** pytest is the standard for Python projects. The ns-3 test
framework is for C++. Mixing them would require running Python tests through
`./ns3 run`, which is slow and unnecessary.

---

## What This Project Will NOT Do

- Attempt to visualize every ns-3 module in one GSoC — the generic parser
  makes future extension easy, but scope is NR first.
- Replace NetSimulyzer — the bridge module exports compatible JSON so both
  tools coexist.
- Require any changes to ns-3 core — all changes are in ns-3-nr only.
- Maintain a compiled GUI — all output is files (PNG, GIF, JSON, HTML).
