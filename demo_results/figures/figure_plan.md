# English Pre-Plot Figure Plan

Status: CONFIRMED by the user's explicit request to plot and write the demo results.

## Figure objective

Show what each bundled demonstration actually computes, while making the numerical scope
and the distinction between reduced-order demonstrations and the IDAES/Pyomo.DAE reference
solve immediately visible.

## Panel map

- **a — Fixed-bed adsorption:** outlet CO2/N2 mole fractions versus time, with the reduced
  model's reported CO2 breakthrough time marked when available.
- **b — PSA:** product purity and recovery versus cycle, with the CSS state delta shown in
  the companion single-panel export.
- **c — Membrane separation:** retentate and permeate component mole fractions versus
  membrane coordinate, with final purity, recovery, and stage cut annotated.
- **d — Membrane reactor:** reaction-side component molar flows versus axial coordinate,
  with the reported conversion and permeated H2 amount annotated.
- **e — IDAES/Pyomo.DAE reference:** outlet composition versus time for the guarded fixed-bed
  reference model, with solver status, DOF, and maximum constraint residual annotated.
- **f — Result snapshot:** headline values and backend/evidence boundaries in one compact
  audit panel; no cross-model ranking is implied.

## Visual system

Use a consistent pastel academic palette: teal for CO2/hero quantities, coral for N2,
orange for CH4, green/blue/red for A/B/H2, and slate for numerical diagnostics. Use English
axis labels with SI units and native mathtext subscripts. Use solid lines for retentate or
reaction-side quantities and dashed lines for permeate quantities.

## Export contract

Write one composite figure and five single-panel figures as PNG previews, editable SVG, and
TrueType-font PDF. Keep the source CSV files unchanged and write the plotting script and QA
artifacts beside the exports.

## Limitations

The plots visualize the supplied model outputs only. They do not add experimental uncertainty,
literature comparison, CFD/DEM physics, detailed IDAES thermodynamics, or physical validation.
