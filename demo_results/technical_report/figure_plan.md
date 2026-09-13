# English Figure Plan

Status: CONFIRMED by the user's explicit request for calculation principles, modeling
principles, an Aspen-like flowchart, initial-parameter plots, reasonableness, and validation.

## Core objective

Make the chain from initial parameters and equations to unit-operation outputs and numerical
validation visible in one auditable technical package.

## Figures

1. `process_flow_aspen_like`: feed/specification → properties and constitutive laws → unit
   operation branches → ODE/DAE/cycle solver → results and validation.
2. `initial_parameters_isotherm_kinetics`: dual-site Langmuir isotherms, LDF loading response,
   LDF rate response, and membrane permeance selectivity.
3. `validation_evidence`: mass-balance/residual errors, CSS convergence, fixed-bed mesh check,
   and a text panel separating numerical evidence from missing physical validation.
4. Existing `demo_results_overview`: headline outputs for the four reduced-order demos and the
   IDAES/Pyomo.DAE reference solve.

## Export contract

Each new figure is written as PNG preview, editable SVG, and PDF. Derived curves are also
written as `processed_isotherms.csv`, `processed_ldf_curves.csv`, and
`validation_error_metrics.csv`; source files are not overwritten.

## Interpretation boundary

The flowchart is Aspen-like in organization only and is not a native Aspen file. The parameter
curves are model-generated responses, not experimental isotherms or rate measurements. The
validation panel reports numerical and physical-reasonableness checks but does not claim
experimental, literature, or industrial validation.
