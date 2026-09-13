#!/usr/bin/env python3
"""Evaluate candidate specs and select one using Pyomo/CBC."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from idaes_process_modeler.engine import run_model
from idaes_process_modeler.optimization import select_best_candidate
from idaes_process_modeler.spec import load_spec, set_dotted_value


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("--parameter", required=True)
    parser.add_argument("--values", nargs="+", required=True)
    parser.add_argument("--objective", required=True, help="summary metric; prefix min: for minimization")
    parser.add_argument("--constraints-json", default="{}")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    base = load_spec(args.spec)
    candidates = []
    for raw in args.values:
        try:
            value = float(raw)
        except ValueError:
            value = raw
        data = base.to_mapping()
        set_dotted_value(data, args.parameter, value)
        result = run_model(data)
        candidate = {"parameter_value": value, **result["summary"]}
        candidates.append(candidate)
    selection = select_best_candidate(
        candidates,
        objective=args.objective,
        constraints=json.loads(args.constraints_json),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(selection, indent=2, default=str), encoding="utf-8")
    print(json.dumps(selection, indent=2, default=str))
    return 0 if selection["selected_index"] is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
