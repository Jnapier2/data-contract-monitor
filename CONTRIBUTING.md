# Contributing

Thank you for improving Data Contract Monitor.

## Development setup

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.lock
python -m pip install -r requirements-test.lock
python -m pip install --no-deps -e .
python -m pytest
```

Compile the dashboard after changing `frontend/src/app.ts`:

```bash
tsc --project frontend/tsconfig.json
cp frontend/dist/app.js src/data_contract_monitor/web/app.js
```

## Change requirements

- Add tests for pass and fail behavior.
- Preserve one shared rule interpretation across all interfaces.
- Do not add raw source values to results, logs, history, or diagnostics.
- Reject unknown configuration instead of silently ignoring it.
- Update the contract reference and JSON Schema for model changes.
- Document performance, privacy, security, and compatibility tradeoffs.
- Do not weaken endpoint protection or recommend broad exclusions.

## Pull requests

Describe the user problem, behavioral change, tests, security/privacy impact, and any migration requirement. Keep generated files synchronized with their source and avoid unrelated formatting churn.
