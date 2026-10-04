import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.scraper_parser import extract_from_html

def test_json_ld_extraction():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": "Air Jordan 1 Retro High OG Chicago",
        "image": ["https://images.nike.com/aj1-chicago.jpg"],
        "description": "Iconic high-top basketball sneaker.",
        "brand": {
          "@type": "Brand",
          "name": "Nike"
        },
        "offers": {
          "@type": "Offer",
          "priceCurrency": "USD",
          "price": "180.00",
          "seller": {
            "@type": "Organization",
            "name": "Nike Official Store"
          }
        },
        "aggregateRating": {
          "@type": "AggregateRating",
          "ratingValue": "4.8",
          "reviewCount": "1250"
        }
      }
      </script>
    </head>
    <body><h1>Fallback Header</h1></body>
    </html>
    """
    res = extract_from_html(html, "https://nike.com/product/aj1")
    assert res["title"] == "Air Jordan 1 Retro High OG Chicago"
    assert res["price"] == 180.0
    assert res["currency"] == "USD"
    assert res["brand_claimed"] == "Nike"
    assert res["seller_name"] == "Nike Official Store"
    assert res["seller_rating"] == 4.8
    assert res["seller_reviews_count"] == 1250
    assert "https://images.nike.com/aj1-chicago.jpg" in res["image_urls"]

def test_opengraph_extraction():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
      <meta property="og:title" content="Rolex Submariner Date 126610LN">
      <meta property="product:price:amount" content="10250.00">
      <meta property="product:price:currency" content="USD">
      <meta property="product:brand" content="Rolex">
      <meta property="og:image" content="https://rolex.com/submariner.png">
    </head>
    <body></body>
    </html>
    """
    res = extract_from_html(html, "https://luxurywatches.com/item123")
    assert res["title"] == "Rolex Submariner Date 126610LN"
    assert res["price"] == 10250.0
    assert res["brand_claimed"] == "Rolex"
    assert res["currency"] == "USD"
    assert "https://rolex.com/submariner.png" in res["image_urls"]

def test_amazon_adapter():
    html = """
    <html>
    <head><title>Amazon.com: Nike Sneaker</title></head>
    <body>
      <span id="productTitle">Nike Air Force 1 '07 Men's Shoes</span>
      <a id="bylineInfo">Brand: Nike</a>
      <span id="priceblock_ourprice">$115.00</span>
      <div id="merchant-info">Sold by Nike and Fulfilled by Amazon.</div>
      <div id="acrPopover"><span class="a-icon-alt">4.7 out of 5 stars</span></div>
      <img id="landingImage" src="https://m.media-amazon.com/images/I/71xyz.jpg" />
    </body>
    </html>
    """
    res = extract_from_html(html, "https://www.amazon.com/dp/B08XYZ123")
    assert "Nike Air Force 1" in res["title"]
    assert res["price"] == 115.0
    assert res["brand_claimed"] == "Nike"
    assert res["seller_name"] == "Sold by Nike and Fulfilled by Amazon."
    assert res["seller_rating"] == 4.7
    assert len(res["image_urls"]) > 0

def test_flipkart_adapter():
    html = """
    <html>
    <body>
      <span class="VU-ZEz">Samba Classic Sneakers For Men</span>
      <span class="mEh187">ADIDAS</span>
      <div class="Nx9bqj CxhGGd">₹7,999</div>
      <div id="sellerName"><span>RetailNet</span></div>
      <div class="XQDdHH">4.4</div>
      <img class="DByuf4" src="https://rukminim2.flixcart.com/image/samba.jpeg" />
    </body>
    </html>
    """
    res = extract_from_html(html, "https://www.flipkart.com/adidas-samba/p/itm123")
    assert "Samba Classic Sneakers" in res["title"]
    assert res["price"] == 7999.0
    assert res["currency"] == "INR"
    assert res["brand_claimed"] == "ADIDAS"
    assert res["seller_name"] == "RetailNet"
    assert res["seller_rating"] == 4.4
    assert len(res["image_urls"]) > 0

def test_graceful_fallback_missing_fields():
    html = """
    <html>
    <head><title>Casual Canvas Shoes - Homage Edition</title></head>
    <body>
      <h1>Casual Classic Low Top Shoes</h1>
      <p>Only $29.99 today! High quality canvas.</p>
      <img src="https://store.com/dupe-shoe.jpg" />
    </body>
    </html>
    """
    res = extract_from_html(html, "https://unknownstore.com/casual-shoe")
    assert res["title"] == "Casual Classic Low Top Shoes"
    assert res["price"] == 29.99
    assert res["brand_claimed"] is None
    assert res["seller_name"] is None
    assert res["seller_rating"] is None
    assert "https://store.com/dupe-shoe.jpg" in res["image_urls"]

if __name__ == "__main__":
    print("Running scraper unit tests...")
    test_json_ld_extraction()
    print("[PASS] JSON-LD Product extraction")
    test_opengraph_extraction()
    print("[PASS] OpenGraph meta-tag extraction")
    test_amazon_adapter()
    print("[PASS] Amazon adapter extraction")
    test_flipkart_adapter()
    print("[PASS] Flipkart adapter extraction")
    test_graceful_fallback_missing_fields()
    print("[PASS] Graceful fallback on missing fields")
    print("\nALL SCRAPER TESTS PASSED!")
