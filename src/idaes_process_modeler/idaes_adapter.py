"""Optional Pyomo.DAE/IDAES integration points.

The adapter is guarded so the base package remains importable for lightweight
workflow checks. It deliberately builds an equation-oriented fixed-bed
reference model instead of pretending to supply a universal IDAES property
package. A production model should replace the simple ideal-gas expressions
with a configured IDAES property package and unit operation.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
from typing import Any, Dict, Optional

from .spec import ModelSpec, load_spec
from .units import si_value


@dataclass
class DependencyStatus:
    idaes: bool
    pyomo: bool
    pyomo_dae: bool
    ipopt: bool
    cbc: bool
    messages: list

    def as_dict(self) -> Dict[str, Any]:
        return {
            "idaes": self.idaes,
            "pyomo": self.pyomo,
            "pyomo_dae": self.pyomo_dae,
            "ipopt": self.ipopt,
            "cbc": self.cbc,
            "messages": self.messages,
        }


def dependency_status() -> DependencyStatus:
    """Return optional dependency and solver availability without raising."""

    pyomo = importlib.util.find_spec("pyomo") is not None
    idaes_available = importlib.util.find_spec("idaes") is not None
    pyomo_dae = pyomo
    messages = []
    ipopt = False
    cbc = False
    if pyomo:
        try:
            from pyomo.environ import SolverFactory

            ipopt_solver = SolverFactory("ipopt")
            cbc_solver = SolverFactory("cbc")
            ipopt = bool(ipopt_solver.available(exception_flag=False))
            cbc = bool(cbc_solver.available(exception_flag=False))
            if idaes_available:
                import idaes as idaes_module

                for name, solver_object in (("ipopt", ipopt_solver), ("cbc", cbc_solver)):
                    extension_path = Path(idaes_module.bin_directory) / name
                    if extension_path.exists():
                        solver_object.set_executable(str(extension_path), validate=False)
                ipopt = bool(ipopt_solver.available(exception_flag=False))
                cbc = bool(cbc_solver.available(exception_flag=False))
        except Exception as exc:  # pragma: no cover - dependency-specific
            messages.append(f"solver probe failed: {exc}")
    if not idaes_available:
        messages.append("IDAES is not installed; install idaes-pse and run 'idaes get-extensions'")
    return DependencyStatus(idaes_available, pyomo, pyomo_dae, ipopt, cbc, messages)


def build_fixed_bed_dae(source: Any):
    """Build a small dynamic fixed-bed model using IDAES FlowsheetBlock + Pyomo.DAE.

    Supported equation-of-state assumptions are ideal gas and constant
    temperature/pressure. The model is an adapter example for development and
    initialization; it is not a validated thermodynamic property package.
    """

    status = dependency_status()
    if not status.pyomo or not status.pyomo_dae:
        raise RuntimeError("Pyomo and Pyomo.DAE are required for the IDAES adapter")
    if not status.idaes:
        raise RuntimeError("IDAES is required for the IDAES adapter")
    import pyomo.environ as pyo
    from idaes.core import FlowsheetBlock
    from pyomo.dae import ContinuousSet, DerivativeVar

    spec = load_spec(source)
    if spec.model_type not in {"fixed_bed_adsorption", "psa", "vsa", "tsa"}:
        raise ValueError("the current adapter builds fixed-bed adsorption specifications")
    components = list(spec.components)
    length = si_value(spec.get("geometry.length"), "length", field_name="geometry.length")
    horizon = si_value(
        spec.get("numerics.time_horizon", "1800 s"), "time", field_name="numerics.time_horizon"
    )
    pressure = si_value(spec.get("feed.pressure"), "pressure", field_name="feed.pressure")
    temperature = si_value(spec.get("feed.temperature"), "temperature", field_name="feed.temperature")
    porosity = si_value(spec.get("bed.porosity"), "dimensionless", field_name="bed.porosity")
    solid_density = si_value(
        spec.get("bed.particle_density"), "mass_density", field_name="bed.particle_density"
    )
    velocity = si_value(
        spec.get("bed.superficial_velocity", "0.01 m/s"), "velocity", field_name="bed.superficial_velocity"
    )
    axial_dispersion = si_value(
        spec.get("bed.axial_dispersion", "1e-4 m2/s"),
        "diffusivity",
        field_name="bed.axial_dispersion",
    )
    feed_y = {component: float(spec.get(f"feed.composition.{component}")) for component in components}
    adsorption = spec.get("adsorption", {})
    equilibrium_model = str(adsorption.get("equilibrium_model", "langmuir")).lower().replace("-", "_")
    if equilibrium_model not in {"langmuir", "dual_site_langmuir"}:
        raise ValueError("Pyomo adapter currently supports langmuir and dual_site_langmuir")
    parameters = adsorption.get("parameters", {})

    model = pyo.ConcreteModel(name="idaes_process_modeler_fixed_bed")
    model.fs = FlowsheetBlock(
        dynamic=True,
        time_set=[0.0, horizon],
        time_units=pyo.units.s,
    )
    model.fs.z = ContinuousSet(bounds=(0.0, length))
    model.fs.components = pyo.Set(initialize=components, ordered=True)
    model.fs.C = pyo.Var(model.fs.time, model.fs.z, model.fs.components, bounds=(0.0, None), initialize=0.0)
    model.fs.q = pyo.Var(model.fs.time, model.fs.z, model.fs.components, bounds=(0.0, None), initialize=0.0)
    model.fs.dCdt = DerivativeVar(model.fs.C, wrt=model.fs.time)
    model.fs.dCdz = DerivativeVar(model.fs.C, wrt=model.fs.z)
    model.fs.d2Cdz2 = DerivativeVar(model.fs.dCdz, wrt=model.fs.z)
    model.fs.dqdt = DerivativeVar(model.fs.q, wrt=model.fs.time)
    model.fs.feed_pressure = pyo.Param(initialize=pressure, mutable=False)
    model.fs.temperature = pyo.Param(initialize=temperature, mutable=False)
    model.fs.porosity = pyo.Param(initialize=porosity, mutable=False)
    model.fs.solid_density = pyo.Param(initialize=solid_density, mutable=False)
    model.fs.velocity = pyo.Param(initialize=velocity, mutable=False)
    model.fs.axial_dispersion = pyo.Param(initialize=axial_dispersion, mutable=False)
    model.fs.feed_concentration = pyo.Param(
        model.fs.components,
        initialize={c: feed_y[c] * pressure / (8.31446261815324 * temperature) for c in components},
        mutable=False,
    )

    def qeq_rule(m, t, z, component):
        params = parameters.get(component, {})
        concentration_pressure = m.C[t, z, component] * m.temperature * 8.31446261815324
        if equilibrium_model == "langmuir":
            qs = si_value(params.get("qs"), "loading", field_name=f"adsorption.parameters.{component}.qs")
            b = si_value(params.get("b"), "inverse_pressure", field_name=f"adsorption.parameters.{component}.b")
            return qs * b * concentration_pressure / (1.0 + b * concentration_pressure)
        qs1 = si_value(params.get("qs1"), "loading", field_name=f"adsorption.parameters.{component}.qs1")
        b1 = si_value(params.get("b1"), "inverse_pressure", field_name=f"adsorption.parameters.{component}.b1")
        qs2 = si_value(params.get("qs2"), "loading", field_name=f"adsorption.parameters.{component}.qs2")
        b2 = si_value(params.get("b2"), "inverse_pressure", field_name=f"adsorption.parameters.{component}.b2")
        return (
            qs1 * b1 * concentration_pressure / (1.0 + b1 * concentration_pressure)
            + qs2 * b2 * concentration_pressure / (1.0 + b2 * concentration_pressure)
        )

    model.fs.qeq = pyo.Expression(model.fs.time, model.fs.z, model.fs.components, rule=qeq_rule)

    def mass_balance_rule(m, t, z, component):
        if t == m.time.first() or z == m.z.first():
            return pyo.Constraint.Skip
        k = adsorption.get("kinetic_parameters", {}).get(component, {}).get("k", 0.01)
        return (
            m.porosity * m.dCdt[t, z, component]
            + m.velocity * m.dCdz[t, z, component]
            - m.porosity * m.axial_dispersion * m.d2Cdz2[t, z, component]
            + (1.0 - m.porosity) * m.solid_density * m.dqdt[t, z, component]
            == 0
        )

    def kinetic_rule(m, t, z, component):
        if t == m.time.first():
            return pyo.Constraint.Skip
        k = adsorption.get("kinetic_parameters", {}).get(component, {}).get("k", 0.01)
        k_value = si_value(k, "rate_constant", field_name=f"adsorption.kinetic_parameters.{component}.k")
        return m.dqdt[t, z, component] == k_value * (m.qeq[t, z, component] - m.q[t, z, component])

    model.fs.mass_balance = pyo.Constraint(model.fs.time, model.fs.z, model.fs.components, rule=mass_balance_rule)
    model.fs.kinetics = pyo.Constraint(model.fs.time, model.fs.z, model.fs.components, rule=kinetic_rule)
    model.fs.inlet_bc = pyo.Constraint(
        model.fs.time,
        model.fs.components,
        rule=lambda m, t, c: m.C[t, m.z.first(), c] == m.feed_concentration[c],
    )
    model.fs.outlet_dispersion_bc = pyo.Constraint(
        model.fs.time,
        model.fs.components,
        rule=lambda m, t, c: m.dCdz[t, m.z.last(), c] == 0,
    )
    model.fs.outlet_curvature_bc = pyo.Constraint(
        model.fs.time,
        model.fs.components,
        rule=lambda m, t, c: m.d2Cdz2[t, m.z.last(), c] == 0,
    )
    model.fs.initial_c = pyo.Constraint(
        model.fs.z,
        model.fs.components,
        rule=lambda m, z, c: pyo.Constraint.Skip if z == m.z.first() else m.C[m.time.first(), z, c] == 0,
    )
    model.fs.initial_q = pyo.Constraint(
        model.fs.z,
        model.fs.components,
        rule=lambda m, z, c: m.q[m.time.first(), z, c] == 0,
    )
    model._idaes_process_modeler_metadata = {
        "backend": "pyomo_dae_idaes",
        "idaes_version": getattr(__import__("idaes"), "__version__", "unknown"),
        "model_form": "ideal-gas constant-pressure fixed-bed reference",
    }
    return model


def discretize_fixed_bed(model: Any, *, time_elements: int = 20, space_elements: int = 20) -> Any:
    """Apply portable finite-difference transformations to both domains."""

    from pyomo.environ import TransformationFactory

    transformation = TransformationFactory("dae.finite_difference")
    transformation.apply_to(model, wrt=model.fs.time, nfe=time_elements, scheme="BACKWARD")
    transformation.apply_to(model, wrt=model.fs.z, nfe=space_elements, scheme="FORWARD")
    return model


def initialize_fixed_bed(model: Any) -> Any:
    """Fill derivative/intermediate variables so nonlinear solvers get a finite start."""

    pyo = __import__("pyomo.environ", fromlist=["Var"])
    from pyomo.core.expr.visitor import identify_variables

    variables = list(model.component_data_objects(ctype=pyo.Var))
    used_ids = set()
    for constraint in model.component_data_objects(ctype=pyo.Constraint, active=True):
        used_ids.update(id(variable) for variable in identify_variables(constraint.body))
    for variable in variables:
        if variable.value is None:
            variable.set_value(0.0)
        # Derivative variables on skipped initial/boundary equations can be
        # structurally unused. Fixing them prevents an IPOPT/ASL edge case for
        # zero-curvature boundary variables while preserving the physical DOF.
        if not variable.fixed and id(variable) not in used_ids:
            variable.fix(0.0)
    return model


def solve_pyomo_model(model: Any, solver: str = "ipopt") -> Dict[str, Any]:
    """Solve a prepared model and return a small auditable status mapping."""

    import pyomo.environ as pyo

    initialize_fixed_bed(model)
    if not list(model.component_data_objects(ctype=pyo.Objective, active=True)):
        # A non-constant regularizing objective avoids solver-specific
        # behaviour for feasibility-only NLPs while leaving the equations to
        # determine the state.
        model._idaes_process_modeler_objective = pyo.Objective(
            expr=sum(variable**2 for variable in model.fs.C.values())
        )

    opt = pyo.SolverFactory(solver)
    if solver in {"ipopt", "cbc", "bonmin", "couenne"}:
        try:
            import idaes

            idaes_solver = Path(idaes.bin_directory) / solver
            if idaes_solver.exists():
                # Prefer the extension binary installed by `idaes
                # get-extensions`; the Conda IPOPT build can differ in linear
                # solver support and has been observed to fail on this DAE.
                opt.set_executable(str(idaes_solver), validate=False)
        except (ImportError, AttributeError, OSError):
            pass
    if not opt.available(exception_flag=False):
        return {"termination": "unavailable", "solver": solver}
    result = opt.solve(model, tee=False)
    return {
        "termination": str(result.solver.termination_condition),
        "status": str(result.solver.status),
        "solver": solver,
    }
