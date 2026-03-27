from __future__ import annotations

from importlib import import_module
from pkgutil import iter_modules
from typing import List

from validators.plugins.base import ValidatorPlugin


def discover_plugins() -> List[ValidatorPlugin]:
    """
    Discover plugins under validators.plugins package.
    Modules may expose `get_plugins()` returning list[ValidatorPlugin].
    """
    plugins: list[ValidatorPlugin] = []
    import validators.plugins as package

    for module_info in iter_modules(package.__path__):
        name = module_info.name
        if name in ("base", "registry"):
            continue
        mod = import_module(f"validators.plugins.{name}")
        getter = getattr(mod, "get_plugins", None)
        if callable(getter):
            for p in getter() or []:
                if isinstance(p, ValidatorPlugin):
                    plugins.append(p)

    plugins.sort(key=lambda p: (p.order, p.id))
    return plugins

