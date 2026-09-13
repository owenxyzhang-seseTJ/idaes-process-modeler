# PSA/VSA/TSA cycle framework

The cycle is a list of data objects, not a hard-coded sequence. Each step has a
name, duration, inlet/outlet labels, and optional target pressure. Typical
classes are pressurization, adsorption, co-current depressurization,
counter-current blowdown, purge, repressurization, pressure equalization, and
evacuation.

For each cycle retain the end state `x = [pressure, loadings, temperatures,
inventories, ...]` and compute a normalized state delta. CSS is a numerical
stopping criterion only:

`max(abs(x_n - x_(n-1)) / max(abs(x_n), scale)) < css_tolerance`.

Metrics must define the integration basis: product outlet label, target
component, feed basis, cycle time, adsorbent mass, and energy convention. A
purity number without those definitions is not reproducible. Single-bed and
multi-bed models should share the step schema but not share hidden state.

The bundled PSA runner is a lumped-bed reduced-order map. It is useful for
cycle-schema tests, initialization, and sensitivity scaffolding. It does not
resolve axial gradients, thermal fronts, valve transients, or inter-bed timing.
Use a distributed IDAES/Pyomo.DAE model for claims that require those effects.

## Flexible MOF gate-open extension

Use `assets/templates/gate_open_psa.yaml` and model type `gate_open_psa` for the
binary nonisothermal mixed-tank extension. `scripts/run_gate_open_demo.py`
generates the full report and sensitivity cases. This is a SciPy reduced-order
route, not an IDAES unit. Total and component partial pressure are distinct;
gas composition must evolve during closed-feed evacuation. Crystal expansion
changes gas void volume and diffusion distance at fixed adsorbent mass.
The effective heat basis is per mole CO2 and includes structural effects;
do not add a duplicate phase heat. Unknown gate hysteresis and temperature
dependence require explicit assumptions and sensitivity checks. Reject claims
of physical validation from CSS or equation balance alone.
