# Modeling principles and ModelSpec contract

`ModelSpec` is the boundary between natural language and executable equations.
The agent should create it, validate it, and show it to the user before adding
or changing equations.

## Minimum shape

```yaml
model_type: fixed_bed_adsorption
components: [CO2, N2]
feed:
  pressure: 5 bar
  temperature: 298 K
  molar_flow: 0.01 mol/s
  composition: {CO2: 0.15, N2: 0.85}
geometry: {length: 1 m, diameter: 0.05 m}
numerics: {spatial_elements: 40, time_horizon: 1200 s, time_step: 10 s}
```

For each physical value retain `value`, `unit`, and `source` when the source
matters. The bundled parser accepts a compact quantity string for convenience.
Required values block execution; recommended values may use a declared default;
optional values may be omitted.

## Provenance boundaries

- Experiment: raw data, uncertainty, and preprocessing are preserved.
- Literature: citation/DOI and temperature/pressure basis are recorded.
- Fit: objective, weights, bounds, initial guess, and residuals are recorded.
- GCMC/DFT/MD: the predicted observable and its scale are recorded. Equilibrium
  uptake does not determine process kinetics; a diffusivity is not an LDF rate
  without a stated mapping.
- Assumption: value, rationale, sensitivity range, and effect on outputs are
  listed in the result bundle.

## Scale transitions

Material → particle → bed → device → flowsheet transitions require explicit
interfaces: isotherm/heat/diffusivity → particle geometry and density → bed
voidage/dispersion/velocity → unit-operation boundary conditions → stream and
utility connections. Do not silently copy a material-scale value into a
process-scale parameter with a different definition.
