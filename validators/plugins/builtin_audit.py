from __future__ import annotations

from typing import Callable, Any

from validators.plugins.base import ValidatorPlugin


def get_plugins_from_mapping(run_by_id: dict[str, Callable[[], dict[str, Any]]]) -> list[ValidatorPlugin]:
    """
    Build built-in plugin list from an execution mapping provided by audit runner.
    This keeps plugin metadata separate while preserving existing validator logic.
    """
    defs = [
        ("validate_data_consistency_tool", "Data consistency", "HIGH", "arxml", 10),
        ("validate_port_references_tool", "Port references", "HIGH", "arxml", 20),
        ("validate_component_refs_tool", "Component references", "HIGH", "arxml", 30),
        ("check_duplicate_uuids_tool", "Duplicate UUIDs", "MEDIUM", "arxml", 40),
        ("duplicate_ports_tool", "Duplicate ports", "LOW", "arxml", 50),
        ("validate_version_compatibility_tool", "Version compatibility", "MEDIUM", "arxml", 60),
        ("validate_swc_tool", "SWC validation", "HIGH", "arxml", 70),
        ("validate_communication_tool", "Communication", "HIGH", "arxml", 80),
        ("validate_memory_tool", "Memory", "MEDIUM", "arxml", 90),
        ("validate_rte_tool", "RTE", "HIGH", "arxml", 100),
        ("validate_diagnostics_tool", "Diagnostics", "MEDIUM", "arxml", 110),
        ("validate_ecu_bsw_tool", "ECU/BSW", "MEDIUM", "arxml", 120),
    ]
    plugins: list[ValidatorPlugin] = []
    for vid, name, sev, applies, order in defs:
        run = run_by_id.get(vid)
        if run is None:
            continue
        plugins.append(
            ValidatorPlugin(
                id=vid,
                name=name,
                severity=sev,
                applies_to=applies,
                schema_version="1.0.0",
                order=order,
                run=run,
            )
        )
    return plugins


def get_plugins() -> list[ValidatorPlugin]:
    # Discovery-only fallback; execution mapping is provided in audit runner.
    return []

