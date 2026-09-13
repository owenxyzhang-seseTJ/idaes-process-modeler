"""Extensible adsorption isotherm and kinetic correlations.

All pressures are Pa and all loadings are mol/kg in this module. Parameter
values may be plain SI numbers or explicit quantity strings in a ModelSpec.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

import numpy as np

from ..units import UnitError, si_value


class AdsorptionModelError(ValueError):
    """Raised for an incomplete or invalid adsorption correlation."""


def _param(params: Mapping[str, Any], name: str, dimension: str, default: Any = None) -> float:
    value = params.get(name, default)
    if value is None:
        raise AdsorptionModelError(f"missing adsorption parameter {name!r}")
    try:
        return si_value(value, dimension, field_name=f"adsorption.{name}")
    except UnitError as exc:
        raise AdsorptionModelError(str(exc)) from exc


def langmuir(pressure_pa: Any, qs: Any, b: Any) -> np.ndarray:
    p = np.maximum(np.asarray(pressure_pa, dtype=float), 0.0)
    q_capacity = _param({"q": qs}, "q", "loading")
    affinity = _param({"b": b}, "b", "inverse_pressure")
    return q_capacity * affinity * p / (1.0 + affinity * p)


def dual_site_langmuir(pressure_pa: Any, params: Mapping[str, Any]) -> np.ndarray:
    p = np.maximum(np.asarray(pressure_pa, dtype=float), 0.0)
    site1 = params.get("site1", params)
    site2 = params.get("site2", params)
    if site1 is params:
        keys = ("qs1", "b1")
    else:
        keys = ("qs", "b")
    if site2 is params:
        keys2 = ("qs2", "b2")
    else:
        keys2 = ("qs", "b")
    q1 = langmuir(p, _param(site1, keys[0], "loading"), _param(site1, keys[1], "inverse_pressure"))
    q2 = langmuir(p, _param(site2, keys2[0], "loading"), _param(site2, keys2[1], "inverse_pressure"))
    return q1 + q2


def sips(pressure_pa: Any, params: Mapping[str, Any]) -> np.ndarray:
    p = np.maximum(np.asarray(pressure_pa, dtype=float), 0.0)
    qs = _param(params, "qs", "loading")
    b = _param(params, "b", "inverse_pressure")
    exponent = float(params.get("n", 1.0))
    if exponent <= 0:
        raise AdsorptionModelError("Sips exponent n must be > 0")
    bp = np.maximum(b * p, 0.0)
    return qs * np.power(bp, exponent) / (1.0 + np.power(bp, exponent))


def toth(pressure_pa: Any, params: Mapping[str, Any]) -> np.ndarray:
    p = np.maximum(np.asarray(pressure_pa, dtype=float), 0.0)
    qs = _param(params, "qs", "loading")
    b = _param(params, "b", "inverse_pressure")
    exponent = float(params.get("t", 1.0))
    if exponent <= 0:
        raise AdsorptionModelError("Toth exponent t must be > 0")
    return qs * b * p / np.power(1.0 + np.power(b * p, exponent), 1.0 / exponent)


def henry(pressure_pa: Any, params: Mapping[str, Any]) -> np.ndarray:
    p = np.maximum(np.asarray(pressure_pa, dtype=float), 0.0)
    kh = _param(params, "kH", "loading")
    return kh * p


def competitive_langmuir(
    partial_pressures_pa: Mapping[str, Any],
    component_params: Mapping[str, Mapping[str, Any]],
) -> Dict[str, np.ndarray]:
    denominator = np.ones_like(np.asarray(next(iter(partial_pressures_pa.values())), dtype=float))
    affinities: Dict[str, float] = {}
    for component, params in component_params.items():
        b = _param(params, "b", "inverse_pressure")
        affinities[component] = b
        denominator = denominator + b * np.maximum(np.asarray(partial_pressures_pa.get(component, 0.0)), 0.0)
    result: Dict[str, np.ndarray] = {}
    for component, params in component_params.items():
        qs = _param(params, "qs", "loading")
        p = np.maximum(np.asarray(partial_pressures_pa.get(component, 0.0)), 0.0)
        result[component] = qs * affinities[component] * p / denominator
    return result


def competitive_dsl(
    partial_pressures_pa: Mapping[str, Any],
    component_params: Mapping[str, Mapping[str, Any]],
) -> Dict[str, np.ndarray]:
    """Two-site competitive Langmuir with shared saturation per site."""

    result: Dict[str, np.ndarray] = {}
    site_values = []
    for site in (1, 2):
        denominator = np.ones_like(np.asarray(next(iter(partial_pressures_pa.values())), dtype=float))
        for component, params in component_params.items():
            site_params = params.get(f"site{site}", params)
            b = _param(site_params, "b" if f"b{site}" not in site_params else f"b{site}", "inverse_pressure")
            denominator = denominator + b * np.maximum(
                np.asarray(partial_pressures_pa.get(component, 0.0)), 0.0
            )
        site_values.append(denominator)
    for component, params in component_params.items():
        total = None
        for site, denominator in zip((1, 2), site_values):
            site_params = params.get(f"site{site}", params)
            q_name = "qs" if f"qs{site}" not in site_params else f"qs{site}"
            b_name = "b" if f"b{site}" not in site_params else f"b{site}"
            qs = _param(site_params, q_name, "loading")
            b = _param(site_params, b_name, "inverse_pressure")
            p = np.maximum(np.asarray(partial_pressures_pa.get(component, 0.0)), 0.0)
            contribution = qs * b * p / denominator
            total = contribution if total is None else total + contribution
        result[component] = total
    return result


def equilibrium_loadings(
    partial_pressures_pa: Mapping[str, Any],
    adsorption_model: str,
    parameters: Mapping[str, Any],
) -> Dict[str, np.ndarray]:
    """Evaluate all component equilibrium loadings through the registry."""

    model = adsorption_model.lower().replace("-", "_").replace(" ", "_")
    if model == "competitive_langmuir":
        return competitive_langmuir(partial_pressures_pa, parameters)
    if model == "competitive_dsl":
        return competitive_dsl(partial_pressures_pa, parameters)
    result: Dict[str, np.ndarray] = {}
    for component, component_parameters in parameters.items():
        pressure = partial_pressures_pa.get(component, 0.0)
        if model == "langmuir":
            result[component] = langmuir(
                pressure,
                _param(component_parameters, "qs", "loading"),
                _param(component_parameters, "b", "inverse_pressure"),
            )
        elif model == "dual_site_langmuir":
            result[component] = dual_site_langmuir(pressure, component_parameters)
        elif model == "sips":
            result[component] = sips(pressure, component_parameters)
        elif model == "toth":
            result[component] = toth(pressure, component_parameters)
        elif model == "henry":
            result[component] = henry(pressure, component_parameters)
        else:
            raise AdsorptionModelError(f"unsupported isotherm {adsorption_model!r}")
    return result


def ldf_rates(
    loading: Mapping[str, np.ndarray],
    equilibrium: Mapping[str, np.ndarray],
    adsorption: Mapping[str, Any],
) -> Dict[str, np.ndarray]:
    """Return dq/dt for equilibrium, LDF, or dual-resistance LDF modes."""

    kinetic_model = str(adsorption.get("kinetic_model", "LDF")).lower()
    kinetic_parameters = adsorption.get("kinetic_parameters", {})
    rates: Dict[str, np.ndarray] = {}
    for component, q in loading.items():
        q_star = np.asarray(equilibrium[component], dtype=float)
        params = kinetic_parameters.get(component, {}) if isinstance(kinetic_parameters, Mapping) else {}
        if kinetic_model == "equilibrium":
            k = si_value(
                params.get("rate_constant", 100.0),
                "rate_constant",
                field_name=f"adsorption.kinetic_parameters.{component}.rate_constant",
            )
            rates[component] = k * (q_star - q)
        elif kinetic_model in {"dual_resistance_ldf", "dual_resistance"}:
            k_fast = si_value(
                params.get("k_fast", params.get("k", 0.01)),
                "rate_constant",
                field_name=f"adsorption.kinetic_parameters.{component}.k_fast",
            )
            k_slow = si_value(
                params.get("k_slow", params.get("k", 0.001)),
                "rate_constant",
                field_name=f"adsorption.kinetic_parameters.{component}.k_slow",
            )
            fraction_fast = float(params.get("fraction_fast", 0.5))
            k_eff = fraction_fast * k_fast + (1.0 - fraction_fast) * k_slow
            rates[component] = k_eff * (q_star - q)
        else:
            k = si_value(
                params.get("k", params.get("rate_constant", 0.01)),
                "rate_constant",
                field_name=f"adsorption.kinetic_parameters.{component}.k",
            )
            rates[component] = k * (q_star - q)
    return rates
