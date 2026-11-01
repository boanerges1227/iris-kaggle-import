import csv
import json
import os
import re
import sys

MAX_ROWS = int(os.environ.get("KAGGLE_MAX_ROWS", 1000000))
MAX_FILE_MB = int(os.environ.get("KAGGLE_MAX_FILE_MB", 100))

RESERVED = {'date', 'time', 'timestamp', 'user', 'group', 'order', 'table',
            'select', 'from', 'where', 'insert', 'update', 'delete', 'create',
            'drop', 'alter', 'index', 'view', 'key', 'primary', 'foreign',
            'case', 'when', 'then', 'else', 'end', 'null', 'true', 'false',
            'label', 'text', 'type', 'name', 'id', 'schema', 'number', 'value',
            'count', 'sum', 'avg', 'min', 'max', 'like', 'between', 'in', 'is',
            'not', 'and', 'or', 'as', 'on', 'by', 'set', 'to', 'top', 'all',
            'any', 'some', 'exists', 'having', 'union', 'except', 'intersect',
            'join', 'left', 'right', 'inner', 'outer', 'full', 'cross',
            'into', 'values', 'default', 'check', 'unique', 'constraint',
            'cast', 'convert', 'coalesce', 'nullif', 'row', 'rows', 'range'}


def clean_name(name):
    """Normalize a SQL identifier and avoid leading digits and reserved words."""
    name = name.strip().lower()
    name = re.sub(r'[^a-z0-9_]', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_')
    if not name or name[0].isdigit():
        name = 'c_' + name
    if name in RESERVED:
        name = name + '_'
    return name


def clean_part(name):
    """Clean a name fragment used as a suffix (no digit-prefix or reserved rules)."""
    name = name.strip().lower()
    name = re.sub(r'[^a-z0-9_]', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('_')
    return name or 'x'


def _unique_column_names(names):
    """Normalize column names and resolve duplicate or suffix collisions."""
    used = set()
    result = []
    for index, name in enumerate(names):
        base = clean_name(name if name.strip() else f"col{index + 1}")
        candidate = base
        suffix = 1
        while candidate in used:
            candidate = f"{base}_{suffix}"
            suffix += 1
        used.add(candidate)
        result.append(candidate)
    return result


def _is_int(v):
    """Recognize canonical integers while preserving leading-zero values as text."""
    try:
        iv = int(v)
    except (ValueError, OverflowError):
        return False
    if v.startswith("-"):
        return v[1:] == str(abs(iv))
    return v == str(iv)


def _is_float(v):
    """Recognize floating-point text without losing leading-zero codes."""
    # leading zeros (e.g. "00123") indicate a code, not a number — keep as text
    if len(v) > 1 and v[0] == '0' and v[1] != '.':
        return False
    if len(v) > 2 and v.startswith('-0') and v[2] != '.':
        return False
    try:
        float(v)
        return True
    except ValueError:
        return False


def infer_column_type(values):
    """Infer a SQL type from all nonempty CSV values."""
    non_empty = [v for v in values if v != ""]
    if not non_empty:
        return "VARCHAR(4000)"
    if all(_is_int(v) for v in non_empty):
        return "BIGINT"
    if all(_is_float(v) for v in non_empty):
        return "DOUBLE"
    if all(v.strip().lower() in ("true", "false") for v in non_empty):
        return "BIT"
    return "VARCHAR(4000)"


def _convert_value(sql_type, v):
    """Convert a CSV value to an IRIS SQL parameter."""
    # IRIS embedded Python rejects Python None for SQL params;
    # empty string is stored as NULL for every column type
    if v is None or v == "":
        return ""
    if sql_type == "BIGINT":
        return int(v)
    if sql_type == "DOUBLE":
        return float(v)
    if sql_type == "BIT":
        return 1 if str(v).strip().lower() == "true" else 0
    return str(v)


def _parquet_to_sql_type(pa_type):
    """Map an Arrow type to a supported IRIS SQL type."""
    import pyarrow as pa
    if pa.types.is_integer(pa_type):
        return "BIGINT"
    if pa.types.is_floating(pa_type):
        return "DOUBLE"
    if pa.types.is_boolean(pa_type):
        return "BIT"
    if pa.types.is_date(pa_type):
        return "DATE"
    if pa.types.is_timestamp(pa_type):
        return "TIMESTAMP"
    return "VARCHAR(4000)"


def _parquet_value(pa_type, val):
    """Convert Arrow values to IRIS parameters and encode nested values as JSON."""
    import datetime
    if val is None:
        return ""
    import pyarrow as pa
    if pa.types.is_list(pa_type) or pa.types.is_struct(pa_type) or pa.types.is_map(pa_type):
        return json.dumps(val, default=str)
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.isoformat()
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, bool):
        return 1 if val else 0
    return val


def _list_data_files(root):
    """List supported and unsupported files below the dataset directory."""
    data_files = []
    other_files = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            ext = fn.lower().rsplit(".", 1)[-1] if "." in fn else ""
            if ext in ("csv", "parquet"):
                data_files.append((rel, full, ext))
            else:
                other_files.append(rel)
    return sorted(data_files), sorted(other_files)


def load_kaggle_to_iris(handle, target="", mode="replace", limit=0):
    """Download a Kaggle dataset into IRIS and return per-file results."""
    import iris

    result = {"status": "error", "error": "", "tables": [], "notImported": []}

    try:
        limit = int(limit or 0)
        if limit < 0:
            raise ValueError("limit must not be negative")
    except (TypeError, ValueError) as e:
        result["error"] = f"invalid limit: {e}"
        return result
    if mode not in ("replace", "append", "fail"):
        result["error"] = "mode must be replace, append, or fail"
        return result

    if not handle:
        result["error"] = "dataset handle is required (owner/name or owner/name/versions/N)"
        return result

    try:
        import kagglehub
    except ImportError:
        result["error"] = "kagglehub is not installed: pip3 install kagglehub"
        return result

    try:
        local_path = kagglehub.dataset_download(handle)
    except ValueError as e:
        result["error"] = f"invalid handle: {e}"
        return result
    except Exception as e:
        msg = str(e)
        if "401" in msg or "403" in msg:
            msg = ("authentication or consent required: set KAGGLE_USERNAME/KAGGLE_KEY "
                   "or KAGGLE_API_TOKEN environment variables. Original error: " + msg)
        result["error"] = msg
        return result

    if os.path.isfile(local_path):
        root = os.path.dirname(local_path)
    else:
        root = local_path

    parts = handle.split("/")
    ds_name = parts[1] if len(parts) > 1 else parts[0]
    pinned = len(parts) == 4 and parts[2] == "versions"

    if not target:
        target = f"KaggleData.{clean_name(ds_name)}"

    dot = target.find(".")
    if dot < 0:
        schema_name = "SQLUser"
        prefix = clean_name(target)
    else:
        schema_name = target[:dot]
        prefix = clean_name(target[dot + 1:])

    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', schema_name):
        result["error"] = "target schema must contain only letters, digits and underscores"
        return result

    data_files, other_files = _list_data_files(root)
    result["notImported"] = other_files

    if not data_files:
        result["error"] = f"no CSV or Parquet files found in dataset '{handle}'"
        return result

    # Preflight normalized table names to prevent files overwriting one another.
    table_files = {}
    for rel, _full, _ext in data_files:
        file_stem = re.sub(r'\.[^.]+$', '', rel.replace(os.sep, '_'))
        table_name = f"{prefix}_{clean_part(file_stem)}"
        if table_name in table_files:
            result["error"] = f"files '{table_files[table_name]}' and '{rel}' map to the same target table '{table_name}'"
            return result
        table_files[table_name] = rel

    for rel, full, ext in data_files:
        size_mb = os.path.getsize(full) / (1024 * 1024)
        if size_mb > MAX_FILE_MB:
            result["error"] = (f"file '{rel}' is {size_mb:.1f} MB, over the "
                               f"{MAX_FILE_MB} MB limit")
            return result

        file_stem = re.sub(r'\.[^.]+$', '', rel.replace(os.sep, '_'))
        table_name = f"{prefix}_{clean_part(file_stem)}"

        try:
            if ext == "csv":
                fresult = _import_csv(iris, full, schema_name, table_name, mode, limit)
            else:
                fresult = _import_parquet(iris, full, schema_name, table_name, mode, limit)
        except UnicodeDecodeError:
            result["error"] = f"file '{rel}' is not valid UTF-8"
            return result
        except Exception as e:
            result["error"] = f"file '{rel}' failed to import: {e}"
            return result

        if fresult.get("error"):
            result["error"] = f"file '{rel}' failed: {fresult['error']}"
            return result

        fresult["file"] = rel
        fresult["table"] = f"{schema_name}.{table_name}"
        result["tables"].append(fresult)

    result["status"] = "success"
    result["dataset"] = handle
    result["pinned"] = pinned
    result["rowsWritten"] = sum(t.get("rows", 0) for t in result["tables"])
    return result


def _table_exists(iris, schema_name, table_name):
    """Check table metadata and propagate errors rather than assuming absence."""
    stmt = iris.sql.prepare(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?")
    rs = stmt.execute(schema_name, table_name)
    for row in rs:
        return row[0] > 0
    raise RuntimeError("table metadata query returned no rows")


def _handle_existing_table(iris, schema_name, table_name, mode):
    """Returns None if OK to proceed, or an error string."""
    if not _table_exists(iris, schema_name, table_name):
        return None
    if mode == "fail":
        return f"table {schema_name}.{table_name} already exists and mode is fail"
    if mode == "replace":
        try:
            iris.sql.exec(f'DROP TABLE "{schema_name}"."{table_name}"')
        except Exception as e:
            return f"cannot drop table: {e}"
    return None


def _create_table(iris, schema_name, table_name, columns):
    """Create a table from normalized column names and inferred SQL types."""
    cols_ddl = [f'"{n}" {t}' for n, t in columns]
    create_sql = f'CREATE TABLE "{schema_name}"."{table_name}" ({", ".join(cols_ddl)})'
    try:
        iris.sql.exec(create_sql)
        return None
    except Exception as e:
        return str(e)


def _import_csv(iris, path, schema_name, table_name, mode, limit):
    """Infer CSV types from complete columns and import using the requested mode."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(8192)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        f.seek(0)
        reader = csv.reader(f, dialect)
        try:
            header = next(reader)
        except StopIteration:
            return {"error": "file is empty"}
        if not header or all(not h.strip() for h in header):
            return {"error": "no header row found"}

        raw_rows = []
        col_values = [[] for _ in header]
        for i, row in enumerate(reader):
            if limit and limit > 0 and i >= limit:
                break
            if len(raw_rows) >= MAX_ROWS:
                return {"error": f"file has more than {MAX_ROWS} rows"}
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))
            elif len(row) > len(header):
                return {"error": f"row {i + 2} has more fields than the header"}
            for j, v in enumerate(row):
                col_values[j].append(v)
            raw_rows.append(row)

    col_names = _unique_column_names(header)

    col_types = [infer_column_type(vals) for vals in col_values]
    columns = list(zip(col_names, col_types))

    err = _handle_existing_table(iris, schema_name, table_name, mode)
    if err:
        return {"error": err}

    if mode == "append" and _table_exists(iris, schema_name, table_name):
        pass
    else:
        err = _create_table(iris, schema_name, table_name, columns)
        if err:
            return {"error": err}

    if raw_rows:
        quoted = ", ".join(f'"{n}"' for n in col_names)
        placeholders = ", ".join("?" for _ in col_names)
        insert_sql = (f'INSERT INTO "{schema_name}"."{table_name}" '
                      f'({quoted}) VALUES ({placeholders})')
        stmt = iris.sql.prepare(insert_sql)
        for raw in raw_rows:
            stmt.execute(*[_convert_value(t, v) for t, v in zip(col_types, raw)])

    return {"rows": len(raw_rows), "columns": len(col_names),
            "columnTypes": {n: t for n, t in columns}}


def _import_parquet(iris, path, schema_name, table_name, mode, limit):
    """Create or append to an IRIS table using the Parquet schema."""
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    schema = table.schema
    total = table.num_rows
    if limit and limit > 0:
        total = min(total, limit)
    if total > MAX_ROWS:
        return {"error": f"file has more than {MAX_ROWS} rows"}

    col_names = _unique_column_names(schema.names)
    col_types = [_parquet_to_sql_type(schema.field(i).type) for i in range(len(schema.names))]
    columns = list(zip(col_names, col_types))

    err = _handle_existing_table(iris, schema_name, table_name, mode)
    if err:
        return {"error": err}

    if mode != "append" or not _table_exists(iris, schema_name, table_name):
        err = _create_table(iris, schema_name, table_name, columns)
        if err:
            return {"error": err}

    if total > 0:
        quoted = ", ".join(f'"{n}"' for n in col_names)
        placeholders = ", ".join("?" for _ in col_names)
        insert_sql = (f'INSERT INTO "{schema_name}"."{table_name}" '
                      f'({quoted}) VALUES ({placeholders})')
        stmt = iris.sql.prepare(insert_sql)
        py_cols = [table.column(i).to_pylist() for i in range(len(schema.names))]
        for r in range(total):
            row = [_parquet_value(schema.field(i).type, py_cols[i][r])
                   for i in range(len(schema.names))]
            stmt.execute(*row)

    return {"rows": total, "columns": len(col_names),
            "columnTypes": {n: t for n, t in columns}}


def get_dataset_info(handle):
    """List files of a Kaggle dataset without importing it."""
    result = {"dataset": handle, "files": [], "notImported": []}
    try:
        import kagglehub
        local_path = kagglehub.dataset_download(handle)
    except Exception as e:
        result["error"] = str(e)
        return result

    root = os.path.dirname(local_path) if os.path.isfile(local_path) else local_path
    data_files, other_files = _list_data_files(root)
    result["files"] = [rel for rel, _full, _ext in data_files]
    result["notImported"] = other_files
    return result
