"""Conservative 1-D fixed-bed adsorption breakthrough backend.

This module is a transparent SciPy method-of-lines reference backend. It is
used for smoke tests and workflow demonstrations; the optional Pyomo.DAE
builder is in :mod:`idaes_process_modeler.idaes_adapter`.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, List, Mapping, Optional

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp

from ..spec import ModelSpec, load_spec
from ..units import si_value
from .adsorption import equilibrium_loadings, ldf_rates


R_GAS = 8.31446261815324


def _integral(values: np.ndarray, grid: np.ndarray) -> float:
    """Use the NumPy 2.x name while retaining NumPy 1.x compatibility."""

    trapezoid = getattr(np, "trapezoid", getattr(np, "trapz", None))
    if trapezoid is None:  # pragma: no cover - defensive for unusual NumPy builds
        raise RuntimeError("NumPy does not provide a trapezoidal integration function")
    return float(trapezoid(values, grid))


@dataclass
class FixedBedRun:
    result: Dict[str, Any]


def _value(spec: ModelSpec, path: str, dimension: str, default: Optional[float] = None) -> float:
    raw = spec.get(path)
    if raw is None:
        if default is None:
            raise ValueError(f"missing required field {path}")
        return default
    return si_value(raw, dimension, field_name=path)


def _composition(spec: ModelSpec) -> np.ndarray:
    return np.asarray([float(spec.get(f"feed.composition.{component}")) for component in spec.components])


def _parameter_mapping(spec: ModelSpec) -> Mapping[str, Any]:
    value = spec.get("adsorption.parameters", {})
    return value if isinstance(value, Mapping) else {}


def _time_grid(spec: ModelSpec) -> tuple:
    numerics = spec.get("numerics", {})
    horizon = _value(spec, "numerics.time_horizon", "time", default=1800.0)
    if "time_step" in numerics:
        time_step = _value(spec, "numerics.time_step", "time", default=20.0)
        count = max(2, int(math.ceil(horizon / time_step)) + 1)
        return np.linspace(0.0, horizon, count), time_step
    time_points = int(numerics.get("time_points", 101))
    return np.linspace(0.0, horizon, max(2, time_points)), horizon / max(1, time_points - 1)


def _ergun_gradient(spec: ModelSpec, pressure_pa: float, temperature_k: float, velocity: float) -> float:
    eps = _value(spec, "bed.porosity", "dimensionless")
    dp = _value(spec, "bed.particle_diameter", "length", default=2.0e-3)
    viscosity = _value(spec, "bed.viscosity", "viscosity", default=1.8e-5)
    gas_density = pressure_pa / (R_GAS * temperature_k) * 0.029
    return (
        150.0 * viscosity * (1.0 - eps) ** 2 * velocity / (eps**3 * dp**2)
        + 1.75 * gas_density * (1.0 - eps) * velocity**2 / (eps**3 * dp)
    )


def run_fixed_bed(source: Any, *, backend: str = "reduced_order") -> Dict[str, Any]:
    """Run a 1-D binary/multicomponent fixed-bed breakthrough simulation."""

    spec = load_spec(source)
    components = spec.components
    n_components = len(components)
    if n_components < 2:
        raise ValueError("fixed-bed simulation requires at least two components")
    length = _value(spec, "geometry.length", "length")
    diameter = _value(spec, "geometry.diameter", "length")
    area = math.pi * diameter**2 / 4.0
    eps = _value(spec, "bed.porosity", "dimensionless")
    solid_density = _value(spec, "bed.particle_density", "mass_density")
    feed_pressure = _value(spec, "feed.pressure", "pressure")
    temperature = _value(spec, "feed.temperature", "temperature")
    molar_flow = _value(spec, "feed.molar_flow", "molar_flow")
    feed_y = _composition(spec)
    if "superficial_velocity" in spec.data.get("bed", {}):
        velocity = _value(spec, "bed.superficial_velocity", "velocity")
    else:
        velocity = molar_flow * R_GAS * temperature / feed_pressure / area
    axial_dispersion = _value(spec, "bed.axial_dispersion", "diffusivity", default=1.0e-4)
    nz = int(spec.get("numerics.spatial_elements", 30))
    nz = max(2, nz)
    dz = length / nz
    times, max_step = _time_grid(spec)
    inlet_concentration = feed_y * feed_pressure / (R_GAS * temperature)
    adsorption = spec.get("adsorption", {})
    equilibrium_model = str(adsorption.get("equilibrium_model", "langmuir"))
    parameters = _parameter_mapping(spec)
    initial_loading = spec.get("initial_loading", {})
    q0 = np.zeros((n_components, nz), dtype=float)
    for index, component in enumerate(components):
        if isinstance(initial_loading, Mapping) and component in initial_loading:
            q0[index, :] = si_value(
                initial_loading[component], "loading", field_name=f"initial_loading.{component}"
            )
    c0 = np.zeros((n_components, nz), dtype=float)

    def rhs(_time: float, state: np.ndarray) -> np.ndarray:
        concentration = state[: n_components * nz].reshape(n_components, nz)
        loading = state[n_components * nz :].reshape(n_components, nz)
        partial = {
            component: np.maximum(concentration[index] * R_GAS * temperature, 0.0)
            for index, component in enumerate(components)
        }
        q_star_by_component = equilibrium_loadings(partial, equilibrium_model, parameters)
        q_star = np.vstack([np.asarray(q_star_by_component[component]) for component in components])
        loading_by_component = {
            component: loading[index] for index, component in enumerate(components)
        }
        rate_by_component = ldf_rates(loading_by_component, q_star_by_component, adsorption)
        dqdt = np.vstack([rate_by_component[component] for component in components])

        flux = np.empty((n_components, nz + 1), dtype=float)
        flux[:, 0] = velocity * inlet_concentration - eps * axial_dispersion * (
            concentration[:, 0] - inlet_concentration
        ) / dz
        for cell in range(nz - 1):
            flux[:, cell + 1] = velocity * concentration[:, cell] - eps * axial_dispersion * (
                concentration[:, cell + 1] - concentration[:, cell]
            ) / dz
        # Zero dispersive gradient at the outlet.
        flux[:, nz] = velocity * concentration[:, nz - 1]
        dcdt = -(flux[:, 1:] - flux[:, :-1]) / (eps * dz)
        dcdt = dcdt - ((1.0 - eps) * solid_density / eps) * dqdt
        return np.concatenate([dcdt.ravel(), dqdt.ravel()])

    solution = solve_ivp(
        rhs,
        (float(times[0]), float(times[-1])),
        np.concatenate([c0.ravel(), q0.ravel()]),
        t_eval=times,
        method=str(spec.get("numerics.integrator", "BDF")),
        rtol=float(spec.get("numerics.rtol", 1.0e-5)),
        atol=float(spec.get("numerics.atol", 1.0e-8)),
        max_step=max_step,
        dense_output=True,
    )
    if solution.y.shape[1] != len(times):
        raise RuntimeError(f"fixed-bed integrator returned incomplete output: {solution.message}")

    concentration = solution.y[: n_components * nz].reshape(n_components, nz, -1).transpose(2, 0, 1)
    loading = solution.y[n_components * nz :].reshape(n_components, nz, -1).transpose(2, 0, 1)
    concentration = np.maximum(concentration, 0.0)
    loading = np.maximum(loading, 0.0)
    outlet = concentration[:, :, -1]
    outlet_total_concentration = np.maximum(outlet.sum(axis=1), 1.0e-30)
    outlet_y = outlet / outlet_total_concentration[:, None]
    z = (np.arange(nz, dtype=float) + 0.5) * dz
    pressure_gradient = _ergun_gradient(spec, feed_pressure, temperature, velocity)
    pressure_profile = np.maximum(feed_pressure - pressure_gradient * z, 1.0)

    # Conservative component inventory check for the semi-discrete equations.
    # Use a denser audit grid than the reporting grid so a coarse user-facing
    # output interval does not dominate the balance quadrature error.
    inventory_by_component = eps * concentration * dz + (1.0 - eps) * solid_density * loading * dz
    audit_times = np.linspace(float(times[0]), float(times[-1]), max(1001, len(times) * 10))
    audit_state = solution.sol(audit_times)
    audit_concentration = audit_state[: n_components * nz].reshape(n_components, nz, -1).transpose(2, 0, 1)
    audit_loading = audit_state[n_components * nz :].reshape(n_components, nz, -1).transpose(2, 0, 1)
    audit_concentration = np.maximum(audit_concentration, 0.0)
    audit_loading = np.maximum(audit_loading, 0.0)
    audit_inlet_flux = velocity * inlet_concentration[None, :] - eps * axial_dispersion * (
        audit_concentration[:, :, 0] - inlet_concentration[None, :]
    ) / dz
    audit_outlet_flux = velocity * audit_concentration[:, :, -1]
    inlet_total = np.asarray([_integral(audit_inlet_flux[:, i], audit_times) for i in range(n_components)])
    outlet_flow_by_component = np.asarray(
        [_integral(audit_outlet_flux[:, i], audit_times) for i in range(n_components)]
    )
    initial_inventory = np.zeros(n_components)
    final_inventory = (
        eps * audit_concentration[-1].sum(axis=1) * dz
        + (1.0 - eps) * solid_density * audit_loading[-1].sum(axis=1) * dz
    )
    component_error = inlet_total - outlet_flow_by_component - final_inventory + initial_inventory
    scale = np.maximum(np.abs(inlet_total), 1.0e-12)
    mass_balance_error = float(np.max(np.abs(component_error) / scale))

    breakthrough_component = str(spec.get("analysis.breakthrough_component", components[0]))
    target_index = components.index(breakthrough_component) if breakthrough_component in components else 0
    feed_fraction = max(feed_y[target_index], 1.0e-30)
    fraction = outlet[:, target_index] / np.maximum(outlet.sum(axis=1), 1.0e-30) / feed_fraction
    threshold = float(spec.get("analysis.breakthrough_fraction", 0.05))
    crossing = np.flatnonzero(fraction >= threshold)
    breakthrough_time = float(times[crossing[0]]) if len(crossing) else None

    stream_records: List[Dict[str, Any]] = []
    for row, time in enumerate(times):
        record: Dict[str, Any] = {
            "time_s": float(time),
            "total_concentration_mol_m3": float(outlet_total_concentration[row]),
        }
        for index, component in enumerate(components):
            record[f"{component}_concentration_mol_m3"] = float(outlet[row, index])
            record[f"{component}_mole_fraction"] = float(outlet_y[row, index])
        stream_records.append(record)
    profile_records: List[Dict[str, Any]] = []
    for row, time in enumerate(times):
        for cell, position in enumerate(z):
            for index, component in enumerate(components):
                profile_records.append(
                    {
                        "time_s": float(time),
                        "z_m": float(position),
                        "component": component,
                        "concentration_mol_m3": float(concentration[row, index, cell]),
                        "loading_mol_kg": float(loading[row, index, cell]),
                        "pressure_pa": float(pressure_profile[cell]),
                    }
                )

    assumptions = []
    if "bed.superficial_velocity" not in spec.data.get("bed", {}):
        assumptions.append("superficial velocity computed from ideal-gas feed flow and cross-sectional area")
    if "bed.axial_dispersion" not in spec.data.get("bed", {}):
        assumptions.append("axial dispersion defaulted to 1e-4 m2/s")
    if "bed.particle_diameter" not in spec.data.get("bed", {}):
        assumptions.append("particle diameter defaulted to 2 mm for Ergun diagnostic")
    if "bed.viscosity" not in spec.data.get("bed", {}):
        assumptions.append("gas viscosity defaulted to 1.8e-5 Pa s in Ergun diagnostic")
    warnings = [
        "reduced-order constant-pressure concentration model; Ergun pressure profile is diagnostic, not coupled",
        "results are not experimental validation or a benchmark against Aspen/IDAES",
    ]
    summary = {
        "model_type": spec.model_type,
        "backend": backend,
        "solver": {"termination": "success" if solution.success else "failed", "message": solution.message},
        "components": components,
        "spatial_elements": nz,
        "time_points": len(times),
        "breakthrough_component": breakthrough_component,
        "breakthrough_time_s": breakthrough_time,
        "final_outlet_target_fraction": float(fraction[-1]),
        "mass_balance_error": mass_balance_error,
        "pressure_drop_pa": float(pressure_gradient * length),
        "final_outlet_mole_fraction": {
            component: float(outlet_y[-1, index]) for index, component in enumerate(components)
        },
        "assumptions": assumptions,
        "warnings": warnings,
    }
    metrics = pd.DataFrame(
        [
            {"metric": "breakthrough_time_s", "value": breakthrough_time},
            {"metric": "final_outlet_target_fraction", "value": float(fraction[-1])},
            {"metric": "mass_balance_error", "value": mass_balance_error},
            {"metric": "pressure_drop_pa", "value": float(pressure_gradient * length)},
        ]
    )
    return {
        "summary": summary,
        "streams": pd.DataFrame(stream_records),
        "profiles": pd.DataFrame(profile_records),
        "metrics": metrics,
        "convergence": {
            "kind": "time_integration",
            "integrator": str(spec.get("numerics.integrator", "BDF")),
            "success": bool(solution.success),
            "message": solution.message,
        },
        "assumptions": assumptions,
        "warnings": warnings,
        "figure_data": {
            "time_s": times.tolist(),
            "outlet_mole_fraction": outlet_y.tolist(),
            "z_m": z.tolist(),
            "pressure_profile_pa": pressure_profile.tolist(),
        },
    }
