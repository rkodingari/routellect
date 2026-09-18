# Routellect G2 Verification Report

Status: **Release candidate verified; awaiting G2 sponsor decision**  
Date: 2026-09-15  
Version: `0.1.0`  
Tagline: **Know the right model before you run.**

## Outcome

Routellect is a working advisory-only MVP. It accepts a prompt and user constraints, profiles the
task, filters ineligible model configurations, and returns a ranked recommendation plus useful
alternatives with quality, request-cost, and latency ranges. It never invokes a recommended model.

The MVP includes a responsive single-screen web dashboard, CLI, typed HTTP API, dated offline model
catalog, content-free receipts, structured feedback capture, benchmark endpoint, and a hardened
Podman image. The hybrid local assessor is available but defaults to Off until a larger evaluation
supports promotion.

## Verified product boundary

- No provider SDK, target-model adapter, inference proxy, provider credential field, budget
  reservation, or automatic spend.
- API responses set `non_executing: true`.
- The final hybrid/privacy acceptance flow ran in a container with `network=none`.
- A persisted database canary did not contain the submitted prompt.
- Receipt-table inspection found no API-key or credential column.
- Feedback responses state `prompt_stored: false`; feedback is structured and contains no free text.

## Automated verification

| Check | Result |
|---|---:|
| Python tests | 17 passed |
| Python coverage | 85.12% |
| Ruff lint | Passed |
| Frontend TypeScript check | Passed |
| Frontend production build | Passed in 593 ms |
| Production JavaScript | 227.09 kB; 71.20 kB gzip |
| Production CSS | 7.26 kB; 2.48 kB gzip |
| CLI/direct-advisor parity | Passed |
| OpenAPI JSON parse | Passed |

## Deterministic benchmark

The built-in G2 software-verification set contains seven frozen, balanced task-family fixtures. It
tests the deterministic path and makes no target-model calls.

| Metric | Result |
|---|---:|
| Task-family accuracy | 7/7 (100%) |
| Advisor mean latency | 0.095 ms |
| Advisor p95 latency | 0.253 ms |
| Target-provider calls | 0 |
| Raw prompts persisted | 0 |

This is a software fixture set, not an external model-quality leaderboard. It supports correctness
and regression claims only.

## Local assessor bake-off

### Rejected designs

1. SmolLM2-360M free-form/constrained generation over-predicted `reasoning` and achieved only 2/7
   on an exploratory paraphrase set. A narrower generated schema still produced invalid confidence
   values. Generated classification was rejected.
2. The official Qwen3-0.6B GGUF candidate is Apache-2.0 and 639 MB, but the development network
   substituted a corporate block page for the Xet-hosted artifact. Both attempted downloads were
   rejected by SHA-256 validation, so the candidate was not benchmarked or bundled. See the
   [official Qwen artifact](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/blob/main/Qwen3-0.6B-Q8_0.gguf).

### Selected G2 candidate

The bundled, Apache-2.0
[SmolLM2-360M Q8 GGUF](https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct-GGUF/blob/main/smollm2-360m-instruct-q8_0.gguf)
is pinned to SHA-256 `48ab3034d0dd401fbc721eb1df3217902fee7dab9078992d66431f09b7750201`.
Routellect uses it as a deterministic semantic-embedding signal against versioned task prototypes;
it does not generate a classification, see catalog scores, or select a target model directly.

On a seven-item paraphrase probe designed to remove the fast path's literal terms:

| Mode/control | Accuracy | Mean assessor latency |
|---|---:|---:|
| Deterministic Off | 0/7 (0%) | 0 ms |
| Content-blind balanced control | 1/7 (14.3%) | n/a |
| Embedding hybrid Always, high-margin merge | 3/7 (42.9%) | 97.0 ms |

Cold first assessment was 349.9 ms; subsequent assessments were approximately 54.8 ms on the
7-CPU, 2 GiB ARM64 Podman machine. A separate final acceptance request completed in 88.6 ms.

The direction is promising but `n=7` is not claim-eligible evidence. Off therefore remains the G2
default. Auto and Always are explicitly experimental until the preregistered G5 benchmark shows
statistically supported prompt-specific utility over Off and a share-matched content-blind control.

## Podman verification

The final image was built with Podman 6.1.0 on ARM64.

- Image ID: `17452518d375f52674a4e85cf9d29d53ff283f4b767f3cddd5831d9bbb303875`
- Manifest digest: `sha256:ccbd1e5a54b10c18f2f450ee308a62c9fe5ba590698d32dd27cbb8b8c1fe73c1`
- Size: 678,513,326 bytes (about 647 MiB), including the 386 MB assessor.
- Runtime user: `10001:10001`.
- Root filesystem: read-only.
- Linux capabilities: all default capabilities dropped.
- Security option: `no-new-privileges`.
- Data: named `/data` volume owned for the non-root user.
- Temporary files: `noexec,nosuid` tmpfs at `/tmp`.
- Health check: healthy.
- Air-gap test: healthy with `--network none`; hybrid assessment and local-only advice completed.
- Local-only invariant: every returned deployment was `local`.

The native llama.cpp build was verified on a 2 GiB Podman machine. It is deliberately single-threaded
during compilation to avoid memory-dependent failures. The dependency layer is separated so normal
application changes reuse the compiled runtime.

## Dashboard verification

- React/TypeScript production bundle compiles and is served by the same FastAPI process.
- Root HTML, JavaScript, and CSS returned HTTP 200.
- No remote font, script, image, analytics, or CDN dependency is present at runtime.
- Responses include a same-origin Content Security Policy, `no-store`, frame denial, MIME-sniffing
  denial, and no-referrer policy.
- The single screen provides prompt input, four optimization goals, three privacy levels, assessor
  Off/Auto/Always controls, ranked recommendation cards, transparent configuration/evidence, and
  structured worked/did-not-work feedback.

Automated screenshot inspection could not be completed because the Codex in-app browser blocks
loopback URLs with `ERR_BLOCKED_BY_CLIENT`. This is an environment limitation: the live server and
all built assets were verified over localhost, and TypeScript/build checks passed. Full visual and
accessibility regression testing remains a G4 exit criterion.

## Catalog evidence boundary

The starter catalog is a dated set of provider documentation and transparent priors, not a universal
leaderboard. It was observed on 2026-09-15 and has an explicit freshness deadline. Primary references
include [OpenAI model documentation](https://developers.openai.com/api/docs/models),
[Anthropic model documentation](https://platform.claude.com/docs/en/about-claude/models/overview), and
[Google Gemini model guidance](https://ai.google.dev/gemini-api/docs/models).

## Known limitations and deferrals

- Auto is not promoted by the small exploratory bake-off; it remains opt-in.
- Feedback capture works, but learned personalization, bounded influence, export/delete/reset, and
  promotion controls are G3 work.
- The catalog is bundled and dated; signed imports and rollback are G3 work.
- External routing datasets, confidence intervals, Pareto frontiers, and “best” claim eligibility are
  G5 work. No “best in benchmarks” claim is made at G2.
- AMD64 image execution was not available on this ARM64 development host; the build is designed for
  both architectures and multi-architecture release evidence remains G6.
- Full browser visual/accessibility regression awaits an environment that permits localhost capture.

## Reproduction

```sh
podman build -t routellect:0.1.0 .
podman volume create routellect-data
podman run --rm --name routellect \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=128m \
  --cap-drop=all --security-opt=no-new-privileges \
  -p 8080:8080 -v routellect-data:/data:Z \
  routellect:0.1.0
```

Open `http://127.0.0.1:8080`. No provider key is required.
