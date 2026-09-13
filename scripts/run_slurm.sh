#!/usr/bin/env bash
# Submit a generated array job on Linux/HPC. Core models remain platform neutral.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 generated_job.sbatch" >&2
  exit 2
fi

sbatch "$1"
