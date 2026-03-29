#!/usr/bin/env python3
"""
run_all.py — One-command runner for the ns-3 NR Visualization Toolkit
======================================================================
Runs all tasks in sequence and prints a summary of outputs.

Usage:
    python run_all.py              # full pipeline
    python run_all.py --task 1    # run only Task 1 (flow filter)
    python run_all.py --list      # list all available tasks
"""

import argparse
import sys
import time
from pathlib import Path

TASKS = {
    1:  ("Flow-ID / UE Filter Engine",         "flow_filter",         "plot_ue_deep_dive"),
    2:  ("JSON Trace Exporter",                 "json_exporter",       "export_simulation_json"),
    3:  ("Advanced KPI Dashboard",              "kpi_dashboard",       "build_kpi_dashboard"),
    8:  ("NetSimulyzer JSON Bridge",            "netsimulyzer_bridge", "export_netsimulyzer_json"),
    9:  ("Automated HTML Report",               "report_generator",    "build_html_report"),
    10: ("AI Agent Observation Interface",      "report_generator",    "build_ai_agent_observation"),
    12: ("SEM Parameter Sweep",                 "sem_integration",     "plot_parameter_sweep"),
    13: ("ns-3 Style Compliance Report",        "style_checker",       "run_compliance_report"),
    14: ("NetAnim XML Parser & Overlay",        "netanim_parser",      "plot_netanim_overlay"),
    15: ("Multi-Run Statistical CI",            "multi_run_ci",        "plot_multi_run_ci"),
    16: ("Real-Time Dashboard Preview",         "realtime_dashboard",  None),
}


def run_generate_traces():
    print("\n[0] Generating synthetic ns-3 NR trace files ...")
    from generate_traces import main as gen
    gen()


def run_core_visuals():
    print("\n[Core] Building base dashboard & handover animation ...")
    from visualize_nr import main as viz
    from animate_handover import main as anim
    viz()
    anim()


def run_task(task_id: int):
    if task_id not in TASKS:
        print(f"  Unknown task {task_id}. Use --list to see available tasks.")
        return

    name, module, func = TASKS[task_id]
    print(f"\n[Task {task_id:02d}] {name}")
    t0 = time.time()
    try:
        mod = __import__(module)
        if func:
            getattr(mod, func)()
        else:
            # realtime_dashboard: just render preview
            dash = mod.RealTimeDashboard()
            dash.render_preview_gif()
        print(f"  Done in {time.time()-t0:.1f}s")
    except Exception as e:
        print(f"  ERROR: {e}")


def list_tasks():
    print("\nAvailable tasks:")
    print(f"  {'ID':>3}  {'Module':<25}  Description")
    print(f"  {'-'*3}  {'-'*25}  {'-'*40}")
    for tid, (name, mod, _) in sorted(TASKS.items()):
        print(f"  {tid:>3}  {mod:<25}  {name}")


def main():
    parser = argparse.ArgumentParser(
        description="ns-3 NR Visualization Toolkit — one-command runner"
    )
    parser.add_argument("--task", type=int, default=None,
                        help="Run only this task ID (see --list)")
    parser.add_argument("--list", action="store_true",
                        help="List all available tasks")
    parser.add_argument("--skip-generate", action="store_true",
                        help="Skip synthetic trace generation (use existing data/)")
    args = parser.parse_args()

    if args.list:
        list_tasks()
        return

    print("=" * 60)
    print("  ns-3 NR Visualization Toolkit (GSoC 2026 PoC)")
    print("  github.com/web1havv/ns3-nr-visualization")
    print("=" * 60)

    Path("data").mkdir(exist_ok=True)
    Path("figures").mkdir(exist_ok=True)

    if args.task:
        if not args.skip_generate:
            run_generate_traces()
        run_task(args.task)
        return

    # Full pipeline
    if not args.skip_generate:
        run_generate_traces()

    run_core_visuals()

    for tid in sorted(TASKS.keys()):
        run_task(tid)

    print("\n" + "=" * 60)
    print("  All tasks complete.")
    print("  Outputs:")
    print("    figures/  — all PNG dashboards and GIF animations")
    print("    data/     — JSON exports and trace files")
    print("    report.html — self-contained HTML report")
    print("=" * 60)


if __name__ == "__main__":
    main()
