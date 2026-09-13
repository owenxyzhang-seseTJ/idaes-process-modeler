# Verification and visual QA

- Full package regression: 17 tests passed, including anchor reproduction,
  constant solid mass, inventory closure, energy closure and state bounds.
- Baseline/refined/long-contact and two assumption controls all reached CSS.
- BDF max step 2 to 0.5 s, with tightened tolerances: product and capacity
  relative changes about 4.5e-9. This is numerical evidence only.
- PNG six-panel figure inspected: legible labels, correct pressure and uptake
  units, no overlaps; reference equilibrium and actual dynamics distinguished.
- SVG/PDF companion exports and raw CSV/YAML/JSON are retained.
- `python scripts/render_reports.py`: passed; the bilingual report rendered to a five-page
  PDF, and the figure plan, method-search packet, and QA report each rendered to one-page
  PDFs.
- Rendered page previews were inspected: the result table, equilibrium/kinetic plots,
  process flow diagram, crystal-volume and heat/structure equations, inventory balances,
  and validation text remain inside the page boundary and are readable.
- 40 kJ/mol basis is explicitly assumed per mol CO2; phase heat not duplicated.
- Unknown thermal gate shift and pore-dependent diffusivity remain physical
  uncertainties. A fixed-gate-temperature control is included.
