"""
Gate Registry — auto-discovers gate plugins and manages mandatory gates.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from gates.base import GatePlugin

# Gates that CANNOT be disabled — they always run
MANDATORY_GATES: set[str] = {
    "build-gate",
    "test-gate",
    "coverage-gate",
    "security-gate",
    "integration-gate",
    "business-analysis-gate",
    "acceptance-gate",
    "capability-gate",  # Pre-bootstrap capability check (G0)
    # deployment-gate is NOT mandatory — requires live service
}

_registry: dict[str, type[GatePlugin]] = {}


def discover_gates(gates_dir: Optional[Path] = None) -> list[type[GatePlugin]]:
    """
    Auto-discover gate plugins from ~/.hermes/gates/gates/*.py.

    Each .py file must export a class that inherits from GatePlugin.
    The class is registered by its `name` attribute.
    """
    global _registry

    if gates_dir is None:
        gates_dir = Path(__file__).resolve().parent / "gates"

    if not gates_dir.is_dir():
        return []

    discovered = []

    for py_file in sorted(gates_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue

        # Load module from file path
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            f"gates.gates.{py_file.stem}",
            str(py_file)
        )
        if spec is None or spec.loader is None:
            continue

        try:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            print(f"  ⚠ Gate module '{py_file.stem}' skipped: {e}", flush=True)
            continue

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, GatePlugin)
                and attr is not GatePlugin
                and attr.name  # must have a non-empty name
            ):
                _registry[attr.name] = attr
                discovered.append(attr)

    return discovered


def get_gate(name: str) -> Optional[type[GatePlugin]]:
    """Get a gate class by name. Auto-discovers if registry is empty."""
    if not _registry:
        discover_gates()
    return _registry.get(name)


def get_enabled_gates(
    config: dict,
    mode: str = "balanced",
) -> list[GatePlugin]:
    """
    Return instantiated gates that are enabled for the current mode.

    Args:
        config: parsed config.yaml dict
        mode: 'speed', 'balanced', or 'quality'

    Returns:
        list of GatePlugin instances, with mandatory gates ALWAYS included
    """
    if not _registry:
        discover_gates()

    enabled = []

    # Apply mode overrides
    mode_config = config.get("modes", {}).get(mode, {})
    gates_config = config.get("gates", {})

    for name, gate_cls in _registry.items():
        # Mandatory gates ALWAYS run
        if name in MANDATORY_GATES:
            instance = gate_cls()
            _apply_config(instance, gates_config.get(name, {}), mode_config.get(name, {}))
            enabled.append(instance)
            continue

        # Check if gate is enabled
        gate_cfg = {**gates_config.get(name, {}), **mode_config.get(name, {})}
        if not gate_cfg.get("enabled", True):
            continue

        instance = gate_cls()
        _apply_config(instance, gate_cfg, {})
        enabled.append(instance)

    return enabled


def _apply_config(
    instance: GatePlugin,
    gate_config: dict,
    mode_override: dict,
) -> None:
    """Apply config overrides to a gate instance."""
    merged = {**gate_config, **mode_override}

    if "threshold" in merged:
        instance.threshold = merged["threshold"]


def list_gates() -> list[dict]:
    """List all discovered gates with metadata."""
    if not _registry:
        discover_gates()

    return [
        {
            "name": name,
            "version": cls.version,
            "description": cls.description,
            "mandatory": name in MANDATORY_GATES,
            "depends_on": cls.depends_on,
        }
        for name, cls in sorted(_registry.items())
    ]
