# Final PSA figure plan

Direct execution authorized by user: replace purge with 5 kPa vacuum and include
crystal volume, mass-transfer and heat coupling. Six panels: 298 K reference
isotherms, total/partial pressure, loadings, temperature, solid volume, effective
LDF coefficient. Separate rate plot and conceptual flowsheet. Read numerical
CSV without smoothing; label all curves simulations; export PNG/SVG/PDF.

Method: user-specified anchors and gate width; local component/energy inventory
equations; SciPy BDF documentation inspected at
https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html.
40 kJ/mol interpreted as effective heat per mol CO2, no duplicate phase heat.
Unknown thermal gate relation explicitly compared with a fixed-threshold case.
