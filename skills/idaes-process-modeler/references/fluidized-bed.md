# Bubbling fluidized bed boundary

IDAES `BubblingFluidizedBed` is an engineering/reduced-order unit model with
gas/solid phases and interphase transfer. Record the property/reaction package,
phase definitions, hydrodynamic correlations, and active heat/mass-transfer
terms.

A 1-D bubbling model cannot answer local bubble dynamics, channeling,
particle-scale mixing, CFD, or CFD-DEM questions. When those observables are
requested, state the mismatch and recommend MFiX, OpenFOAM, or CFD-DEM rather
than inflating the interpretation of an IDAES result.
