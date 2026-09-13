# Technical Report QA Report

Date: 2026-09-13

## Checks completed

- `validate_python_comments.py scripts/build_technical_report.py`: passed.
- Process flow, parameter, and validation figures were rendered as PNG and inspected at high
  resolution.
- The process-flow redraw removed the overlapping middle title and redundant feedback labels.
- All axes carry units or dimensionless labels; CO₂, N₂, CH₄, and H₂ use readable subscripts.
- Isotherm markers identify the current feed partial-pressure points; no experimental points or
  uncertainty bars were invented.
- The IDAES reference and reduced-order evidence are explicitly separated in the report.
- SVG outputs retain editable text; PDF outputs are single-page exports with TrueType font
  settings.
- Raw YAML, CSV, and JSON result bundles remain separate from derived parameter CSV files.

## Scientific boundary

The report validates implementation behavior, units/bounds, numerical termination, residuals,
mass balances, CSS, and a limited fixed-bed mesh change. It does not validate material data,
kinetics, membrane permeance, thermal behavior, a full distributed PSA, or industrial process
performance against experiments, literature, or native Aspen results.
