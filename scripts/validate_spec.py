#!/usr/bin/env python3
"""Validate one YAML/JSON ModelSpec."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from idaes_process_modeler.validation import validate_spec


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    args = parser.parse_args(argv)
    report = validate_spec(args.spec)
    print(json.dumps(report.as_dict(), indent=2))
    return 0 if report.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
