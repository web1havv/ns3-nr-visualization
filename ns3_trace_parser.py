"""
ns3_trace_parser.py — Generic ns-3 Trace File Parser
======================================================
Addresses mentor feedback (Alberto Gallegos, GSoC 2026):
  "How much of this visualizer can be re-used to the rest of the ns-3 models?"

Design principle:
  This base class handles the generic parts of ANY ns-3 tab-separated trace
  file (comment stripping, column mapping, type casting, unit conversion).
  Module-specific parsers (NR, LTE, WiFi, CSMA) subclass it and only define
  their column schema — they do not rewrite any parsing logic.

  Adding support for a new ns-3 module means adding ~10 lines: a subclass
  with a COLUMNS dict. Nothing else changes.

Supported out of the box:
  - NrBearerStatsCalculator  (5G NR RLC stats)
  - PhyStatsCalculator        (5G NR PHY SINR)
  - LteStatsCalculator        (LTE RLC stats — same format as NR)
  - RadioBearerStatsCalculator (LTE/NR generic)

Easily extensible to:
  - WiFi EDCA queue stats
  - CSMA channel utilization traces
  - TCP socket throughput traces
  - Any future ns-3 module trace
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import numpy as np
import pandas as pd


# ─── Column Schema Type ───────────────────────────────────────────────────────

class ColDef:
    """Definition for a single column in an ns-3 trace file."""

    def __init__(self, name: str, dtype: type = float,
                 unit: Optional[str] = None,
                 transform=None, description: str = ""):
        self.name        = name        # output column name (snake_case)
        self.dtype       = dtype       # int, float, str
        self.unit        = unit        # display unit (for axis labels)
        self.transform   = transform   # optional callable: raw_value → final_value
        self.description = description # human-readable description


# ─── Generic Base Parser ──────────────────────────────────────────────────────

class Ns3TraceParser:
    """
    Base class for all ns-3 tab-separated trace file parsers.

    Subclass this and define COLUMNS to support any ns-3 module.
    The parsing, type casting, and unit conversion are handled here.

    Maintenance guarantee:
      If ns-3 adds a new column to a trace file, update COLUMNS in the
      subclass only. No other code changes. If a column is removed, mark
      it with dtype=None and it will be silently dropped.

    Usage::

        df = NrRlcStatsParser.from_file("DlRlcStats.txt")
        df = LteRlcStatsParser.from_file("DlRlcStats.txt")  # same call
    """

    # Subclasses must define this: ordered list of ColDef matching trace columns
    COLUMNS: list[ColDef] = []

    # Character that marks comment lines (ns-3 uses '%' for header rows)
    COMMENT_CHAR = "%"

    @classmethod
    def from_file(cls, path: str | Path) -> pd.DataFrame:
        """
        Parse a trace file and return a typed DataFrame.

        Raises FileNotFoundError if the file does not exist.
        Skips malformed rows with a warning (does not crash).
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Trace file not found: {path}")

        if not cls.COLUMNS:
            raise NotImplementedError(
                f"{cls.__name__} must define a COLUMNS list"
            )

        rows = []
        with open(path) as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith(cls.COMMENT_CHAR):
                    continue
                parts = line.split("\t")
                if len(parts) < len(cls.COLUMNS):
                    # tolerate extra columns from future ns-3 versions
                    continue
                row = {}
                try:
                    for i, col in enumerate(cls.COLUMNS):
                        if col.dtype is None:
                            continue  # dropped column
                        raw = col.dtype(parts[i])
                        row[col.name] = col.transform(raw) if col.transform else raw
                except (ValueError, IndexError):
                    continue  # skip malformed rows silently
                rows.append(row)

        if not rows:
            return pd.DataFrame(columns=[c.name for c in cls.COLUMNS if c.dtype])

        return pd.DataFrame(rows)

    @classmethod
    def column_units(cls) -> dict[str, str]:
        """Return {column_name: unit_string} for axis label generation."""
        return {c.name: c.unit for c in cls.COLUMNS if c.unit}

    @classmethod
    def column_descriptions(cls) -> dict[str, str]:
        """Return {column_name: description} for documentation."""
        return {c.name: c.description for c in cls.COLUMNS if c.description}


# ─── NR / LTE RLC Stats Parser ────────────────────────────────────────────────

def _bytes_to_mbps(raw_bytes: int, epoch_s: float = 0.1) -> float:
    """Convert byte count over one epoch to Mbps. Epoch = 100 ms default."""
    return (raw_bytes * 8) / (epoch_s * 1e6)


class NrRlcStatsParser(Ns3TraceParser):
    """
    Parser for NrBearerStatsCalculator output (DlRlcStats.txt, UlRlcStats.txt).
    Also works unchanged for LTE RadioBearerStatsCalculator (same format).

    Column order from nr-bearer-stats-calculator.cc::
      start end cellId IMSI RNTI LCID nTxPDUs TxBytes nRxPDUs RxBytes
      delay_mean delay_min delay_max delay_std
      pduSize_mean pduSize_min pduSize_max pduSize_std
    """
    COLUMNS = [
        ColDef("start_time",     float, "s",   description="Epoch start time"),
        ColDef("end_time",       float, "s",   description="Epoch end time"),
        ColDef("cellId",         int,   None,  description="Serving cell ID"),
        ColDef("IMSI",           int,   None,  description="UE identity"),
        ColDef("RNTI",           int,   None,  description="Radio network temp ID"),
        ColDef("LCID",           int,   None,  description="Logical channel ID"),
        ColDef("nTxPDUs",        int,   None,  description="TX PDU count"),
        ColDef("TxBytes",        int,   "B",   description="Transmitted bytes"),
        ColDef("nRxPDUs",        int,   None,  description="RX PDU count"),
        ColDef("RxBytes",        int,   "B",   description="Received bytes"),
        ColDef("delay_mean",     float, "s",   description="Mean PDU delay"),
        ColDef("delay_min",      float, "s",   description="Min PDU delay"),
        ColDef("delay_max",      float, "s",   description="Max PDU delay"),
        ColDef("delay_std",      float, "s",   description="Std dev PDU delay"),
        ColDef("pduSize_mean",   float, "B",   description="Mean PDU size"),
        ColDef("pduSize_min",    float, "B",   description="Min PDU size"),
        ColDef("pduSize_max",    float, "B",   description="Max PDU size"),
        ColDef("pduSize_std",    float, "B",   description="Std dev PDU size"),
    ]

    @classmethod
    def from_file(cls, path: str | Path) -> pd.DataFrame:
        df = super().from_file(path)
        if df.empty:
            return df
        epoch = df["end_time"] - df["start_time"]
        epoch = epoch.replace(0, 0.1)  # guard against zero-length epochs
        df["DL_throughput_mbps"] = (df["RxBytes"] * 8) / (epoch * 1e6)
        df["packet_loss_pct"]    = np.where(
            df["nTxPDUs"] > 0,
            100.0 * (df["nTxPDUs"] - df["nRxPDUs"]) / df["nTxPDUs"],
            0.0,
        )
        df["delay_ms"] = df["delay_mean"] * 1000.0
        return df


# ─── NR / LTE PHY SINR Parser ─────────────────────────────────────────────────

def _linear_to_db(x: float) -> float:
    """Convert linear SINR to dB. Clips negative/zero to -50 dB."""
    return float(10.0 * np.log10(max(x, 1e-5)))


def _sinr_to_mcs(sinr_db: float) -> int:
    """
    Estimate MCS index from SINR using 3GPP CQI table (TS 36.213 Table 7.2.3-1).
    Returns MCS in [0, 28]. Monotone: higher SINR → higher MCS.
    """
    thresholds = [-6.7, -4.7, -2.3, 0.2, 2.4, 4.3, 5.9, 8.1, 10.3,
                  11.7, 14.1, 16.3, 18.7, 21.0, 22.7, 24.0, 25.5, 27.0, 28.0]
    for mcs, t in enumerate(thresholds):
        if sinr_db < t:
            return mcs
    return 28


class NrPhySinrParser(Ns3TraceParser):
    """
    Parser for PhyStatsCalculator output (DlPhySinr.txt, UlPhySinr.txt).
    Also works for LTE PhyStatsCalculator (same format).

    Column order from phy-stats-calculator.cc::
      time cellId IMSI RNTI sinrLinear componentCarrierId
    """
    COLUMNS = [
        ColDef("time",               float, "s",  description="Measurement time"),
        ColDef("cellId",             int,   None, description="Serving cell ID"),
        ColDef("IMSI",               int,   None, description="UE identity"),
        ColDef("RNTI",               int,   None, description="Radio network temp ID"),
        ColDef("sinrLinear",         float, None, description="SINR in linear scale"),
        ColDef("componentCarrierId", int,   None, description="Component carrier index"),
    ]

    @classmethod
    def from_file(cls, path: str | Path) -> pd.DataFrame:
        df = super().from_file(path)
        if df.empty:
            return df
        df["sinr_dB"] = df["sinrLinear"].apply(_linear_to_db)
        df["mcs"]     = df["sinr_dB"].apply(_sinr_to_mcs)
        return df


# ─── LTE alias (same format, different class name for clarity) ────────────────

LteRlcStatsParser  = NrRlcStatsParser   # identical format
LtePhySinrParser   = NrPhySinrParser    # identical format


# ─── Convenience factory (auto-detects format from filename) ──────────────────

_FORMAT_MAP = {
    "dlrlcstats":  NrRlcStatsParser,
    "ulrlcstats":  NrRlcStatsParser,
    "dlphysinr":   NrPhySinrParser,
    "ulphysinr":   NrPhySinrParser,
}


def auto_parse(path: str | Path) -> pd.DataFrame:
    """
    Auto-detect trace type from filename and parse.

    Supports: DlRlcStats.txt, UlRlcStats.txt, DlPhySinr.txt, UlPhySinr.txt
    (case-insensitive, any prefix/suffix).
    """
    stem = Path(path).stem.lower().replace("-", "").replace("_", "")
    for key, parser in _FORMAT_MAP.items():
        if key in stem:
            return parser.from_file(path)
    raise ValueError(
        f"Cannot auto-detect trace type from filename: {path}\n"
        f"Supported stems: {list(_FORMAT_MAP.keys())}"
    )


if __name__ == "__main__":
    # Demo: show column docs for each parser
    for cls in [NrRlcStatsParser, NrPhySinrParser]:
        print(f"\n{cls.__name__}:")
        for name, desc in cls.column_descriptions().items():
            unit = cls.column_units().get(name, "—")
            print(f"  {name:<22} [{unit:<4}]  {desc}")
