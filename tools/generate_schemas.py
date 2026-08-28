from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from data_contract_monitor.models import Contract, ValidationResult

    target = root / "schemas"
    target.mkdir(parents=True, exist_ok=True)
    schemas = {
        "native-contract.schema.json": Contract.model_json_schema(by_alias=True),
        "validation-result.schema.json": ValidationResult.model_json_schema(),
    }
    for name, payload in schemas.items():
        payload["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        (target / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(f"Generated {len(schemas)} JSON Schemas in {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
