"""PFR-like membrane-reactor and fixed-bed reactor reference backends."""

from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp

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


def run_membrane_reactor(source: Any, *, backend: str = "reduced_order") -> Dict[str, Any]:
    """Integrate reaction-side molar flows and optional distributed H2 removal."""

    spec = load_spec(source)
    components = spec.components
    n = len(components)
    feed_y = np.asarray(
        [float(spec.get(f"feed.composition.{component}")) for component in components], dtype=float
    )
    feed_flow = _q(spec, "feed.molar_flow", "molar_flow")
    feed_flows = feed_flow * feed_y
    temperature = _q(spec, "feed.temperature", "temperature")
    pressure = _q(spec, "feed.pressure", "pressure")
    length = _q(spec, "geometry.length", "length")
    points = max(2, int(spec.get("numerics.spatial_elements", 50)) + 1)
    reaction = spec.get("reaction", {})
    stoich_map = reaction.get("stoichiometry", {})
    stoich = np.asarray([float(stoich_map.get(component, 0.0)) for component in components], dtype=float)
    pre_exponential = _q(spec, "reaction.pre_exponential", "rate_constant")
    activation_energy = _q(spec, "reaction.activation_energy", "energy_per_mol")
    reference_temperature = _q(spec, "reaction.reference_temperature", "temperature", default=temperature)
    rate_constant = pre_exponential * math.exp(
        -activation_energy / R_GAS * (1.0 / temperature - 1.0 / reference_temperature)
    )
    reactant = str(reaction.get("rate_component", components[0]))
    reactant_index = components.index(reactant) if reactant in components else 0
    residence_velocity = _q(spec, "reaction.residence_velocity", "velocity", default=1.0)
    membrane_enabled = spec.model_type == "membrane_reactor"
    if membrane_enabled:
        membrane = spec.get("membrane", {})
        membrane_area = _q(spec, "membrane.area", "area", default=1.0)
        membrane_permeate_pressure = _q(spec, "membrane.permeate_pressure", "pressure")
        permeance_map = membrane.get("permeance", {})
        target = str(membrane.get("membrane_component", "H2"))
        target_index = components.index(target) if target in components else 0
        target_permeance = si_value(
            permeance_map.get(components[target_index]),
            "permeance",
            field_name=f"membrane.permeance.{components[target_index]}",
        )
        area_per_length = membrane_area / length
    else:
        target_index = -1
        target_permeance = 0.0
        membrane_permeate_pressure = 1.0
        area_per_length = 0.0

    sweep_flow = _q(spec, "membrane.sweep_flow", "molar_flow", default=0.0) if membrane_enabled else 0.0
    sweep_y = np.zeros(n, dtype=float)
    if membrane_enabled:
        sweep_map = spec.get("membrane.sweep_composition", {})
        if isinstance(sweep_map, dict):
            sweep_y = np.asarray([float(sweep_map.get(c, 0.0)) for c in components], dtype=float)
            if sweep_y.sum() <= 0:
                sweep_y[target_index] = 1.0
            sweep_y /= sweep_y.sum()
    state0 = np.concatenate([feed_flows, sweep_flow * sweep_y])

    def rhs(_z: float, state: np.ndarray) -> np.ndarray:
        flows = np.maximum(state[:n], 1.0e-20)
        permeate = np.maximum(state[n:], 1.0e-20)
        y = flows / max(flows.sum(), 1.0e-30)
        yp = permeate / max(permeate.sum(), 1.0e-30)
        reaction_rate = rate_constant * flows[reactant_index] / max(residence_velocity, 1.0e-30)
        reaction_change = stoich * reaction_rate
        membrane_change = np.zeros(n, dtype=float)
        if membrane_enabled:
            partial_feed = y[target_index] * pressure
            partial_perm = yp[target_index] * membrane_permeate_pressure
            flux = max(target_permeance * (partial_feed - partial_perm), 0.0) * area_per_length
            membrane_change[target_index] = -flux
        return np.concatenate([reaction_change + membrane_change, -membrane_change])

    z = np.linspace(0.0, length, points)
    solution = solve_ivp(rhs, (0.0, length), state0, t_eval=z, method="BDF", rtol=1.0e-7, atol=1.0e-12)
    if not solution.success:
        raise RuntimeError(f"reactor integration failed: {solution.message}")
    state = np.maximum(solution.y.T, 0.0)
    ret = state[:, :n]
    perm = state[:, n:]
    conversion = float((feed_flows[reactant_index] - ret[-1, reactant_index]) / max(feed_flows[reactant_index], 1.0e-30))
    rows: List[Dict[str, Any]] = []
    for row, position in enumerate(z):
        total = max(float(ret[row].sum()), 1.0e-30)
        for index, component in enumerate(components):
            rows.append(
                {
                    "z_m": float(position),
                    "component": component,
                    "reaction_side_flow_mol_s": float(ret[row, index]),
                    "reaction_side_mole_fraction": float(ret[row, index] / total),
                    "permeate_flow_mol_s": float(perm[row, index]),
                }
            )
    summary = {
        "model_type": spec.model_type,
        "backend": backend,
        "solver": {"termination": "success", "message": "SciPy PFR-like integration"},
        "components": components,
        "conversion": conversion,
        "reaction_rate_constant_s-1": rate_constant,
        "membrane_component": components[target_index] if membrane_enabled else None,
        "permeated_target_mol_s": float(perm[-1, target_index]) if membrane_enabled else 0.0,
        "warnings": [
            "PFR-like reduced-order reactor; detailed IDAES thermodynamics and heat effects are not included",
            "stoichiometric and kinetic parameters need independent validation",
        ],
    }
    return {
        "summary": summary,
        "streams": pd.DataFrame(
            [
                {"stream": "feed", **{f"{c}_mol_s": float(feed_flows[i]) for i, c in enumerate(components)}},
                {"stream": "reaction_outlet", **{f"{c}_mol_s": float(ret[-1, i]) for i, c in enumerate(components)}},
                {"stream": "permeate", **{f"{c}_mol_s": float(perm[-1, i]) for i, c in enumerate(components)}},
            ]
        ),
        "profiles": pd.DataFrame(rows),
        "metrics": pd.DataFrame(
            [{"metric": "conversion", "value": conversion}, {"metric": "permeated_target_mol_s", "value": summary["permeated_target_mol_s"]}]
        ),
        "convergence": {"kind": "spatial_integration", "points": points, "success": True},
        "assumptions": ["constant temperature and pressure", "single reaction-rate expression"],
        "warnings": summary["warnings"],
        "figure_data": {"z_m": z.tolist(), "reaction_side_flows": ret.tolist(), "permeate_flows": perm.tolist()},
    }
