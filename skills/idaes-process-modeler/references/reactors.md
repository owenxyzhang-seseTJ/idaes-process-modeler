# Reactors and membrane reactors

For a PFR-like reference model, define stoichiometry, rate basis, reactant,
temperature, pressure, residence/velocity scale, and any heat-transfer terms.
Arrhenius expressions require a declared energy basis:

`k(T) = A exp(-Ea/(R T))`.

A membrane reactor adds a reaction-side balance and a distributed membrane
flux, for example `J_H2 = Pi_H2 (p_H2,reaction - p_H2,permeate)`. Track reaction
and membrane contributions separately so conversion is not confused with
permeation.

The current demo backend is PFR-like and constant-temperature/pressure. An
IDAES production route should use a compatible property package, reaction
package, and unit model; verify API compatibility against the installed IDAES
version before constructing the flowsheet.
