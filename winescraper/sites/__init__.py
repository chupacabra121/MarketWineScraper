"""Site adapters. Importing this package registers every adapter."""

from . import (  # noqa: F401
    auchan, boltfood, carrefour, freshful, kaufland, mega_image, penny, selgros,
    sezamo, unsupported,
)
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
