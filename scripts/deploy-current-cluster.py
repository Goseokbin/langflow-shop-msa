#!/usr/bin/env python3
"""현재 OpenShift에 소스 빌드와 배포. 비밀값은 클러스터 Secret에만 생성한다."""

import base64
import concurrent.futures
import json
import pathlib
import secrets
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
NS = "shopping-mall"
SERVICES = {
    "user-service": 8001,
    "product-service": 8002,
    "cart-service": 8003,
    "order-service": 8004,
    "langflow-ai-service": 8005,
    "api-gateway": 8000,
    "frontend": 3000,
}
LABELS = {
    "app.kubernetes.io/part-of": "langflow-shop",
    "app.kubernetes.io/managed-by": "langflow-shop-deployer",
}


def oc(*args, data=None, capture=False):
    return subprocess.run(
        ["oc", *args],
        input=data,
        text=True,
        check=True,
        stdout=subprocess.PIPE if capture else None,
    ).stdout


def resource(kind, name, api="v1", **fields):
    return {
        "apiVersion": api,
        "kind": kind,
        "metadata": {"name": name, "namespace": NS, "labels": LABELS},
        **fields,
    }


def apply(items):
    oc(
        "apply",
        "-f",
        "-",
        data=json.dumps({"apiVersion": "v1", "kind": "List", "items": items}),
    )


def secret(name, values):
    if not oc(
        "get",
        "secret",
        name,
        "-n",
        NS,
        "--ignore-not-found",
        "-o",
        "name",
        capture=True,
    ).strip():
        oc(
            "create",
            "-f",
            "-",
            data=json.dumps(resource("Secret", name, type="Opaque", stringData=values)),
        )


def val(k, v):
    return {"name": k, "value": v}


def ref(k, s, key=None, optional=False):
    return {
        "name": k,
        "valueFrom": {
            "secretKeyRef": {"name": s, "key": key or k, "optional": optional}
        },
    }


def deployment(
    name,
    image,
    port,
    env,
    volumes=None,
    mounts=None,
    health="/health",
    memory="256Mi",
    limit="512Mi",
):
    return resource(
        "Deployment",
        name,
        "apps/v1",
        spec={
            "replicas": 1,
            "selector": {"matchLabels": {"app": name}},
            "strategy": {"type": "Recreate"} if volumes else {"type": "RollingUpdate"},
            "template": {
                "metadata": {
                    "labels": {**LABELS, "app": name, "app.kubernetes.io/name": name}
                },
                "spec": {
                    "serviceAccountName": "shop-runtime",
                    "automountServiceAccountToken": False,
                    "enableServiceLinks": False,
                    "securityContext": {
                        "runAsNonRoot": True,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "containers": [
                        {
                            "name": name,
                            "image": image,
                            "imagePullPolicy": "IfNotPresent",
                            "ports": [{"containerPort": port}],
                            "env": env,
                            "securityContext": {
                                "allowPrivilegeEscalation": False,
                                "capabilities": {"drop": ["ALL"]},
                            },
                            "resources": {
                                "requests": {"cpu": "100m", "memory": memory},
                                "limits": {"cpu": "2", "memory": limit},
                            },
                            "volumeMounts": mounts or [],
                            "startupProbe": {
                                "httpGet": {"path": health, "port": port},
                                "periodSeconds": 10,
                                "failureThreshold": 90,
                            },
                            "readinessProbe": {
                                "httpGet": {"path": health, "port": port},
                                "periodSeconds": 10,
                            },
                            "livenessProbe": {
                                "httpGet": {"path": health, "port": port},
                                "periodSeconds": 20,
                                "failureThreshold": 6,
                            },
                        }
                    ],
                    "volumes": volumes or [],
                },
            },
        },
    )


def service(name, port):
    return resource(
        "Service",
        name,
        spec={
            "selector": {"app": name},
            "ports": [{"name": "http", "port": port, "targetPort": port}],
        },
    )


def route(name, port):
    return resource(
        "Route",
        name,
        "route.openshift.io/v1",
        spec={
            "to": {"kind": "Service", "name": name},
            "port": {"targetPort": port},
            "tls": {"termination": "edge", "insecureEdgeTerminationPolicy": "Redirect"},
        },
    )


def build(name):
    with tempfile.NamedTemporaryFile(suffix=".tar.gz") as f:
        with tarfile.open(f.name, "w:gz") as tar:

            def filt(info):
                return (
                    None
                    if any(
                        x in pathlib.PurePosixPath(info.name).parts
                        for x in [
                            "node_modules",
                            ".next",
                            ".git",
                            "__pycache__",
                            ".DS_Store",
                        ]
                    )
                    else info
                )

            tar.add(ROOT / "services" / name, arcname=".", filter=filt)
        result = oc(
            "start-build",
            name,
            "-n",
            NS,
            "--from-archive=" + f.name,
            "-o",
            "name",
            capture=True,
        ).strip()
    print("Started " + result, flush=True)
    return result


if __name__ == "__main__":
    apply(
        [
            {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {"name": NS, "labels": LABELS},
            },
            resource("ServiceAccount", "shop-runtime"),
        ]
    )
    secret(
        "postgres-secrets",
        {"POSTGRES_USER": "shop", "POSTGRES_PASSWORD": secrets.token_hex(24)},
    )
    secret("jwt-secret", {"JWT_SECRET_KEY": secrets.token_hex(32)})
    secret(
        "langflow-admin",
        {
            "LANGFLOW_SUPERUSER": "shop-admin",
            "LANGFLOW_SUPERUSER_PASSWORD": secrets.token_urlsafe(32),
            "LANGFLOW_SECRET_KEY": base64.urlsafe_b64encode(
                secrets.token_bytes(32)
            ).decode(),
        },
    )
    secret(
        "langflow-api",
        {
            "LANGFLOW_API_KEY": "",
            "LANGFLOW_URL": "http://langflow:7860/api/v1/run/shopping-assistant",
        },
    )
    items = []
    for name in ["postgres-data", "langflow-data"]:
        items.append(
            resource(
                "PersistentVolumeClaim",
                name,
                spec={
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {"requests": {"storage": "10Gi"}},
                },
            )
        )
    db = deployment(
        "postgresql",
        "quay.io/sclorg/postgresql-16-c9s@sha256:c9990e93bf07321bf5f8cc31ef97951ec181d0f40293c0438422e8e53e2ef06e",
        5432,
        [
            ref("POSTGRESQL_USER", "postgres-secrets", "POSTGRES_USER"),
            ref("POSTGRESQL_PASSWORD", "postgres-secrets", "POSTGRES_PASSWORD"),
            val("POSTGRESQL_DATABASE", "user_db"),
        ],
        [{"name": "data", "persistentVolumeClaim": {"claimName": "postgres-data"}}],
        [{"name": "data", "mountPath": "/var/lib/pgsql/data"}],
        memory="512Mi",
        limit="1Gi",
    )
    c = db["spec"]["template"]["spec"]["containers"][0]
    for key in ["startupProbe", "readinessProbe", "livenessProbe"]:
        c[key].pop("httpGet")
        c[key]["exec"] = {
            "command": ["/bin/sh", "-c", "pg_isready -h 127.0.0.1 -p 5432"]
        }
    items.extend([db, service("postgresql", 5432)])
    lf = deployment(
        "langflow",
        "docker.io/langflowai/langflow@sha256:36a1cf1e329a94dba77980fd0b0db3237d49d5a30df39cdad703a6a9bf67782b",
        7860,
        [
            ref("OPENAI_API_KEY", "model-api", optional=True),
            val("HOME", "/data"),
            val("LANGFLOW_CONFIG_DIR", "/data"),
            val("LANGFLOW_DATABASE_URL", "sqlite:////data/langflow.db"),
            val("LANGFLOW_HOST", "0.0.0.0"),
            val("LANGFLOW_AUTO_LOGIN", "false"),
            val("LANGFLOW_CUSTOM_COMPONENT_ADMIN_ONLY", "true"),
            val("LANGFLOW_BACKEND_ONLY", "false"),
            val("LANGFLOW_DO_NOT_TRACK", "true"),
            val("DO_NOT_TRACK", "true"),
            val("LANGFLOW_WORKERS", "1"),
            val("LANGFLOW_CACHE_TYPE", "memory"),
            ref("LANGFLOW_SUPERUSER", "langflow-admin"),
            ref("LANGFLOW_SUPERUSER_PASSWORD", "langflow-admin"),
            ref("LANGFLOW_SECRET_KEY", "langflow-admin"),
        ],
        [
            {"name": "data", "persistentVolumeClaim": {"claimName": "langflow-data"}},
            {"name": "tmp", "emptyDir": {}},
        ],
        [{"name": "data", "mountPath": "/data"}, {"name": "tmp", "mountPath": "/tmp"}],
        health="/health",
        memory="2Gi",
        limit="6Gi",
    )
    items.extend([lf, service("langflow", 7860), route("langflow", 7860)])
    for name in SERVICES:
        items.append(resource("ImageStream", name, "image.openshift.io/v1"))
        items.append(
            resource(
                "BuildConfig",
                name,
                "build.openshift.io/v1",
                spec={
                    "source": {"type": "Binary", "binary": {}},
                    "strategy": {
                        "type": "Docker",
                        "dockerStrategy": {"dockerfilePath": "Dockerfile"},
                    },
                    "output": {
                        "to": {"kind": "ImageStreamTag", "name": name + ":current"}
                    },
                    "resources": {
                        "requests": {"cpu": "100m", "memory": "512Mi"},
                        "limits": {"cpu": "2", "memory": "3Gi"},
                    },
                    "triggers": [],
                },
            )
        )
    apply(items)
    oc("rollout", "status", "deployment/postgresql", "-n", NS, "--timeout=180s")
    for dbname in ["product_db", "cart_db", "order_db"]:
        exists = oc(
            "exec",
            "-n",
            NS,
            "deployment/postgresql",
            "--",
            "psql",
            "-U",
            "postgres",
            "-tAc",
            f"SELECT 1 FROM pg_database WHERE datname='{dbname}'",
            capture=True,
        ).strip()
        if exists != "1":
            oc(
                "exec",
                "-n",
                NS,
                "deployment/postgresql",
                "--",
                "psql",
                "-U",
                "postgres",
                "-c",
                f"CREATE DATABASE {dbname} OWNER shop",
            )
    if "--skip-build" not in sys.argv:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            builds = list(pool.map(build, SERVICES))
        for b in builds:
            deadline = time.monotonic() + 900
            while True:
                phase = oc(
                    "get", b, "-n", NS, "-o", "jsonpath={.status.phase}", capture=True
                )
                if phase == "Complete":
                    break
                if (
                    phase in ["Failed", "Error", "Cancelled"]
                    or time.monotonic() > deadline
                ):
                    raise RuntimeError(f"{b}: {phase}; oc logs -n {NS} {b}")
                time.sleep(2)
    items = []
    for name, port in SERVICES.items():
        env = [val("JWT_ALGORITHM", "HS256"), ref("JWT_SECRET_KEY", "jwt-secret")]
        for svc, p in SERVICES.items():
            key = {
                "api-gateway": "API_GATEWAY_URL",
                "langflow-ai-service": "AI_SERVICE_URL",
            }.get(svc, svc.upper().replace("-", "_") + "_URL")
            env.append(val(key, f"http://{svc}:{p}"))
        if name in ["user-service", "product-service", "cart-service", "order-service"]:
            env += [
                val("POSTGRES_HOST", "postgresql"),
                val("POSTGRES_PORT", "5432"),
                val("POSTGRES_DB", name.split("-")[0] + "_db"),
                ref("POSTGRES_USER", "postgres-secrets"),
                ref("POSTGRES_PASSWORD", "postgres-secrets"),
            ]
        if name == "langflow-ai-service":
            env += [
                ref("LANGFLOW_API_KEY", "langflow-api"),
                ref("LANGFLOW_URL", "langflow-api"),
            ]
        image = json.loads(
            oc("get", "istag", name + ":current", "-n", NS, "-o", "json", capture=True)
        )["image"]["dockerImageReference"]
        items.extend(
            [
                deployment(
                    name,
                    image,
                    port,
                    env,
                    health="/" if name == "frontend" else "/ready",
                    memory="256Mi",
                    limit="1Gi",
                ),
                service(name, port),
            ]
        )
    items += [route("frontend", 3000), route("api-gateway", 8000)]
    apply(items)
    for name in ["postgresql", "langflow", *SERVICES]:
        oc("rollout", "status", "deployment/" + name, "-n", NS, "--timeout=180s")
    print(
        "배포 완료. Langflow Flow 설정과 실제 기능 검증은 configure-langflow.py, smoke-test.py로 수행합니다.",
        flush=True,
    )
