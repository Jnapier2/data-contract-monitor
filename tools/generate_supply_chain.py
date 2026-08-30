from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path


LICENSES = {
    "annotated-doc": "MIT",
    "annotated-types": "MIT",
    "anyio": "MIT",
    "certifi": "MPL-2.0",
    "coverage": "Apache-2.0",
    "click": "BSD-3-Clause",
    "et-xmlfile": "MIT",
    "fastapi": "MIT",
    "h11": "MIT",
    "httpcore": "BSD-3-Clause",
    "httpx": "BSD-3-Clause",
    "idna": "BSD-3-Clause",
    "iniconfig": "MIT",
    "jinja2": "BSD-3-Clause",
    "markdown-it-py": "MIT",
    "markupsafe": "BSD-3-Clause",
    "mdurl": "MIT",
    "numpy": "BSD-3-Clause",
    "openpyxl": "MIT",
    "packaging": "Apache-2.0 OR BSD-2-Clause",
    "pandas": "BSD-3-Clause",
    "pluggy": "MIT",
    "pydantic": "MIT",
    "pydantic-core": "MIT",
    "pygments": "BSD-2-Clause",
    "pytest": "MIT",
    "pytest-cov": "MIT",
    "python-dateutil": "Apache-2.0 OR BSD-3-Clause",
    "python-multipart": "Apache-2.0",
    "pytz": "MIT",
    "pyyaml": "MIT",
    "rich": "MIT",
    "setuptools": "MIT",
    "shellingham": "ISC",
    "six": "MIT",
    "starlette": "BSD-3-Clause",
    "typer": "MIT",
    "typing-extensions": "PSF-2.0",
    "typing-inspection": "MIT",
    "tzdata": "Apache-2.0",
    "uvicorn": "BSD-3-Clause",
    "wheel": "MIT",
    "typescript": "Apache-2.0",
}


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_lock(path: Path, scope: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, version = line.split("==", 1)
        key = normalized(name)
        rows.append(
            {
                "name": name,
                "normalized": key,
                "version": version,
                "license": LICENSES.get(key, "NOASSERTION"),
                "scope": scope,
                "ecosystem": "PyPI",
            }
        )
    return rows


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    version = (root / "VERSION.txt").read_text(encoding="utf-8").strip()
    build_info = json.loads((root / "src" / "data_contract_monitor" / "build_info.json").read_text(encoding="utf-8"))
    build_id = str(build_info.get("build_id") or "source")
    dependencies = read_lock(root / "requirements.lock", "runtime")
    test_dependencies = read_lock(root / "requirements-test.lock", "test")
    existing = {(item["normalized"], item["version"]) for item in dependencies}
    dependencies.extend(item for item in test_dependencies if (item["normalized"], item["version"]) not in existing)
    dependencies.append(
        {
            "name": "typescript",
            "normalized": "typescript",
            "version": "5.8.3",
            "license": LICENSES["typescript"],
            "scope": "frontend-build",
            "ecosystem": "npm",
        }
    )
    dependencies.sort(key=lambda item: (item["ecosystem"], item["normalized"], item["version"]))

    packages = [
        {
            "SPDXID": "SPDXRef-Package-DataContractMonitor",
            "name": "data-contract-monitor",
            "versionInfo": version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "Apache-2.0",
            "licenseDeclared": "Apache-2.0",
            "copyrightText": "Copyright © 2026 Gateway Information Group LLC. All rights reserved.",
            "supplier": "Organization: Gateway Information Group LLC",
            "primaryPackagePurpose": "APPLICATION",
        }
    ]
    relationships: list[dict[str, str]] = []
    for index, item in enumerate(dependencies, start=1):
        spdx_id = f"SPDXRef-Dependency-{index}"
        packages.append(
            {
                "SPDXID": spdx_id,
                "name": item["name"],
                "versionInfo": item["version"],
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": item["license"],
                "licenseDeclared": item["license"],
                "copyrightText": "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": (
                            f"pkg:pypi/{item['normalized']}@{item['version']}"
                            if item["ecosystem"] == "PyPI"
                            else f"pkg:npm/{item['normalized']}@{item['version']}"
                        ),
                    }
                ],
                "annotations": [
                    {
                        "annotationType": "OTHER",
                        "annotator": "Tool: Data Contract Monitor supply-chain generator",
                        "annotationDate": datetime.now(UTC).isoformat(),
                        "comment": f"Dependency scope: {item['scope']}",
                    }
                ],
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-Package-DataContractMonitor",
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": spdx_id,
            }
        )

    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"Data Contract Monitor {version} SBOM",
        "documentNamespace": f"https://spdx.org/spdxdocs/data-contract-monitor-{version}-{build_id}",
        "creationInfo": {
            "created": datetime.now(UTC).isoformat(),
            "creators": ["Organization: Gateway Information Group LLC", "Tool: tools/generate_supply_chain.py"],
            "licenseListVersion": "3.25",
        },
        "documentDescribes": ["SPDXRef-Package-DataContractMonitor"],
        "packages": packages,
        "relationships": relationships,
    }
    (root / "SBOM.spdx.json").write_text(
        json.dumps(sbom, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    lines = [
        "# Third-Party Notices",
        "",
        "Data Contract Monitor depends on the packages below. Versions are locked in `requirements.lock`, `requirements-test.lock`, and `frontend/package-lock.json`.",
        "",
        "License identifiers are a compact inventory, not a substitute for the license files distributed by each project. `NOASSERTION` would require manual review before public distribution; none are expected in this release.",
        "",
        "| Package | Version | Ecosystem | Scope | Declared license |",
        "|---|---:|---|---|---|",
    ]
    for item in dependencies:
        lines.append(
            f"| `{item['name']}` | `{item['version']}` | {item['ecosystem']} | {item['scope']} | `{item['license']}` |"
        )
    lines.extend(
        [
            "",
            "TypeScript is used to compile the reviewer dashboard. The compiled JavaScript is included in the application package.",
            "",
            "Copyright © 2026 Gateway Information Group LLC. All rights reserved.",
        ]
    )
    (root / "THIRD_PARTY_NOTICES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote SBOM and notices for {len(dependencies)} dependency entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
