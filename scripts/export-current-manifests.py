#!/usr/bin/env python3
"""현재 배포의 비밀값 없는 매니페스트를 저장한다. 이미지 digest를 고정한 스냅샷이다."""

import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
NS = "shopping-mall"


def export(kind, name, path):
    d = json.loads(
        subprocess.check_output(
            ["oc", "get", kind, name, "-n", NS, "-o", "json"], text=True
        )
    )
    meta = d["metadata"]
    out = {
        "apiVersion": d["apiVersion"],
        "kind": d["kind"],
        "metadata": {k: meta[k] for k in ["name", "namespace", "labels"] if k in meta},
        "spec": d["spec"],
    }
    if kind == "service":
        out["spec"] = {
            k: d["spec"][k] for k in ["selector", "ports", "type"] if k in d["spec"]
        }
    if kind == "route":
        out["spec"].pop("host", None)
    if kind == "pvc":
        out["spec"] = {
            k: d["spec"][k]
            for k in ["accessModes", "resources", "storageClassName"]
            if k in d["spec"]
        }
    yaml = subprocess.check_output(
        [
            "oc",
            "create",
            "--dry-run=client",
            "--validate=false",
            "-f",
            "-",
            "-o",
            "yaml",
        ],
        input=json.dumps(out),
        text=True,
    )
    (ROOT / path).write_text(yaml)


for name in [
    "user-service",
    "product-service",
    "cart-service",
    "order-service",
    "langflow-ai-service",
    "api-gateway",
    "frontend",
    "langflow",
    "postgresql",
]:
    filename = {
        "langflow": "langflow.yaml",
        "langflow-ai-service": "langflow-ai-deployment.yaml",
    }.get(name, name + "-deployment.yaml")
    export("deployment", name, "openshift/deployments/" + filename)
    filename = {
        "frontend": "frontend-service.yaml",
        "api-gateway": "api-gateway-service.yaml",
    }.get(name, name + ".yaml")
    export("service", name, "openshift/services/" + filename)
for name in ["frontend", "api-gateway", "langflow"]:
    export("route", name, "openshift/routes/" + name + "-route.yaml")
(ROOT / "openshift/volumes").mkdir(exist_ok=True)
for name in ["postgres-data", "langflow-data"]:
    export("pvc", name, "openshift/volumes/" + name + ".yaml")
print("Deployment, Service, Route, PVC snapshots exported. Secret values excluded.")
