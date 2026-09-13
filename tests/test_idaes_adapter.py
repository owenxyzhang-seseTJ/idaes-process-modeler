import pytest

from idaes_process_modeler.idaes_adapter import dependency_status


def test_dependency_probe_is_non_throwing():
    status = dependency_status()
    assert isinstance(status.as_dict(), dict)


@pytest.mark.skipif(not dependency_status().idaes, reason="IDAES not installed in this environment")
def test_idaes_dae_builder_constructs():
    from pathlib import Path

    from idaes_process_modeler.idaes_adapter import build_fixed_bed_dae, discretize_fixed_bed

    root = Path(__file__).resolve().parents[1]
    model = build_fixed_bed_dae(root / "assets" / "templates" / "fixed_bed.yaml")
    discretize_fixed_bed(model, time_elements=2, space_elements=2)
    assert hasattr(model, "fs")
    assert len(list(model.fs.C.values())) > 0


@pytest.mark.skipif(not dependency_status().ipopt, reason="IPOPT not installed in this environment")
def test_idaes_reference_solves_with_extension_solver():
    from pathlib import Path

    from idaes_process_modeler.idaes_adapter import build_fixed_bed_dae, discretize_fixed_bed, solve_pyomo_model

    root = Path(__file__).resolve().parents[1]
    model = build_fixed_bed_dae(root / "assets" / "templates" / "fixed_bed.yaml")
    discretize_fixed_bed(model, time_elements=1, space_elements=2)
    result = solve_pyomo_model(model, "ipopt")
    assert result["termination"] == "optimal", result
