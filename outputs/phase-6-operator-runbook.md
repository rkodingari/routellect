# Routellect 0.5.0 Operator Runbook

Status: Gated release candidate; do not publish or expose publicly before G6 approval.

## Build and start

```sh
podman machine start                    # macOS only
podman build --format docker -t localhost/routellect:0.5.0 .
podman volume create routellect-data
podman run --detach --name routellect \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=128m \
  --cap-drop=all --security-opt=no-new-privileges \
  -p 127.0.0.1:8080:8080 -v routellect-data:/data:Z \
  localhost/routellect:0.5.0
curl --fail http://127.0.0.1:8080/health/ready
```

Bind to loopback by default. Put authentication and TLS at a trusted reverse proxy before any shared
network exposure. Routellect needs no provider credentials and must not be given any.

## Normal checks

- `GET /health/live` confirms the process.
- `GET /health/ready` confirms storage and catalog initialization.
- Default write controls are 1 MiB per body and 600 requests/minute/client. Set
  `ROUTELLECT_MAX_REQUEST_BYTES` and `ROUTELLECT_RATE_LIMIT_PER_MINUTE` only after capacity testing.
- A recommendation response must always contain `non_executing: true`.

## Backup and retention

Create backups outside `/data` and then move them to encrypted storage:

```sh
podman exec routellect routellect admin backup /tmp/routellect-backup.tar.gz
podman cp routellect:/tmp/routellect-backup.tar.gz ./routellect-backup.tar.gz
```

Restore into an empty directory or volume and smoke-test it before replacing production data:

```sh
routellect admin restore ./routellect-backup.tar.gz \
  --data-dir ./empty-restore-target --yes
routellect admin purge --older-than-days 90 --yes
```

Retention is never automatic. Review and back up first; `--yes` is deliberately required for purge
and restore.

## Upgrade and rollback

1. Record the running image digest and create a verified backup.
2. Build or pull the new image by immutable digest; verify its SBOM and signature.
3. Stop the old container without deleting its image or volume.
4. Start the new image against a cloned/test volume, check readiness, advice, feedback, and export.
5. Move the production volume only after the smoke test. To roll back, stop the new container and
   start the recorded old digest against the untouched backup/volume.

Do not downgrade the SQLite data in place. Restore the pre-upgrade backup for rollback.

## Verify release evidence

```sh
.venv/bin/python scripts/verify_release_manifest.py
```

For public publication, sign the final registry digest or manifest with Cosign keyless signing and
retain the Sigstore bundle. The included Ed25519 signature is an offline QA signature, not a public
identity attestation.

## Multi-architecture local build

```sh
podman build --platform linux/arm64 -t localhost/routellect:0.5.0-arm64 .
podman build --platform linux/amd64 -t localhost/routellect:0.5.0-amd64 .
podman manifest create localhost/routellect:0.5.0-multiarch \
  localhost/routellect:0.5.0-arm64 localhost/routellect:0.5.0-amd64
podman manifest inspect localhost/routellect:0.5.0-multiarch
```

Use native runners for routine dual-architecture releases. Do not push the manifest before approval.

## Troubleshooting

- Podman connection errors on macOS: run `podman machine start`, then retry.
- Readiness fails: inspect `podman logs routellect`; confirm `/data` is writable by UID/GID 10001.
- Assessor unavailable: advice still falls back deterministically. Confirm the model exists at
  `/opt/routellect/models/assessor.gguf` and matches the release manifest.
- 413 response: reduce request size or deliberately adjust the body limit.
- 429 response: honor `Retry-After`; do not disable throttling to hide abusive load.
- Catalog fallback warning: verify the signed catalog/public key or roll back to the previous signed
  snapshot. The built-in catalog remains available.

## Incident procedure

Stop the container but preserve the volume and image. Record the image digest and incident times,
create a checksummed backup on encrypted storage, and avoid copying prompt content into tickets.
Rotate any host/reverse-proxy/registry credentials that may be affected. Rebuild from pinned inputs,
re-run vulnerability and secret checks, verify the release signature, and restore only into an empty
location after containment.

## Removal

After a verified backup, remove the container. Remove `routellect-data` only when permanent local
data deletion is intended; volume removal is not recoverable unless a backup exists.

References: [Sigstore signing](https://docs.sigstore.dev/cosign/signing/signing_with_blobs/) and
[verification](https://docs.sigstore.dev/cosign/verifying/verify/).
