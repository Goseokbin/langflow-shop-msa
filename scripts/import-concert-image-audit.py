#!/usr/bin/env python3
"""이미지별 SBOM과 CVE를 순차 업로드하고 실제 이미지 연결 결과를 확인한다."""

import argparse
import importlib.util
import json
import pathlib
import time
from concert_image_identity import identity, select_artifact, normalize_sbom

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / ".runtime/image-scans"
spec = importlib.util.spec_from_file_location(
    "concert_audit_api", ROOT / "scripts/concert-audit-api.py"
)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
ap = argparse.ArgumentParser()
ap.add_argument("--authorization-file")
ap.add_argument("--only", nargs="*")
args = ap.parse_args()
c = api.Concert(authorization=args.authorization_file)


def artifacts():
    return c.request(api.APP + "/build_artifacts?page_size=2000")["build_artifacts"]


def counts(art):
    root = api.APP + "/build_artifacts/" + art["id"]
    p = c.request(root + "/packages?page_size=1")["pagination"]["total_count"]
    v = c.request(root + "/cve_findings?page_size=1")["pagination"]["total_count"]
    return p, v


def wait_for(image_name, digest, min_packages=0, min_cves=0):
    deadline = time.monotonic() + 300
    while True:
        a = select_artifact(artifacts(), image_name, digest)
        p, v = counts(a)
        if p >= min_packages and v >= min_cves:
            return a, p, v
        if time.monotonic() > deadline:
            raise RuntimeError(
                f"Ingestion verification timed out for {digest}, wanted packages={min_packages}, cves={min_cves}, observed {p},{v}"
            )
        time.sleep(3)


summary = json.loads((OUT / "summary.json").read_text())
results = (
    json.loads((OUT / "import-summary.json").read_text())
    if (OUT / "import-summary.json").exists()
    else []
)
for entry in summary:
    name = entry["name"]
    if args.only and name not in args.only:
        continue
    if entry["status"] not in ["scanned", "inventory_only_os_unsupported"]:
        raise RuntimeError(name + " scan did not succeed")
    image, digest = identity(entry["image"])
    art = select_artifact(artifacts(), image, digest)
    inventory_only = (
        entry["status"] == "inventory_only_os_unsupported" or name == "postgresql"
    )
    file = OUT / (
        name + ".inventory.cdx.json" if inventory_only else name + ".cdx.json"
    )
    sbom = json.loads(file.read_text())
    expected_pkgs = len(
        {
            x["purl"]
            for x in sbom.get("components", [])
            if x.get("type") != "operating-system" and x.get("purl")
        }
    )
    raw = json.loads((OUT / (name + ".trivy.json")).read_text())
    expected_cves = sum(
        len(x.get("Vulnerabilities", [])) for x in raw.get("Results", [])
    )
    metadata = {
        "image_name": image,
        "component_name": image,
        "component_type": "image",
        "digest": digest,
        "scanner_name": "trivy",
        "application_name": "langflow-shop",
        "application_version": "1.0.0",
    }
    sbom = normalize_sbom(sbom, image, digest)
    normalized_file = OUT / (name + ".canonical.cdx.json")
    normalized_file.write_text(json.dumps(sbom))
    p, v = counts(art)
    if p < expected_pkgs:
        print(f"Uploading {name} package inventory ({expected_pkgs})", flush=True)
        r = c.upload(normalized_file, "package_sbom", metadata)
        (OUT / (name + ".package-import.json")).write_text(json.dumps(r, indent=2))
        c.wait_for_upload(r)
        art, p, v = wait_for(image, digest, min_packages=expected_pkgs)
    if not inventory_only and v < expected_cves:
        print(f"Uploading {name} vulnerabilities ({expected_cves})", flush=True)
        r = c.upload(normalized_file, "image_scan", metadata)
        (OUT / (name + ".image-import.json")).write_text(json.dumps(r, indent=2))
        c.wait_for_upload(r)
        art, p, v = wait_for(image, digest, min_packages=expected_pkgs, min_cves=expected_cves)
    result = {
        "name": name,
        "digest": digest,
        "artifact_id": art["id"],
        "package_count": p,
        "cve_count": v,
        "status": "inventory_only_os_unsupported" if inventory_only else "verified",
    }
    results = [x for x in results if x["name"] != name] + [result]
    (OUT / "import-summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result), flush=True)
print("Sequential import and artifact verification complete.", flush=True)
