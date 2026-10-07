"""Indicators: built-ins + custom ports (indicators/custom/*.py are imported automatically)."""
import importlib
import pkgutil

from indicators import builtin  # noqa: F401  (registers the built-in indicators)
from indicators import custom

for module in pkgutil.iter_modules(custom.__path__):
    importlib.import_module(f"{custom.__name__}.{module.name}")
