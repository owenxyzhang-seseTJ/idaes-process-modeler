#!/usr/bin/env python3
"""Optional H2-selective membrane-reactor demonstration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from idaes_process_modeler.engine import run_model
from idaes_process_modeler.reporting import write_result_bundle


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "demo_results" / "membrane_reactor")
    parser.add_argument("--spec", type=Path, default=ROOT / "assets" / "templates" / "membrane_reactor.yaml")
    args = parser.parse_args(argv)
    result = run_model(args.spec, backend="reduced_order")
    output = write_result_bundle(result, args.spec, args.output_dir)
    print(json.dumps({"output_dir": str(output), **result["summary"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
