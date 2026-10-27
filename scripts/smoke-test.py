#!/usr/bin/env python3
"""실제 배포된 Route에서 상품·인증·장바구니·주문·취소 흐름을 검증한다."""

import json
import secrets
import subprocess
import urllib.error
import urllib.request
import uuid

host = subprocess.check_output(
    [
        "oc",
        "get",
        "route",
        "frontend",
        "-n",
        "shopping-mall",
        "-o",
        "jsonpath={.spec.host}",
    ],
    text=True,
)
BASE = "https://" + host
TOKEN = None
results = []


def req(path, data=None, method=None, status=200):
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            code = response.status
            body = response.read()
    except urllib.error.HTTPError as error:
        code = error.code
        body = error.read()
    assert code == status, (path, code, body[:400].decode())
    return json.loads(body) if body else None


req("/api/cart", status=401)
results.append("unauthenticated cart: 401")
email = "smoke-" + uuid.uuid4().hex[:10] + "@example.com"
password = secrets.token_urlsafe(18)
user = req(
    "/api/auth/register",
    {"email": email, "password": password, "name": "Deployment Smoke Test"},
    status=201,
)
results.append("registration: 201")
req("/api/auth/login", {"email": email, "password": "invalid-password"}, status=401)
results.append("invalid login: 401")
TOKEN = req("/api/auth/login", {"email": email, "password": password})["access_token"]
assert req("/api/users/me")["id"] == user["id"]
results.append("login and profile: PASS")
products = req("/api/products")
if not products:
    for name, price, category in [
        ("Laptop Pro 15", 1299.99, "Electronics"),
        ("Wireless Mouse", 29.99, "Accessories"),
        ("USB-C Hub", 49.99, "Accessories"),
        ("Mechanical Keyboard", 89.99, "Accessories"),
        ("4K Monitor UltraView 27", 349.99, "Electronics"),
    ]:
        req(
            "/api/products",
            {
                "name": name,
                "description": "Langflow Shop demo catalog product",
                "price": price,
                "inventory": 50,
                "category": category,
            },
            method="POST",
            status=201,
        )
    products = req("/api/products")
assert len(products) >= 1
results.append("catalog: " + str(len(products)) + " products")
product = products[0]
before = product["inventory"]
cart = req("/api/cart/items", {"product_id": product["id"], "quantity": 2})
cart = req("/api/cart")
assert len(cart["items"]) == 1 and cart["items"][0]["quantity"] == 2
req("/api/cart/items/" + cart["items"][0]["id"], {"quantity": 1}, method="PUT")
assert req("/api/cart")["items"][0]["quantity"] == 1
results.append("cart add/read/update: PASS")
order = req("/api/orders", {"shipping_address": "Deployment test address, Seoul"})
assert float(order["total_amount"]) == float(product["price"])
assert req("/api/cart")["items"] == []
assert req("/api/products/" + product["id"])["inventory"] == before - 1
orders = req("/api/orders")
assert any(x["id"] == order["id"] for x in orders)
results.append("checkout, order history, inventory and cart clear: PASS")
req("/api/orders/" + order["id"] + "/cancel", {}, method="POST")
assert req("/api/products/" + product["id"])["inventory"] == before
results.append("cancel and restore inventory: PASS")
print(
    json.dumps(
        {
            "base": BASE,
            "results": results,
            "test_user": email,
            "test_order": order["id"],
        },
        ensure_ascii=False,
        indent=2,
    )
)
