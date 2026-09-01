from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

EXPECTED_BATCH_ACTIONS = {
    "START_DATA_CONTRACT_MONITOR.bat": "serve",
    "VERIFY_RELEASE.bat": "doctor",
    "RUN_DEMO.bat": "demo",
    "RUN_TESTS.bat": "test",
    "REPAIR_INSTALLATION.bat": "repair",
    "CREATE_SUPPORT_EXPORT.bat": "export",
}
CANONICAL_BATCH_BACKEND = "tools/launch.bat"
APPROVED_EXACT_DUPLICATE_GROUPS = {
    frozenset(
        {
            "examples/contracts/customer_orders.yml",
            "src/data_contract_monitor/resources/contracts/customer_orders.yml",
        }
    ): "intentional source/package boundary: reviewer example and installed-package demo resource",
}
TEXT_SUFFIXES = {
    ".bat", ".cmd", ".css", ".html", ".ini", ".json", ".md", ".py", ".sh",
    ".toml", ".txt", ".yaml", ".yml", ".ts", ".xml",
}
IGNORED_NAMES = {".coverage", "LATEST_LAUNCH_STATUS.txt", "PACKAGE_METADATA.json.tmp", "MANIFEST.json.tmp", "MANIFEST.sha256.tmp"}
IGNORED_SUFFIXES = {".pyc", ".pyo", ".tmp"}
IGNORED_PARTS = {
    ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__",
    "backups", "build", "cache", "diagnostics", "dist", "downloads", "exports", "logs", "node_modules",
    "reports", "state", "temp",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def included(root: Path, path: Path) -> bool:
    if not path.is_file():
        return False
    if path.name in IGNORED_NAMES or path.name.startswith(".coverage.") or path.suffix in IGNORED_SUFFIXES:
        return False
    rel = path.relative_to(root)
    return not any(part in IGNORED_PARTS or part.endswith(".egg-info") for part in rel.parts)


def purpose_for(path: str) -> str:
    if path.endswith(".bat") or path == CANONICAL_BATCH_BACKEND:
        return "Windows action launcher" if path != CANONICAL_BATCH_BACKEND else "canonical Windows launcher backend"
    if path.startswith("src/data_contract_monitor/"):
        return "application runtime/source"
    if path.startswith("tests/"):
        return "automated verification"
    if path.startswith("tools/"):
        return "build/release/maintenance tooling"
    if path.startswith("frontend/"):
        return "TypeScript dashboard source"
    if path.startswith("examples/"):
        return "credential-free demonstration input"
    if path.startswith("schemas/"):
        return "generated public schema"
    if path.startswith("packages/"):
        return "installable package artifact"
    if path.startswith("docs/"):
        return "documentation/evidence"
    if path.startswith(".github/") or path == "action.yml":
        return "CI/integration configuration"
    if path.startswith("MANIFEST") or path == "PACKAGE_METADATA.json" or path == "VERSION.txt":
        return "release identity/control"
    if path.startswith("SBOM") or path == "THIRD_PARTY_NOTICES.md":
        return "supply-chain evidence"
    return "project source/documentation"


def producer_for(path: str) -> str:
    if path in {"MANIFEST.json", "MANIFEST.sha256", "PACKAGE_METADATA.json", "RELEASE_MODE"}:
        return "tools/build_release.py"
    if path.startswith("packages/") and path.endswith(".whl"):
        return "tools/build_release.py / pip wheel"
    if path in {"schemas/native-contract.schema.json", "schemas/validation-result.schema.json"}:
        return "tools/generate_schemas.py"
    if path in {"SBOM.spdx.json", "THIRD_PARTY_NOTICES.md"}:
        return "tools/generate_supply_chain.py"
    if path == "src/data_contract_monitor/resources/contracts/customer_orders.yml":
        return "maintained package-boundary copy of examples/contracts/customer_orders.yml"
    return "maintained source"


def load_manifest(root: Path) -> set[str]:
    try:
        payload = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
        return {str(item["path"]) for item in payload.get("managed_files", [])}
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError):
        return set()


def reference_map(root: Path, rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    texts: dict[str, str] = {}
    for row in rows:
        path = root / row["path"]
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 2 * 1024 * 1024:
            continue
        try:
            texts[row["path"]] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    refs: dict[str, list[str]] = {}
    for row in rows:
        target = row["path"]
        basename = Path(target).name
        matches = []
        for source, text in texts.items():
            if source == target:
                continue
            if target in text or (basename and basename in text):
                matches.append(source)
        refs[target] = sorted(set(matches))[:100]
    return refs


def validate_batch_inventory(root: Path) -> list[str]:
    errors: list[str] = []
    batch_cmd = sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".bat", ".cmd"} and included(root, p)
    )
    expected = sorted([*EXPECTED_BATCH_ACTIONS, CANONICAL_BATCH_BACKEND])
    if batch_cmd != expected:
        errors.append(f"BAT/CMD inventory differs: expected {expected}; found {batch_cmd}")
    for name, action in EXPECTED_BATCH_ACTIONS.items():
        path = root / name
        if not path.is_file():
            continue
        expected_lines = [
            "@echo off",
            f'call "%~dp0tools\\launch.bat" {action}',
            "exit /b %ERRORLEVEL%",
        ]
        if path.read_text(encoding="ascii").splitlines() != expected_lines:
            errors.append(f"{name} is not a logic-free forwarder")
    return errors


def build_index(root: Path) -> dict[str, Any]:
    root = root.resolve()
    managed = load_manifest(root)
    files = sorted((p for p in root.rglob("*") if included(root, p)), key=lambda p: p.relative_to(root).as_posix().lower())
    rows: list[dict[str, Any]] = []
    hashes: dict[str, list[str]] = defaultdict(list)
    for path in files:
        rel = path.relative_to(root).as_posix()
        digest = sha256_file(path)
        hashes[digest].append(rel)
        rows.append(
            {
                "path": rel,
                "type": path.suffix.lower().lstrip(".") or "file",
                "size": path.stat().st_size,
                "sha256": digest,
                "purpose": purpose_for(rel),
                "producer": producer_for(rel),
                "consumers": [],
                "references": [],
                "status": "managed" if rel in managed else ("identity" if rel in {"MANIFEST.json", "MANIFEST.sha256"} else "source"),
                "lineage": "v0.3.3 Windows-freshness successor; v0.3.2 is Windows field-started predecessor and v0.1.2 remains the confirmed rollback authority",
                "ownership": "Gateway Information Group LLC first-party project file",
            }
        )
    refs = reference_map(root, rows)
    for row in rows:
        row["consumers"] = refs.get(row["path"], [])
        row["references"] = refs.get(row["path"], [])

    exact_groups = []
    duplicate_errors = []
    for digest, paths in sorted(hashes.items()):
        if len(paths) < 2:
            continue
        key = frozenset(paths)
        exception = APPROVED_EXACT_DUPLICATE_GROUPS.get(key)
        exact_groups.append({"sha256": digest, "paths": paths, "approved_exception": exception})
        if exception is None:
            duplicate_errors.append(f"unapproved exact duplicate group: {paths}")

    launcher_errors = validate_batch_inventory(root)
    return {
        "schema_version": "1.0",
        "root_name": root.name,
        "discovered_file_count": len(rows),
        "indexed_file_count": len(rows),
        "total_size_bytes": sum(int(row["size"]) for row in rows),
        "files": rows,
        "exact_duplicate_groups": exact_groups,
        "functional_duplicate_groups": [
            {
                "capability": "Windows action routing",
                "active_backend": CANONICAL_BATCH_BACKEND,
                "forwarders": EXPECTED_BATCH_ACTIONS,
                "status": "consolidated; forwarders contain no business/bootstrap logic",
            },
            {
                "capability": "tooling atomic/hash helpers",
                "active_backend": "tools/tooling_common.py",
                "consumers": ["tools/bootstrap.py", "tools/build_release.py", "tools/release_gate.py"],
                "status": "consolidated",
            },
            {
                "capability": "application atomic/hash helpers",
                "active_backend": "src/data_contract_monitor/atomic.py",
                "status": "consolidated within application boundary",
            },
        ],
        "approved_duplicate_exceptions": [
            {"paths": sorted(group), "reason": reason}
            for group, reason in APPROVED_EXACT_DUPLICATE_GROUPS.items()
        ],
        "validation_errors": [*launcher_errors, *duplicate_errors],
        "passed": not launcher_errors and not duplicate_errors and len(rows) > 0,
    }


def write_outputs(index: dict[str, Any], output_dir: Path, prefix: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{prefix}_Full_File_Index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (output_dir / f"{prefix}_Full_File_Index.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["path", "type", "size", "sha256", "purpose", "producer", "consumers", "status", "lineage", "ownership"],
        )
        writer.writeheader()
        for row in index["files"]:
            out = dict(row)
            out["consumers"] = "; ".join(out["consumers"])
            out.pop("references", None)
            writer.writerow({key: out.get(key, "") for key in writer.fieldnames})
    lines = [
        f"# {prefix.replace('_', ' ')} — File Consolidation Report",
        "",
        f"- Discovered/indexed: {index['discovered_file_count']}/{index['indexed_file_count']}",
        f"- Total indexed size: {index['total_size_bytes']} bytes",
        f"- Exact duplicate groups: {len(index['exact_duplicate_groups'])}",
        f"- Validation status: {'PASS' if index['passed'] else 'FAIL'}",
        "",
        "## Exact duplicate groups",
        "",
    ]
    if index["exact_duplicate_groups"]:
        for group in index["exact_duplicate_groups"]:
            reason = group["approved_exception"] or "UNAPPROVED"
            lines.append(f"- `{group['sha256']}` — {', '.join(group['paths'])} — {reason}")
    else:
        lines.append("- None.")
    lines += ["", "## Functional consolidation", ""]
    for group in index["functional_duplicate_groups"]:
        lines.append(f"- **{group['capability']}** — active backend: `{group['active_backend']}` — {group['status']}")
    lines += ["", "## Validation errors", ""]
    if index["validation_errors"]:
        lines.extend(f"- {item}" for item in index["validation_errors"])
    else:
        lines.append("- None.")
    (output_dir / f"{prefix}_Consolidation_Report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Index a Data Contract Monitor tree and enforce consolidation rules")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--prefix", default="Data_Contract_Monitor")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    index = build_index(args.root)
    if args.output_dir and not args.check_only:
        write_outputs(index, args.output_dir, args.prefix)
    if index["validation_errors"]:
        for error in index["validation_errors"]:
            print(f"[ERROR] {error}")
    else:
        print(f"[OK] Indexed {index['indexed_file_count']} files; consolidation checks passed")
    return 0 if index["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
