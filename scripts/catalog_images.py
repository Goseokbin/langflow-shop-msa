#!/usr/bin/env python3
"""Supply and verify images for the demo catalog without replacing custom images."""

import argparse
import json
import os
import urllib.request
from urllib.parse import urlsplit


DEMO_PRODUCT_IMAGES = {
    "Laptop Pro 15": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=800&q=85",
    "Wireless Mouse": "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?auto=format&fit=crop&w=800&q=85",
    "USB-C Hub": "https://cdn.t-nb.com/image/upload/VISUEL_HD/HUBALU8C/03303170121191_C1R0_s01.jpg",
    "Mechanical Keyboard": "https://images.unsplash.com/photo-1625948515291-69613efd103f?auto=format&fit=crop&w=800&q=85",
    "4K Monitor UltraView 27": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=800&q=85",
}

# Historical demo mappings showed a keyboard for the hub and a membrane keyboard
# for the mechanical keyboard. Repair only these known mappings, not custom media.
INCORRECT_IMAGE_PATHS = {
    "USB-C Hub": {"/photo-1625948515291-69613efd103f"},
    "Mechanical Keyboard": {"/photo-1587829741301-dc798b83add3"},
}


def ensure_catalog_images(request, products):
    """Repair missing URLs and known incorrect mappings on named demo products."""
    updated = []
    for product in products:
        image_url = DEMO_PRODUCT_IMAGES.get(product["name"])
        current = (product.get("image_url") or "").strip()
        parsed = urlsplit(current)
        incorrect = parsed.hostname == "images.unsplash.com" and parsed.path in INCORRECT_IMAGE_PATHS.get(product["name"], set())
        if image_url and (not current or incorrect):
            request("/api/products/" + product["id"], {"image_url": image_url}, method="PUT")
            updated.append(product["name"])
    return updated


def verify_catalog_images(products):
    """Fail on missing or unreachable images instead of accepting placeholders."""
    checked = []
    for product in products:
        if product["name"] not in DEMO_PRODUCT_IMAGES:
            continue
        url = (product.get("image_url") or "").strip()
        if not url.startswith("https://"):
            raise AssertionError("Missing HTTPS product image: " + product["name"])
        with urllib.request.urlopen(url, timeout=45) as response:
            media_type = response.headers.get_content_type()
            body = response.read(5 * 1024 * 1024 + 1)
            signature_ok = body.startswith(b"\xff\xd8\xff") or body.startswith(b"\x89PNG\r\n\x1a\n") or (
                body.startswith(b"RIFF") and body[8:12] == b"WEBP"
            )
            if response.status != 200 or not media_type.startswith("image/") or not signature_ok:
                raise AssertionError("Invalid image response: " + product["name"])
            if not 1000 <= len(body) <= 5 * 1024 * 1024:
                raise AssertionError("Unexpected image size: " + product["name"])
            checked.append({"name": product["name"], "content_type": media_type, "bytes": len(body)})
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Frontend HTTPS Route, without /api")
    parser.add_argument("--apply", action="store_true", help="Fill missing demo image URLs")
    parser.add_argument("--check-images", action="store_true", help="Fetch and validate image responses")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    if not base.startswith("https://"):
        parser.error("--base-url must use HTTPS")

    def request(path, data=None, method=None):
        headers = {"Content-Type": "application/json"}
        token = os.environ.get("SHOP_API_TOKEN")
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(base + path, data=json.dumps(data).encode() if data is not None else None, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.load(response)

    products = request("/api/products")
    missing = [p["name"] for p in products if p["name"] in DEMO_PRODUCT_IMAGES and not p.get("image_url")]
    updated = ensure_catalog_images(request, products) if args.apply else []
    products = request("/api/products") if updated else products
    checked = verify_catalog_images(products) if args.check_images else []
    print(json.dumps({"base": base, "missing_before": missing, "updated": updated, "image_checks": checked}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
