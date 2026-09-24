# Routellect Phase 3 Verification Report

Status: Complete; awaiting sponsor decision at G3  
Date: 2026-09-15  
Candidate version: `0.2.0`

## Outcome

G3 delivers a signed offline catalog lifecycle and a private, replay-gated feedback loop without
changing Routellect's advisory-only boundary. No recommended model is called, no provider credential
is accepted, no prompt is retained, and ranking personalization remains off by default.

## Research-informed design

The catalog uses Ed25519 verify-or-reject behavior, following the Python Cryptographic Authority's
[Ed25519 guidance](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/). The
dependency is pinned to `cryptography==50.0.1`, the current verified PyPI release at implementation
time ([PyPI project](https://pypi.org/project/cryptography/)).

The import sequence and expiry rules adapt the Update Framework's defenses: clients do not replace
trusted metadata with an older version and do not activate expired metadata
([TUF specification](https://theupdateframework.github.io/specification/v1.0.26/)). Routellect does
not add a network updater or claim full TUF compliance; it applies those narrow principles to local
catalog files.

The resulting design is intentionally small:

- strict catalog document + signed envelope;
- SHA-256 content check followed by Ed25519 verification;
- explicitly trusted public keys only, with key-ID collision rejection;
- monotonic sequence, timezone, observed/expiry, nonnegative estimate, and HTTPS evidence checks;
- atomic active/previous snapshots, monotonic high-water sequence, one-step rollback, and builtin
  offline fallback;
- structured local feedback only, with no prompt or free-text field;
- profile-scoped Beta-Binomial adjustment, five-outcome support floor, and ±0.04 score cap;
- chronological replay with a 0.005 Brier non-regression tolerance before manual promotion.

## Automated verification

Final local verification:

| Check | Result |
|---|---:|
| Python tests | 29 passed |
| Python coverage | 85% overall |
| Ruff lint | Passed |
| TypeScript project build/typecheck | Passed |
| Vite production build | Passed |
| Target-provider calls in benchmark | 0 |
| Raw prompts persisted in benchmark | 0 |

The test suite now directly covers:

- valid signed import, persisted trust, key rotation by distinct key ID, and rollback;
- hash mismatch, bad signature, unknown fields, negative price, unsafe HTTP URL, replayed sequence,
  expiry, corrupt-active fallback, and duplicate/invalid catalog values;
- G2 SQLite schema migration with legacy receipt preservation;
- feedback receipt validation, opt-out, export, item deletion, full reset, and prompt canary absence;
- profile isolation, sparse-support suppression, Bayesian shrinkage, and bounded negative influence;
- insufficient-data promotion refusal and chronological non-regression promotion;
- API parity for settings, export, deletion, and manual promotion controls.

## Benchmark evidence

### Deterministic software fixture

Seven frozen task-family fixtures produced 100% task-family classification on this verification run,
with 0.191 ms mean and 0.847 ms p95 advisory latency on the host. This is a software regression
fixture, not an external model-routing benchmark.

### Feedback replay fixture

A chronological synthetic fixture with ten successful comparable outcomes used the first eight for
training and the last two for holdout. The global-prior Brier score was 0.01235 and the bounded
task/model posterior scored 0.00381, so manual promotion was allowed. Four outcomes produced exactly
zero adjustment. Twenty adverse outcomes hit, but did not exceed, the −0.04 bound. Profile-B data had
no effect on Profile A.

These fixtures prove the safety mechanics and non-regression gate. They do not establish that
feedback improves real-world routing; that claim remains reserved for G5's preregistered external
evaluation.

## Rootless Podman verification

The final Docker-format image was built with rootless Podman 6.1.0 on ARM64:

- image: `localhost/routellect:0.2.0`;
- image ID: `0e46c655d1eac2dd755792990f0dee4bf1840065c445e084d54d0812121ae6e0`;
- digest: `sha256:ea568110ced7879830fc23c0b1b2c840fd0019e2df28ff5b5ff662075cab0f29`;
- size: 695,299,757 bytes;
- runtime user: `10001:10001`;
- root filesystem: read-only;
- capabilities: all default capabilities dropped;
- `no-new-privileges`: enabled;
- declared health check: healthy after startup;
- one named `/data` volume and one temporary `/tmp` mount.

The upgrade test first ran retained image `0.1.0`, created synthetic receipt
`rec_e6df3b77daef40d9a64e85bf35bb0796` and feedback
`fb_b6597ece50bf454ebae31996a342d279`, then mounted the same volume into `0.2.0`. The receipt/feedback
survived migration; feedback settings were added with personalization off. Two ephemeral signed
catalogs were activated, rollback restored `container-test-2`, and a fresh G3 container restart
preserved both that verified catalog and the original feedback item.

All temporary verification containers and the `routellect-g3-upgrade-verify` volume were removed.
The final `0.2.0` image and prior `0.1.0` image remain available locally. The Podman VM is stopped.

## Privacy and security review

- Prompts remain memory-only; database and export canaries contain no prompt bytes.
- Feedback contains identifiers, derived task/difficulty, structured outcomes, optional numeric
  observations, and no free text.
- Feedback cannot bypass privacy/capability/context/budget/latency/quality eligibility because it is
  added only after hard filtering.
- Sparse data cannot influence scores, and supported feedback cannot add more than ±0.04.
- An API caller cannot submit a new trust key; keys come from local CLI trust or operator-provided
  environment configuration.
- Private signing keys are neither accepted nor stored. Runtime advice/catalog use causes no network
  access.
- Corrupt imported state falls back to the visible builtin snapshot; failed imports do not replace
  the active catalog.

## Known limits and recorded deferrals

- Personalization is supported but remains off until each profile passes replay and a person requests
  promotion.
- G3 does not recalibrate the local assessor trigger or confidence features; there was no evidence to
  promote such a change.
- The current envelope supports one trusted Ed25519 signer per update, not TUF threshold signing or
  delegated roles.
- The starter catalog remains dated prior evidence, not a universal leaderboard.
- Real outcome-level routing benchmarks, statistical confidence intervals, and superiority claims
  remain G5 work.
- Full dashboard comparison/history polish and accessibility/visual-regression testing remain G4.
- AMD64 execution, SBOM, image signing, and release vulnerability scanning remain G6.

## Reproduction

```sh
.venv/bin/ruff check src tests
.venv/bin/pytest --cov=routellect --cov-report=term-missing
cd frontend && pnpm build && cd ..
podman build --format docker -t routellect:0.2.0 .
podman volume create routellect-data
podman run --rm --name routellect \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=128m \
  --cap-drop=all --security-opt=no-new-privileges \
  -p 8080:8080 -v routellect-data:/data:Z \
  routellect:0.2.0
```

## Traceability

- Architecture decision: `docs/adr/0002-signed-catalog-and-bounded-feedback.md`
- Catalog implementation: `src/routellect/catalog.py`
- Feedback persistence/control: `src/routellect/storage.py`
- Conservative learning/replay: `src/routellect/learning.py`
- API and dashboard: `src/routellect/api.py`, `frontend/src/App.tsx`
- Verification: `tests/test_catalog.py`, `tests/test_feedback.py`, `tests/test_api.py`
