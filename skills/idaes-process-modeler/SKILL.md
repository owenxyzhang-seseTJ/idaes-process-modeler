---
name: idaes-process-modeler
description: Build, validate, run, and revise auditable IDAES/Pyomo chemical-process models from natural-language requirements and structured ModelSpec files; use for adsorption cycles, membranes, reactors, flowsheets, parameter estimation, optimization, and numerical/physical validation.
---

# IDAES Process Modeler

Use this Skill when the user asks for an IDAES/Pyomo process model, dynamic
simulation, PSA/VSA/TSA cycle, fixed-bed adsorption, membrane separation or
reactor, reactor/flowsheet model, parameter estimation, sensitivity analysis,
optimization, cyclic steady state, or multi-scale materials-to-process link.
Do not use it for CFD/DEM, molecular simulation, or an Aspen-only workflow;
route those questions to the appropriate tool and state the boundary.

## Operating contract

The output is a reproducible project and an auditable report, not an isolated
Python snippet. Keep user-provided data unchanged and separate:

- measured or literature data;
- fitted parameters and their objective/weights;
- IAST/GCMC/DFT/MD inputs and predictions;
- reduced-order scenario assumptions;
- numerical convergence evidence; and
- experimental or benchmark validation.

Never call a draft, assumed parameter, converged solver result, or reduced-order
simulation “validated” without the corresponding evidence.

## Workflow

1. Bootstrap and verify the IDAES runtime before constructing or solving any
   model. On a new machine, create the environment from `environment.yml` with
   Conda/Miniforge, activate `idaes-process`, and run `idaes get-extensions`.
   Then run `scripts/check_environment.py --strict` in that environment. The
   strict check must find IDAES, Pyomo/Pyomo.DAE, and a usable solver. On
   Apple Silicon, prefer the IDAES-managed extension solver (normally
   `~/.idaes/bin/ipopt`) when a Conda solver has compatibility problems. If
   installation or extension download fails, stop before writing a process
   model and report the exact command and error.
2. Parse the request into a `ModelSpec` before writing a model. Identify model
   family, components, geometry, feeds, thermodynamics, constitutive laws,
   boundary/initial conditions, targets, constraints, numerical settings, and
   desired deliverables. Label every parameter `required`, `recommended`, or
   `optional`, and record its source (`user`, `experiment`, `literature`,
   `fit`, or `assumption`).
3. Use explicit SI-compatible units for physical quantities. Run
   `scripts/validate_spec.py <spec.yaml>` and fix errors before constructing a
   model. Numeric values without units may be accepted for programmatic input,
   but the report must mark them as assumed SI.
4. Select a backend deliberately. The bundled reduced-order backends are for
   smoke tests, initialization, parameter/sensitivity scaffolding, and clearly
   labelled scenario studies. Do not silently substitute them for a requested
   IDAES model. For fluidized-bed questions involving bubble dynamics,
   channeling, CFD, or particle-scale mixing, state that a 1-D engineering
   model is insufficient and recommend MFiX/OpenFOAM/CFD-DEM.
5. Pre-solve: validate units and states, count degrees of freedom, check bounds,
   initialize variables, inspect boundary conditions, apply scaling, and verify
   discretization. Diagnose in this order when a solve fails: DOF → units →
   bounds → initialization → scaling → discretization → thermodynamics →
   solver log. Report `Likely cause / Evidence / Suggested correction`.
6. Solve with recorded versions, solver, options, tolerance, mesh, time grid,
   and initialization. For PSA/VSA/TSA, construct the cycle from the user
   sequence; compare normalized end-of-cycle state vectors and stop only when
   `max(abs(x_n - x_(n-1))) < css_tolerance` or report non-convergence.
7. Post-solve: check termination, residuals, component/total mass balance,
   energy balance when enabled, negative flows/concentrations, mole-fraction
   closure, pressure/loading bounds, and CSS. Save error metrics, not just
   plots. A solver status of `optimal`/`success` is not physical validation.
8. Run mesh/time-step convergence for PDE/DAE claims. Compare the requested
   observables (purity, recovery, productivity, breakthrough time, conversion,
   energy) at at least two refinements. Read `references/validation.md` before
   declaring any validation result.
9. Write the standard bundle: `summary.json`, `streams.csv`, `profiles.csv`,
   `metrics.csv`, `convergence.json`, `model_spec.yaml`, and `figures/`. Include
   assumptions, missing required inputs, warnings, provenance, and benchmark or
   experimental comparisons when supplied.

## Model routing

- Fixed-bed adsorption → `references/adsorption.md`, then the fixed-bed
  template/backend. Support convection, axial dispersion, gas accumulation,
  adsorption storage, LDF/dual resistance, selectable isotherms, Ergun
  diagnostics, and isothermal/adiabatic/non-isothermal extension points.
- PSA/VSA/TSA → `references/psa.md`. Treat the cycle as data, not hard-coded
  Python branches. Keep single-bed implementation separate from a future
  multi-bed interface.
- Membrane separation → `references/membranes.md`; distinguish co-current and
  counter-current boundary conditions, permeance source, stage cut, purity,
  recovery, area, and pressure ratio.
- Membrane/fixed-bed reactor → `references/reactors.md`; distinguish reaction,
  convection, membrane transfer, heat effects, and stoichiometric closure.
- Bubbling fluidized bed → `references/fluidized-bed.md`; use IDAES
  `BubblingFluidizedBed` only with a compatible property package and state the
  reduced-order limitation.
- Material-to-process inputs → use the materials schema in
  `references/modeling-principles.md`. GCMC equilibrium uptake is not a dynamic
  mass-transfer coefficient; DFT adsorption energy is not an isotherm fit.

## Failure and accuracy policy

Do not randomize parameters after a failed solve. Preserve the failing case,
log, and solver status, then apply the diagnostic order above. Distinguish
thermodynamic/property error, model-form error, parameter uncertainty, and
numerical discretization error. Use experimental data first, then a literature
benchmark, then an Aspen benchmark, then mesh/time-step convergence. Say when a
requested result cannot be supported by the available data or model.

Read only the relevant reference file(s) for the selected model family. The
scripts and templates in this plugin are runnable support resources; inspect
their command help before adapting them.
