# Figure QA Report

Date: 2026-09-13

## Outputs checked

- `demo_results_overview.{png,svg,pdf}`
- `fixed_bed_breakthrough.{png,svg,pdf}`
- `psa_performance_detail.{png,svg,pdf}`
- `membrane_profiles_detail.{png,svg,pdf}`
- `membrane_reactor_detail.{png,svg,pdf}`
- `idaes_reference_breakthrough.{png,svg,pdf}`

## Checks

- Raw source CSV files were read without modification.
- The composite panel order follows fixed bed → PSA → membrane → membrane reactor → IDAES
  reference → audit snapshot.
- Axes have units; fixed-bed time is displayed in minutes and PSA performance in percent.
- Component names use native subscripts where applicable (`CO₂`, `N₂`, `CH₄`, `H₂`).
- Solid/dashed line semantics distinguish retentate or reaction-side quantities from permeate
  quantities.
- No uncertainty bars, p-values, significance marks, or invented benchmark values were added.
- The IDAES reference panel explicitly reports `optimal`, DOF `0`, maximum residual
  `2.32e-11`, and the low outlet signal within the sampled time window.
- PNG files were rendered and inspected at high resolution; no visible text, legend, or panel
  overlap was found.
- SVG exports retain text elements (`svg.fonttype = none`); PDF exports use TrueType font
  embedding (`pdf.fonttype = 42`).
- `validate_python_comments.py scripts/plot_demo_results.py`: passed.

## Evidence boundary

The four reduced-order outputs are scenario/smoke results. The IDAES/Pyomo.DAE output is a
guarded ideal-gas, constant-pressure/temperature reference solve. None of the figures is
experimental validation or proof of process-scale performance.
