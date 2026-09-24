import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from routellect.catalog import CatalogDocument, CatalogManager, canonical_catalog_bytes


def signed_catalog(
    sequence: int = 2, *, expired: bool = False
) -> tuple[dict[str, object], str]:
    raw = json.loads(
        files("routellect").joinpath("data/catalog.json").read_text(encoding="utf-8")
    )
    now = datetime.now(UTC)
    observed_at = now - timedelta(days=2) if expired else now - timedelta(minutes=1)
    expires_at = now - timedelta(days=1) if expired else now + timedelta(days=30)
    raw.update(
        {
            "catalog_version": f"test-catalog-{sequence}",
            "sequence": sequence,
            "observed_at": observed_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
    )
    document = CatalogDocument.model_validate(raw)
    canonical = canonical_catalog_bytes(document)
    private_key = Ed25519PrivateKey.generate()
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    envelope: dict[str, object] = {
        "envelope_version": "1.0",
        "key_id": f"test-key-{sequence}",
        "signed_sha256": hashlib.sha256(canonical).hexdigest(),
        "signed": document.model_dump(mode="json"),
        "signature": base64.b64encode(private_key.sign(canonical)).decode(),
    }
    return envelope, base64.b64encode(public_raw).decode()


def test_signed_catalog_import_persists_and_rolls_back(tmp_path: Path) -> None:
    first, public_key = signed_catalog(2)
    manager = CatalogManager(tmp_path, trusted_keys={"test-key-2": public_key})
    previous, summary = manager.import_envelope(first)
    assert previous.endswith("g2-starter.1")
    assert summary.catalog_version == "test-catalog-2"
    assert summary.signature_verified is True

    second, second_public_key = signed_catalog(3)
    # The signer rotates only through an explicit local trust action.
    manager.import_envelope(
        second, public_key_b64=second_public_key, persist_public_key=True
    )
    replaced, restored = manager.rollback()
    assert replaced == "test-catalog-3"
    assert restored.catalog_version == "test-catalog-2"
    assert CatalogManager(tmp_path, trusted_keys={"test-key-2": public_key}).current().version == (
        "test-catalog-2"
    )


@pytest.mark.parametrize(
    "mutation, error",
    [
        (lambda item: item.update({"signed_sha256": "0" * 64}), "hash"),
        (
            lambda item: item.update(
                {"signature": base64.b64encode(b"0" * 64).decode()}
            ),
            "signature",
        ),
        (
            lambda item: item["signed"].update({"unknown_field": True}),
            "Extra inputs are not permitted",
        ),
        (
            lambda item: item["signed"]["configurations"][0].update(
                {"input_usd_per_million": -1}
            ),
            "greater than or equal to 0",
        ),
        (
            lambda item: item["signed"]["configurations"][0]["evidence"].update(
                {"url": "http://unsafe.example/catalog"}
            ),
            "HTTPS",
        ),
    ],
)
def test_catalog_validation_rejects_unsafe_inputs(
    tmp_path: Path, mutation, error: str  # type: ignore[no-untyped-def]
) -> None:
    envelope, public_key = signed_catalog()
    mutation(envelope)
    with pytest.raises(ValueError, match=error):
        CatalogManager(tmp_path, trusted_keys={"test-key-2": public_key}).import_envelope(
            envelope
        )


def test_catalog_rejects_replay_and_expiry_and_falls_back_offline(tmp_path: Path) -> None:
    envelope, public_key = signed_catalog(2)
    manager = CatalogManager(tmp_path, trusted_keys={"test-key-2": public_key})
    manager.import_envelope(envelope)
    with pytest.raises(ValueError, match="not newer"):
        manager.import_envelope(envelope)

    manager.active_path.write_text("corrupt", encoding="utf-8")
    summary = manager.summary()
    assert summary.source == "builtin"
    assert summary.fallback_reason is not None
    with pytest.raises(ValueError, match="trusted sequence 2"):
        manager.import_envelope(envelope)

    expired, expired_key = signed_catalog(3, expired=True)
    with pytest.raises(ValueError, match="expired"):
        CatalogManager(tmp_path / "expired").import_envelope(
            expired, public_key_b64=expired_key
        )
