"""One-dimensional gas-membrane separation backend."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Tuple

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares

from ..spec import ModelSpec, load_spec
from ..units import si_value


R_GAS = 8.31446261815324


def _q(spec: ModelSpec, path: str, dimension: str, default: float = None) -> float:
    raw = spec.get(path)
    if raw is None:
        if default is None:
            raise ValueError(f"missing required field {path}")
        return float(default)
    return si_value(raw, dimension, field_name=path)


def _component_values(spec: ModelSpec, path: str, dimension: str) -> np.ndarray:
    values = spec.get(path, {})
    if not isinstance(values, Mapping):
        raise ValueError(f"{path} must be a component mapping")
    return np.asarray(
        [si_value(values[component], dimension, field_name=f"{path}.{component}") for component in spec.components],
        dtype=float,
    )


def _effective_permeance(spec: ModelSpec, base: np.ndarray, temperature: float, pressure: np.ndarray) -> np.ndarray:
    membrane = spec.get("membrane", {})
    reference_temperature = _q(spec, "membrane.reference_temperature", "temperature", default=temperature)
    activation_energy = _q(spec, "membrane.activation_energy", "energy_per_mol", default=0.0)
    temperature_factor = math.exp(-activation_energy / R_GAS * (1.0 / temperature - 1.0 / reference_temperature))
    exponent = float(membrane.get("pressure_exponent", 0.0))
    reference_pressure = _q(spec, "membrane.reference_pressure", "pressure", default=101325.0)
    pressure_factor = np.power(np.maximum(pressure, 1.0) / reference_pressure, exponent)
    return base * temperature_factor * pressure_factor


def _composition(flows: np.ndarray) -> np.ndarray:
    total = max(float(np.sum(flows)), 1.0e-30)
    return np.maximum(flows, 0.0) / total


def _profile_rows(
    z: np.ndarray,
    retentate: np.ndarray,
    permeate: np.ndarray,
    fluxes: np.ndarray,
    components: List[str],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for index, position in enumerate(z):
        ret_y = _composition(retentate[index])
        perm_y = _composition(permeate[index])
        for component_index, component in enumerate(components):
            rows.append(
                {
                    "z_m": float(position),
                    "component": component,
                    "retentate_flow_mol_s": float(retentate[index, component_index]),
                    "permeate_flow_mol_s": float(permeate[index, component_index]),
                    "retentate_mole_fraction": float(ret_y[component_index]),
                    "permeate_mole_fraction": float(perm_y[component_index]),
                    "flux_mol_m2_s": float(fluxes[index, component_index]),
                }
            )
    return rows


def _run_co_current(
    spec: ModelSpec,
    feed_flows: np.ndarray,
    permeance: np.ndarray,
    area: float,
    length: float,
    feed_pressure: float,
    permeate_pressure: float,
    temperature: float,
    points: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    components = spec.components
    n = len(components)
    permeate_flow = _q(spec, "membrane.initial_permeate_flow", "molar_flow", default=1.0e-12)
    initial_permeate_y = np.asarray(
        spec.get("membrane.initial_permeate_composition", spec.get("feed.composition", {})), dtype=object
    )
    if isinstance(spec.get("membrane.initial_permeate_composition"), Mapping):
        initial_permeate_y = np.asarray(
            [float(spec.get(f"membrane.initial_permeate_composition.{c}", 0.0)) for c in components], dtype=float
        )
        initial_permeate_y = initial_permeate_y / max(initial_permeate_y.sum(), 1.0e-30)
    else:
        initial_permeate_y = _composition(feed_flows)
    state0 = np.concatenate([feed_flows, permeate_flow * initial_permeate_y])
    area_per_length = area / length

    def rhs(_z: float, state: np.ndarray) -> np.ndarray:
        ret = np.maximum(state[:n], 1.0e-20)
        perm = np.maximum(state[n:], 1.0e-20)
        ret_y = _composition(ret)
        perm_y = _composition(perm)
        p_feed = ret_y * feed_pressure
        p_perm = perm_y * permeate_pressure
        p_eff = _effective_permeance(spec, permeance, temperature, p_feed)
        flux = np.maximum(p_eff * (p_feed - p_perm), 0.0)
        # Limit local removal by the retentate inventory. This keeps the
        # explicit ODE non-negative even when a permeance is intentionally
        # stress-tested outside the dilute-flow regime.
        available_flux = np.maximum(state[:n], 0.0) / max(area_per_length, 1.0e-30)
        flux = np.minimum(flux, available_flux)
        return np.concatenate([-flux * area_per_length, flux * area_per_length])

    z_eval = np.linspace(0.0, length, max(points, 2))
    solution = solve_ivp(rhs, (0.0, length), state0, t_eval=z_eval, method="BDF", rtol=1e-7, atol=1e-12)
    if not solution.success:
        raise RuntimeError(f"co-current membrane integration failed: {solution.message}")
    state = solution.y.T
    ret = state[:, :n]
    perm = state[:, n:]
    fluxes = np.zeros_like(ret)
    for row in range(len(z_eval)):
        ret_y = _composition(ret[row])
        perm_y = _composition(perm[row])
        p_eff = _effective_permeance(spec, permeance, temperature, ret_y * feed_pressure)
        fluxes[row] = np.maximum(p_eff * (ret_y * feed_pressure - perm_y * permeate_pressure), 0.0)
    return z_eval, ret, perm, fluxes


def _run_counter_current(
    spec: ModelSpec,
    feed_flows: np.ndarray,
    permeance: np.ndarray,
    area: float,
    length: float,
    feed_pressure: float,
    permeate_pressure: float,
    temperature: float,
    points: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    n = len(spec.components)
    sweep_flow = _q(spec, "membrane.sweep_flow", "molar_flow", default=0.1 * float(feed_flows.sum()))
    sweep_map = spec.get("membrane.sweep_composition", spec.get("feed.composition", {}))
    if not isinstance(sweep_map, Mapping):
        raise ValueError("membrane.sweep_composition must be a mapping")
    sweep_y = np.asarray([float(sweep_map.get(c, 0.0)) for c in spec.components], dtype=float)
    sweep_y = sweep_y / max(sweep_y.sum(), 1.0e-30)
    target_at_L = sweep_flow * sweep_y
    area_per_length = area / length
    z_eval = np.linspace(0.0, length, max(points, 2))

    def integrate(permeate_at_zero: np.ndarray):
        state0 = np.concatenate([feed_flows, np.maximum(permeate_at_zero, 1.0e-14)])

        def rhs(_z: float, state: np.ndarray) -> np.ndarray:
            ret = np.maximum(state[:n], 1.0e-20)
            perm = np.maximum(state[n:], 1.0e-20)
            ret_y = _composition(ret)
            perm_y = _composition(perm)
            p_feed = ret_y * feed_pressure
            p_perm = perm_y * permeate_pressure
            p_eff = _effective_permeance(spec, permeance, temperature, p_feed)
            flux = np.maximum(p_eff * (p_feed - p_perm), 0.0)
            available_flux = np.maximum(state[:n], 0.0) / max(area_per_length, 1.0e-30)
            flux = np.minimum(flux, available_flux)
            # z points from retentate feed to retentate outlet; permeate flows
            # in the opposite direction, hence the negative sign.
            return np.concatenate([-flux * area_per_length, -flux * area_per_length])

        solution = solve_ivp(rhs, (0.0, length), state0, t_eval=z_eval, method="BDF", rtol=1e-7, atol=1e-12)
        if not solution.success:
            raise RuntimeError(solution.message)
        return solution

    scale = np.maximum(target_at_L, 1.0e-8)

    def residual(log_guess: np.ndarray) -> np.ndarray:
        guess = np.exp(log_guess)
        solution = integrate(guess)
        return (solution.y[n:, -1] - target_at_L) / scale

    initial = target_at_L + 0.1 * feed_flows
    fit = least_squares(residual, np.log(np.maximum(initial, 1.0e-12)), max_nfev=100)
    if not fit.success:
        raise RuntimeError(f"counter-current shooting failed: {fit.message}")
    solution = integrate(np.exp(fit.x))
    state = solution.y.T
    ret = state[:, :n]
    perm = state[:, n:]
    fluxes = np.zeros_like(ret)
    for row in range(len(z_eval)):
        ret_y = _composition(ret[row])
        perm_y = _composition(perm[row])
        p_eff = _effective_permeance(spec, permeance, temperature, ret_y * feed_pressure)
        fluxes[row] = np.maximum(p_eff * (ret_y * feed_pressure - perm_y * permeate_pressure), 0.0)
    return z_eval, ret, perm, fluxes


def run_membrane(source: Any, *, backend: str = "reduced_order") -> Dict[str, Any]:
    """Run co-current or counter-current 1-D membrane separation."""

    spec = load_spec(source)
    components = spec.components
    feed_y = np.asarray(
        [float(spec.get(f"feed.composition.{component}")) for component in components], dtype=float
    )
    feed_flows = _q(spec, "feed.molar_flow", "molar_flow") * feed_y
    feed_pressure = _q(spec, "feed.pressure", "pressure")
    temperature = _q(spec, "feed.temperature", "temperature")
    length = _q(spec, "membrane.length", "length")
    area = _q(spec, "membrane.area", "area", default=1.0)
    permeate_pressure = _q(spec, "membrane.permeate_pressure", "pressure")
    permeance = _component_values(spec, "membrane.permeance", "permeance")
    points = int(spec.get("numerics.spatial_elements", 50)) + 1
    mode = str(spec.get("membrane.mode", "co_current")).lower().replace("-", "_")
    if mode in {"countercurrent", "counter_current"}:
        mode = "counter_current"
        z, ret, perm, fluxes = _run_counter_current(
            spec, feed_flows, permeance, area, length, feed_pressure, permeate_pressure, temperature, points
        )
        sweep_flow = _q(spec, "membrane.sweep_flow", "molar_flow", default=0.1 * float(feed_flows.sum()))
        sweep_map = spec.get("membrane.sweep_composition", spec.get("feed.composition", {}))
        sweep_y = np.asarray([float(sweep_map.get(c, 0.0)) for c in components], dtype=float)
        sweep_y /= max(sweep_y.sum(), 1.0e-30)
        sweep_flows = sweep_flow * sweep_y
        product_flows = perm[0] - sweep_flows
        mass_residual = feed_flows + sweep_flows - ret[-1] - product_flows
        assumptions = ["counter-current solution uses a shooting/fixed-boundary approximation"]
    else:
        mode = "co_current"
        z, ret, perm, fluxes = _run_co_current(
            spec, feed_flows, permeance, area, length, feed_pressure, permeate_pressure, temperature, points
        )
        product_flows = perm[-1]
        mass_residual = feed_flows - ret[-1] - product_flows
        assumptions = ["co-current permeate stream is initialized with a negligible seed flow"]
    ret_out = ret[-1]
    product_total = max(float(product_flows.sum()), 1.0e-30)
    ret_total = max(float(ret_out.sum()), 1.0e-30)
    target_component = str(spec.get("analysis.product_component", components[0]))
    target_index = components.index(target_component) if target_component in components else 0
    purity = float(product_flows[target_index] / product_total)
    recovery = float(product_flows[target_index] / max(feed_flows[target_index], 1.0e-30))
    stage_cut = product_total / max(float(feed_flows.sum()), 1.0e-30)
    mass_balance_error = float(np.max(np.abs(mass_residual) / np.maximum(np.abs(feed_flows), 1.0e-12)))
    stream_records = [
        {
            "stream": "feed",
            **{f"{c}_flow_mol_s": float(feed_flows[i]) for i, c in enumerate(components)},
            "total_flow_mol_s": float(feed_flows.sum()),
        },
        {
            "stream": "retentate",
            **{f"{c}_flow_mol_s": float(ret_out[i]) for i, c in enumerate(components)},
            "total_flow_mol_s": float(ret_total),
        },
        {
            "stream": "permeate",
            **{f"{c}_flow_mol_s": float(product_flows[i]) for i, c in enumerate(components)},
            "total_flow_mol_s": float(product_total),
        },
    ]
    warnings = [
        "constant-pressure ideal-gas membrane model; concentration-polarization and module pressure drop are omitted",
        "permeance and reaction/property parameters require independent experimental or literature support",
    ]
    summary = {
        "model_type": spec.model_type,
        "backend": backend,
        "solver": {"termination": "success", "message": "SciPy method-of-lines integration"},
        "mode": mode,
        "components": components,
        "purity": purity,
        "recovery": recovery,
        "stage_cut": stage_cut,
        "mass_balance_error": mass_balance_error,
        "target_component": target_component,
        "membrane_area_m2": area,
        "pressure_ratio": feed_pressure / max(permeate_pressure, 1.0),
        "assumptions": assumptions,
        "warnings": warnings,
    }
    return {
        "summary": summary,
        "streams": pd.DataFrame(stream_records),
        "profiles": pd.DataFrame(_profile_rows(z, ret, perm, fluxes, components)),
        "metrics": pd.DataFrame(
            [
                {"metric": "purity", "value": purity},
                {"metric": "recovery", "value": recovery},
                {"metric": "stage_cut", "value": stage_cut},
                {"metric": "mass_balance_error", "value": mass_balance_error},
            ]
        ),
        "convergence": {"kind": "spatial_integration", "points": len(z), "success": True},
        "assumptions": assumptions,
        "warnings": warnings,
        "figure_data": {
            "z_m": z.tolist(),
            "flux_mol_m2_s": fluxes.tolist(),
            "retentate_mole_fraction": [_composition(row).tolist() for row in ret],
            "permeate_mole_fraction": [_composition(row).tolist() for row in perm],
        },
    }
