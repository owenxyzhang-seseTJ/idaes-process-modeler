"""Auditable, IDAES/Pyomo-oriented process-modeling helpers."""

__version__ = "0.1.0"

from .spec import ModelSpec, load_spec
from .validation import ValidationReport, validate_spec

__all__ = ["ModelSpec", "ValidationReport", "__version__", "load_spec", "validate_spec"]
