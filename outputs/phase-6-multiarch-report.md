# Routellect 0.5.0 Multi-Architecture Readiness

Date: 2026-09-16  
Decision: **Pass for local release candidate; publication not performed**

## Built and tested images

| Platform | Manifest digest | Image ID | Verification |
|---|---|---|---|
| `linux/arm64/v8` | `sha256:7afa312429314eef520a6fb62da6347631e6c0655e81311ccd71cfc44151ca11` | `32d70dbcb70d78d962c22b6fd3111ea286b6941fb054676ea6f9f02357682ca6` | Native full resilience suite |
| `linux/amd64` | `sha256:c344f83f15771cc5b81139aeb2cb5220e66446facc79b44561341c5d3a8873a7` | `ffa908b8771c317a4d5dee6ae6680e9484e79e54b9686baae3d92034f7e3b1c9` | Podman/QEMU full build and smoke test |

The local OCI index `localhost/routellect:0.5.0-multiarch` has manifest ID
`8d5be01961a74aacead75183e83fa843dda140c08548ebdfa4b018022fc25806` and contains exactly the
two platform manifests above.

The amd64 preflight reported `x86_64`. Its full image became healthy under emulation, ran as UID/GID
10001 with a read-only root filesystem, all capabilities dropped, and no-new-privileges, then served
20/20 advisory requests. Emulated readiness was 5.32 seconds; mean advisory latency was 15.45 ms.

## Reproducibility notes

- Node and Python bases are pinned by multi-platform index digest.
- Both indexes contain arm64 and amd64 manifests.
- The bundled model uses one immutable revision and SHA-256 across architectures.
- The pure-Python Routellect wheel had SHA-256
  `3a98dde19da730270f3b96a164f9960473f3710a7a10f09ca7043a27b54e1cce` on both builds.
- `llama-cpp-python` is intentionally compiled per architecture with `GGML_NATIVE=OFF`.

No registry push, public manifest, release, or deployment occurred. Native amd64 CI remains the
preferred publication check because the local emulated C++ build is materially slower.

Reference: [Podman multi-platform build documentation](https://docs.podman.io/en/stable/markdown/podman-build.1.html).
