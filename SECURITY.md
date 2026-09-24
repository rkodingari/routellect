# Security Policy

## Scope and guarantees

Routellect advises; it never executes a recommended target model. It requires no provider key and
does not persist raw prompts by default. The optional assessor runs locally and cannot access the
catalog, ranker, tools, provider APIs, or durable prompt memory.

## Reporting

Until a public security contact is approved, report suspected vulnerabilities privately to the
project owner. Do not include real credentials or sensitive prompts in a report; use synthetic
reproduction data.

## Supported version

Only the latest sponsor-approved release is supported. Version `0.5.0` is a gated release candidate,
not a production security release until G6 is approved.

## Runtime controls

- Write request bodies are limited to 1 MiB by default (`ROUTELLECT_MAX_REQUEST_BYTES`).
- Write requests are limited to 600 per minute per client by default
  (`ROUTELLECT_RATE_LIMIT_PER_MINUTE`).
- One feedback event is accepted per recommendation receipt unless the prior event is deleted.
- Run the container rootless, read-only, with all capabilities dropped and no-new-privileges.

## Incident response

Stop the container while preserving the data volume, record the image digest and relevant times,
and copy a checksummed backup to encrypted storage. Do not include prompt text in incident notes.
Rotate any host or registry credentials that might have been exposed (Routellect itself stores no
provider credentials), rebuild from pinned inputs, verify the release manifest and SBOM, and restore
only into an empty data directory after the cause is resolved.
