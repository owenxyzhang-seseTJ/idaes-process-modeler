from pathlib import Path

from idaes_process_modeler.engine import run_model


ROOT = Path(__file__).resolve().parents[1]


def test_fixed_bed_smoke():
    spec = (ROOT / "assets" / "templates" / "fixed_bed.yaml").read_text(encoding="utf-8")
    # Keep the test small while using the same schema as the demo.
    import yaml

    data = yaml.safe_load(spec)
    data["numerics"]["spatial_elements"] = 6
    data["numerics"]["time_horizon"] = "120 s"
    data["numerics"]["time_step"] = "20 s"
    result = run_model(data)
    assert result["summary"]["solver"]["termination"] == "success"
    assert result["streams"].shape[0] == 7
    # The template requests a 1e-5 integrator tolerance; the audit should be
    # comfortably within that order, not artificially below it.
    assert result["summary"]["mass_balance_error"] < 1e-5
