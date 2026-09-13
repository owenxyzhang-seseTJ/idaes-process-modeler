"""Command-line interface for the local package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import run_model
from .idaes_adapter import dependency_status
from .reporting import write_result_bundle
from .spec import load_spec
from .validation import validate_spec


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="idaes-model")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check-env", help="inspect IDAES/Pyomo and solver availability")
    check.add_argument("--json", action="store_true")
    validate = sub.add_parser("validate", help="preflight a YAML/JSON ModelSpec")
    validate.add_argument("spec", type=Path)
    run = sub.add_parser("run", help="run a supported reduced-order model")
    run.add_argument("spec", type=Path)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--backend", default="reduced_order")
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "check-env":
        payload = dependency_status().as_dict()
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            for key, value in payload.items():
                print(f"{key}: {value}")
        return 0
    if args.command == "validate":
        report = validate_spec(args.spec)
        print(json.dumps(report.as_dict(), indent=2))
        return 0 if report.valid else 2
    result = run_model(args.spec, backend=args.backend)
    write_result_bundle(result, load_spec(args.spec), args.output_dir)
    print(json.dumps(result["summary"], indent=2, default=str))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
