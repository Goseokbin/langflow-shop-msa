#!/usr/bin/env python3
"""Langflow 로그인 → Flow 등록 → 앱 전용 API 키를 Secret에 저장. 비밀값은 출력하지 않는다."""

import base64
import json
import pathlib
import re
import subprocess
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
NS = "shopping-mall"


def oc(*args, data=None):
    return subprocess.check_output(["oc", *args], input=data, text=True)


def secret(name):
    return {
        k: base64.b64decode(v).decode()
        for k, v in json.loads(oc("get", "secret", name, "-n", NS, "-o", "json"))[
            "data"
        ].items()
    }


base = "https://" + oc(
    "get", "route", "langflow", "-n", NS, "-o", "jsonpath={.spec.host}"
)
admin = secret("langflow-admin")


def request(path, data=None, method=None, token=None, key=None, form=False):
    body = (
        urllib.parse.urlencode(data).encode()
        if form
        else (json.dumps(data).encode() if data is not None else None)
    )
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
        if form
        else "application/json"
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    if key:
        headers["x-api-key"] = key
    try:
        return json.load(
            urllib.request.urlopen(
                urllib.request.Request(
                    base + path, data=body, headers=headers, method=method
                ),
                timeout=120,
            )
        )
    except urllib.error.HTTPError as exc:
        detail = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", exc.read().decode())
        raise RuntimeError(f"{path}: HTTP {exc.code}: {detail[:1800]}") from None


token = request(
    "/api/v1/login",
    {
        "username": admin["LANGFLOW_SUPERUSER"],
        "password": admin["LANGFLOW_SUPERUSER_PASSWORD"],
    },
    form=True,
)["access_token"]
flow = json.loads((ROOT / "openshift/flows/shopping-assistant.json").read_text())
existing = request("/api/v1/flows/?remove_example_flows=true", token=token)
found = next(
    (f for f in existing if f.get("endpoint_name") == "shopping-assistant"), None
)
if found:
    registered = request(
        "/api/v1/flows/" + found["id"], flow, method="PATCH", token=token
    )
else:
    registered = request("/api/v1/flows/", flow, token=token)
app = secret("langflow-api")
key = app.get("LANGFLOW_API_KEY")
if not key:
    created = request(
        "/api/v1/api_key/", {"name": "langflow-shop-service"}, token=token
    )
    key = created.get("api_key") or created.get("key")
    if not key:
        raise RuntimeError("API key response did not include a key")
url = "http://langflow:7860/api/v1/run/" + registered["id"]
patch = {"stringData": {"LANGFLOW_API_KEY": key, "LANGFLOW_URL": url}}
oc(
    "patch",
    "secret",
    "langflow-api",
    "-n",
    NS,
    "--type=merge",
    "--patch-file=/dev/stdin",
    data=json.dumps(patch),
)
print("Flow configured:", registered["id"], registered["name"])
result = request(
    "/api/v1/run/" + registered["id"],
    {
        "input_value": "한국어로 쇼핑몰 방문자에게 짧게 인사해 주세요.",
        "input_type": "chat",
        "output_type": "chat",
        "session_id": "deployment-smoke",
    },
    key=key,
)
text = result["outputs"][0]["outputs"][0]["results"]["message"]["text"]
print("Langflow model smoke test:", text)
