#!/usr/bin/env python3
"""Run a fixed-bed mesh convergence study and write convergence.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from idaes_process_modeler.engine import run_model
from idaes_process_modeler.spec import load_spec


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("--elements", nargs="+", type=int, default=[20, 40, 80])
    parser.add_argument("--metric", default="breakthrough_time_s")
    parser.add_argument("--tolerance", type=float, default=0.02)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    base = load_spec(args.spec)
    if base.model_type != "fixed_bed_adsorption":
        raise SystemExit("mesh_convergence currently targets fixed_bed_adsorption")
    records = []
    for elements in args.elements:
        data = base.to_mapping()
        data.setdefault("numerics", {})["spatial_elements"] = elements
        result = run_model(data, backend="reduced_order")
        records.append({"spatial_elements": elements, "value": result["summary"].get(args.metric)})
    differences = []
    for previous, current in zip(records, records[1:]):
        old = previous["value"]
        new = current["value"]
        if old is None or new is None:
            relative = None
        else:
            relative = abs(float(new) - float(old)) / max(abs(float(new)), 1.0e-12)
        differences.append({"from": previous["spatial_elements"], "to": current["spatial_elements"], "relative_change": relative})
    converged = bool(differences) and differences[-1]["relative_change"] is not None and differences[-1]["relative_change"] <= args.tolerance
    payload = {
        "kind": "spatial_mesh_convergence",
        "metric": args.metric,
        "tolerance": args.tolerance,
        "records": records,
        "differences": differences,
        "converged": converged,
        "interpretation": "numerical discretization evidence only; not physical validation",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if converged else 1


if __name__ == "__main__":
    raise SystemExit(main())
