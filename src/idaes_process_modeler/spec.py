"""Structured model specifications and YAML/JSON I/O."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Union

import yaml


class SpecError(ValueError):
    """Raised when a model specification cannot be loaded."""


@dataclass
class ModelSpec:
    """A thin typed boundary around a user-authored structured specification.

    Keeping the payload as a mapping makes the schema forward-compatible while
    the validator enforces the fields required by each model family.
    """

    data: Dict[str, Any]
    source: Optional[str] = None

    @property
    def model_type(self) -> str:
        return str(self.data.get("model_type", ""))

    @property
    def components(self):
        return list(self.data.get("components", []))

    def get(self, path: str, default: Any = None) -> Any:
        """Read a dotted path, e.g. ``feed.composition.CO2``."""

        current: Any = self.data
        for token in path.split("."):
            if not isinstance(current, Mapping) or token not in current:
                return default
            current = current[token]
        return current

    def copy(self) -> "ModelSpec":
        return ModelSpec(deepcopy(self.data), source=self.source)

    def to_mapping(self) -> Dict[str, Any]:
        return deepcopy(self.data)


def _load_mapping(path: Path) -> Dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecError(f"Cannot read specification {path}: {exc}") from exc
    try:
        if path.suffix.lower() == ".json":
            loaded = json.loads(text)
        else:
            loaded = yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise SpecError(f"Cannot parse specification {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise SpecError(f"Specification {path} must contain a top-level mapping")
    return loaded


def load_spec(source: Union[str, Path, Mapping[str, Any], ModelSpec]) -> ModelSpec:
    """Load a ``ModelSpec`` from a path or mapping."""

    if isinstance(source, ModelSpec):
        return source.copy()
    if isinstance(source, (str, Path)):
        path = Path(source)
        return ModelSpec(_load_mapping(path), source=str(path))
    if isinstance(source, Mapping):
        return ModelSpec(deepcopy(dict(source)))
    raise SpecError(f"Unsupported specification source: {type(source).__name__}")


def dump_spec(spec: Union[ModelSpec, Mapping[str, Any]], path: Union[str, Path]) -> None:
    """Write a specification as YAML or JSON, selected by the extension."""

    model_spec = load_spec(spec)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() == ".json":
        target.write_text(json.dumps(model_spec.data, indent=2, sort_keys=False), encoding="utf-8")
    else:
        target.write_text(yaml.safe_dump(model_spec.data, sort_keys=False), encoding="utf-8")


def set_dotted_value(mapping: Dict[str, Any], path: str, value: Any) -> None:
    """Set a nested mapping path for parameter sweeps."""

    tokens = path.split(".")
    if not tokens or any(not token for token in tokens):
        raise SpecError(f"Invalid dotted path {path!r}")
    current: Dict[str, Any] = mapping
    for token in tokens[:-1]:
        child = current.get(token)
        if not isinstance(child, dict):
            child = {}
            current[token] = child
        current = child
    current[tokens[-1]] = value
