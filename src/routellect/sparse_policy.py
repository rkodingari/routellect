"""Dependency-free inference for the frozen G7 sparse prompt-strength artifact."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from routellect.profiler import deterministic_profile_v3
from routellect.schemas import AssessorMode

ARTIFACT_PATH = Path(__file__).with_name("data") / "g7_sparse_strength.json"
TOKEN_PATTERN = re.compile(r"[^\W_]+(?:['’-][^\W_]+)?", re.UNICODE)


def _bucket(name: str, dimensions: int, seed: str) -> tuple[int, float]:
    digest = hashlib.blake2b(f"{seed}|{name}".encode(), digest_size=8).digest()
    value = int.from_bytes(digest, "big")
    return value % dimensions, 1.0 if value & (1 << 63) else -1.0


def hashed_features(
    text: str,
    dimensions: int,
    seed: str,
    *,
    include_profile: bool = True,
) -> dict[int, float]:
    """Create a stable, normalized sparse feature vector without retaining prompt text."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    tokens = TOKEN_PATTERN.findall(normalized)[:2_000]
    names = {f"w:{token}" for token in tokens}
    names.update(f"b:{left}_{right}" for left, right in zip(tokens, tokens[1:], strict=False))
    length = len(normalized)
    names.add(f"chars:{min(12, int(math.log2(max(1, length))))}")
    names.add(f"words:{min(10, int(math.log2(max(1, len(tokens)))))}")
    if re.search(r"\d", normalized):
        names.add("shape:digit")
    if re.search(r"[=+*/^<>]", normalized):
        names.add("shape:math")
    if "```" in normalized:
        names.add("shape:fence")
    if any(ord(character) > 127 for character in normalized):
        names.add("shape:unicode")
    if include_profile:
        profile = deterministic_profile_v3(text, AssessorMode.OFF)
        names.add(f"task:{profile.task_family}")
        names.add(f"difficulty:{profile.difficulty}")
        for capability in profile.required_capabilities:
            names.add(f"capability:{capability}")

    features: dict[int, float] = {}
    for name in names:
        index, sign = _bucket(name, dimensions, seed)
        features[index] = features.get(index, 0.0) + sign
    norm = math.sqrt(sum(value * value for value in features.values())) or 1.0
    return {index: features[index] / norm for index in sorted(features)}


@dataclass(frozen=True)
class SparseStrengthPrediction:
    recommended_model: str
    strength: str
    confidence: float
    predicted_correctness: dict[str, float]
    predicted_utility: dict[str, float]


class SparseStrengthModel:
    def __init__(self, artifact: dict[str, object]) -> None:
        if artifact.get("schema_version") != "routellect-sparse-strength-v1":
            raise ValueError("unsupported sparse strength artifact")
        self.artifact = artifact
        self.dimensions = int(artifact["dimensions"])
        self.seed = str(artifact["hash_seed"])
        self.cost_weight = float(artifact["cost_weight"])
        self.include_profile = bool(artifact["include_profile_features"])
        self.models = tuple(str(item) for item in artifact["models"])  # type: ignore[arg-type]
        self.intercepts = {
            str(key): float(value)
            for key, value in artifact["intercepts"].items()  # type: ignore[union-attr]
        }
        self.mean_compute = {
            str(key): float(value)
            for key, value in artifact["mean_normalized_compute"].items()  # type: ignore[union-attr]
        }
        self.weights = {
            str(model): {int(index): float(value) for index, value in values.items()}
            for model, values in artifact["weights"].items()  # type: ignore[union-attr]
        }
        self.parameter_billions = {
            str(key): float(value)
            for key, value in artifact["parameter_billions"].items()  # type: ignore[union-attr]
        }

    def predict(self, text: str) -> SparseStrengthPrediction:
        features = hashed_features(
            text,
            self.dimensions,
            self.seed,
            include_profile=self.include_profile,
        )
        correctness: dict[str, float] = {}
        utilities: dict[str, float] = {}
        for model in self.models:
            value = self.intercepts[model] + sum(
                self.weights[model].get(index, 0.0) * feature
                for index, feature in features.items()
            )
            correctness[model] = min(1.0, max(0.0, value))
            utilities[model] = correctness[model] - self.cost_weight * self.mean_compute[model]
        ranked = sorted(
            self.models,
            key=lambda model: (-utilities[model], self.parameter_billions[model], model),
        )
        margin = utilities[ranked[0]] - utilities[ranked[1]]
        size = self.parameter_billions[ranked[0]]
        if size >= 50:
            strength = "high"
        elif size >= 5:
            strength = "medium"
        else:
            strength = "low"
        confidence = min(0.95, max(0.35, 0.50 + margin * 1.5))
        return SparseStrengthPrediction(
            recommended_model=ranked[0],
            strength=strength,
            confidence=confidence,
            predicted_correctness=correctness,
            predicted_utility=utilities,
        )


class MultiSourceStrengthModel:
    """Experimental G7-C2 strong-tier gate plus the G7 lower-tier predictor."""

    def __init__(self, artifact: dict[str, object]) -> None:
        if artifact.get("schema_version") != "routellect-multisource-strength-v1":
            raise ValueError("unsupported multi-source strength artifact")
        self.dimensions = int(artifact["dimensions"])
        self.seed = str(artifact["hash_seed"])
        self.threshold = float(artifact["strong_threshold"])
        self.intercept = float(artifact["strong_intercept"])
        self.weights = {
            int(index): float(value)
            for index, value in artifact["strong_weights"].items()  # type: ignore[union-attr]
        }
        self.strong_model = str(artifact["strong_model"])
        self.lower_tier = SparseStrengthModel(artifact["lower_tier_model"])  # type: ignore[arg-type]

    def strong_probability(self, text: str) -> float:
        features = hashed_features(
            text, self.dimensions, self.seed, include_profile=True
        )
        value = self.intercept + sum(
            self.weights.get(index, 0.0) * feature
            for index, feature in features.items()
        )
        value = max(-20.0, min(20.0, value))
        return 1 / (1 + math.exp(-value))

    def choose(self, text: str) -> str:
        if self.strong_probability(text) >= self.threshold:
            return self.strong_model
        prediction = self.lower_tier.predict(text)
        candidates = [
            model for model in prediction.predicted_utility if model != self.strong_model
        ]
        return min(
            candidates,
            key=lambda model: (
                -prediction.predicted_utility[model],
                self.lower_tier.parameter_billions[model],
                model,
            ),
        )


@lru_cache(maxsize=1)
def load_sparse_strength_model(path: Path = ARTIFACT_PATH) -> SparseStrengthModel | None:
    if not path.exists():
        return None
    return SparseStrengthModel(json.loads(path.read_text()))
