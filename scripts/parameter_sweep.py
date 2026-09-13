#!/usr/bin/env python3
"""Run a portable parameter sweep into runs/case_NNN directories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from idaes_process_modeler.engine import run_model
from idaes_process_modeler.reporting import write_result_bundle
from idaes_process_modeler.spec import load_spec, set_dotted_value


def _parse_values(args):
    if args.values_file:
        return json.loads(args.values_file.read_text(encoding="utf-8"))
    values = []
    for raw in args.values:
        try:
            values.append(float(raw))
        except ValueError:
            values.append(raw)
    return values


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("--parameter", required=True, help="dotted ModelSpec path")
    parser.add_argument("--values", nargs="*", default=[])
    parser.add_argument("--values-file", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--backend", default="reduced_order")
    parser.add_argument("--case-index", type=int, help="zero-based single case index for Slurm arrays")
    args = parser.parse_args(argv)
    if not args.values and not args.values_file:
        raise SystemExit("provide --values or --values-file")
    values = _parse_values(args)
    base = load_spec(args.spec)
    args.output_root.mkdir(parents=True, exist_ok=True)
    if args.case_index is not None:
        if args.case_index < 0 or args.case_index >= len(values):
            raise SystemExit("case-index is outside the values array")
        selected = [(args.case_index + 1, values[args.case_index])]
    else:
        selected = list(enumerate(values, start=1))
    records = []
    for index, value in selected:
        data = base.to_mapping()
        set_dotted_value(data, args.parameter, value)
        case_dir = args.output_root / f"case_{index:03d}"
        try:
            result = run_model(data, backend=args.backend)
            write_result_bundle(result, data, case_dir)
            records.append({"case": case_dir.name, "parameter": value, "status": "success", "summary": result["summary"]})
        except Exception as exc:
            case_dir.mkdir(parents=True, exist_ok=True)
            (case_dir / "error.json").write_text(json.dumps({"error": str(exc), "parameter": value}, indent=2), encoding="utf-8")
            records.append({"case": case_dir.name, "parameter": value, "status": "failed", "error": str(exc)})
    manifest = {"parameter": args.parameter, "case_index": args.case_index, "cases": records}
    (args.output_root / "sweep_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    print(json.dumps(manifest, indent=2, default=str))
    return 0 if all(row["status"] == "success" for row in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
