from pathlib import Path

import numpy as np
import yaml

from idaes_process_modeler.calibration import fit_fixed_bed_parameter
from idaes_process_modeler.models.fixed_bed import run_fixed_bed


ROOT = Path(__file__).resolve().parents[1]


def test_single_parameter_fit_returns_audit_fields(tmp_path):
    data = yaml.safe_load((ROOT / "assets/templates/fixed_bed.yaml").read_text(encoding="utf-8"))
    data["numerics"]["spatial_elements"] = 4
    data["numerics"]["time_horizon"] = "60 s"
    data["numerics"]["time_step"] = "20 s"
    data["adsorption"]["kinetic_parameters"]["CO2"]["k"] = 0.01
    source_result = run_fixed_bed(data)
    observed = source_result["streams"][["time_s", "CO2_mole_fraction"]].copy()
    observed["CO2_mole_fraction"] += np.linspace(0.0, 1.0e-5, len(observed))
    data_path = tmp_path / "breakthrough.csv"
    observed.to_csv(data_path, index=False)
    fit, fitted = fit_fixed_bed_parameter(
        data,
        data_path,
        parameter_path="adsorption.kinetic_parameters.CO2.k",
        target_column="CO2_mole_fraction",
        bounds=(0.001, 0.1),
    )
    assert fit.success
    assert "summary" in fitted
    assert fit.parameter_path.endswith("CO2.k")
