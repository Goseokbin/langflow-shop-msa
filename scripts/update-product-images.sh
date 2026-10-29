#!/usr/bin/env bash
set -euo pipefail

# Example: scripts/update-product-images.sh --base-url https://<frontend-route> --apply --check-images
# SHOP_API_TOKEN may provide an existing bearer token when required by the API.
exec python3 "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/catalog_images.py" "$@"
