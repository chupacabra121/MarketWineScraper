"""Carrefour tile parsing."""

from selectolax.parser import HTMLParser

from winescraper.sites.carrefour import CarrefourAdapter

# Real tile markup, trimmed. Note the meta price sits ABOVE the displayed price.
TILE = """
<li class="product" data-product-id="1266843">
  <div class="productItem-name">
    <a href="https://carrefour.ro/produse/spumant-zaz-0-75l-19-10508684">Spumant Zaz Francusa alb sec 0.75L</a>
  </div>
  <div class="price-box" data-product-id="1266843">
    <div data-price-amount="34,55" itemprop="price" class="price price-final"></div>
  </div>
  <meta itemprop="price" content="35.05">
  <img class="product-image-photo" data-src="https://cdn/x.webp" alt="Spumant Zaz">
  <button class="tocart" data-id="10508684" data-brand="Zaz"
          data-category="Vinuri/Spumante" data-dimension10="available"></button>
</li>
"""


def _tile():
    return HTMLParser(TILE).css_first("li.product")


def test_price_read_from_data_price_amount():
    p = CarrefourAdapter(fetcher=None)._parse_tile(_tile())
    assert p.price == 34.55
    assert p.external_id == "10508684"
    assert p.brand == "Zaz"
    assert p.in_stock is True


def test_meta_price_is_not_treated_as_a_discount():
    """The <meta> price is a rounding artifact, ~1.3% above the shelf price on
    96% of Carrefour wines. Reading it as a former price flagged 93% of the
    catalogue as on promotion."""
    p = CarrefourAdapter(fetcher=None)._parse_tile(_tile())
    assert p.list_price is None
    assert p.on_promotion is False
