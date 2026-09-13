"""Pyomo-backed constrained selection over explicitly simulated candidates."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence


def select_best_candidate(
    candidates: Sequence[Mapping[str, Any]],
    *,
    objective: str,
    constraints: Mapping[str, Mapping[str, float]] = None,
    solver: str = "cbc",
) -> Dict[str, Any]:
    """Select one simulated candidate using a Pyomo MILP.

    This is intentionally a candidate-selection wrapper: the physical model is
    evaluated before Pyomo sees the metrics. It is not a claim of continuous
    equation-oriented optimization. Use a full Pyomo/IDAES NLP model when
    derivatives and simultaneous optimization are required.
    """

    if not candidates:
        raise ValueError("at least one candidate is required")
    if any(objective not in candidate for candidate in candidates):
        raise ValueError(f"all candidates need objective metric {objective!r}")
    try:
        import pyomo.environ as pyo
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Pyomo is required for candidate optimization") from exc
    from pyomo.opt import SolverFactory

    constraints = constraints or {}
    model = pyo.ConcreteModel(name="idaes_process_candidate_selection")
    indices = list(range(len(candidates)))
    model.I = pyo.Set(initialize=indices, ordered=True)
    model.select = pyo.Var(model.I, domain=pyo.Binary)
    model.one_candidate = pyo.Constraint(expr=sum(model.select[i] for i in indices) == 1)
    sense = pyo.maximize
    if objective.startswith("min:"):
        objective = objective.split(":", 1)[1]
        sense = pyo.minimize
    model.objective = pyo.Objective(
        expr=sum(float(candidates[i][objective]) * model.select[i] for i in indices), sense=sense
    )
    model.metric_constraints = pyo.ConstraintList()
    for metric, bounds in constraints.items():
        values = [float(candidate[metric]) for candidate in candidates]
        if "lower" in bounds:
            model.metric_constraints.add(sum(values[i] * model.select[i] for i in indices) >= float(bounds["lower"]))
        if "upper" in bounds:
            model.metric_constraints.add(sum(values[i] * model.select[i] for i in indices) <= float(bounds["upper"]))
    opt = SolverFactory(solver)
    if not opt.available(exception_flag=False) and solver in {"cbc", "ipopt", "bonmin", "couenne"}:
        # IDAES extensions live in ~/.idaes/bin and are not always added to a
        # Conda environment's PATH.
        try:
            import idaes

            candidate = Path(idaes.bin_directory) / solver
            if candidate.exists():
                opt.set_executable(str(candidate), validate=False)
        except (ImportError, AttributeError, OSError):
            pass
    if not opt.available(exception_flag=False):
        raise RuntimeError(f"solver {solver!r} is unavailable; install it or use an available MILP solver")
    solved = opt.solve(model, tee=False)
    termination = str(solved.solver.termination_condition)
    chosen = [i for i in indices if float(model.select[i].value or 0.0) > 0.5]
    return {
        "solver": solver,
        "termination": termination,
        "objective": objective,
        "constraints": constraints,
        "selected_index": chosen[0] if chosen else None,
        "selected": candidates[chosen[0]] if chosen else None,
        "candidates": list(candidates),
        "interpretation": "Pyomo MILP selection over precomputed simulations; not continuous equation-oriented optimization",
    }
