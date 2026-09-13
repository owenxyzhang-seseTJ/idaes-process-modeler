import pytest


def test_pyomo_candidate_selection():
    pytest.importorskip("pyomo")
    from idaes_process_modeler.optimization import select_best_candidate

    result = select_best_candidate(
        [
            {"purity": 0.94, "recovery": 0.80, "energy": 10.0},
            {"purity": 0.96, "recovery": 0.70, "energy": 8.0},
            {"purity": 0.97, "recovery": 0.85, "energy": 12.0},
        ],
        objective="recovery",
        constraints={"purity": {"lower": 0.95}},
    )
    assert result["termination"] == "optimal"
    assert result["selected"]["recovery"] == 0.85
