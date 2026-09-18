#!/usr/bin/env python3
"""Verify the published G6 QA manifest, signature, public key, and receipt."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def verify(
    manifest_path: Path,
    public_key_path: Path,
    signature_path: Path,
    receipt_path: Path,
) -> dict[str, object]:
    payload = manifest_path.read_bytes()
    signature = base64.b64decode(signature_path.read_text().strip(), validate=True)
    public_key = serialization.load_pem_public_key(public_key_path.read_bytes())
    if not isinstance(public_key, Ed25519PublicKey):
        raise ValueError("release public key is not Ed25519")
    public_key.verify(signature, payload)
    receipt = json.loads(receipt_path.read_text())
    digest = hashlib.sha256(payload).hexdigest()
    if receipt.get("manifest_sha256") != digest:
        raise ValueError("verification receipt does not match the manifest")
    result: dict[str, object] = {
        "signature_verified": True,
        "receipt_matches_manifest": True,
        "manifest_sha256": digest,
        "release": json.loads(payload)["release"],
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("outputs/routellect-0.5.0-release-manifest.json"),
    )
    parser.add_argument(
        "--public-key",
        type=Path,
        default=Path("outputs/routellect-0.5.0-release-public-key.pem"),
    )
    parser.add_argument(
        "--signature",
        type=Path,
        default=Path("outputs/routellect-0.5.0-release-manifest.sig"),
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path("outputs/routellect-0.5.0-signature-verification.json"),
    )
    args = parser.parse_args()
    print(
        json.dumps(
            verify(args.manifest, args.public_key, args.signature, args.receipt),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
