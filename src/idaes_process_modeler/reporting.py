"""Reproducible result bundles and compact diagnostic figures."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .spec import ModelSpec, dump_spec, load_spec
from .validation import validate_result


def _json_default(value: Any):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, default=_json_default, allow_nan=False), encoding="utf-8")


def _plot_fixed_bed(result: Mapping[str, Any], output: Path) -> None:
    data = result.get("figure_data", {})
    times = np.asarray(data.get("time_s", []), dtype=float)
    values = np.asarray(data.get("outlet_mole_fraction", []), dtype=float)
    components = result.get("summary", {}).get("components", [])
    if times.size == 0 or values.size == 0:
        return
    fig, ax = plt.subplots(figsize=(6.5, 4.0), constrained_layout=True)
    for index, component in enumerate(components):
        ax.plot(times, values[:, index], label=component)
    ax.set(xlabel="Time (s)", ylabel="Outlet mole fraction", title="Fixed-bed breakthrough")
    ax.legend(frameon=False)
    fig.savefig(output / "breakthrough.png", dpi=160)
    plt.close(fig)


def _plot_psa(result: Mapping[str, Any], output: Path) -> None:
    data = result.get("figure_data", {})
    cycles = np.asarray(data.get("cycle", []), dtype=float)
    if cycles.size == 0:
        return
    fig, axes = plt.subplots(2, 1, figsize=(6.5, 6.0), sharex=True, constrained_layout=True)
    axes[0].plot(cycles, data.get("purity", []), label="purity")
    axes[0].plot(cycles, data.get("recovery", []), label="recovery")
    axes[0].set_ylabel("Fraction")
    axes[0].legend(frameon=False)
    css_delta = np.asarray(
        [np.nan if value is None else float(value) for value in data.get("css_state_delta", [])], dtype=float
    )
    axes[1].semilogy(cycles, np.maximum(css_delta, 1.0e-16))
    axes[1].set(xlabel="Cycle", ylabel="CSS state delta")
    fig.savefig(output / "psa_css.png", dpi=160)
    plt.close(fig)


def _plot_membrane(result: Mapping[str, Any], output: Path) -> None:
    data = result.get("figure_data", {})
    z = np.asarray(data.get("z_m", []), dtype=float)
    values = np.asarray(data.get("retentate_mole_fraction", []), dtype=float)
    components = result.get("summary", {}).get("components", [])
    if z.size == 0 or values.size == 0:
        return
    fig, ax = plt.subplots(figsize=(6.5, 4.0), constrained_layout=True)
    for index, component in enumerate(components):
        ax.plot(z, values[:, index], label=component)
    ax.set(xlabel="Membrane coordinate (m)", ylabel="Retentate mole fraction", title="Membrane separation")
    ax.legend(frameon=False)
    fig.savefig(output / "membrane_profiles.png", dpi=160)
    plt.close(fig)


def write_result_bundle(result: Mapping[str, Any], source: Any, output_dir: Any) -> Path:
    """Write the standard JSON/CSV/figure bundle and return its directory."""

    spec = load_spec(source)
    output = Path(output_dir)
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    summary = dict(result.get("summary", {}))
    summary["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    summary["post_solve_validation"] = validate_result(summary).as_dict()
    _write_json(output / "summary.json", summary)
    for name in ("streams", "profiles", "metrics"):
        frame = result.get(name)
        if frame is None:
            frame = pd.DataFrame()
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(frame)
        frame.to_csv(output / f"{name}.csv", index=False)
    _write_json(output / "convergence.json", result.get("convergence", {}))
    dump_spec(spec, output / "model_spec.yaml")
    model_type = str(summary.get("model_type", spec.model_type))
    if model_type in {"fixed_bed_adsorption"}:
        _plot_fixed_bed(result, figures)
    elif model_type in {"psa", "vsa", "tsa"}:
        _plot_psa(result, figures)
    elif model_type in {"membrane_separation"}:
        _plot_membrane(result, figures)
    return output
