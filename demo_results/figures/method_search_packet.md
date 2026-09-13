# Method Search Packet

Status: READY_FOR_PREPROCESSING (direct model-result plotting; no experimental preprocessing)

Search date: 2026-09-13

Figure type: Composite quantitative data/result figure with companion single-panel figures.

Material/system: The bundled IDAES Process Modeler demonstration systems: CO2/N2 fixed-bed
adsorption, four-step CO2/N2 PSA, CO2/CH4 co-current membrane separation, H2-selective
membrane reactor, and the guarded IDAES/Pyomo.DAE fixed-bed reference case.

Sources searched:

- `summary.json`, `profiles.csv`, and `metrics.csv` in each generated demo-result bundle.
- The corresponding model specifications in `model_spec.yaml`.
- The model and reporting code in `src/idaes_process_modeler/models/` and
  `src/idaes_process_modeler/reporting.py`.

No external literature method was imported because this is a direct visualization of
machine-readable model outputs, not a literature comparison or an experimental-data
preprocessing task.

Chosen preprocessing method:

- Read the generated CSV files without overwriting them.
- Select the maximum axial coordinate for fixed-bed outlet curves.
- Convert fixed-bed outlet concentrations to mole fractions by dividing each component
  concentration by the local total concentration; zero-total rows are plotted as zero.
- Convert seconds to minutes only for the fixed-bed x-axis and fractions to percent only
  for the PSA purity/recovery display.
- Preserve all other values and units as written in the result bundles.

Rationale: These operations expose the existing model outputs in physically interpretable
coordinates and do not smooth, fit, interpolate, or invent data.

Rejected alternatives:

- No smoothing or spline interpolation, because it could hide numerical behavior.
- No normalization to an arbitrary scale, because the result bundles already provide units.
- No statistical error bars or significance marks, because no replicate data or uncertainty
  model was supplied.

Assumptions and limits:

- All panels are numerical model outputs, not experiments.
- Reduced-order panels retain the assumptions and warnings in their source `summary.json`.
- The IDAES reference panel is an ideal-gas, constant-pressure/temperature reference solve,
  not a production property-package flowsheet.

Fields required from raw data: the columns present in each source `profiles.csv` and
`metrics.csv`; component names and headline metrics from `summary.json`.

Fields produced after preprocessing: plotted arrays only; no replacement raw-data files.
