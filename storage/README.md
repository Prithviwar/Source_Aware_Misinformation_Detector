# storage/ (published subset)

`storage/` is the workspace's local area for large data, backups and recovered material. The local folder
holds more than Git does. Only these notes are published:

- `datasets/README_RECOVERY_NOTE.md`: what the AVeriTeC train knowledge-store sample was, and why it is missing.
- `recovery_staging/*/`: recovery manifests and notes for authority-v2, the bottleneck analysis and the evidence package.

These stay local and are excluded by the root `.gitignore`:

- `backups/`: the unredacted annotation-pilot backup (third-party email addresses), old session backups,
  and the Git-migration backups made on 14 Nov 2026.
- Any dataset content under `datasets/`.
