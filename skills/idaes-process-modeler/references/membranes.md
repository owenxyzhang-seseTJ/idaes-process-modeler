# Membrane separation

The minimum local constitutive law is

`J_i = Pi_i (p_i,feed - p_i,permeate)`.

The ModelSpec must state membrane mode (co-current or counter-current), length,
area or area-per-length, feed/permeate pressure, permeance basis and
temperature/pressure dependence. Report stage cut, retentate/permeate flows,
purity, recovery, pressure ratio, flux profiles, and component balance error.

Permeance may be constant or an explicit function of temperature, pressure, or
composition. Mixed-matrix, facilitated-transport, hollow-fiber, and
competitive sorption-diffusion additions need a new constitutive model and
validation data; do not silently emulate them with a fitted scalar permeance.

The bundled backend integrates a transparent 1-D ideal-gas balance. Module
pressure drop and concentration polarization are omitted unless the user adds
equations. For a counter-current model, check both boundary streams and the
shooting residual before accepting outputs.
