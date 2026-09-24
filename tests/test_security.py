import importlib.util
from pathlib import Path
from types import ModuleType

from routellect.security import TokenBucketLimiter


def _load_secret_scanner() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "scan_secrets.py"
    spec = importlib.util.spec_from_file_location("scan_secrets", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load secret scanner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SECRET_SCANNER = _load_secret_scanner()


def test_token_bucket_limits_and_refills() -> None:
    now = [100.0]
    limiter = TokenBucketLimiter(2, clock=lambda: now[0])
    assert limiter.allow("client") == (True, 0)
    assert limiter.allow("client") == (True, 0)
    allowed, retry_after = limiter.allow("client")
    assert allowed is False
    assert retry_after == 30
    assert limiter.allow("other") == (True, 0)

    now[0] += 30
    assert limiter.allow("client") == (True, 0)
    limiter.reset()
    assert limiter.allow("client") == (True, 0)


def test_token_bucket_rejects_invalid_capacity() -> None:
    try:
        TokenBucketLimiter(0)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("invalid capacity should fail")


def test_secret_scanner_allows_only_exact_synthetic_canaries(tmp_path: Path) -> None:
    canary = tmp_path / "src/routellect/data/deterministic_invariants.json"
    canary.parent.mkdir(parents=True)
    synthetic_key = "AKIA" + "ABCDEFGHIJKLMNOP"
    canary.write_text(f'{{"prompt":"Synthetic AWS key {synthetic_key}"}}\n')
    safe = SECRET_SCANNER.scan(tmp_path)
    assert safe["finding_count"] == 0
    assert safe["acknowledged_synthetic_canary_count"] == 1

    unrecognized_key = "AKIA" + "0000000000000000"
    canary.write_text(f'{{"prompt":"{unrecognized_key}"}}\n')
    unsafe = SECRET_SCANNER.scan(tmp_path)
    assert unsafe["finding_count"] == 1
