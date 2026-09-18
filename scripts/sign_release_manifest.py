#!/usr/bin/env python3
"""Sign and independently verify a release manifest with an offline Ed25519 QA key."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def sign_and_verify(
    manifest_path: Path,
    key_path: Path,
    public_key_path: Path,
    signature_path: Path,
    receipt_path: Path,
) -> dict[str, object]:
    payload = manifest_path.read_bytes()
    if key_path.exists():
        private_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        if not isinstance(private_key, Ed25519PrivateKey):
            raise ValueError("QA signing key is not Ed25519")
    else:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        private_key = Ed25519PrivateKey.generate()
        key_path.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    os.chmod(key_path, 0o600)
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    signature = private_key.sign(payload)
    public_key.verify(signature, payload)
    tamper_rejected = False
    try:
        public_key.verify(signature, payload + b"tampered")
    except InvalidSignature:
        tamper_rejected = True
    if not tamper_rejected:
        raise RuntimeError("signature verification did not reject a modified manifest")

    public_key_path.parent.mkdir(parents=True, exist_ok=True)
    public_key_path.write_bytes(public_pem)
    signature_path.write_text(base64.b64encode(signature).decode() + "\n")
    public_der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    receipt: dict[str, object] = {
        "schema": "routellect-release-signature-receipt-v1",
        "verified_at": datetime.now(UTC).isoformat(),
        "algorithm": "Ed25519",
        "purpose": "offline G6 QA release-manifest signature",
        "production_signing": False,
        "manifest": str(manifest_path),
        "manifest_sha256": hashlib.sha256(payload).hexdigest(),
        "public_key": str(public_key_path),
        "public_key_sha256": hashlib.sha256(public_der).hexdigest(),
        "signature": str(signature_path),
        "signature_verified": True,
        "tamper_test_rejected": tamper_rejected,
        "private_key_location": str(key_path),
        "private_key_in_deliverables": False,
        "publication_note": (
            "For publication, sign the final registry digest or this manifest with Cosign "
            "keyless sign-blob and retain the Sigstore bundle."
        ),
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("outputs/routellect-0.5.0-release-manifest.json"),
    )
    parser.add_argument(
        "--key", type=Path, default=Path("work/g6-release-qa-ed25519-private.pem")
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
    receipt = sign_and_verify(
        args.manifest, args.key, args.public_key, args.signature, args.receipt
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
