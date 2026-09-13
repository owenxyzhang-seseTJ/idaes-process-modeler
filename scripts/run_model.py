#!/usr/bin/env python3
"""Validate, run, and report a ModelSpec."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from idaes_process_modeler.engine import run_model
from idaes_process_modeler.reporting import write_result_bundle
from idaes_process_modeler.spec import load_spec


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--backend", choices=("reduced_order", "reference"), default="reduced_order")
    args = parser.parse_args(argv)
    result = run_model(args.spec, backend=args.backend)
    output = write_result_bundle(result, load_spec(args.spec), args.output_dir)
    print(json.dumps({"output_dir": str(output), **result["summary"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
