"""German market study: PET-bottle and bag-in-box wine, and what it costs.

A separate package from the Romanian scraper rather than another set of
adapters inside it. The two studies answer different questions with different
vocabularies — this one classifies containers and applies German Einwegpfand,
where the other tracks a Romanian catalogue under SGR — and the shared parts
(politeness, cache, "leave a field null rather than guess it") are cheaper to
restate than to generalise.
"""

from .model import EXPORT_COLUMNS, Listing
from .packaging import BAG_IN_BOX, IN_SCOPE, PET, classify, pfand

__all__ = ["Listing", "EXPORT_COLUMNS", "classify", "pfand",
           "BAG_IN_BOX", "PET", "IN_SCOPE"]
