#!/usr/bin/env python3
"""
Generate realistic ns-3 5G NR simulation trace files.

These traces follow the exact format produced by ns-3's NrBearerStatsCalculator
and PHY stats calculator. Format is taken directly from the ns-3 NR module source:
  helper/nr-bearer-stats-calculator.cc
  src/lte/helper/phy-stats-calculator.cc

Columns for RLC/PDCP traces:
  start_time  end_time  cellId  IMSI  RNTI  LCID
  txPackets  txBytes  rxPackets  rxBytes
  delay_mean  delay_min  delay_max  delay_stddev
  pduSize_mean  pduSize_min  pduSize_max  pduSize_stddev

Columns for PHY SINR traces:
  time  cellId  IMSI  RNTI  sinrLinear  componentCarrierId

Usage:
  python3 generate_traces.py
  -> writes DlRlcStats.txt, UlRlcStats.txt, DlPdcpStats.txt, UlPdcpStats.txt,
            DlPhySinr.txt, UlPhySinr.txt, flow_monitor.xml
"""

import numpy as np
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os

np.random.seed(42)

# Simulation parameters
SIM_TIME = 5.0        # seconds
EPOCH = 0.1           # stats epoch duration
N_GNB = 3            # number of gNBs
N_UE = 10            # number of UEs
CENTRAL_FREQ = 3.5e9  # 3.5 GHz (sub-6 GHz 5G NR)
BANDWIDTH = 100e6     # 100 MHz

# UE assignments to gNBs (cell IDs 1,2,3)
ue_cell = {i+1: ((i % N_GNB) + 1) for i in range(N_UE)}  # IMSI -> cellId
ue_rnti = {i+1: (i % 4) + 1 for i in range(N_UE)}        # IMSI -> RNTI

# Base throughput per UE per direction (Mbps) — varies by distance to gNB
base_dl_tput = {i+1: np.random.uniform(20, 150) for i in range(N_UE)}
base_ul_tput = {i+1: np.random.uniform(5, 40) for i in range(N_UE)}


def rlc_stats_row(t_start, t_end, cell_id, imsi, rnti, lcid,
                  tput_mbps, direction="dl"):
    """Generate one row of RLC stats in ns-3 format."""
    epoch_dur = t_end - t_start
    # Add realistic noise to throughput
    noise = np.random.normal(0, 0.05 * tput_mbps)
    actual_tput = max(0, tput_mbps + noise)

    tx_bytes = int(actual_tput * 1e6 * epoch_dur / 8)
    rx_bytes = int(tx_bytes * np.random.uniform(0.95, 1.0))  # small packet loss
    pkt_size = 1460  # typical IP packet
    tx_pkts = max(1, tx_bytes // pkt_size)
    rx_pkts = max(1, rx_bytes // pkt_size)

    delay_mean = np.random.uniform(1e-4, 5e-3)   # seconds
    delay_min  = delay_mean * 0.5
    delay_max  = delay_mean * 3.0
    delay_std  = delay_mean * 0.3

    pdu_mean = pkt_size * np.random.uniform(0.9, 1.1)
    pdu_min  = pdu_mean * 0.5
    pdu_max  = pdu_mean * 1.5
    pdu_std  = pdu_mean * 0.2

    return (f"{t_start:.4f}\t{t_end:.4f}\t{cell_id}\t{imsi}\t{rnti}\t{lcid}\t"
            f"{tx_pkts}\t{tx_bytes}\t{rx_pkts}\t{rx_bytes}\t"
            f"{delay_mean:.6e}\t{delay_min:.6e}\t{delay_max:.6e}\t{delay_std:.6e}\t"
            f"{pdu_mean:.2f}\t{pdu_min:.2f}\t{pdu_max:.2f}\t{pdu_std:.2f}")


def generate_rlc_traces():
    """Generate DL and UL RLC stats files."""
    epochs = np.arange(0, SIM_TIME, EPOCH)
    header = ("% start\tend\tCellId\tIMSI\tRNTI\tLCID\t"
              "nTxPDUs\tTxBytes\tnRxPDUs\tRxBytes\t"
              "DLdelay\tDLdelayMin\tDLdelayMax\tDLdelayStdDev\t"
              "PDUSize\tPDUSizeMin\tPDUSizeMax\tPDUSizeStdDev")

    dl_lines = [header]
    ul_lines = [header]

    # Simulate handover at t=2.5s: UE 3 moves from cell 1 to cell 2
    handover_ue = 3
    handover_t = 2.5

    for t in epochs:
        t_end = round(t + EPOCH, 6)
        for imsi in range(1, N_UE + 1):
            cell_id = ue_cell[imsi]
            rnti = ue_rnti[imsi]

            # Simulate handover: UE 3 moves to cell 2 after t=2.5
            if imsi == handover_ue and t >= handover_t:
                cell_id = 2

            # Simulate mobility: throughput degrades then recovers
            t_factor = 1.0
            if imsi % 3 == 0:  # moving UEs
                t_factor = 0.7 + 0.3 * np.sin(2 * np.pi * t / SIM_TIME)

            # Brief outage during handover
            if imsi == handover_ue and abs(t - handover_t) < 0.2:
                t_factor = 0.1

            dl_row = rlc_stats_row(round(t, 6), t_end, cell_id, imsi, rnti, 3,
                                   base_dl_tput[imsi] * t_factor, "dl")
            ul_row = rlc_stats_row(round(t, 6), t_end, cell_id, imsi, rnti, 3,
                                   base_ul_tput[imsi] * t_factor, "ul")
            dl_lines.append(dl_row)
            ul_lines.append(ul_row)

    with open("data/DlRlcStats.txt", "w") as f:
        f.write("\n".join(dl_lines))
    with open("data/UlRlcStats.txt", "w") as f:
        f.write("\n".join(ul_lines))

    print("✓ Generated DlRlcStats.txt and UlRlcStats.txt")


def generate_sinr_traces():
    """Generate PHY SINR trace files (format from phy-stats-calculator.cc)."""
    # % time  cellId  IMSI  RNTI  sinrLinear  componentCarrierId
    header_sinr = "% time\tcellId\tIMSI\tRNTI\tsinrLinear\tcomponentCarrierId"

    dl_sinr = [header_sinr]
    ul_sinr = [header_sinr]

    # SINR for each UE based on distance to gNB — 5G NR typical range 0 dB to 30 dB
    base_sinr_db = {i+1: np.random.uniform(5, 30) for i in range(N_UE)}

    t = 0.0
    report_interval = 0.01  # 10ms SINR reporting
    handover_ue = 3
    handover_t = 2.5

    while t < SIM_TIME:
        for imsi in range(1, N_UE + 1):
            cell_id = ue_cell[imsi]
            rnti = ue_rnti[imsi]

            if imsi == handover_ue and t >= handover_t:
                cell_id = 2

            # SINR varies with time (mobility, shadowing)
            sinr_db = base_sinr_db[imsi]
            sinr_db += np.random.normal(0, 2)       # fast fading
            sinr_db += 3 * np.sin(2 * np.pi * t)    # slow fading / mobility

            # Handover dip
            if imsi == handover_ue and abs(t - handover_t) < 0.2:
                sinr_db -= 15

            sinr_linear = 10 ** (sinr_db / 10)
            sinr_linear = max(0.01, sinr_linear)

            cc_id = 0  # component carrier 0
            dl_sinr.append(f"{t:.4f}\t{cell_id}\t{imsi}\t{rnti}\t{sinr_linear:.4f}\t{cc_id}")
            ul_sinr.append(f"{t:.4f}\t{cell_id}\t{imsi}\t{rnti}\t{sinr_linear*0.7:.4f}\t{cc_id}")

        t = round(t + report_interval, 6)

    with open("data/DlPhySinr.txt", "w") as f:
        f.write("\n".join(dl_sinr))
    with open("data/UlPhySinr.txt", "w") as f:
        f.write("\n".join(ul_sinr))

    print("✓ Generated DlPhySinr.txt and UlPhySinr.txt")


def generate_topology():
    """Generate node positions for topology visualization."""
    import json

    # gNB positions in meters (hexagonal layout)
    gnb_positions = [
        {"id": 1, "x": 0.0,   "y": 0.0,    "type": "gNB"},
        {"id": 2, "x": 500.0, "y": 0.0,    "type": "gNB"},
        {"id": 3, "x": 250.0, "y": 433.0,  "type": "gNB"},
    ]

    # UE positions — randomly distributed in coverage area
    ue_positions = []
    for i in range(N_UE):
        # Assign UE near its serving gNB
        gnb = gnb_positions[i % N_GNB]
        angle = np.random.uniform(0, 2*np.pi)
        dist  = np.random.uniform(50, 200)
        pos = {
            "id": i + 1,
            "x": round(gnb["x"] + dist * np.cos(angle), 2),
            "y": round(gnb["y"] + dist * np.sin(angle), 2),
            "type": "UE",
            "serving_gnb": gnb["id"]
        }
        ue_positions.append(pos)

    topology = {
        "gnbs": gnb_positions,
        "ues": ue_positions,
        "sim_time": SIM_TIME,
        "n_gnb": N_GNB,
        "n_ue": N_UE,
        "freq_ghz": CENTRAL_FREQ / 1e9,
        "bw_mhz": BANDWIDTH / 1e6,
    }

    with open("data/topology.json", "w") as f:
        import json
        json.dump(topology, f, indent=2)

    print("✓ Generated topology.json")


def generate_flowmonitor():
    """Generate a FlowMonitor-style XML summary."""
    flows = []
    for imsi in range(1, N_UE + 1):
        tput = base_dl_tput[imsi] * 1e6  # bits/s
        flows.append({
            "flowId": imsi,
            "sourceAddress": f"10.1.{imsi}.2",
            "destinationAddress": f"7.0.0.{imsi}",
            "protocol": "17",  # UDP
            "txBytes": int(tput * SIM_TIME / 8),
            "rxBytes": int(tput * SIM_TIME / 8 * 0.98),
            "txPackets": int(tput * SIM_TIME / 8 / 1460),
            "rxPackets": int(tput * SIM_TIME / 8 / 1460 * 0.98),
            "delaySum": f"{np.random.uniform(0.01, 0.05):.6f}s",
            "meanDelay_ms": round(np.random.uniform(1, 20), 2),
            "throughput_mbps": round(tput / 1e6, 2),
        })

    with open("data/flow_monitor.json", "w") as f:
        import json
        json.dump({"flows": flows, "sim_time": SIM_TIME}, f, indent=2)

    print("✓ Generated flow_monitor.json")


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    print("Generating ns-3 5G NR simulation traces...")
    print(f"  Config: {N_GNB} gNBs, {N_UE} UEs, {SIM_TIME}s sim @ {CENTRAL_FREQ/1e9:.1f} GHz")
    generate_rlc_traces()
    generate_sinr_traces()
    generate_topology()
    generate_flowmonitor()
    print("\n✓ All trace files generated in data/")
