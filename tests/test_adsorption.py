import numpy as np

from idaes_process_modeler.models.adsorption import equilibrium_loadings


def test_dual_site_langmuir_is_monotonic():
    pressure = np.asarray([0.0, 1.0e4, 1.0e5])
    result = equilibrium_loadings(
        {"CO2": pressure},
        "dual_site_langmuir",
        {"CO2": {"qs1": "1 mol/kg", "b1": "1e-5 1/Pa", "qs2": "1 mol/kg", "b2": "1e-6 1/Pa"}},
    )["CO2"]
    assert result[0] == 0.0
    assert np.all(np.diff(result) >= 0)
