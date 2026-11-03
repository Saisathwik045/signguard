#!/usr/bin/env bash
# Full OS + language scan, no severity/unfixed/ignore suppression. Host daemon access is trusted CI only.
set -euo pipefail
image_ref="$1"
output_dir="$2"
mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
scanner_ref='aquasec/trivy@sha256:790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c'
ca_mount=()
if [[ -f /etc/ssl/certs/ca-certificates.crt ]]; then
  ca_mount=(-v /etc/ssl/certs/ca-certificates.crt:/run/ca.pem:ro -e SSL_CERT_FILE=/run/ca.pem)
fi
docker run --rm --user "$(id -u):$(id -g)" --group-add "$(stat -c %g /var/run/docker.sock)" \
  --cap-drop=ALL --security-opt=no-new-privileges --memory=6g \
  --tmpfs=/cache:rw,nosuid,size=2g --tmpfs=/tmp:rw,nosuid,size=2g \
  -v /var/run/docker.sock:/var/run/docker.sock:ro -v "$output_dir:/out" "${ca_mount[@]}" \
  --entrypoint /bin/sh "$scanner_ref" -ec '
    trivy image --cache-dir /cache --db-repository ghcr.io/aquasecurity/trivy-db:2 \
      --scanners vuln --list-all-pkgs --ignorefile /dev/null --format json --output /out/full-scan.json "$1"
    trivy --cache-dir /cache --version > /out/scanner-version.txt
  ' scanner "$image_ref"
