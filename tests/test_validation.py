from pathlib import Path

from idaes_process_modeler.validation import validate_spec


ROOT = Path(__file__).resolve().parents[1]


def test_fixed_bed_template_is_valid():
    report = validate_spec(ROOT / "assets" / "templates" / "fixed_bed.yaml")
    assert report.valid, report.as_dict()


def test_missing_pressure_is_rejected():
    report = validate_spec(
        {
            "model_type": "membrane_separation",
            "components": ["A", "B"],
            "feed": {"temperature": "298 K", "molar_flow": "1 mol/s", "composition": {"A": 0.5, "B": 0.5}},
            "membrane": {
                "length": "1 m",
                "permeate_pressure": "0.1 bar",
                "permeance": {"A": "1e-8 mol/(m2*s*Pa)", "B": "1e-8 mol/(m2*s*Pa)"},
            },
        }
    )
    assert not report.valid
    assert any(issue.path == "feed.pressure" for issue in report.errors)
