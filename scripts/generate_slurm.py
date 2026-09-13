#!/usr/bin/env python3
"""Generate a Slurm array job without embedding macOS-specific commands."""

from __future__ import annotations

import argparse
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("--parameter", required=True)
    parser.add_argument("--values-file", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--job-name", default="idaes-process")
    parser.add_argument("--time", default="01:00:00")
    parser.add_argument("--memory", default="4G")
    parser.add_argument("--cpus", type=int, default=1)
    parser.add_argument("--partition")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    values = __import__("json").loads(args.values_file.read_text(encoding="utf-8"))
    if not values:
        raise SystemExit("values-file must contain a non-empty JSON array")
    lines = [
        "#!/usr/bin/env bash",
        f"#SBATCH --job-name={args.job_name}",
        f"#SBATCH --array=0-{len(values) - 1}",
        f"#SBATCH --time={args.time}",
        f"#SBATCH --mem={args.memory}",
        f"#SBATCH --cpus-per-task={args.cpus}",
    ]
    if args.partition:
        lines.append(f"#SBATCH --partition={args.partition}")
    lines += [
        "set -euo pipefail",
        "module load python || true",
        "PROJECT_ROOT=" + repr(str(Path(__file__).resolve().parents[1])),
        "cd \"$PROJECT_ROOT\"",
        "SPEC_PATH=" + repr(str(args.spec.resolve())),
        "VALUES_PATH=" + repr(str(args.values_file.resolve())),
        "OUTPUT_ROOT=" + repr(str(args.output_root.resolve())),
        "python scripts/parameter_sweep.py \"$SPEC_PATH\" \\",
        "  --parameter " + repr(args.parameter) + " \\",
        "  --values-file \"$VALUES_PATH\" \\",
        "  --case-index \"$SLURM_ARRAY_TASK_ID\" \\",
        "  --output-root \"$OUTPUT_ROOT\"",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    args.output.chmod(0o755)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
