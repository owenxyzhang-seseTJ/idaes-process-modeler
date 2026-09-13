# Linux/HPC and Slurm

Core model code must not depend on macOS APIs. Use the same spec and package on
macOS and Linux, and vary only environment/launcher settings. Keep each sweep
case self-contained:

```text
runs/case_001/{model_spec.yaml,summary.json,streams.csv,profiles.csv,metrics.csv,figures/,error.json}
```

`scripts/generate_slurm.py` creates an array job and
`scripts/run_slurm.sh` submits it. Array jobs should write to separate case
directories and include the git/package version, solver status, and input
hash. PETSc, mpi4py, HiGHS, MA57/HSL, and multi-core settings are optional and
must be detected on the target Linux environment, not assumed from macOS.

Do not move a failing case directly into a large sweep. Run one case locally,
capture its log, then scale out.
