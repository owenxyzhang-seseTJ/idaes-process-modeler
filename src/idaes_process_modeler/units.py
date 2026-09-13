"""Small, explicit unit parser used before optional Pyomo/IDAES units.

The parser intentionally covers the units used by the bundled templates and
keeps numeric-without-unit values usable for programmatic callers. Such values
are marked as assumed SI by the validator rather than silently presented as
experimental data.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, Optional, Tuple


class UnitError(ValueError):
    """Raised when a value cannot be interpreted with the requested units."""


@dataclass(frozen=True)
class Quantity:
    """A parsed quantity represented in SI base units."""

    value_si: float
    dimension: str
    original: Any
    assumed_si: bool = False


_UNIT_TABLE: Dict[str, Tuple[str, float]] = {
    "1": ("dimensionless", 1.0),
    "": ("dimensionless", 1.0),
    "m": ("length", 1.0),
    "cm": ("length", 1.0e-2),
    "mm": ("length", 1.0e-3),
    "um": ("length", 1.0e-6),
    "m2": ("area", 1.0),
    "m^2": ("area", 1.0),
    "cm2": ("area", 1.0e-4),
    "cm^2": ("area", 1.0e-4),
    "m3": ("volume", 1.0),
    "m^3": ("volume", 1.0),
    "l": ("volume", 1.0e-3),
    "L": ("volume", 1.0e-3),
    "s": ("time", 1.0),
    "sec": ("time", 1.0),
    "min": ("time", 60.0),
    "h": ("time", 3600.0),
    "hr": ("time", 3600.0),
    "pa": ("pressure", 1.0),
    "kpa": ("pressure", 1.0e3),
    "mpa": ("pressure", 1.0e6),
    "bar": ("pressure", 1.0e5),
    "atm": ("pressure", 101325.0),
    "1/pa": ("inverse_pressure", 1.0),
    "1/kpa": ("inverse_pressure", 1.0e-3),
    "1/mpa": ("inverse_pressure", 1.0e-6),
    "1/bar": ("inverse_pressure", 1.0e-5),
    "k": ("temperature", 1.0),
    "kelvin": ("temperature", 1.0),
    "degc": ("temperature_c", 1.0),
    "c": ("temperature_c", 1.0),
    "mol/s": ("molar_flow", 1.0),
    "mol/sec": ("molar_flow", 1.0),
    "kmol/s": ("molar_flow", 1.0e3),
    "kmol/h": ("molar_flow", 1.0e3 / 3600.0),
    "kg/m3": ("mass_density", 1.0),
    "kg/m^3": ("mass_density", 1.0),
    "g/cm3": ("mass_density", 1.0e3),
    "g/cm^3": ("mass_density", 1.0e3),
    "mol/m3": ("molar_density", 1.0),
    "mol/m^3": ("molar_density", 1.0),
    "m/s": ("velocity", 1.0),
    "pa*s": ("viscosity", 1.0),
    "pa.s": ("viscosity", 1.0),
    "cp": ("viscosity", 1.0e-3),
    "m2/s": ("diffusivity", 1.0),
    "m^2/s": ("diffusivity", 1.0),
    "1/s": ("rate_constant", 1.0),
    "s-1": ("rate_constant", 1.0),
    "s^-1": ("rate_constant", 1.0),
    "mol/kg": ("loading", 1.0),
    "mmol/g": ("loading", 1.0),
    "j/mol": ("energy_per_mol", 1.0),
    "kj/mol": ("energy_per_mol", 1.0e3),
    "w/m2/k": ("heat_transfer", 1.0),
    "w/m^2/k": ("heat_transfer", 1.0),
    "mol/(m2*s*pa)": ("permeance", 1.0),
    "mol/(m^2*s*pa)": ("permeance", 1.0),
    "mol/m2/s/pa": ("permeance", 1.0),
    "mol/m^2/s/pa": ("permeance", 1.0),
}


def _normalise_unit(unit: str) -> str:
    """Normalise harmless spelling/spacing variations without guessing."""

    value = unit.strip().replace("·", "*").replace("µ", "u")
    value = value.replace(" ", "")
    return value.lower()


def parse_quantity(
    value: Any,
    expected_dimension: Optional[str] = None,
    *,
    field_name: str = "value",
    allow_assumed_si: bool = True,
) -> Quantity:
    """Parse a number, ``"number unit"`` string, or ``{"value", "unit"}``.

    Numeric values are interpreted as SI only when ``allow_assumed_si`` is
    true. The returned ``assumed_si`` flag lets preflight reports surface the
    assumption to the user.
    """

    assumed = False
    unit = None
    raw_value = value
    if isinstance(value, Quantity):
        parsed = value
        if expected_dimension and parsed.dimension != expected_dimension:
            raise UnitError(
                f"{field_name}: expected {expected_dimension}, got {parsed.dimension}"
            )
        return parsed
    if isinstance(value, dict):
        if "value" not in value:
            raise UnitError(f"{field_name}: quantity mapping needs a 'value' key")
        raw_value = value["value"]
        unit = value.get("unit")
    elif isinstance(value, str):
        match = re.match(
            r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(.*?)\s*$",
            value,
        )
        if not match:
            raise UnitError(f"{field_name}: cannot parse quantity {value!r}")
        raw_value = float(match.group(1))
        unit = match.group(2) or None
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if not allow_assumed_si:
            raise UnitError(f"{field_name}: explicit units are required")
        assumed = True
        raw_value = float(value)
        unit = None
    else:
        raise UnitError(f"{field_name}: unsupported quantity type {type(value).__name__}")

    try:
        numeric = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise UnitError(f"{field_name}: numeric value required, got {raw_value!r}") from exc

    if unit is None:
        dimension = expected_dimension or "dimensionless"
        factor = 1.0
    else:
        key = _normalise_unit(str(unit))
        # The lower-case table is intentional; this also accepts L as l.
        candidates = {k.lower(): v for k, v in _UNIT_TABLE.items()}
        if key not in candidates:
            raise UnitError(f"{field_name}: unsupported unit {unit!r}")
        dimension, factor = candidates[key]
        if dimension == "temperature_c":
            dimension = "temperature"
            numeric = numeric + 273.15
        if expected_dimension and dimension != expected_dimension:
            raise UnitError(
                f"{field_name}: expected {expected_dimension}, got {dimension} from {unit!r}"
            )

    return Quantity(numeric * factor, dimension, value, assumed_si=assumed)


def si_value(
    value: Any,
    expected_dimension: Optional[str] = None,
    *,
    field_name: str = "value",
    allow_assumed_si: bool = True,
) -> float:
    """Return a parsed SI value, raising a contextual ``UnitError`` on failure."""

    return parse_quantity(
        value,
        expected_dimension,
        field_name=field_name,
        allow_assumed_si=allow_assumed_si,
    ).value_si
