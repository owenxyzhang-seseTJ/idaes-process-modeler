from idaes_process_modeler.units import parse_quantity, si_value


def test_pressure_conversion():
    assert si_value("5 bar", "pressure") == 500000.0


def test_numeric_value_is_marked_assumed_si():
    quantity = parse_quantity(0.4, "dimensionless")
    assert quantity.assumed_si is True
    assert quantity.value_si == 0.4


def test_temperature_celsius_conversion():
    assert abs(si_value("25 degC", "temperature") - 298.15) < 1e-9
