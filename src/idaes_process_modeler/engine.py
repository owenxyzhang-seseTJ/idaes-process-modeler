"""Model routing, preflight enforcement, and backend selection."""

from __future__ import annotations

from typing import Any, Dict

from .models.fixed_bed import run_fixed_bed
from .models.membrane import run_membrane
from .models.membrane_reactor import run_membrane_reactor
from .models.psa import run_psa
from .spec import load_spec
from .validation import validate_spec


def run_model(source: Any, *, backend: str = "reduced_order") -> Dict[str, Any]:
    """Validate and route a ModelSpec to a supported backend.

    ``idaes`` is intentionally explicit: callers should use
    ``idaes_adapter.build_fixed_bed_dae`` when they need a Pyomo model object,
    since not every reduced-order family has an IDAES unit-operation adapter in
    this initial release.
    """

    spec = load_spec(source)
    preflight = validate_spec(spec)
    if not preflight.valid:
        details = "; ".join(f"{item.path}: {item.message}" for item in preflight.errors)
        raise ValueError(f"pre-solve validation failed: {details}")
    if backend == "idaes":
        raise ValueError(
            "Use idaes_process_modeler.idaes_adapter.build_fixed_bed_dae for the explicit IDAES/Pyomo.DAE path; "
            "the CLI reduced-order runners will not silently substitute it."
        )
    if spec.model_type == "gate_open_psa":
        from .models.gate_open_psa import run_gate_open
        result = run_gate_open(spec, backend=backend)
    elif spec.model_type == "fixed_bed_adsorption":
        result = run_fixed_bed(spec, backend=backend)
    elif spec.model_type in {"psa", "vsa", "tsa"}:
        result = run_psa(spec, backend=backend)
    elif spec.model_type == "membrane_separation":
        result = run_membrane(spec, backend=backend)
    elif spec.model_type in {"membrane_reactor", "fixed_bed_reactor"}:
        result = run_membrane_reactor(spec, backend=backend)
    elif spec.model_type == "bubbling_fluidized_bed":
        raise NotImplementedError(
            "Bubbling fluidized-bed routing is documented but not implemented by the reduced-order backend; "
            "use an IDAES BFB unit or CFD/MFiX/OpenFOAM for local bubble dynamics."
        )
    else:  # guarded by validation, retained for defensive programming
        raise ValueError(f"unsupported model type {spec.model_type!r}")
    result["pre_solve_validation"] = preflight.as_dict()
    return result
