#!/usr/bin/env python3
"""Concert 스캔 감사 API. 인증정보는 로컬 파일에서만 읽고 출력하지 않는다."""

import argparse
import json
import pathlib
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
HOST = os.environ["CONCERT_HOST"]
APP = os.environ["CONCERT_APP_API"]


class Concert:
    def __init__(self, session=None, authorization=None):
        self.headers = {
            "Accept": "application/json",
            "InstanceID": "0000-0000-0000-0000",
        }
        if authorization:
            self.headers["Authorization"] = (
                pathlib.Path(authorization).read_text().strip()
            )
        else:
            state = json.loads(
                pathlib.Path(
                    session or ROOT / ".runtime/concert-browser-state.json"
                ).read_text()
            )
            self.headers["Cookie"] = "; ".join(
                c["name"] + "=" + c["value"]
                for c in state["cookies"]
                if HOST.endswith(c["domain"].lstrip("."))
            )

    def request(self, path, data=None, method=None, content_type=None):
        headers = dict(self.headers)
        if content_type:
            headers["Content-Type"] = content_type
        try:
            with urllib.request.urlopen(
                urllib.request.Request(
                    "https://" + HOST + path, data=data, headers=headers, method=method
                ),
                timeout=180,
            ) as r:
                body = r.read()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            raise RuntimeError(
                f"HTTP {e.code} {path}: {e.read().decode()[:1200]}"
            ) from None

    def wait_for_upload(self, response, timeout=600):
        """Wait for ingestion completion, not just a 202 or pre-existing counts."""
        for event in response.get("event_ids", []):
            deadline = time.monotonic() + timeout
            while True:
                query = {"filters": {"logic": "and", "conditions": [
                    {"field": "event_id", "value": event, "operator": "="}]},
                    "pagination": {"page": 1, "page_size": 50}}
                records = self.request(
                    "/concert/ingestion/api/v1/table_of_contents/lz/advanced_search",
                    json.dumps(query).encode(), "POST", "application/json"
                ).get("toc_records", [])
                if records:
                    record = records[0]
                    status = record.get("status", "")
                    if status == "processing_completed":
                        break
                    if status.startswith("error"):
                        raise RuntimeError(f"Ingestion {event}: {record.get('additional_details', status)}")
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"Ingestion {event} did not complete within {timeout}s")
                time.sleep(3)

    def snapshot(self):
        arts = self.request(APP + "/build_artifacts?page_size=2000")["build_artifacts"]
        result = []
        for a in arts:
            p = self.request(
                APP + "/build_artifacts/" + a["id"] + "/packages?page_size=2000"
            )
            v = self.request(
                APP + "/build_artifacts/" + a["id"] + "/cve_findings?page_size=1"
            )
            result.append(
                {
                    "name": a["name"],
                    "id": a["id"],
                    "digest": a["digest"],
                    "package_count": p["pagination"]["total_count"],
                    "cve_count": v["pagination"]["total_count"],
                    "packages": [
                        {
                            "name": x["name"],
                            "version": x["version"],
                            "registry": x.get("registry"),
                        }
                        for x in p.get("packages", [])
                    ],
                }
            )
        return result

    def upload(self, path, datatype, metadata):
        path = pathlib.Path(path)
        if datatype == "package_sbom" and metadata.get("repo_url"):
            doc = json.loads(path.read_text())
            if doc.get("bomFormat") != "CycloneDX" or not metadata.get("repo_name"):
                raise ValueError("Repository ingestion requires CycloneDX and repo_name")
            if metadata.get("image_name") or metadata.get("digest"):
                raise ValueError("Do not mix repository and image identities")
            if doc.get("metadata", {}).get("component", {}).get("name") != metadata["repo_name"]:
                raise ValueError("Source SBOM root must match repo_name")
        elif datatype in ("package_sbom", "image_scan"):
            from concert_image_identity import identity
            image, digest = identity(metadata["image_name"], metadata["digest"])
            doc = json.loads(path.read_text())
            if doc.get("bomFormat") != "CycloneDX":
                raise ValueError("Use a normalized CycloneDX report, not raw Trivy JSON")
            if doc.get("metadata", {}).get("component", {}).get("name") != image + "@" + digest:
                raise ValueError("SBOM image and upload metadata must have the same canonical identity")
            metadata = dict(metadata, image_name=image, component_name=image, component_type="image", digest=digest)
        # A scan is replayable after interruption. Concert rejects the same CDX
        # serialNumber/version pair even when a previous request partially completed.
        # Document identity is distinct from package/image/repository identity.
        payload = path.read_bytes()
        document = json.loads(payload)
        submitted_serial = None
        if document.get("bomFormat") == "CycloneDX":
            submitted_serial = "urn:uuid:" + str(uuid.uuid4())
            document["serialNumber"] = submitted_serial
            payload = json.dumps(document).encode()
        boundary = "concert-audit-" + uuid.uuid4().hex
        parts = []
        for k, v in [("data_type", datatype), ("metadata", json.dumps(metadata))]:
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
            )
        parts += [
            f'--{boundary}\r\nContent-Disposition: form-data; name="filename"; filename="{path.name}"\r\nContent-Type: application/json\r\n\r\n'.encode(),
            payload,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
        response = self.request(
            "/concert/ingestion/api/v1/upload_files",
            b"".join(parts),
            "POST",
            "multipart/form-data; boundary=" + boundary,
        )
        if submitted_serial:
            response["submitted_sbom_serial_number"] = submitted_serial
        return response


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["snapshot", "upload"])
    ap.add_argument("--file")
    ap.add_argument("--data-type", default="package_sbom")
    ap.add_argument("--image-name")
    ap.add_argument("--digest")
    ap.add_argument("--authorization-file")
    ap.add_argument("--output")
    args = ap.parse_args()
    c = Concert(authorization=args.authorization_file)
    if args.action == "snapshot":
        result = c.snapshot()
    else:
        result = c.upload(
            args.file,
            args.data_type,
            {
                "image_name": args.image_name,
                "digest": args.digest,
                "scanner_name": "trivy",
                "application_name": "langflow-shop",
                "application_version": "1.0.0",
            },
        )
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        pathlib.Path(args.output).write_text(text + "\n")
    else:
        print(text)
