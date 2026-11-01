# Changelog

## 1.0.1

- Add `rpds-py` to satisfy missing IPM JSON-tooling dependencies observed in a clean installation.
- Document IPM's `-extra-pip-flags "--upgrade"` option to prevent stale package code when pip installs into a shared target directory. This option can upgrade dependencies shared with other applications, and old `.dist-info` directories may still remain.
- Use the same Python dependency list for Docker builds and IPM installations.
- Add a packaging check for the required dependency.

## 1.0.0

- Initial release: import Kaggle CSV and Parquet datasets into IRIS tables.
