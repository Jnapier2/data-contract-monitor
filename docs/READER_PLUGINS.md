# Reader plugin interface

Built-in readers cover CSV, Excel, JSON, JSON Lines, and optional Parquet. Third-party packages can register additional readers without changing the validation engine.

Use the Python entry-point group:

```text
data_contract_monitor.readers
```

An entry point should load an object exposing:

```python
suffixes = (".example",)

def create_reader(path, limits, sheet_name, mode):
    ...
```

The returned object implements:

```python
mode: Literal["memory", "streaming"]
inspect_columns() -> list[str]
iter_batches() -> Iterator[DatasetBatch]
```

Plugins are optional boundaries. A broken third-party plugin cannot disable built-in readers. Readers must obey the caller's resource limits, avoid network access unless their own explicit product contract authorizes it, and return pandas DataFrames with stable string column names.

The public plugin surface is intentionally narrow in v0.3.3 and may gain compatibility guarantees after wider use.
