"""Configurable cyclic adsorption (PSA/VSA/TSA) smoke backend.

The cycle is data-driven: step names, durations, inlet/outlet labels, and
pressure targets come from the specification. The backend is intentionally a
lumped-bed map suitable for workflow tests and initialization studies; a
distributed IDAES cycle remains a separate model-building task.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping

import numpy as np
import pandas as pd

from ..spec import ModelSpec, load_spec
from ..units import si_value
from .adsorption import equilibrium_loadings


R_GAS = 8.31446261815324


def _q(spec: ModelSpec, path: str, dimension: str, default: float = None) -> float:
    raw = spec.get(path)
    if raw is None:
        if default is None:
            raise ValueError(f"missing required field {path}")
        return float(default)
    return si_value(raw, dimension, field_name=path)


def _step_class(name: str) -> str:
    normalised = name.lower().replace("_", " ").replace("-", " ")
    if "adsorp" in normalised:
        return "adsorption"
    if "pressur" in normalised or "repressur" in normalised:
        return "pressurization"
    if "purge" in normalised:
        return "purge"
    if "equal" in normalised:
        return "equalization"
    if "blow" in normalised or "depressur" in normalised or "evac" in normalised:
        return "desorption"
    return "other"


def _normalised_composition(values: Mapping[str, Any], components: List[str]) -> np.ndarray:
    result = np.asarray([float(values.get(component, 0.0)) for component in components], dtype=float)
    total = result.sum()
    if total <= 0:
        raise ValueError("cycle inlet composition must have positive total")
    return result / total


def _equilibrium(spec: ModelSpec, pressure: float, composition: np.ndarray) -> np.ndarray:
    components = spec.components
    partial = {component: pressure * composition[i] for i, component in enumerate(components)}
    adsorption = spec.get("adsorption", {})
    params = adsorption.get("parameters", {})
    values = equilibrium_loadings(partial, adsorption.get("equilibrium_model", "langmuir"), params)
    return np.asarray([float(np.asarray(values[component])) for component in components], dtype=float)


def _kinetic_relaxation(spec: ModelSpec, duration: float, component: str) -> float:
    adsorption = spec.get("adsorption", {})
    kinetic = str(adsorption.get("kinetic_model", "LDF")).lower()
    params = adsorption.get("kinetic_parameters", {})
    component_params = params.get(component, {}) if isinstance(params, Mapping) else {}
    if kinetic == "equilibrium":
        return 1.0
    if kinetic in {"dual_resistance_ldf", "dual_resistance"}:
        k = float(component_params.get("k", component_params.get("k_fast", 0.01)))
    else:
        k = float(component_params.get("k", component_params.get("rate_constant", 0.01)))
    return float(1.0 - math.exp(-max(k, 0.0) * duration))


def run_psa(source: Any, *, backend: str = "reduced_order") -> Dict[str, Any]:
    """Run a configurable single-bed cycle and CSS convergence map."""

    spec = load_spec(source)
    components = spec.components
    feed_y = _normalised_composition(spec.get("feed.composition", {}), components)
    feed_flow = _q(spec, "feed.molar_flow", "molar_flow")
    feed_pressure = _q(spec, "feed.pressure", "pressure")
    temperature = _q(spec, "feed.temperature", "temperature")
    length = _q(spec, "geometry.length", "length")
    diameter = _q(spec, "geometry.diameter", "length")
    volume = math.pi * diameter**2 / 4.0 * length
    porosity = _q(spec, "bed.porosity", "dimensionless")
    solid_density = _q(spec, "bed.particle_density", "mass_density")
    solid_mass = (1.0 - porosity) * solid_density * volume
    cycle_settings = spec.get("cycle_settings", {})
    if not isinstance(cycle_settings, Mapping):
        cycle_settings = {}
    high_pressure = _q(spec, "cycle_settings.high_pressure", "pressure", default=feed_pressure)
    low_pressure = _q(spec, "cycle_settings.low_pressure", "pressure", default=1.0e4)
    max_cycles = int(cycle_settings.get("max_cycles", 25))
    css_tolerance = float(cycle_settings.get("css_tolerance", 1.0e-4))
    product_outlet = str(spec.get("analysis.product_outlet", "product"))
    product_component = str(spec.get("analysis.product_component", components[0]))
    target_index = components.index(product_component) if product_component in components else 0

    steps = spec.get("cycle", [])
    if not isinstance(steps, list) or not steps:
        raise ValueError("PSA cycle must contain at least one step")
    purge_y = feed_y
    if isinstance(spec.get("purge.composition"), Mapping):
        purge_y = _normalised_composition(spec.get("purge.composition"), components)

    state = np.zeros(len(components) + 1, dtype=float)
    state[0] = low_pressure
    previous_state = None
    convergence_records: List[Dict[str, Any]] = []
    stream_records: List[Dict[str, Any]] = []
    profile_records: List[Dict[str, Any]] = []
    cycle_metrics: List[Dict[str, Any]] = []
    all_assumptions = [
        "single-bed lumped cyclic map; distributed axial gradients are not represented",
        "ideal-gas bed void inventory and approximate pressure-work energy are used",
        "cycle metrics are backend outputs, not experimental or literature validation",
    ]
    cumulative_feed_target = 0.0

    for cycle_number in range(1, max_cycles + 1):
        cycle_product = np.zeros(len(components), dtype=float)
        cycle_input = np.zeros(len(components), dtype=float)
        cycle_energy = 0.0
        for step_index, raw_step in enumerate(steps):
            if not isinstance(raw_step, Mapping):
                raise ValueError(f"cycle step {step_index} must be a mapping")
            name = str(raw_step.get("name", f"step_{step_index + 1}"))
            duration = _q_from_mapping(raw_step, "duration", "time")
            kind = _step_class(name)
            inlet_label = str(raw_step.get("inlet", "closed" if kind == "desorption" else "feed"))
            outlet_label = str(raw_step.get("outlet", "waste" if kind == "desorption" else "product"))
            if "target_pressure" in raw_step:
                target_pressure = si_value(raw_step["target_pressure"], "pressure", field_name=f"cycle[{step_index}].target_pressure")
            elif kind == "desorption":
                target_pressure = low_pressure
            elif kind in {"adsorption", "pressurization", "equalization"}:
                target_pressure = high_pressure
            else:
                target_pressure = state[0]
            target_pressure = max(target_pressure, 1.0)
            pressure_start = float(state[0])
            pressure_end = float(target_pressure)
            contact_y = purge_y if inlet_label.lower() in {"purge", "sweep"} else feed_y
            if inlet_label.lower() in {"closed", "none", ""}:
                contact_y = np.zeros_like(feed_y)
            q_old = state[1:].copy()
            q_star = _equilibrium(spec, pressure_end, contact_y) if contact_y.sum() > 0 else np.zeros_like(q_old)
            relax = np.asarray(
                [_kinetic_relaxation(spec, duration, component) for component in components], dtype=float
            )
            if kind == "other":
                relax *= 0.0
            gas_inventory_start = porosity * volume * pressure_start / (R_GAS * temperature)
            gas_inventory_end = porosity * volume * pressure_end / (R_GAS * temperature)
            gas_in = max(gas_inventory_end - gas_inventory_start, 0.0) * contact_y
            gas_out = max(gas_inventory_start - gas_inventory_end, 0.0) * feed_y
            feed_in = np.zeros_like(feed_y)
            if inlet_label.lower() not in {"closed", "none", ""}:
                feed_in = feed_flow * duration * contact_y
            raw_q_new = q_old + relax * (q_star - q_old)
            raw_uptake = np.maximum(raw_q_new - q_old, 0.0) * solid_mass
            # A lumped map cannot create adsorption from an unlimited
            # reservoir: uptake is capped by gas admitted during this step.
            # This keeps the periodic material balance meaningful even when a
            # deliberately large equilibrium capacity is used in a smoke case.
            uptake = np.minimum(raw_uptake, feed_in + gas_in)
            q_new = q_old + np.where(raw_uptake > 0.0, uptake / max(solid_mass, 1.0e-30), raw_q_new - q_old)
            desorbed = np.maximum(q_old - q_new, 0.0) * solid_mass
            outlet_amount = np.maximum(feed_in + gas_out + desorbed - uptake, 0.0)
            # Count both continuous inlet flow and gas inventory admitted
            # during pressure increases; otherwise cyclic recovery can exceed
            # one simply because the void volume was omitted from the basis.
            cycle_input += feed_in + gas_in
            if outlet_label == product_outlet:
                cycle_product += outlet_amount
            cycle_energy += abs(gas_inventory_end - gas_inventory_start) * R_GAS * temperature
            state[0] = pressure_end
            state[1:] = q_new
            record: Dict[str, Any] = {
                "cycle": cycle_number,
                "step": step_index + 1,
                "name": name,
                "kind": kind,
                "duration_s": duration,
                "inlet": inlet_label,
                "outlet": outlet_label,
                "pressure_start_pa": pressure_start,
                "pressure_end_pa": pressure_end,
                "uptake_total_mol": float(uptake.sum()),
                "desorbed_total_mol": float(desorbed.sum()),
                "outlet_total_mol": float(outlet_amount.sum()),
            }
            for index, component in enumerate(components):
                record[f"{component}_outlet_mol"] = float(outlet_amount[index])
                record[f"{component}_loading_mol_kg"] = float(q_new[index])
            stream_records.append(record)
            for index, component in enumerate(components):
                profile_records.append(
                    {
                        "cycle": cycle_number,
                        "step": step_index + 1,
                        "name": name,
                        "component": component,
                        "loading_mol_kg": float(q_new[index]),
                        "pressure_pa": pressure_end,
                    }
                )

        cycle_time = sum(_q_from_mapping(step, "duration", "time") for step in steps)
        product_total = float(cycle_product.sum())
        product_purity = float(cycle_product[target_index] / product_total) if product_total > 0 else 0.0
        feed_target = float(cycle_input[target_index])
        # Feed passed through all cycles is the basis for the reported recovery.
        cumulative_feed_target += feed_target
        recovery = float(cycle_product[target_index] / feed_target) if feed_target > 0 else 0.0
        productivity = float(cycle_product[target_index] / max(solid_mass * cycle_time, 1.0e-30))
        state_scale = np.maximum(np.abs(state), 1.0)
        css_delta = (
            float(np.max(np.abs(state - previous_state) / state_scale))
            if previous_state is not None
            else None
        )
        converged = bool(css_delta is not None and css_delta < css_tolerance)
        convergence_records.append(
            {"cycle": cycle_number, "state_delta": css_delta, "tolerance": css_tolerance, "converged": converged}
        )
        cycle_metrics.append(
            {
                "cycle": cycle_number,
                "purity": product_purity,
                "recovery": recovery,
                "productivity_mol_kg_s": productivity,
                "energy_consumption_j": cycle_energy,
                "product_total_mol": product_total,
                "feed_target_mol": feed_target,
                "css_state_delta": css_delta,
            }
        )
        previous_state = state.copy()
        if converged:
            break

    final_metrics = cycle_metrics[-1]
    summary = {
        "model_type": spec.model_type,
        "backend": backend,
        "solver": {"termination": "not_applicable", "message": "explicit reduced-order cycle map"},
        "components": components,
        "cycles_run": len(cycle_metrics),
        "css_converged": bool(convergence_records[-1]["converged"]),
        "css_tolerance": css_tolerance,
        "purity": final_metrics["purity"],
        "recovery": final_metrics["recovery"],
        "productivity_mol_kg_s": final_metrics["productivity_mol_kg_s"],
        "energy_consumption_j": final_metrics["energy_consumption_j"],
        "product_component": product_component,
        "assumptions": all_assumptions,
        "warnings": [
            "This cycle map does not resolve axial concentration, temperature, or pressure profiles.",
            "CSS convergence of a reduced-order map is not proof of a validated PSA model.",
        ],
    }
    return {
        "summary": summary,
        "streams": pd.DataFrame(stream_records),
        "profiles": pd.DataFrame(profile_records),
        "metrics": pd.DataFrame(cycle_metrics),
        "convergence": {"kind": "cyclic_steady_state", "records": convergence_records},
        "assumptions": all_assumptions,
        "warnings": summary["warnings"],
        "figure_data": {
            "cycle": [row["cycle"] for row in cycle_metrics],
            "purity": [row["purity"] for row in cycle_metrics],
            "recovery": [row["recovery"] for row in cycle_metrics],
            "css_state_delta": [row["css_state_delta"] for row in cycle_metrics],
        },
    }


def _q_from_mapping(mapping: Mapping[str, Any], key: str, dimension: str) -> float:
    if key not in mapping:
        raise ValueError(f"missing {key!r} in cycle step")
    return si_value(mapping[key], dimension, field_name=f"cycle_step.{key}")
