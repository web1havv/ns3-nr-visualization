#!/usr/bin/env python3
"""
ns3_nr_parser.py — Parser for ns-3 5G NR simulation trace files.

Parses the exact output format produced by:
  - NrBearerStatsCalculator (DlRlcStats.txt, UlRlcStats.txt,
                              DlPdcpStats.txt, UlPdcpStats.txt)
  - LTE/NR PHY stats calculator (DlPhySinr.txt, UlPhySinr.txt)
  - FlowMonitor JSON output

All column names and formats are taken directly from the ns-3 NR source:
  https://gitlab.com/cttc-lena/nr/-/blob/master/helper/nr-bearer-stats-calculator.cc
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path


# ─── RLC / PDCP stats columns (NrBearerStatsCalculator) ─────────────────────
RLC_COLUMNS = [
    "start_time", "end_time", "cellId", "IMSI", "RNTI", "LCID",
    "nTxPDUs", "TxBytes", "nRxPDUs", "RxBytes",
    "delay_mean", "delay_min", "delay_max", "delay_std",
    "pduSize_mean", "pduSize_min", "pduSize_max", "pduSize_std",
]

# ─── PHY SINR columns (phy-stats-calculator) ─────────────────────────────────
SINR_COLUMNS = ["time", "cellId", "IMSI", "RNTI", "sinrLinear", "ccId"]


def load_rlc_stats(filepath: str) -> pd.DataFrame:
    """
    Load RLC or PDCP stats file produced by NrBearerStatsCalculator.

    The file uses tab-separated values with a comment header line starting
    with '% start' matching the format written by WriteUlResults/WriteDlResults.
    """
    df = pd.read_csv(
        filepath,
        sep="\t",
        comment="%",
        header=None,
        names=RLC_COLUMNS,
        dtype={
            "cellId": int, "IMSI": int, "RNTI": int, "LCID": int,
            "nTxPDUs": int, "TxBytes": int, "nRxPDUs": int, "RxBytes": int,
        },
    )
    # Compute derived metrics
    epoch_dur = df["end_time"] - df["start_time"]
    df["DL_throughput_mbps"] = (df["RxBytes"] * 8) / (epoch_dur * 1e6)
    df["packet_loss_pct"] = ((df["nTxPDUs"] - df["nRxPDUs"]) / df["nTxPDUs"] * 100).clip(0, 100)
    df["delay_ms"] = df["delay_mean"] * 1e3
    return df


def load_sinr_stats(filepath: str) -> pd.DataFrame:
    """
    Load PHY SINR stats file.

    Format: time  cellId  IMSI  RNTI  sinrLinear  componentCarrierId
    as written by PhyStatsCalculator::ReportCurrentCellRsrpSinr.
    """
    df = pd.read_csv(
        filepath,
        sep="\t",
        comment="%",
        header=None,
        names=SINR_COLUMNS,
    )
    # Convert linear SINR to dB
    df["sinr_dB"] = 10 * np.log10(df["sinrLinear"].clip(1e-6))
    # Estimate MCS from SINR (3GPP NR CQI mapping approximation)
    df["mcs"] = df["sinr_dB"].apply(_sinr_to_mcs)
    return df


def _sinr_to_mcs(sinr_db: float) -> int:
    """
    Approximate MCS index from SINR (dB) following 3GPP NR CQI table.
    MCS 0-28 for NR (64QAM).
    """
    if sinr_db < -6:   return 0
    if sinr_db < -4:   return 1
    if sinr_db < -2:   return 2
    if sinr_db < 0:    return 3
    if sinr_db < 2:    return 5
    if sinr_db < 4:    return 7
    if sinr_db < 6:    return 9
    if sinr_db < 8:    return 11
    if sinr_db < 10:   return 13
    if sinr_db < 12:   return 16
    if sinr_db < 14:   return 18
    if sinr_db < 16:   return 20
    if sinr_db < 20:   return 22
    if sinr_db < 24:   return 24
    if sinr_db < 28:   return 26
    return 28


def load_topology(filepath: str) -> dict:
    """Load topology JSON (gNB and UE node positions)."""
    with open(filepath) as f:
        return json.load(f)


def load_flow_monitor(filepath: str) -> pd.DataFrame:
    """Load FlowMonitor JSON summary."""
    with open(filepath) as f:
        data = json.load(f)
    return pd.DataFrame(data["flows"])


def compute_cell_stats(dl_rlc: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-cell throughput and fairness metrics."""
    cell_stats = dl_rlc.groupby(["cellId", "start_time"]).agg(
        total_tput_mbps=("DL_throughput_mbps", "sum"),
        n_ues=("IMSI", "nunique"),
        mean_delay_ms=("delay_ms", "mean"),
        mean_loss_pct=("packet_loss_pct", "mean"),
    ).reset_index()
    cell_stats["tput_per_ue_mbps"] = cell_stats["total_tput_mbps"] / cell_stats["n_ues"]
    return cell_stats


def compute_jains_fairness(dl_rlc: pd.DataFrame) -> pd.Series:
    """
    Compute Jain's Fairness Index per time epoch.
    JFI = (sum(x))^2 / (n * sum(x^2))
    """
    def jfi(group):
        x = group["DL_throughput_mbps"].values
        n = len(x)
        if n == 0 or x.sum() == 0:
            return np.nan
        return (x.sum() ** 2) / (n * (x ** 2).sum())

    return dl_rlc.groupby("start_time").apply(jfi)


def print_summary(dl_rlc, ul_rlc, dl_sinr):
    """Print a concise simulation summary."""
    print("=" * 60)
    print("   ns-3 5G NR Simulation Summary")
    print("=" * 60)
    print(f"  UEs tracked : {dl_rlc['IMSI'].nunique()}")
    print(f"  gNBs (cells): {dl_rlc['cellId'].nunique()}")
    print(f"  Sim duration: {dl_rlc['end_time'].max():.1f} s")
    print(f"  Avg DL tput : {dl_rlc['DL_throughput_mbps'].mean():.1f} Mbps/UE")
    print(f"  Avg UL tput : {ul_rlc['DL_throughput_mbps'].mean():.1f} Mbps/UE")
    print(f"  Avg SINR    : {dl_sinr['sinr_dB'].mean():.1f} dB")
    print(f"  Avg delay   : {dl_rlc['delay_ms'].mean():.2f} ms")
    print(f"  Avg loss    : {dl_rlc['packet_loss_pct'].mean():.2f}%")
    jfi = compute_jains_fairness(dl_rlc).mean()
    print(f"  Jain's FI   : {jfi:.4f}  (1.0 = perfect fairness)")
    print("=" * 60)


if __name__ == "__main__":
    data_dir = Path("data")
    dl_rlc  = load_rlc_stats(data_dir / "DlRlcStats.txt")
    ul_rlc  = load_rlc_stats(data_dir / "UlRlcStats.txt")
    dl_sinr = load_sinr_stats(data_dir / "DlPhySinr.txt")
    topo    = load_topology(data_dir / "topology.json")
    flows   = load_flow_monitor(data_dir / "flow_monitor.json")

    print_summary(dl_rlc, ul_rlc, dl_sinr)
