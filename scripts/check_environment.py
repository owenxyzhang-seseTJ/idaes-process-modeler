#!/usr/bin/env python3
"""Report platform, package, solver, and memory availability."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from idaes_process_modeler.idaes_adapter import dependency_status


def _memory_bytes():
    if sys.platform == "darwin":
        try:
            return int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip())
        except (OSError, ValueError, subprocess.CalledProcessError):
            return None
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    return None


def _version(distribution: str):
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def build_report():
    status = dependency_status()
    payload = {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "memory_bytes": _memory_bytes(),
        "packages": {
            "idaes-pse": _version("idaes-pse"),
            "pyomo": _version("pyomo"),
            "numpy": _version("numpy"),
            "scipy": _version("scipy"),
            "pandas": _version("pandas"),
            "pytest": _version("pytest"),
        },
        "solvers": status.as_dict(),
        "executables": {name: shutil.which(name) for name in ("ipopt", "cbc", "glpsol", "sbatch")},
        "recommendations": [],
    }
    if not status.idaes:
        payload["recommendations"].append("conda install -c conda-forge idaes-pse pyomo")
    if not status.ipopt:
        payload["recommendations"].append("run 'idaes get-extensions' or install a supported IPOPT binary")
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        payload["recommendations"].append("keep large sweeps/HPC jobs on Linux; use this host for development and small cases")
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="fail if IDAES, Pyomo, or IPOPT is unavailable")
    args = parser.parse_args(argv)
    payload = build_report()
    print(json.dumps(payload, indent=2))
    if args.strict:
        status = payload["solvers"]
        return 0 if status["idaes"] and status["pyomo"] and status["ipopt"] else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
