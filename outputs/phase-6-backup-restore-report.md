# Routellect 0.5.0 Backup, Restore, and Retention Verification

Date: 2026-09-16  
Decision: **Pass**

## Proven behavior

- Live SQLite data is copied with SQLite's online backup API and checked with `PRAGMA integrity_check`.
- Every archived file has a size and SHA-256 value in `routellect-backup-v1`.
- Existing archives are never overwritten.
- Restore accepts regular files only and rejects absolute paths, parent traversal, duplicate members,
  duplicate manifest paths, malformed entries, checksum mismatches, archives over 2 GiB, and non-empty
  targets.
- Restored files and directories receive restrictive local permissions, followed by a SQLite
  integrity check.
- The container test created a live backup and restored one database file; archive SHA-256 matched
  before and after restore.
- Explicit age-based retention is opt-in and unit-tested. It preserves receipts that still have
  feedback newer than the cutoff.

## Test evidence

- 49 application tests passed, including traversal, malformed-manifest, overwrite refusal,
  round-trip restore, and retention cases.
- Runtime round trip: `routellect-backup-v1`, one file restored, checksum match `true`.

## Encryption boundary

The archive is integrity-protected, not encrypted. Store it only on encrypted media or encrypt it
before transfer. The tool never overwrites an existing backup or restores over populated data.
