"""Parameter-estimation helpers with explicit residual/provenance output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from .engine import run_model
from .spec import ModelSpec, load_spec, set_dotted_value


@dataclass
class FitResult:
    parameter_path: str
    initial_value_si: float
    fitted_value_si: float
    lower_bound_si: float
    upper_bound_si: float
    success: bool
    cost: float
    residuals: Sequence[float]
    solver_message: str
    assumptions: Sequence[str]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "parameter_path": self.parameter_path,
            "initial_value_si": self.initial_value_si,
            "fitted_value_si": self.fitted_value_si,
            "bounds_si": [self.lower_bound_si, self.upper_bound_si],
            "success": self.success,
            "cost": self.cost,
            "residuals": list(self.residuals),
            "solver_message": self.solver_message,
            "assumptions": list(self.assumptions),
        }


def _load_data(data: Any) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data.copy()
    return pd.read_csv(Path(data))


def fit_fixed_bed_parameter(
    source: Any,
    data: Any,
    *,
    parameter_path: str,
    target_column: str,
    time_column: str = "time_s",
    sigma_column: Optional[str] = None,
    bounds: Tuple[float, float] = (0.0, np.inf),
    backend: str = "reduced_order",
) -> Tuple[FitResult, Dict[str, Any]]:
    """Fit one SI-valued spec parameter to a measured/published CSV column.

    The data file is never overwritten. The model must expose a stream column
    with the same time grid or a `time_s` column that can be interpolated.
    """

    base = load_spec(source)
    frame = _load_data(data)
    if time_column not in frame or target_column not in frame:
        raise ValueError(f"data must contain {time_column!r} and {target_column!r}")
    times = np.asarray(frame[time_column], dtype=float)
    observed = np.asarray(frame[target_column], dtype=float)
    sigma = np.ones_like(observed)
    if sigma_column:
        sigma = np.maximum(np.asarray(frame[sigma_column], dtype=float), 1.0e-30)
    try:
        initial = float(base.get(parameter_path))
    except (TypeError, ValueError):
        raise ValueError("parameter_path must initially contain a plain SI numeric value for fitting")
    lower, upper = bounds
    if not lower <= initial <= upper:
        raise ValueError("initial parameter must lie inside bounds")

    def residual(vector: np.ndarray) -> np.ndarray:
        data_mapping = base.to_mapping()
        set_dotted_value(data_mapping, parameter_path, float(vector[0]))
        result = run_model(data_mapping, backend=backend)
        stream = result["streams"]
        if time_column not in stream or target_column not in stream:
            raise ValueError(f"model output must contain {time_column!r} and {target_column!r}")
        prediction = np.interp(times, np.asarray(stream[time_column]), np.asarray(stream[target_column]))
        return (prediction - observed) / sigma

    fit = least_squares(residual, np.asarray([initial]), bounds=([lower], [upper]), method="trf")
    fitted_mapping = base.to_mapping()
    set_dotted_value(fitted_mapping, parameter_path, float(fit.x[0]))
    fitted_run = run_model(fitted_mapping, backend=backend)
    result = FitResult(
        parameter_path=parameter_path,
        initial_value_si=initial,
        fitted_value_si=float(fit.x[0]),
        lower_bound_si=float(lower),
        upper_bound_si=float(upper),
        success=bool(fit.success),
        cost=float(fit.cost),
        residuals=fit.fun.tolist(),
        solver_message=str(fit.message),
        assumptions=[
            "fit parameter is interpreted in SI because the optimizer varies a scalar",
            "least-squares identifiability and uncertainty require additional analysis",
        ],
    )
    return result, fitted_run
