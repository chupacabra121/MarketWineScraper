"""Site adapters. Importing this package registers every adapter."""

from . import auchan, carrefour, kaufland, mega_image, penny, selgros, unsupported  # noqa: F401
from .base import (  # noqa: F401
    Adapter,
    SiteUnsupported,
    all_adapters,
    get_adapter,
    register,
    scrapable_adapters,
)

__all__ = [
    "Adapter", "SiteUnsupported", "all_adapters", "get_adapter",
    "register", "scrapable_adapters",
]
