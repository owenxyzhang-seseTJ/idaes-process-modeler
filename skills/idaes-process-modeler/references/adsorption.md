# Fixed-bed adsorption

The reference equation for a constant-pressure isothermal gas bed is

\[
\varepsilon\partial_t C_i + \partial_z(u C_i)
- \varepsilon D_{ax}\partial_{zz} C_i
+ (1-\varepsilon)\rho_s\partial_t q_i = 0.
\]

Kinetics can be equilibrium (algebraic/fast-limit), LDF,
`dq_i/dt = k_i(q_i^* - q_i)`, or a dual-resistance approximation with fast and
slow contributions. The isotherm registry includes Langmuir, dual-site
Langmuir, Sips, Toth, Henry, competitive Langmuir, and competitive DSL. New
models should implement the same pressure-to-loading interface and declare
parameter units.

Ergun pressure drop is a diagnostic unless the selected model couples pressure
to the PDE:

\[
-dP/dz = 150\mu(1-\varepsilon)^2u/(\varepsilon^3d_p^2)
 + 1.75\rho_g(1-\varepsilon)u^2/(\varepsilon^3d_p).
\]

For non-isothermal work add gas/solid energy storage, adsorption heat, gas-solid
heat transfer, and wall exchange with explicit heat capacities and boundary
conditions. Report whether these terms are active.

Smoke path: `demos/demo_fixed_bed.py`. IDAES path:
`idaes_process_modeler.idaes_adapter.build_fixed_bed_dae`, then discretize and
solve after replacing the reference ideal-gas property assumptions as needed.
