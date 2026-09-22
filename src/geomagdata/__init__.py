from importlib.metadata import PackageNotFoundError, version

from .base import get_indices, get_storm_ap

try:
    __version__ = version("geomagdata")
except PackageNotFoundError:  # not installed, e.g. running from a raw checkout
    __version__ = "unknown"

__all__ = ["__version__", "get_indices", "get_storm_ap"]
