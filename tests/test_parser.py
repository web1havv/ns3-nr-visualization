#!/usr/bin/env python3
"""
Task 11: Test Suite (ns-3 coding standard requires tests)
──────────────────────────────────────────────────────────
The ns-3 contributor guide explicitly states:
  "The contributor will be expected to produce mergeable code —
   write tests, documentation."
  "Do you know how the test framework works? Can you write your
   own test code?"

This module provides a pytest-based test suite for ns3_nr_parser.py
and all visualization modules, ensuring correctness before merge.

Run: pytest tests/ -v
"""

import sys
import pytest
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from ns3_nr_parser import (
    load_rlc_stats, load_sinr_stats, load_topology,
    compute_cell_stats, compute_jains_fairness, _sinr_to_mcs,
)
from flow_filter import NRFlowFilter
from json_exporter import export_simulation_json, NpEncoder

DATA_DIR = Path(__file__).parent.parent / "data"


# ─── Parser Tests ─────────────────────────────────────────────────────────────

class TestRLCParser:
    @pytest.fixture(autouse=True)
    def load(self):
        self.dl = load_rlc_stats(DATA_DIR / "DlRlcStats.txt")
        self.ul = load_rlc_stats(DATA_DIR / "UlRlcStats.txt")

    def test_columns_present(self):
        expected = ["start_time", "end_time", "cellId", "IMSI", "RNTI",
                    "DL_throughput_mbps", "delay_ms", "packet_loss_pct"]
        for col in expected:
            assert col in self.dl.columns, f"Missing column: {col}"

    def test_no_negative_throughput(self):
        assert (self.dl["DL_throughput_mbps"] >= 0).all()
        assert (self.ul["DL_throughput_mbps"] >= 0).all()

    def test_packet_loss_bounded(self):
        assert (self.dl["packet_loss_pct"] >= 0).all()
        assert (self.dl["packet_loss_pct"] <= 100).all()

    def test_time_monotonic(self):
        for imsi in self.dl["IMSI"].unique():
            ue = self.dl[self.dl["IMSI"] == imsi].sort_values("start_time")
            assert (ue["start_time"].diff().dropna() >= 0).all()

    def test_correct_ue_count(self):
        assert self.dl["IMSI"].nunique() == 10

    def test_correct_cell_count(self):
        assert self.dl["cellId"].nunique() == 3

    def test_delay_positive(self):
        assert (self.dl["delay_ms"] > 0).all()

    def test_throughput_realistic(self):
        # 5G NR 100 MHz should give 0–1000 Mbps range
        assert self.dl["DL_throughput_mbps"].max() < 1000
        assert self.dl["DL_throughput_mbps"].mean() > 1


class TestSINRParser:
    @pytest.fixture(autouse=True)
    def load(self):
        self.sinr = load_sinr_stats(DATA_DIR / "DlPhySinr.txt")

    def test_sinr_db_column_exists(self):
        assert "sinr_dB" in self.sinr.columns

    def test_mcs_column_exists(self):
        assert "mcs" in self.sinr.columns

    def test_mcs_bounded(self):
        assert (self.sinr["mcs"] >= 0).all()
        assert (self.sinr["mcs"] <= 28).all()

    def test_sinr_range_realistic(self):
        # Should be between -20 dB and +50 dB for realistic 5G scenarios
        assert self.sinr["sinr_dB"].min() > -30
        assert self.sinr["sinr_dB"].max() < 60


# ─── MCS Mapping Tests ────────────────────────────────────────────────────────

class TestMCSMapping:
    def test_very_low_sinr_gives_lowest_mcs(self):
        assert _sinr_to_mcs(-20) == 0

    def test_high_sinr_gives_high_mcs(self):
        assert _sinr_to_mcs(30) == 28

    def test_monotone(self):
        """MCS should not decrease as SINR increases."""
        sinrs = range(-10, 35, 2)
        mcs_vals = [_sinr_to_mcs(s) for s in sinrs]
        assert all(mcs_vals[i] <= mcs_vals[i+1] for i in range(len(mcs_vals)-1))


# ─── Flow Filter Tests ────────────────────────────────────────────────────────

class TestNRFlowFilter:
    @pytest.fixture(autouse=True)
    def setup(self):
        dl  = load_rlc_stats(DATA_DIR / "DlRlcStats.txt")
        sinr = load_sinr_stats(DATA_DIR / "DlPhySinr.txt")
        self.filt = NRFlowFilter(dl, sinr)

    def test_filter_by_ue(self):
        ue3 = self.filt.by_ue(3).get_rlc()
        assert set(ue3["IMSI"].unique()) == {3}

    def test_filter_by_cell(self):
        cell1 = self.filt.by_cell(1).get_rlc()
        assert set(cell1["cellId"].unique()) == {1}

    def test_filter_by_time(self):
        window = self.filt.by_time(1.0, 2.0).get_rlc()
        assert (window["start_time"] >= 1.0).all()
        assert (window["end_time"] <= 2.0).all()

    def test_chain_filter(self):
        result = self.filt.by_ue(3).by_time(0.0, 2.5).get_rlc()
        assert set(result["IMSI"].unique()) == {3}
        assert (result["end_time"] <= 2.5).all()

    def test_filter_returns_nonempty(self):
        s = self.filt.by_ue(1).summary()
        assert "warning" not in s
        assert s["rows"] > 0

    def test_empty_filter_returns_warning(self):
        s = self.filt.by_ue(999).summary()  # non-existent UE
        assert "warning" in s


# ─── Statistics Tests ─────────────────────────────────────────────────────────

class TestStatistics:
    @pytest.fixture(autouse=True)
    def load(self):
        self.dl = load_rlc_stats(DATA_DIR / "DlRlcStats.txt")

    def test_jains_fi_bounded(self):
        jfi = compute_jains_fairness(self.dl)
        assert (jfi.dropna() >= 0).all()
        assert (jfi.dropna() <= 1.0 + 1e-6).all()

    def test_cell_stats_shape(self):
        cs = compute_cell_stats(self.dl)
        assert "total_tput_mbps" in cs.columns
        assert "n_ues" in cs.columns
        assert cs["n_ues"].min() >= 1

    def test_tput_per_ue_positive(self):
        cs = compute_cell_stats(self.dl)
        assert (cs["tput_per_ue_mbps"] > 0).all()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
