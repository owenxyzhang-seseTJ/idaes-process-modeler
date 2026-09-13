# IDAES Process Modeler

An auditable Codex plugin and Python package for structured chemical-process
modeling. The first release provides a reusable `ModelSpec` contract, unit and
physics preflight checks, reduced-order smoke backends for fixed beds, PSA, and
membranes, report bundles, mesh/sweep/HPC helpers, and an optional
Pyomo.DAE/IDAES adapter.

The reduced-order backend is deliberately explicit: it is useful for demos,
workflow tests, and sensitivity scaffolding, but it is not an experimental
validation, a CFD model, or a substitute for a fully configured IDAES property
package and solver.

## Quick start

Install and verify IDAES first. Do not construct a process model until the
strict environment check passes.

```bash
conda env create -f environment.yml
conda activate idaes-process
idaes get-extensions
python scripts/check_environment.py --strict
python -m pip install -e '.[test]'
python demos/demo_fixed_bed.py --output-dir demo_results/fixed_bed
python demos/demo_psa.py --output-dir demo_results/psa
python demos/demo_membrane.py --output-dir demo_results/membrane
python scripts/plot_demo_results.py
pytest -q
```

The plotting command writes the composite and single-panel PNG/SVG/PDF exports
to `demo_results/figures/` and leaves the source CSV result bundles unchanged.

On Apple Silicon, the IDAES extension bundle supplies a compatible IPOPT
executable. If the Conda IPOPT binary is unstable for a Pyomo.DAE case, use
the IDAES-managed solver under `~/.idaes/bin/ipopt`; the reference adapter
selects it explicitly.

On a minimal machine without IDAES/Pyomo, `python -m pip install -e '.[test]'`
can run only the deterministic reduced-order smoke demos. It is not a valid
substitute for the IDAES installation and strict check above.

## Codex usage

Use `$idaes-process-modeler` when the request involves IDAES/Pyomo process
models, dynamic simulation, adsorption cycles, membranes, reactors, parameter
estimation, optimization, or process-model validation. The Skill requires a
structured specification before model construction and separates required,
assumed, and optional parameters.

## Current boundary

The package does not claim that every listed IDAES unit operation or every
thermodynamic model is already implemented. The model registry currently has
working reduced-order fixed-bed adsorption, cyclic adsorption, membrane
separation, and membrane-reactor paths, plus a guarded Pyomo.DAE/IDAES builder.
Fluidized-bed and advanced property-package routes are documented extension
points and are rejected or flagged when the current backend cannot answer the
question.
