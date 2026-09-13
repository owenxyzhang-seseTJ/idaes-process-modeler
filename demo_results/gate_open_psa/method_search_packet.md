# Method and provenance

Status: READY_FOR_PREPROCESSING

Sources: user-specified CO2/N2 capacities, gate width and gas composition;
local model references/psa.md and references/validation.md; SciPy solve_ivp
documentation inspected online at
https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html
(BDF implicit variable-order integration for stiff ODEs).

Method: ideal-gas component inventories plus LDF and a structural relaxation
state; no raw experimental curves supplied. Save solver samples in CSV before
plotting. Convert cm3(STP)/g using 273.15 K and 101325 Pa. No smoothing,
normalization or row removal. Refinement is a solver tolerance/max-step test,
not a fit or physical validation. Rejected: treating purge gas CO2 as recovered
adsorbate; imposing 5 kPa CO2 throughout desorption; interpreting the cycle as
vacuum PSA after user selected 1 bar purge; claiming an unknown hysteresis loop.
