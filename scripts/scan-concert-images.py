#!/usr/bin/env python3
"""현재 실행 이미지 9개를 격리된 Trivy Pod에서 스캔하고 raw/CycloneDX 결과를 보관한다."""

import collections
import json
import pathlib
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / ".runtime/image-scans"
OUT.mkdir(parents=True, exist_ok=True)
NS = "shopping-mall"
POD = "concert-image-audit"
items = json.loads(
    subprocess.check_output(
        ["oc", "get", "deployments", "-n", NS, "-o", "json"], text=True
    )
)["items"]
items.sort(key=lambda d: (d["metadata"]["name"] == "langflow", d["metadata"]["name"]))
summary = []
for d in items:
    name = d["metadata"]["name"]
    image = d["spec"]["template"]["spec"]["containers"][0]["image"]
    raw = f"/work/results/{name}.trivy.json"
    cdx = f"/work/results/{name}.cdx.json"
    auth = (
        "export TRIVY_USERNAME=serviceaccount; read -r TRIVY_PASSWORD < /var/run/secrets/kubernetes.io/serviceaccount/token; export TRIVY_PASSWORD; "
        if image.startswith("image-registry.")
        else ""
    )
    cmd = (
        auth
        + f"trivy image --image-src remote --cache-dir /work/cache --scanners vuln --format json --list-all-pkgs --skip-version-check --timeout 15m --output {raw} {image}"
    )
    print("Scanning " + name, flush=True)
    start = time.monotonic()
    with (OUT / f"{name}.log").open("w") as log:
        r = subprocess.run(
            ["oc", "exec", "-n", NS, POD, "--", "sh", "-c", cmd],
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if r.returncode:
        summary.append(
            {
                "name": name,
                "image": image,
                "status": "failed",
                "log": str(OUT / f"{name}.log"),
            }
        )
        print("FAILED " + name, flush=True)
        continue
    with (OUT / f"{name}.trivy.json").open("wb") as f:
        subprocess.run(
            ["oc", "exec", "-n", NS, POD, "--", "cat", raw], stdout=f, check=True
        )
    with (OUT / f"{name}.convert.log").open("w") as log:
        subprocess.run(
            [
                "oc",
                "exec",
                "-n",
                NS,
                POD,
                "--",
                "trivy",
                "convert",
                "--format",
                "cyclonedx",
                "--output",
                cdx,
                raw,
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
    with (OUT / f"{name}.cdx.json").open("wb") as f:
        subprocess.run(
            ["oc", "exec", "-n", NS, POD, "--", "cat", cdx], stdout=f, check=True
        )
    report = json.loads((OUT / f"{name}.trivy.json").read_text())
    counts = collections.Counter()
    vulns = collections.Counter()
    examples = []
    for result in report.get("Results", []):
        typ = result.get("Type", "unknown")
        counts[typ] += len(result.get("Packages", []))
        vulns[typ] += len(result.get("Vulnerabilities", []))
        for pkg in result.get("Packages", []):
            if pkg.get("Name", "").lower() in [
                "fastapi",
                "starlette",
                "next",
                "react",
                "langflow",
                "sqlalchemy",
                "postgresql-server",
            ]:
                examples.append(
                    {"name": pkg["Name"], "version": pkg.get("Version"), "type": typ}
                )
    entry = {
        "name": name,
        "image": image,
        "status": "scanned",
        "package_counts": dict(counts),
        "vulnerability_counts": dict(vulns),
        "examples": examples,
        "duration_seconds": round(time.monotonic() - start, 1),
    }
    if report.get("Metadata", {}).get("OS", {}).get("Family") == "centos-stream":
        inventory = f"/work/results/{name}.inventory.cdx.json"
        with (OUT / f"{name}.inventory.log").open("w") as log:
            subprocess.run(
                [
                    "oc",
                    "exec",
                    "-n",
                    NS,
                    POD,
                    "--",
                    "trivy",
                    "image",
                    "--image-src",
                    "remote",
                    "--cache-dir",
                    "/work/cache",
                    "--format",
                    "cyclonedx",
                    "--skip-version-check",
                    "--output",
                    inventory,
                    image,
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
        with (OUT / f"{name}.inventory.cdx.json").open("wb") as f:
            subprocess.run(
                ["oc", "exec", "-n", NS, POD, "--", "cat", inventory],
                stdout=f,
                check=True,
            )
        entry["status"] = "inventory_only_os_unsupported"
        entry["os_family"] = "centos-stream"
        entry["inventory_file"] = name + ".inventory.cdx.json"
    summary.append(entry)
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(entry, ensure_ascii=False), flush=True)
(OUT / "summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
)
if any(
    x["status"] not in ["scanned", "inventory_only_os_unsupported"] for x in summary
):
    raise SystemExit(1)
