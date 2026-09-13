from pathlib import Path

from idaes_process_modeler.engine import run_model


ROOT = Path(__file__).resolve().parents[1]


def test_membrane_mass_balance_and_metrics():
    result = run_model(ROOT / "assets" / "templates" / "membrane.yaml")
    summary = result["summary"]
    assert summary["solver"]["termination"] == "success"
    assert 0.0 <= summary["purity"] <= 1.0
    assert 0.0 <= summary["stage_cut"] <= 1.0
    assert summary["mass_balance_error"] < 1e-6
