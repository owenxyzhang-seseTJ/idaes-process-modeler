from pathlib import Path

from idaes_process_modeler.engine import run_model


ROOT = Path(__file__).resolve().parents[1]


def test_psa_cycle_schema_and_metrics():
    result = run_model(ROOT / "assets" / "templates" / "psa.yaml")
    summary = result["summary"]
    assert summary["cycles_run"] >= 2
    assert 0.0 <= summary["purity"] <= 1.0
    assert 0.0 <= summary["recovery"] <= 1.0
    assert not result["streams"].empty
