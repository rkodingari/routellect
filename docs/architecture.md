# Routellect architecture

Routellect is an advisory-only model selection system. It analyzes a prompt locally and recommends
an eligible LLM configuration, but it never sends the prompt to or invokes the recommended model.
This document describes the implemented `0.5.0` architecture.

## System context

```mermaid
flowchart TB
    U[User or integrating application]

    subgraph C[Rootless Podman container]
        UI[React dashboard]
        API[FastAPI service]
        CLI[CLI]
        ADV[Recommendation engine]
        ASSESS[Optional local semantic assessor]
        CAT[Catalog manager]
        LEARN[Feedback learner and benchmark runner]
        STORE[(SQLite and signed catalog state)]

        UI --> API
        CLI --> ADV
        API --> ADV
        ADV --> ASSESS
        ADV --> CAT
        ADV --> LEARN
        CAT --> STORE
        LEARN --> STORE
    end

    U -->|Prompt and constraints| UI
    U -->|HTTP| API
    U -->|Command| CLI
    ADV -->|Ranked advice only| U
    TARGET[Recommended hosted or local model]
    ADV -. no execution path .-> TARGET
```

The dashed edge is a deliberate non-capability: production code contains no target-model client,
provider API key flow, completion endpoint, or proxy.

## Recommendation pipeline

```mermaid
flowchart TD
    REQ[Prompt, objective, privacy, and optional limits]
    PROFILE[Deterministic profile: task, difficulty, tokens, capabilities, privacy flags]
    MODE{Assessor mode}
    AUTO{Uncertainty threshold reached?}
    EMBED[Local SmolLM2 embedding]
    MATCH[Similarity against versioned task prototypes]
    VALIDATE[Validate and conservatively merge semantic features]
    FALLBACK[Keep deterministic profile]
    PRIVACY[Resolve effective privacy policy]
    FILTER[Apply hard eligibility filters]
    SCORE[Score quality, cost, latency, evidence risk, and uncertainty]
    PARETO[Mark Pareto-efficient candidates]
    SHORTLIST[Select objective winner, economical option, and specialist or private-fast option]
    EXPLAIN[Return ranges, confidence, reasons, warnings, and evidence]

    REQ --> PROFILE --> MODE
    MODE -->|Off| FALLBACK
    MODE -->|Always| EMBED
    MODE -->|Auto| AUTO
    AUTO -->|Yes| EMBED
    AUTO -->|No| FALLBACK
    EMBED --> MATCH --> VALIDATE
    EMBED -. timeout, unavailable, or invalid .-> FALLBACK
    VALIDATE --> PRIVACY
    FALLBACK --> PRIVACY
    PRIVACY --> FILTER --> SCORE --> PARETO --> SHORTLIST --> EXPLAIN
```

The assessor supplies a bounded semantic signal; it cannot see the catalog, prices, feedback,
scores, or selected model. A failed assessor cannot prevent deterministic advice.

## Decision authority and policy order

```mermaid
flowchart LR
    CANDIDATES[Catalog configurations]
    P1{Privacy allowed?}
    P2{Capabilities supported?}
    P3{Context fits?}
    P4{Quality floor met?}
    P5{Within cost limit?}
    P6{Within latency target?}
    ELIGIBLE[Eligible candidates]
    RANK[Objective-weighted deterministic ranking]
    RESULT[Explainable shortlist]
    REJECT[Excluded with no score override]

    CANDIDATES --> P1
    P1 -->|Yes| P2
    P1 -->|No| REJECT
    P2 -->|Yes| P3
    P2 -->|No| REJECT
    P3 -->|Yes| P4
    P3 -->|No| REJECT
    P4 -->|Yes| P5
    P4 -->|No| REJECT
    P5 -->|Yes| P6
    P5 -->|No| REJECT
    P6 -->|Yes| ELIGIBLE
    P6 -->|No| REJECT
    ELIGIBLE --> RANK --> RESULT
```

Privacy, capabilities, context, quality floor, budget, and latency are hard constraints. Neither
the assessor nor feedback can override them. Feedback can adjust an eligible candidate's score only
after its governed promotion gate succeeds, and its influence remains capped.

## Privacy and data flow

```mermaid
flowchart TB
    PROMPT[Raw prompt]

    subgraph MEMORY[In-memory request boundary]
        PROFILER[Deterministic profiler]
        LOCAL[Optional local assessor]
        ADVISOR[Policy and ranking]
    end

    PROMPT --> PROFILER
    PROMPT --> LOCAL
    PROFILER --> ADVISOR
    LOCAL --> ADVISOR

    ADVISOR --> RESPONSE[Recommendation response]
    ADVISOR --> RECEIPT[Derived receipt fields]
    RESPONSE --> USER[User]
    RECEIPT --> DB[(Local data volume)]

    FEEDBACK[Structured outcome feedback] --> DB
    SIGNED[Operator-supplied signed catalog] --> VERIFY[Schema, digest, signature, sequence, and expiry checks]
    VERIFY --> DB

    PROMPT -. not stored .-> DB
    PROMPT -. not sent .-> PROVIDER[Target model provider]
```

Recommendation receipts and feedback exclude the raw prompt. The local assessor has no network,
tools, memory, catalog access, or final-decision authority. Signed catalog imports are explicit
operator actions; recommendation requests do not refresh data from the network.

## Feedback and promotion loop

```mermaid
sequenceDiagram
    participant U as User
    participant A as Active advisor
    participant D as Local feedback store
    participant R as Chronological replay
    participant G as Promotion gate

    A-->>U: Recommendation receipt
    U->>D: Used configuration and structured outcome
    Note over D: No prompt or free-text response stored
    U->>R: Request personalization promotion
    R->>D: Read eligible historical outcomes
    R->>R: Aggregate and per-task holdout evaluation
    R->>G: Candidate policy and non-regression evidence
    alt Gate passes
        G->>A: Activate bounded versioned policy
    else Gate fails
        G-->>U: Reject candidate and retain active policy
    end
```

Individual outcomes never update live ranking immediately. Promotion is explicit, audited,
reversible, and subject to minimum support and non-regression checks.

## Catalog trust lifecycle

```mermaid
flowchart LR
    BUILTIN[Builtin offline catalog]
    FILE[Signed catalog envelope]
    SCHEMA[Strict schema validation]
    DIGEST[SHA-256 digest validation]
    SIGNATURE[Ed25519 signature validation]
    FRESH[Sequence and expiry validation]
    ACTIVATE[Atomic activation]
    ACTIVE[(Active snapshot)]
    PREVIOUS[(Previous snapshot)]
    FALLBACK[Builtin fallback with warning]

    BUILTIN --> ACTIVE
    FILE --> SCHEMA --> DIGEST --> SIGNATURE --> FRESH
    FRESH -->|Valid| ACTIVATE
    ACTIVE -->|Retain prior snapshot| PREVIOUS
    ACTIVATE --> ACTIVE
    FRESH -->|Invalid| FALLBACK
    ACTIVE -->|Corrupt or unavailable| FALLBACK
```

Catalog updates are imported from local files and activated atomically. Rollback retains a
monotonic high-water sequence so an older signed snapshot cannot silently replace newer evidence.

## Podman deployment

```mermaid
flowchart LR
    BROWSER[Browser]
    CLIENT[CLI or API client]

    subgraph PODMAN[Rootless Podman]
        subgraph IMAGE[Single OCI image]
            WEB[Static dashboard]
            SERVICE[FastAPI and CLI]
            POLICY[Advisor and catalog policy]
            MODEL[llama.cpp and pinned SmolLM2 GGUF]
        end
        DATA[(Named volume at /data)]
        TMP[Restricted tmpfs at /tmp]

        WEB --> SERVICE
        SERVICE --> POLICY
        POLICY --> MODEL
        SERVICE --> DATA
        SERVICE --> TMP
    end

    BROWSER -->|Port 8080| WEB
    CLIENT -->|Port 8080| SERVICE
    POLICY -. no target-model calls .-> INTERNET[Hosted model APIs]
```

The runtime supports a read-only root filesystem, non-root user, dropped Linux capabilities, and
`no-new-privileges`. The model and runtime are bundled during the image build, allowing offline
operation after the image exists.

## Code map

| Concern | Primary implementation |
|---|---|
| API and dashboard serving | [`src/routellect/api.py`](../src/routellect/api.py) |
| Deterministic prompt profiling | [`src/routellect/profiler.py`](../src/routellect/profiler.py) |
| Bounded local assessor | [`src/routellect/assessor.py`](../src/routellect/assessor.py) |
| Eligibility, scoring, and shortlist | [`src/routellect/advisor.py`](../src/routellect/advisor.py) |
| Catalog validation and activation | [`src/routellect/catalog.py`](../src/routellect/catalog.py) |
| Feedback governance | [`src/routellect/learning.py`](../src/routellect/learning.py) |
| Local persistence | [`src/routellect/storage.py`](../src/routellect/storage.py) |
| Container build | [`Containerfile`](../Containerfile) |

Architectural decisions and their trade-offs are recorded in [`docs/adr`](adr/).
