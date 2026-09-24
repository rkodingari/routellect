from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import AnyHttpUrl, Field, field_validator, model_validator

from routellect.schemas import CatalogSummary, StrictModel
from routellect.storage import data_dir


class CatalogEvidence(StrictModel):
    id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    url: AnyHttpUrl
    source_type: Literal[
        "provider_documentation", "public_benchmark", "local_benchmark", "curated_rule"
    ]

    @field_validator("url")
    @classmethod
    def https_only(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme != "https":
            raise ValueError("catalog evidence URLs must use HTTPS")
        return value


class CatalogConfiguration(StrictModel):
    configuration_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,199}$")
    provider: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    deployment: Literal["hosted", "local", "self_hosted"]
    settings: dict[str, Any]
    context_window: int = Field(gt=0, le=20_000_000)
    capabilities: list[str] = Field(min_length=1, max_length=50)
    privacy: list[Literal["standard", "no_training", "local_only"]] = Field(
        min_length=1, max_length=3
    )
    input_usd_per_million: float = Field(ge=0, le=1_000_000)
    output_usd_per_million: float = Field(ge=0, le=1_000_000)
    latency_ms: float = Field(gt=0, le=86_400_000)
    quality: dict[str, float]
    evidence: CatalogEvidence
    prior_uncertainty: float = Field(default=0.2, ge=0, le=1)

    @field_validator("capabilities")
    @classmethod
    def unique_capabilities(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("capabilities must be unique")
        return value

    @field_validator("privacy")
    @classmethod
    def coherent_privacy(
        cls, value: list[Literal["standard", "no_training", "local_only"]]
    ) -> list[Literal["standard", "no_training", "local_only"]]:
        if len(value) != len(set(value)):
            raise ValueError("privacy modes must be unique")
        return value

    @field_validator("quality")
    @classmethod
    def quality_scores(cls, value: dict[str, float]) -> dict[str, float]:
        if "general" not in value:
            raise ValueError("quality must include a general score")
        if not value or any(score < 0 or score > 1 for score in value.values()):
            raise ValueError("quality scores must be between 0 and 1")
        return value


class CatalogDocument(StrictModel):
    spec_version: Literal["1.0"] = "1.0"
    catalog_version: str = Field(min_length=1, max_length=100)
    sequence: int = Field(ge=1)
    observed_at: datetime
    expires_at: datetime
    disclaimer: str = Field(default="", max_length=2_000)
    configurations: list[CatalogConfiguration] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_document(self) -> CatalogDocument:
        if self.observed_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("catalog timestamps must include a timezone")
        if self.expires_at <= self.observed_at:
            raise ValueError("catalog expires_at must be after observed_at")
        identifiers = [item.configuration_id for item in self.configurations]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("catalog configuration IDs must be unique")
        return self


class SignedCatalogEnvelope(StrictModel):
    envelope_version: Literal["1.0"] = "1.0"
    key_id: str = Field(min_length=1, max_length=100)
    signed_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    signed: CatalogDocument
    signature: str = Field(min_length=80, max_length=120)


def canonical_catalog_bytes(document: CatalogDocument) -> bytes:
    return json.dumps(
        document.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


@dataclass(frozen=True)
class Catalog:
    version: str
    sequence: int
    observed_at: datetime
    expires_at: datetime
    disclaimer: str
    configurations: tuple[dict[str, Any], ...]

    @classmethod
    def from_document(cls, document: CatalogDocument) -> Catalog:
        return cls(
            version=document.catalog_version,
            sequence=document.sequence,
            observed_at=document.observed_at,
            expires_at=document.expires_at,
            disclaimer=document.disclaimer,
            configurations=tuple(
                item.model_dump(mode="json") for item in document.configurations
            ),
        )

    @classmethod
    def load_builtin(cls) -> Catalog:
        resource = files("routellect").joinpath("data/catalog.json")
        document = CatalogDocument.model_validate_json(resource.read_text(encoding="utf-8"))
        return cls.from_document(document)

    @property
    def freshness_status(self) -> Literal["fresh", "aging", "stale"]:
        now = datetime.now(UTC)
        if now >= self.expires_at:
            return "stale"
        lifetime = (self.expires_at - self.observed_at).total_seconds()
        age = (now - self.observed_at).total_seconds()
        return "aging" if lifetime > 0 and age / lifetime >= 0.7 else "fresh"

    def summary(
        self,
        *,
        source: Literal["builtin", "signed_import"] = "builtin",
        signature_verified: bool = False,
        fallback_reason: str | None = None,
    ) -> CatalogSummary:
        return CatalogSummary(
            catalog_version=self.version,
            observed_at=self.observed_at,
            expires_at=self.expires_at,
            providers=sorted({str(item["provider"]) for item in self.configurations}),
            configuration_count=len(self.configurations),
            freshness_status=self.freshness_status,
            sequence=self.sequence,
            source=source,
            signature_verified=signature_verified,
            fallback_reason=fallback_reason,
        )


BUILTIN_CATALOG = Catalog.load_builtin()


class CatalogManager:
    """Verify and activate catalog snapshots without any network access."""

    def __init__(
        self,
        directory: Path | None = None,
        trusted_keys: dict[str, str] | None = None,
    ) -> None:
        self.directory = directory or data_dir() / "catalogs"
        self.active_path = self.directory / "active.envelope.json"
        self.previous_path = self.directory / "previous.envelope.json"
        self.keys_path = self.directory / "trusted-public-keys.json"
        self.state_path = self.directory / "catalog-state.json"
        self.directory.mkdir(parents=True, exist_ok=True)
        self._explicit_keys = trusted_keys or {}
        self._fallback_reason: str | None = None

    def _trusted_keys(self) -> dict[str, str]:
        keys: dict[str, str] = {}
        if self.keys_path.exists():
            parsed = json.loads(self.keys_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                keys.update({str(key): str(value) for key, value in parsed.items()})
        configured = os.getenv("ROUTELLECT_CATALOG_PUBLIC_KEYS", "")
        if configured:
            parsed = json.loads(configured)
            if not isinstance(parsed, dict) or not all(
                isinstance(key, str) and isinstance(value, str) for key, value in parsed.items()
            ):
                raise ValueError("ROUTELLECT_CATALOG_PUBLIC_KEYS must be a JSON string map")
            keys.update(parsed)
        keys.update(self._explicit_keys)
        return keys

    def trust_public_key(self, key_id: str, public_key_b64: str) -> None:
        self._decode_public_key(public_key_b64)
        existing = self._trusted_keys().get(key_id)
        if existing is not None and existing != public_key_b64:
            raise ValueError("a different public key already uses this key_id")
        keys: dict[str, str] = {}
        if self.keys_path.exists():
            loaded = json.loads(self.keys_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                keys = {str(key): str(value) for key, value in loaded.items()}
        keys[key_id] = public_key_b64
        self._atomic_json(self.keys_path, keys)

    def current(self) -> Catalog:
        self._fallback_reason = None
        if not self.active_path.exists():
            return BUILTIN_CATALOG
        try:
            envelope = self._load_envelope(self.active_path)
            self._verify(envelope, allow_expired=True)
            return Catalog.from_document(envelope.signed)
        except (ValueError, OSError) as exc:
            self._fallback_reason = f"Signed catalog unavailable: {exc}. Using builtin snapshot."
            return BUILTIN_CATALOG

    def summary(self) -> CatalogSummary:
        catalog = self.current()
        imported = catalog is not BUILTIN_CATALOG
        return catalog.summary(
            source="signed_import" if imported else "builtin",
            signature_verified=imported,
            fallback_reason=self._fallback_reason,
        )

    def import_envelope(
        self,
        payload: dict[str, Any],
        *,
        public_key_b64: str | None = None,
        persist_public_key: bool = False,
    ) -> tuple[str, CatalogSummary]:
        envelope = SignedCatalogEnvelope.model_validate(payload)
        if public_key_b64 is not None:
            self._verify(envelope, override_public_key=public_key_b64)
        else:
            self._verify(envelope)
        current = self.current()
        trusted_sequence = max(current.sequence, self._high_water_sequence())
        if envelope.signed.sequence <= trusted_sequence:
            raise ValueError(
                f"catalog sequence {envelope.signed.sequence} is not newer than "
                f"trusted sequence {trusted_sequence}"
            )
        now = datetime.now(UTC)
        if envelope.signed.observed_at > now + timedelta(hours=24):
            raise ValueError("catalog observed_at is unreasonably far in the future")
        if envelope.signed.expires_at <= now:
            raise ValueError("catalog is already expired")
        if persist_public_key and public_key_b64 is not None:
            self.trust_public_key(envelope.key_id, public_key_b64)
        if self.active_path.exists():
            self._atomic_bytes(self.previous_path, self.active_path.read_bytes())
        elif self.previous_path.exists():
            self.previous_path.unlink()
        self._atomic_json(self.active_path, envelope.model_dump(mode="json"))
        self._atomic_json(
            self.state_path, {"highest_verified_sequence": envelope.signed.sequence}
        )
        activated = Catalog.from_document(envelope.signed)
        return current.version, activated.summary(
            source="signed_import", signature_verified=True
        )

    def rollback(self) -> tuple[str, CatalogSummary]:
        current = self.current()
        if current is BUILTIN_CATALOG:
            raise ValueError("no signed catalog is active")
        replaced_version = current.version
        if self.previous_path.exists():
            previous_bytes = self.previous_path.read_bytes()
            previous = SignedCatalogEnvelope.model_validate_json(previous_bytes)
            self._verify(previous, allow_expired=True)
            current_bytes = self.active_path.read_bytes()
            self._atomic_bytes(self.active_path, previous_bytes)
            self._atomic_bytes(self.previous_path, current_bytes)
            catalog = Catalog.from_document(previous.signed)
            return replaced_version, catalog.summary(
                source="signed_import", signature_verified=True
            )
        self.active_path.unlink()
        return replaced_version, BUILTIN_CATALOG.summary()

    def _load_envelope(self, path: Path) -> SignedCatalogEnvelope:
        return SignedCatalogEnvelope.model_validate_json(path.read_text(encoding="utf-8"))

    def _high_water_sequence(self) -> int:
        if not self.state_path.exists():
            return BUILTIN_CATALOG.sequence
        loaded = json.loads(self.state_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("catalog state is invalid")
        sequence = loaded.get("highest_verified_sequence")
        if not isinstance(sequence, int) or sequence < BUILTIN_CATALOG.sequence:
            raise ValueError("catalog trusted sequence is invalid")
        return sequence

    def _verify(
        self,
        envelope: SignedCatalogEnvelope,
        *,
        override_public_key: str | None = None,
        allow_expired: bool = False,
    ) -> None:
        canonical = canonical_catalog_bytes(envelope.signed)
        digest = hashlib.sha256(canonical).hexdigest()
        if digest != envelope.signed_sha256:
            raise ValueError("catalog hash does not match signed content")
        public_key_b64 = override_public_key or self._trusted_keys().get(envelope.key_id)
        if public_key_b64 is None:
            raise ValueError(f"catalog key is not trusted: {envelope.key_id}")
        public_key = self._decode_public_key(public_key_b64)
        try:
            signature = base64.b64decode(envelope.signature, validate=True)
            public_key.verify(signature, canonical)
        except (InvalidSignature, ValueError) as exc:
            raise ValueError("catalog signature verification failed") from exc
        if not allow_expired and envelope.signed.expires_at <= datetime.now(UTC):
            raise ValueError("catalog is already expired")

    @staticmethod
    def _decode_public_key(value: str) -> Ed25519PublicKey:
        try:
            raw = base64.b64decode(value, validate=True)
            if len(raw) != 32:
                raise ValueError("Ed25519 public keys must be 32 bytes")
            return Ed25519PublicKey.from_public_bytes(raw)
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid base64 Ed25519 public key") from exc

    def _atomic_json(self, path: Path, value: object) -> None:
        encoded = json.dumps(value, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        self._atomic_bytes(path, encoded)

    @staticmethod
    def _atomic_bytes(path: Path, value: bytes) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(value)
        os.replace(temporary, path)
