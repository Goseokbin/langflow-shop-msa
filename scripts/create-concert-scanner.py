#!/usr/bin/env python3
"""스캔 전용 ServiceAccount와 임시 Trivy Pod를 생성한다."""

import json
import subprocess

ns = "shopping-mall"
objs = [
    {
        "apiVersion": "v1",
        "kind": "ServiceAccount",
        "metadata": {"name": "concert-image-scanner", "namespace": ns},
    },
    {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "RoleBinding",
        "metadata": {"name": "concert-image-scanner-pull", "namespace": ns},
        "roleRef": {
            "apiGroup": "rbac.authorization.k8s.io",
            "kind": "ClusterRole",
            "name": "system:image-puller",
        },
        "subjects": [
            {"kind": "ServiceAccount", "name": "concert-image-scanner", "namespace": ns}
        ],
    },
    {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "concert-image-audit",
            "namespace": ns,
            "labels": {"app": "concert-image-audit"},
        },
        "spec": {
            "serviceAccountName": "concert-image-scanner",
            "enableServiceLinks": False,
            "restartPolicy": "Never",
            "securityContext": {
                "runAsNonRoot": True,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            "containers": [
                {
                    "name": "trivy",
                    "image": "docker.io/aquasec/trivy:0.75.0",
                    "command": [
                        "sh",
                        "-c",
                        "mkdir -p /work/results /work/cache; touch /work/ready; exec tail -f /dev/null",
                    ],
                    "env": [
                        {"name": "HOME", "value": "/work"},
                        {
                            "name": "SSL_CERT_DIR",
                            "value": "/registry-ca:/etc/ssl/certs",
                        },
                    ],
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                    },
                    "resources": {
                        "requests": {
                            "cpu": "250m",
                            "memory": "1Gi",
                            "ephemeral-storage": "2Gi",
                        },
                        "limits": {
                            "cpu": "2",
                            "memory": "4Gi",
                            "ephemeral-storage": "25Gi",
                        },
                    },
                    "volumeMounts": [
                        {"name": "work", "mountPath": "/work"},
                        {
                            "name": "registry-ca",
                            "mountPath": "/registry-ca",
                            "readOnly": True,
                        },
                    ],
                }
            ],
            "volumes": [
                {"name": "work", "emptyDir": {"sizeLimit": "25Gi"}},
                {
                    "name": "registry-ca",
                    "configMap": {"name": "openshift-service-ca.crt"},
                },
            ],
        },
    },
]
subprocess.run(
    ["oc", "apply", "-f", "-"],
    input=json.dumps({"apiVersion": "v1", "kind": "List", "items": objs}),
    text=True,
    check=True,
)
