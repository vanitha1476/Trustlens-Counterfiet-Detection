"""
Python implementation of the TrustLens 4-tier scraper cascade.
Used by backend utilities, test validation, and simulation.
"""
import json
import re
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup

def extract_from_html(html_content: str, url: str = "https://example.com/product") -> Dict[str, Any]:
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Tier 1: Schema.org JSON-LD
    json_ld_data = None
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            parsed = json.loads(script.string or script.text)
            items = parsed if isinstance(parsed, list) else parsed.get("@graph", [parsed])
            for item in items:
                if item.get("@type") == "Product" or "Product" in str(item.get("@type")):
                    offers = item.get("offers")
                    if isinstance(offers, list) and len(offers) > 0:
                        offers = offers[0]
                    
                    price = None
                    currency = "USD"
                    if isinstance(offers, dict):
                        price_val = offers.get("price") or offers.get("lowPrice")
                        if price_val:
                            try:
                                price = float(price_val)
                            except (ValueError, TypeError):
                                pass
                        currency = offers.get("priceCurrency", "USD")
                    
                    images = []
                    raw_img = item.get("image")
                    if isinstance(raw_img, str):
                        images.append(raw_img)
                    elif isinstance(raw_img, list):
                        images = [img if isinstance(img, str) else img.get("url") for img in raw_img if img]
                    elif isinstance(raw_img, dict) and "url" in raw_img:
                        images.append(raw_img["url"])
                    
                    brand_name = None
                    brand_field = item.get("brand")
                    if isinstance(brand_field, str):
                        brand_name = brand_field
                    elif isinstance(brand_field, dict):
                        brand_name = brand_field.get("name")
                        
                    agg_rating = item.get("aggregateRating", {})
                    seller_name = offers.get("seller", {}).get("name") if isinstance(offers, dict) and isinstance(offers.get("seller"), dict) else None

                    json_ld_data = {
                        "title": item.get("name"),
                        "price": price,
                        "currency": currency,
                        "brand_claimed": brand_name,
                        "seller_name": seller_name,
                        "seller_rating": float(agg_rating.get("ratingValue")) if agg_rating.get("ratingValue") else None,
                        "seller_reviews_count": int(agg_rating.get("reviewCount")) if agg_rating.get("reviewCount") else None,
                        "description": item.get("description", ""),
                        "image_urls": images
                    }
                    break
            if json_ld_data:
                break
        except Exception:
            continue

    # Tier 2: OpenGraph
    og_data = None
    og_title = (soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"}))
    og_image = (soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"}))
    og_price = (soup.find("meta", property="product:price:amount") or soup.find("meta", property="og:price:amount"))
    og_currency = (soup.find("meta", property="product:price:currency") or soup.find("meta", property="og:price:currency"))
    og_brand = (soup.find("meta", property="product:brand") or soup.find("meta", property="og:brand"))

    if og_title or og_image or og_price:
        price_val = None
        if og_price and og_price.get("content"):
            cleaned = re.sub(r"[^\d.]", "", og_price["content"])
            if cleaned:
                price_val = float(cleaned)
        og_data = {
            "title": og_title["content"] if og_title and og_title.get("content") else None,
            "price": price_val,
            "currency": og_currency["content"] if og_currency and og_currency.get("content") else "USD",
            "brand_claimed": og_brand["content"] if og_brand and og_brand.get("content") else None,
            "seller_name": None,
            "seller_rating": None,
            "seller_reviews_count": None,
            "description": "",
            "image_urls": [og_image["content"]] if og_image and og_image.get("content") else []
        }

    # Tier 3: Specialized Adapters (Amazon / Flipkart)
    amazon_data = None
    if "amazon." in url or soup.find(id="productTitle"):
        title_el = soup.find(id="productTitle") or soup.find(id="title")
        title = title_el.get_text(strip=True) if title_el else None
        
        price = None
        price_el = soup.select_one(".a-price .a-offscreen, #priceblock_ourprice, #priceblock_dealprice")
        if price_el:
            match = re.search(r"[\d,.]+", price_el.get_text())
            if match:
                price = float(match.group(0).replace(",", ""))
                
        brand = None
        brand_el = soup.find(id="bylineInfo") or soup.find(id="brand") or soup.select_one(".po-brand .a-span9")
        if brand_el:
            brand = re.sub(r"(?i)Brand:|Visit the | Store", "", brand_el.get_text(strip=True)).strip()
            
        seller = None
        seller_el = soup.find(id="merchant-info") or soup.find(id="sellerProfileTriggerId")
        if seller_el:
            seller = seller_el.get_text(strip=True)
            
        rating = None
        rating_el = soup.select_one("#acrPopover .a-icon-alt")
        if rating_el:
            rmatch = re.search(r"([\d.]+)\s+out of", rating_el.get_text())
            if rmatch:
                rating = float(rmatch.group(1))
                
        images = []
        landing_img = soup.find(id="landingImage") or soup.find(id="imgBlkFront")
        if landing_img and landing_img.get("src"):
            images.append(landing_img["src"])
            
        amazon_data = {
            "title": title,
            "price": price,
            "currency": "USD",
            "brand_claimed": brand,
            "seller_name": seller,
            "seller_rating": rating,
            "seller_reviews_count": None,
            "description": "",
            "image_urls": images
        }

    flipkart_data = None
    if "flipkart." in url or soup.select_one(".B_NuCI, span.VU-ZEz, h1._6EBuvT"):
        title_el = soup.select_one(".B_NuCI, span.VU-ZEz, h1._6EBuvT")
        title = title_el.get_text(strip=True) if title_el else None
        
        price = None
        price_el = soup.select_one("._30jeq3._16Jk6d, div.Nx9bqj.CxhGGd")
        if price_el:
            match = re.search(r"[\d,.]+", price_el.get_text())
            if match:
                price = float(match.group(0).replace(",", ""))
                
        brand = None
        brand_el = soup.select_one("span.mEh187, span.G6XhRU")
        if brand_el:
            brand = brand_el.get_text(strip=True)
            
        seller = None
        seller_el = soup.select_one("#sellerName, div._1RLviY")
        if seller_el:
            seller = re.sub(r"(?i)Seller:\s*", "", seller_el.get_text(strip=True)).strip()
            
        rating = None
        rating_el = soup.select_one("div._3LWZlK, div.XQDdHH")
        if rating_el:
            try:
                rating = float(rating_el.get_text(strip=True))
            except ValueError:
                pass
                
        images = []
        img_el = soup.select_one("img._396cs4._3exPp9, img.DByuf4")
        if img_el and img_el.get("src"):
            images.append(img_el["src"])
            
        flipkart_data = {
            "title": title,
            "price": price,
            "currency": "INR",
            "brand_claimed": brand,
            "seller_name": seller,
            "seller_rating": rating,
            "seller_reviews_count": None,
            "description": "",
            "image_urls": images
        }

    # Tier 4: Generic Fallback
    h1 = soup.find("h1")
    title_fallback = h1.get_text(strip=True) if h1 else (soup.title.string.strip() if soup.title else "")
    
    price_fallback = None
    all_text = soup.get_text()
    match = re.search(r"[\$₹£€]\s*([\d,]+(?:\.\d{2})?)", all_text)
    if match:
        try:
            price_fallback = float(match.group(1).replace(",", ""))
        except ValueError:
            pass
            
    images_fallback = []
    for img in soup.find_all("img"):
        src = img.get("src")
        if src and not src.startswith("data:"):
            images_fallback.append(src)
            if len(images_fallback) >= 3:
                break

    generic_data = {
        "title": title_fallback,
        "price": price_fallback,
        "currency": "USD",
        "brand_claimed": None,
        "seller_name": None,
        "seller_rating": None,
        "seller_reviews_count": None,
        "description": "",
        "image_urls": images_fallback
    }

    # Merge hierarchy
    primary = amazon_data or flipkart_data or json_ld_data or og_data or generic_data
    backup = og_data or generic_data

    return {
        "url": url,
        "title": primary.get("title") or backup.get("title") or "",
        "price": primary.get("price") if primary.get("price") is not None else backup.get("price"),
        "currency": primary.get("currency") or backup.get("currency") or "USD",
        "brand_claimed": primary.get("brand_claimed") or backup.get("brand_claimed"),
        "seller_name": primary.get("seller_name") or backup.get("seller_name"),
        "seller_rating": primary.get("seller_rating") if primary.get("seller_rating") is not None else backup.get("seller_rating"),
        "seller_reviews_count": primary.get("seller_reviews_count") or backup.get("seller_reviews_count"),
        "description": primary.get("description") or backup.get("description") or "",
        "image_urls": primary.get("image_urls") if primary.get("image_urls") else (backup.get("image_urls") or [])
    }
