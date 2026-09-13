#!/usr/bin/env python3
"""Fit one ModelSpec scalar to a measured CSV column."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from idaes_process_modeler.calibration import fit_fixed_bed_parameter
from idaes_process_modeler.reporting import write_result_bundle
from idaes_process_modeler.spec import load_spec, set_dotted_value


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("data", type=Path)
    parser.add_argument("--parameter", required=True)
    parser.add_argument("--target-column", required=True)
    parser.add_argument("--time-column", default="time_s")
    parser.add_argument("--sigma-column")
    parser.add_argument("--lower", type=float, default=0.0)
    parser.add_argument("--upper", type=float, default=float("inf"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    fit, result = fit_fixed_bed_parameter(
        args.spec,
        args.data,
        parameter_path=args.parameter,
        target_column=args.target_column,
        time_column=args.time_column,
        sigma_column=args.sigma_column,
        bounds=(args.lower, args.upper),
    )
    fitted_spec = load_spec(args.spec).to_mapping()
    set_dotted_value(fitted_spec, args.parameter, fit.fitted_value_si)
    output = write_result_bundle(result, fitted_spec, args.output_dir)
    payload = fit.as_dict()
    payload["output_dir"] = str(output)
    (args.output_dir / "fit.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if fit.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
