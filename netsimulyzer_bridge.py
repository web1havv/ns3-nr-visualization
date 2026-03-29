#!/usr/bin/env python3
"""
Task 8: NetSimulyzer JSON Bridge
─────────────────────────────────
Tom Henderson mentioned NetSimulyzer (maintained by Evan Black) as the
current state-of-the-art ns-3 visualizer (mailing list, Feb 22, 2026).

This module generates NetSimulyzer-compatible JSON that can be loaded
directly into the NetSimulyzer 3D visualizer, bridging our Python
dashboard with the existing ns-3 visualization ecosystem.

NetSimulyzer JSON format:
  https://usnistgov.github.io/NetSimulyzer-ns3-module/

Allows visualizing our NR simulation results in 3D with NetSimulyzer
without requiring any C++ changes.
"""

import json
import numpy as np
from pathlib import Path
from ns3_nr_parser import load_rlc_stats, load_sinr_stats, load_topology


def export_netsimulyzer_json(dl_rlc, dl_sinr, topo, output_path: str):
    """
    Generate a NetSimulyzer-compatible JSON file from NR traces.

    NetSimulyzer JSON schema:
      version, configuration, nodes, series (time-series data)
    """
    gnbs = topo["gnbs"]
    ues  = topo["ues"]

    # Node list
    nodes = []

    # gNBs — fixed positions, tower model
    for gnb in gnbs:
        nodes.append({
            "id":    gnb["id"],
            "name":  f"gNB {gnb['id']}",
            "model": "tower.obj",
            "visible": True,
            "position": {
                "x": gnb["x"],
                "y": gnb["y"],
                "z": 30.0,   # gNB height 30 m
            },
            "color": {1: "#E63946", 2: "#457B9D", 3: "#2A9D8F"}[gnb["id"]],
        })

    # UEs — moving positions, phone model
    for ue in ues:
        nodes.append({
            "id":    100 + ue["id"],
            "name":  f"UE {ue['id']}",
            "model": "smartphone.obj",
            "visible": True,
            "position": {
                "x": ue["x"],
                "y": ue["y"],
                "z": 1.5,   # UE height 1.5 m (pedestrian)
            },
        })

    # Time-series: throughput per UE as a "series"
    series = []
    for imsi in sorted(dl_rlc["IMSI"].unique()):
        ue_data = dl_rlc[dl_rlc["IMSI"] == imsi].sort_values("start_time")
        series.append({
            "id":    int(imsi),
            "name":  f"UE {imsi} DL Throughput",
            "type":  "xy",
            "unit":  "Mbps",
            "x_axis": "Time [s]",
            "y_axis": "Throughput [Mbps]",
            "points": [
                {"x": round(float(row["start_time"]), 4),
                 "y": round(float(row["DL_throughput_mbps"]), 3)}
                for _, row in ue_data.iterrows()
            ],
        })

    # SINR series
    for imsi in sorted(dl_sinr["IMSI"].unique()):
        ue_sinr = dl_sinr[dl_sinr["IMSI"] == imsi].sort_values("time")
        # Downsample to 10Hz for file size
        ue_sinr_ds = ue_sinr.iloc[::10]
        series.append({
            "id":    200 + int(imsi),
            "name":  f"UE {imsi} DL SINR",
            "type":  "xy",
            "unit":  "dB",
            "x_axis": "Time [s]",
            "y_axis": "SINR [dB]",
            "points": [
                {"x": round(float(row["time"]), 4),
                 "y": round(float(row["sinr_dB"]), 2)}
                for _, row in ue_sinr_ds.iterrows()
            ],
        })

    # Events: handover annotations
    events = []
    for imsi in sorted(dl_rlc["IMSI"].unique()):
        ue = dl_rlc[dl_rlc["IMSI"] == imsi].sort_values("start_time")
        prev_cell = None
        for _, row in ue.iterrows():
            if prev_cell is not None and row["cellId"] != prev_cell:
                events.append({
                    "time":    round(float(row["start_time"]), 4),
                    "type":    "handover",
                    "node_id": 100 + int(imsi),
                    "message": f"UE {imsi}: Cell {int(prev_cell)} → Cell {int(row['cellId'])}",
                })
            prev_cell = row["cellId"]

    output = {
        "schema": "netsimulyzer-v1.0",
        "generator": "ns3-nr-visualization/netsimulyzer_bridge.py",
        "configuration": {
            "playback_step_ms": 100,
            "coordinate_system": "cartesian",
            "time_unit": "seconds",
        },
        "nodes":  nodes,
        "series": series,
        "events": events,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    size_kb = Path(output_path).stat().st_size / 1024
    print(f"  ✓ NetSimulyzer JSON → {output_path}  ({size_kb:.1f} KB)")
    print(f"    Nodes: {len(nodes)} | Series: {len(series)} | Events: {len(events)}")


if __name__ == "__main__":
    from ns3_nr_parser import load_rlc_stats, load_sinr_stats, load_topology
    data_dir = Path("data")
    dl_rlc  = load_rlc_stats(data_dir / "DlRlcStats.txt")
    dl_sinr = load_sinr_stats(data_dir / "DlPhySinr.txt")
    topo    = load_topology(data_dir / "topology.json")
    export_netsimulyzer_json(dl_rlc, dl_sinr, topo, "data/netsimulyzer_output.json")
