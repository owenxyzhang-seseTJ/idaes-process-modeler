#!/usr/bin/env python3
"""Build, discretize, solve, and report the guarded IDAES/Pyomo.DAE reference model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from idaes_process_modeler.idaes_adapter import (
    build_fixed_bed_dae,
    discretize_fixed_bed,
    solve_pyomo_model,
)
from idaes_process_modeler.reporting import write_result_bundle
from idaes_process_modeler.spec import load_spec


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--time-elements", type=int, default=4)
    parser.add_argument("--space-elements", type=int, default=8)
    parser.add_argument("--solver", default="ipopt")
    args = parser.parse_args(argv)
    try:
        import pyomo.environ as pyo
        from idaes.core.util.model_statistics import degrees_of_freedom

        model = build_fixed_bed_dae(args.spec)
        discretize_fixed_bed(model, time_elements=args.time_elements, space_elements=args.space_elements)
        solver_status = solve_pyomo_model(model, solver=args.solver)
        termination = solver_status.get("termination", "unknown")
        if termination != "optimal":
            raise RuntimeError(f"IDAES reference solve did not reach optimal: {solver_status}")
        components = list(model.fs.components)
        profile_rows = []
        stream_rows = []
        time_values = list(model.fs.time)
        z_values = list(model.fs.z)
        for time in time_values:
            for z in z_values:
                for component in components:
                    profile_rows.append(
                        {
                            "time_s": float(time),
                            "z_m": float(z),
                            "component": component,
                            "concentration_mol_m3": float(pyo.value(model.fs.C[time, z, component])),
                            "loading_mol_kg": float(pyo.value(model.fs.q[time, z, component])),
                        }
                    )
            outlet = [float(pyo.value(model.fs.C[time, z_values[-1], component])) for component in components]
            total = max(sum(outlet), 1.0e-30)
            stream_rows.append(
                {
                    "time_s": float(time),
                    **{f"{component}_concentration_mol_m3": value for component, value in zip(components, outlet)},
                    **{f"{component}_mole_fraction": value / total for component, value in zip(components, outlet)},
                }
            )
        residuals = []
        for constraint in model.component_data_objects(pyo.Constraint, active=True):
            try:
                residuals.append(abs(float(pyo.value(constraint.body - constraint.lower))))
            except (TypeError, ValueError):
                pass
        outlet_fractions = [
            [row[f"{component}_mole_fraction"] for component in components] for row in stream_rows
        ]
        result = {
            "summary": {
                "model_type": load_spec(args.spec).model_type,
                "backend": "pyomo_dae_idaes",
                "solver": solver_status,
                "components": components,
                "time_elements": args.time_elements,
                "space_elements": args.space_elements,
                "degrees_of_freedom_after_discretization": int(degrees_of_freedom(model)),
                "max_constraint_residual": max(residuals) if residuals else None,
                "warnings": [
                    "reference builder uses ideal-gas, constant-pressure/temperature equations",
                    "this solve is an API/numerical smoke result, not experimental validation",
                ],
            },
            "streams": pd.DataFrame(stream_rows),
            "profiles": pd.DataFrame(profile_rows),
            "metrics": pd.DataFrame(
                [{"metric": "max_constraint_residual", "value": max(residuals) if residuals else None}]
            ),
            "convergence": {
                "kind": "pyomo_dae_discretization",
                "time_elements": args.time_elements,
                "space_elements": args.space_elements,
                "solver": solver_status,
            },
            "warnings": [
                "reference builder uses ideal-gas, constant-pressure/temperature equations",
                "this solve is an API/numerical smoke result, not experimental validation",
            ],
            "figure_data": {"time_s": [row["time_s"] for row in stream_rows], "outlet_mole_fraction": outlet_fractions},
        }
        output = write_result_bundle(result, args.spec, args.output_dir)
        print(json.dumps({"output_dir": str(output), **result["summary"]}, indent=2, default=str))
        return 0
    except Exception as exc:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "solver_error.json").write_text(
            json.dumps({"error": type(exc).__name__, "message": str(exc)}, indent=2), encoding="utf-8"
        )
        print(f"IDAES reference solve failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
