"""Pre-solve specification checks and post-solve result checks."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .spec import ModelSpec, load_spec
from .units import UnitError, parse_quantity


@dataclass
class ValidationIssue:
    severity: str
    path: str
    message: str

    def as_dict(self) -> Dict[str, str]:
        return {"severity": self.severity, "path": self.path, "message": self.message}


@dataclass
class ValidationReport:
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> List[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def valid(self) -> bool:
        return not self.errors

    def error(self, path: str, message: str) -> None:
        self.issues.append(ValidationIssue("error", path, message))

    def warning(self, path: str, message: str) -> None:
        self.issues.append(ValidationIssue("warning", path, message))

    def extend(self, other: "ValidationReport") -> None:
        self.issues.extend(other.issues)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "issues": [issue.as_dict() for issue in self.issues],
        }


SUPPORTED_MODEL_TYPES = {
    "fixed_bed_adsorption",
    "psa",
    "vsa",
    "tsa",
    "membrane_separation",
    "membrane_reactor",
    "fixed_bed_reactor",
    "bubbling_fluidized_bed",
}


def _mapping(spec: ModelSpec, path: str) -> Mapping[str, Any]:
    value = spec.get(path, {})
    return value if isinstance(value, Mapping) else {}


def _quantity(
    report: ValidationReport,
    value: Any,
    path: str,
    dimension: str,
    *,
    positive: bool = False,
    nonnegative: bool = False,
) -> Optional[float]:
    if value is None:
        report.error(path, f"missing required quantity with dimension {dimension}")
        return None
    try:
        quantity = parse_quantity(value, dimension, field_name=path)
    except UnitError as exc:
        report.error(path, str(exc))
        return None
    if quantity.assumed_si:
        report.warning(path, "numeric value interpreted as SI; add an explicit unit to the spec")
    if not math.isfinite(quantity.value_si):
        report.error(path, "quantity must be finite")
    if positive and quantity.value_si <= 0:
        report.error(path, "quantity must be > 0")
    if nonnegative and quantity.value_si < 0:
        report.error(path, "quantity must be >= 0")
    return quantity.value_si


def _validate_composition(report: ValidationReport, spec: ModelSpec) -> None:
    composition = spec.get("feed.composition")
    if not isinstance(composition, Mapping):
        report.error("feed.composition", "provide a mapping of component to mole fraction")
        return
    components = spec.components
    missing = [component for component in components if component not in composition]
    extra = [component for component in composition if component not in components]
    if missing:
        report.error("feed.composition", f"missing components: {', '.join(missing)}")
    if extra:
        report.warning("feed.composition", f"ignoring components not in components: {', '.join(extra)}")
    total = 0.0
    for component in components:
        if component not in composition:
            continue
        try:
            fraction = float(composition[component])
        except (TypeError, ValueError):
            report.error(f"feed.composition.{component}", "mole fraction must be numeric")
            continue
        if not math.isfinite(fraction) or fraction < 0 or fraction > 1:
            report.error(f"feed.composition.{component}", "mole fraction must be between 0 and 1")
        total += fraction
    if components and abs(total - 1.0) > 1e-6:
        report.error("feed.composition", f"mole fractions sum to {total:.8g}, not 1")


def _validate_numerics(report: ValidationReport, spec: ModelSpec) -> None:
    numerics = _mapping(spec, "numerics")
    for name, minimum in (("spatial_elements", 2), ("time_elements", 2)):
        if name in numerics:
            value = numerics[name]
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                report.error(f"numerics.{name}", f"must be an integer >= {minimum}")
        else:
            report.warning(f"numerics.{name}", "not set; backend default will be used")
    for name in ("time_horizon", "time_step"):
        if name in numerics:
            _quantity(report, numerics[name], f"numerics.{name}", "time", positive=True)


def _validate_adsorption(report: ValidationReport, spec: ModelSpec) -> None:
    adsorption = _mapping(spec, "adsorption")
    equilibrium = adsorption.get("equilibrium_model")
    allowed_eq = {
        "langmuir",
        "dual_site_langmuir",
        "sips",
        "toth",
        "henry",
        "competitive_langmuir",
        "competitive_dsl",
    }
    if equilibrium not in allowed_eq:
        report.error("adsorption.equilibrium_model", f"must be one of {sorted(allowed_eq)}")
    kinetic = adsorption.get("kinetic_model", "LDF").lower()
    if kinetic not in {"equilibrium", "ldf", "dual_resistance_ldf"}:
        report.error("adsorption.kinetic_model", "must be equilibrium, LDF, or dual_resistance_LDF")
    params = adsorption.get("parameters", {})
    if not isinstance(params, Mapping):
        report.error("adsorption.parameters", "must be a mapping")
    if equilibrium in {"langmuir", "dual_site_langmuir", "sips", "toth", "henry"}:
        if not isinstance(params, Mapping):
            return
        for component in spec.components:
            if component not in params:
                report.error(f"adsorption.parameters.{component}", "missing component parameters")


def _validate_cycle(report: ValidationReport, spec: ModelSpec) -> None:
    cycle = spec.get("cycle")
    if not isinstance(cycle, list) or not cycle:
        report.error("cycle", "PSA/VSA/TSA requires a non-empty list of steps")
        return
    for index, step in enumerate(cycle):
        path = f"cycle[{index}]"
        if not isinstance(step, Mapping):
            report.error(path, "step must be a mapping")
            continue
        if not step.get("name"):
            report.error(f"{path}.name", "step name is required")
        _quantity(report, step.get("duration"), f"{path}.duration", "time", positive=True)


def validate_spec(source: Any) -> ValidationReport:
    """Validate required fields, units, bounds, and model-family choices."""

    report = ValidationReport()
    try:
        spec = load_spec(source)
    except Exception as exc:
        report.error("spec", str(exc))
        return report

    if spec.model_type not in SUPPORTED_MODEL_TYPES:
        report.error("model_type", f"unsupported model type {spec.model_type!r}")
        return report
    if not spec.components or len(spec.components) < 2:
        report.error("components", "provide at least two component names")
    if len(set(spec.components)) != len(spec.components):
        report.error("components", "component names must be unique")
    if any(not isinstance(component, str) or not component.strip() for component in spec.components):
        report.error("components", "component names must be non-empty strings")

    needs_geometry = spec.model_type in {
        "fixed_bed_adsorption",
        "psa",
        "vsa",
        "tsa",
        "fixed_bed_reactor",
        "bubbling_fluidized_bed",
    }
    if needs_geometry:
        _quantity(report, spec.get("geometry.length"), "geometry.length", "length", positive=True)
        _quantity(report, spec.get("geometry.diameter"), "geometry.diameter", "length", positive=True)

    feed = _mapping(spec, "feed")
    _quantity(report, feed.get("pressure"), "feed.pressure", "pressure", positive=True)
    _quantity(report, feed.get("temperature"), "feed.temperature", "temperature", positive=True)
    _quantity(report, feed.get("molar_flow"), "feed.molar_flow", "molar_flow", positive=True)
    _validate_composition(report, spec)

    if spec.model_type in {"fixed_bed_adsorption", "psa", "vsa", "tsa"}:
        bed = _mapping(spec, "bed")
        _quantity(report, bed.get("porosity"), "bed.porosity", "dimensionless", positive=True)
        _quantity(report, bed.get("particle_density"), "bed.particle_density", "mass_density", positive=True)
        _validate_adsorption(report, spec)
    if spec.model_type in {"psa", "vsa", "tsa"}:
        _validate_cycle(report, spec)

    if spec.model_type in {"membrane_separation", "membrane_reactor"}:
        membrane = _mapping(spec, "membrane")
        if spec.model_type == "membrane_separation":
            _quantity(report, membrane.get("length"), "membrane.length", "length", positive=True)
        if membrane.get("area") is not None:
            _quantity(report, membrane.get("area"), "membrane.area", "area", positive=True)
        _quantity(report, membrane.get("permeate_pressure"), "membrane.permeate_pressure", "pressure", positive=True)
        permeance = membrane.get("permeance")
        if isinstance(permeance, Mapping):
            for component in spec.components:
                if component in permeance:
                    _quantity(
                        report,
                        permeance[component],
                        f"membrane.permeance.{component}",
                        "permeance",
                        positive=True,
                    )
                else:
                    report.error(f"membrane.permeance.{component}", "missing component permeance")
        else:
            report.error("membrane.permeance", "provide a component-to-permeance mapping")
    if spec.model_type in {"membrane_reactor", "fixed_bed_reactor"}:
        reaction = _mapping(spec, "reaction")
        if not reaction.get("stoichiometry"):
            report.error("reaction.stoichiometry", "provide a stoichiometry mapping")
        _quantity(report, reaction.get("pre_exponential"), "reaction.pre_exponential", "rate_constant", positive=True)
        _quantity(report, reaction.get("activation_energy"), "reaction.activation_energy", "energy_per_mol", nonnegative=True)
    if spec.model_type == "bubbling_fluidized_bed":
        report.warning(
            "model_type",
            "BubblingFluidizedBed is a reduced-order/engineering route; local bubble dynamics and CFD are out of scope",
        )

    _validate_numerics(report, spec)
    if spec.get("validation.experimental_data") is None and spec.get("validation.benchmark") is None:
        report.warning(
            "validation",
            "no experimental or literature benchmark supplied; numerical convergence is not physical validation",
        )
    return report


def validate_result(summary: Mapping[str, Any]) -> ValidationReport:
    """Check common post-solve metrics without declaring model accuracy."""

    report = ValidationReport()
    solver = summary.get("solver", {})
    if isinstance(solver, Mapping):
        termination = str(solver.get("termination", "unknown")).lower()
        if termination not in {"optimal", "converged", "success", "not_applicable"}:
            report.error("solver.termination", f"non-success termination: {termination}")
    for key in ("mass_balance_error", "energy_balance_error"):
        if key in summary:
            try:
                value = float(summary[key])
            except (TypeError, ValueError):
                report.error(key, "must be numeric")
                continue
            if not math.isfinite(value):
                report.error(key, "must be finite")
    for key in ("purity", "recovery", "stage_cut"):
        if key in summary:
            try:
                value = float(summary[key])
            except (TypeError, ValueError):
                report.error(key, "must be numeric")
                continue
            if not 0 <= value <= 1:
                report.error(key, "must lie between 0 and 1")
    return report
