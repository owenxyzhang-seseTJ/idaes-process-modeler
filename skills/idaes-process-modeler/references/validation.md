# Validation and numerical evidence

Use the following evidence hierarchy when the user asks for validation:

1. measured experimental data with uncertainty and matching operating basis;
2. a literature benchmark with the same equations and parameters;
3. an Aspen or other simulator benchmark with the property package and basis
   documented; and
4. mesh/time-step and solver-tolerance convergence.

The fourth item is numerical evidence, not physical validation. Separate:

- thermodynamic/property error;
- model-form error;
- parameter uncertainty; and
- numerical discretization error.

Minimum post-solve checks include solver termination, maximum residual, total
and component balances, energy balance when enabled, composition closure,
non-negative flows/concentrations, pressure/loading bounds, and CSS when
cyclic. Save the tolerance, mesh, time step, initialization, and solver log.

For a mesh study compare the final requested observables, not only residuals.
Use the bundled `scripts/mesh_convergence.py` for fixed-bed breakthrough and
state explicitly whether the selected tolerance is a user requirement or a
working assumption.
