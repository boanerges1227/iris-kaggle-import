# iris-kaggle-import

[中文说明](README.zh-CN.md)

Load a Kaggle dataset into InterSystems IRIS tables with one line of ObjectScript.
Every CSV and Parquet file of the dataset becomes its own table.

Built for [InterSystems Community Bounty Round 3](https://community.intersystems.com/post/community-bounty-program-idea-application-%E2%80%94-round-3-live), idea [DPI-I-1012](https://ideas.intersystems.com/ideas/DPI-I-1012).

```objectscript
do ##class(dc.kaggleloader.Loader).Load("unsdsn/world-happiness")
```

One call downloads the dataset from Kaggle and creates one IRIS table per data file.

## Quick Start

You need Docker with Compose v2 and internet access.

Clone the repository and start the container:

```bash
git clone https://github.com/boanerges1227/iris-kaggle-import.git
cd iris-kaggle-import
docker compose up -d --build --wait
docker compose exec iris iris session IRIS -U USER
```

Then run the ObjectScript example shown above in the IRIS terminal.

The container exposes ports 21975 (SQL) and 52997 (web). Login: `_SYSTEM` / `SYS`, namespace `USER`.
Compose defaults to the public `intersystems/irishealth-community:2026.2` image.
Set `IRIS_IMAGE` to use another compatible image. The default credentials are for
local evaluation only.

## Usage

### ObjectScript

```objectscript
do ##class(dc.kaggleloader.Loader).Load("unsdsn/world-happiness")
```

Full signature:

```
Load(handle, target="", limit=0, mode="replace")
```

| Argument | Default | Description |
|----------|---------|-------------|
| `handle` | *(required)* | Kaggle dataset: `owner/name` (latest) or `owner/name/versions/N` (pinned) |
| `target` | `"KaggleData.<name>"` | Target `schema.tablePrefix` — each file becomes `<prefix>_<filename>` |
| `limit` | `0` | Max rows per file; `0` = all |
| `mode` | `"replace"` | `replace` / `append` / `fail` |

Returns a JSON summary listing every table, its row count and inferred column types. The following is an excerpt:

```json
{"status":"success","dataset":"unsdsn/world-happiness","pinned":false,"rowsWritten":782,
 "tables":[{"file":"2015.csv","table":"KaggleData.world_happiness_2015","rows":158,"columns":12}],
 "notImported":[]}
```

### Get Dataset Info

```objectscript
write ##class(dc.kaggleloader.Loader).Info("unsdsn/world-happiness")
```

Lists the data files without importing them.

### Examples

```objectscript
;; latest version, default schema KaggleData
do ##class(dc.kaggleloader.Loader).Load("unsdsn/world-happiness")

;; pinned version
do ##class(dc.kaggleloader.Loader).Load("parulpandey/palmer-archipelago-antarctica-penguin-data/versions/1")

;; custom target prefix, first 100 rows of each file
do ##class(dc.kaggleloader.Loader).Load("unsdsn/world-happiness", "Demo.happy", 100)

;; error if tables already exist
do ##class(dc.kaggleloader.Loader).Load("unsdsn/world-happiness", "", 0, "fail")
```

### Authentication

Most public datasets need no credentials. For datasets requiring consent or private datasets,
export your Kaggle API credentials before starting the container:

```bash
KAGGLE_USERNAME=your_user KAGGLE_KEY=your_key docker compose up -d --wait
# or
KAGGLE_API_TOKEN=your_token docker compose up -d --wait
```

Create credentials at [kaggle.com/settings](https://www.kaggle.com/settings) → API → Create New Token.

## Loading Rules

- Each `.csv` and `.parquet` file becomes its own table `<schema>.<prefix>_<filename>`;
  other file types are listed in `notImported` and skipped.
- CSV columns are typed by the **whole column**: if every value parses as an integer the
  column becomes `BIGINT`, if every value parses as a number it becomes `DOUBLE`,
  `true`/`false` becomes `BIT`, otherwise `VARCHAR(4000)`. Leading zeros are preserved
  as text (`00123` stays `00123`). An empty field becomes `NULL`.
- Parquet files keep the types the data declares (integers → `BIGINT`, floats → `DOUBLE`,
  timestamps → `TIMESTAMP`, nested types → JSON text).
- Table and column names are lower-case `[a-z0-9_]`; SQL reserved words get a trailing `_`.
- Columns with matching normalized names get unique numeric suffixes. Files that map
  to the same target table are rejected before importing.
- CSV rows with more fields than their header are rejected; shorter rows are padded with NULLs.
- Repeated calls in `replace` mode rebuild the tables; a failed import returns
  `{"status":"error"}` with the file and reason — rows are never skipped silently.
- Limits: at most 1,000,000 rows per table and 100 MB per file
  (override with `KAGGLE_MAX_ROWS` / `KAGGLE_MAX_FILE_MB`).
- Imports are not atomic: a failure can leave earlier tables or inserted rows in place,
  and `replace` can remove an existing table before a later error. Use a dedicated schema
  and review the result before relying on it. Limits are checked after Kaggle downloads
  and extracts the dataset; they do not limit download size or extraction space.

## Column Type Mapping (Parquet)

| Parquet Type | IRIS Type |
|--------------|-----------|
| int8..int64, uint8..uint64 | `BIGINT` |
| float, double | `DOUBLE` |
| bool | `BIT` |
| date | `DATE` |
| timestamp | `TIMESTAMP` |
| string, list, struct, other | `VARCHAR(4000)` (JSON for nested) |

## Verified Datasets

| Handle | Result |
|--------|--------|
| `unsdsn/world-happiness` | 5 tables (`world_happiness_2015`..`2019`), 782 rows |
| `unsdsn/world-happiness/versions/2` | same, `"pinned": true` |

## Prerequisites

- InterSystems IRIS with Embedded Python (tested with IRIS Community 2026.1 and
  IRIS for Health Community 2026.2 on ARM64;
  compatibility with older releases has not been verified)
- Python packages: `kagglehub>=0.3`, `pyarrow>=14.0`, `rpds-py>=0.7.1`

## IPM Installation

On an existing IRIS instance with IPM installed, network access, and permission to
install Python packages into the instance's Python directory:

```objectscript
zpm "load /path/to/iris-kaggle-import -extra-pip-flags ""--upgrade"""
```

IPM installs the Python dependencies from `requirements.txt` and copies the loader
module into the instance's Python library directory. The `--upgrade` flag is important:
IPM installs into the shared `mgr/python` directory, and without it pip may leave old
package files in place even after installing newer metadata. This can upgrade shared
dependencies used by other applications; verify compatibility on an existing instance.
`rpds-py` is included for IPM installations that lack a dependency of its JSON tooling.
With pip's `--target` installation, older `.dist-info` directories may remain even
after the importable package is upgraded; check the actual loaded version as well as
`pip check`. Do not delete shared metadata without checking other applications.
After version 1.0.1 is published to the IPM registry, use:

```objectscript
zpm "install iris-kaggle-import -extra-pip-flags ""--upgrade"""
```

## Tests

```bash
./tests/test.sh
```

Runs six independently checked acceptance cases and a SQL row-count check against the running container and accesses Kaggle; it creates
and replaces tables in the `KaggleData` schema, so use a disposable instance.
Regression tests can also be run inside the container:

```bash
docker compose exec -T iris python3 -m unittest discover -s /home/irisowner/dev/tests -p test_regressions.py -v
python3 -m unittest discover -s tests -p test_acceptance_parser.py -v
```

## License

MIT. Every dataset keeps its own license and terms — check them before you load or share data.
No dataset is bundled with this repository.
