from __future__ import annotations

import html
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from .models import Finding, Severity, ValidationResult


class ReportFormatError(ValueError):
    """Raised when a report format is unsupported."""


def write_json(result: ValidationResult, path: Path) -> None:
    path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _severity_badge(severity: Severity) -> str:
    return f'<span class="badge badge-{severity.value}">{html.escape(severity.value.upper())}</span>'


def write_html(result: ValidationResult, path: Path) -> None:
    finding_rows = "".join(
        f"""
        <tr>
          <td>{_severity_badge(finding.severity)}</td>
          <td>{html.escape(finding.category)}</td>
          <td><strong>{html.escape(finding.title)}</strong><br><span class="muted">{html.escape(finding.rule_id)}</span></td>
          <td>{html.escape(finding.column or '—')}</td>
          <td>{html.escape(finding.message)}</td>
          <td>{html.escape(', '.join(map(str, finding.sample_rows)) or '—')}</td>
        </tr>
        """
        for finding in result.findings
    ) or '<tr><td colspan="6" class="empty">No findings met the reporting criteria.</td></tr>'
    profile_rows = "".join(
        f"""
        <tr>
          <td>{html.escape(column.name)}</td>
          <td>{html.escape(column.observed_type)}</td>
          <td>{column.null_count}</td>
          <td>{column.null_ratio:.2%}</td>
          <td>{"" if column.distinct_count_exact else "≥"}{column.distinct_count}</td>
          <td>{"" if column.duplicate_count_exact else "≥"}{column.duplicate_count}</td>
        </tr>
        """
        for column in result.profile.columns
    )
    pii_rows = "".join(
        f"""
        <tr>
          <td>{html.escape(signal.column)}</td>
          <td>{html.escape(signal.category)}</td>
          <td>{html.escape(signal.confidence)}</td>
          <td>{'Yes' if signal.name_signal else 'No'}</td>
          <td>{signal.matching_values}/{signal.sampled_values}</td>
        </tr>
        """
        for signal in result.profile.pii_signals
    ) or '<tr><td colspan="5" class="empty">No potential sensitive-field signals detected.</td></tr>'
    status = result.summary.status.upper()
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(result.dataset_name)} — Data Contract Report</title>
<style>
:root {{ color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; }}
body {{ margin: 0; background: #f4f7fb; color: #172033; }}
main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 56px; }}
header {{ background: #13213c; color: white; padding: 28px; border-radius: 16px; }}
h1 {{ margin: 0 0 8px; font-size: clamp(1.7rem, 4vw, 2.6rem); }}
h2 {{ margin-top: 34px; }}
.meta, .muted {{ color: #66738a; }}
header .meta {{ color: #d9e4f5; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin-top: 18px; }}
.card {{ background: white; border: 1px solid #dce4ef; border-radius: 14px; padding: 18px; box-shadow: 0 4px 18px rgba(25, 44, 75, .06); }}
.value {{ font-size: 1.65rem; font-weight: 750; }}
.label {{ color: #66738a; font-size: .88rem; margin-top: 4px; }}
.status-passed {{ color: #0b6e42; }} .status-failed {{ color: #b42318; }}
.table-wrap {{ overflow-x: auto; background: white; border: 1px solid #dce4ef; border-radius: 14px; }}
table {{ border-collapse: collapse; width: 100%; min-width: 760px; }}
th, td {{ text-align: left; padding: 12px 14px; border-bottom: 1px solid #e7edf5; vertical-align: top; }}
th {{ background: #eef3f9; font-size: .84rem; letter-spacing: .02em; }}
.badge {{ border-radius: 999px; padding: 3px 8px; font-size: .74rem; font-weight: 700; }}
.badge-info {{ background:#e7f1ff; color:#174ea6; }} .badge-warning {{ background:#fff4cc; color:#7a4a00; }}
.badge-error {{ background:#fde7e7; color:#a30d16; }} .badge-critical {{ background:#4a0b12; color:white; }}
.note {{ border-left: 4px solid #356bb3; background: #eaf2fd; padding: 14px 16px; border-radius: 8px; }}
.empty {{ text-align:center; color:#66738a; padding:30px; }}
footer {{ margin-top: 36px; color:#66738a; font-size:.86rem; }}
@media (prefers-color-scheme: dark) {{
 body {{ background:#0e1420; color:#eef3fa; }} .card,.table-wrap {{ background:#161f2f; border-color:#2d3a4f; }}
 th {{ background:#202c40; }} th,td {{ border-color:#2d3a4f; }} .meta,.muted,.label,footer {{ color:#a9b7ca; }}
 .note {{ background:#172a46; }}
}}
</style>
</head>
<body><main>
<header>
  <div class="meta">Data Contract Monitor · run {html.escape(result.run_id[:12])}</div>
  <h1>{html.escape(result.dataset_name)}</h1>
  <div class="meta">Contract: {html.escape(result.contract_label)} · Dataset: {html.escape(result.data_label)} · {html.escape(result.completed_at.isoformat())}</div>
</header>
<section class="grid" aria-label="Validation summary">
  <div class="card"><div class="value status-{result.summary.status}">{status}</div><div class="label">Validation status</div></div>
  <div class="card"><div class="value">{result.profile.row_count:,}</div><div class="label">Rows evaluated</div></div>
  <div class="card"><div class="value">{result.summary.critical}</div><div class="label">Critical</div></div>
  <div class="card"><div class="value">{result.summary.errors}</div><div class="label">Errors</div></div>
  <div class="card"><div class="value">{result.summary.warnings}</div><div class="label">Warnings</div></div>
  <div class="card"><div class="value">{result.duration_ms} ms</div><div class="label">Runtime</div></div>
  <div class="card"><div class="value">{html.escape(result.execution_mode.upper())}</div><div class="label">Execution mode</div></div>
</section>
<h2>Findings</h2>
<div class="table-wrap"><table><thead><tr><th>Severity</th><th>Category</th><th>Rule</th><th>Column</th><th>Finding</th><th>Sample rows</th></tr></thead><tbody>{finding_rows}</tbody></table></div>
<h2>Column profile</h2>
<div class="table-wrap"><table><thead><tr><th>Column</th><th>Observed type</th><th>Nulls</th><th>Null ratio</th><th>Distinct</th><th>Duplicate rows</th></tr></thead><tbody>{profile_rows}</tbody></table></div>
<h2>Privacy-field hints</h2>
<p class="note">Heuristic signals require human review. The report intentionally omits raw values.</p>
<div class="table-wrap"><table><thead><tr><th>Column</th><th>Category</th><th>Confidence</th><th>Name signal</th><th>Pattern matches</th></tr></thead><tbody>{pii_rows}</tbody></table></div>
<footer>{html.escape(result.privacy_note)} · Profile mode {html.escape(result.profile.profiling_mode)} · Contract SHA-256 {html.escape(result.contract_sha256[:16])}… · Data SHA-256 {html.escape(result.data_sha256[:16])}…</footer>
</main></body></html>
"""
    path.write_text(document, encoding="utf-8")


def write_junit(result: ValidationResult, path: Path) -> None:
    suite = ET.Element(
        "testsuite",
        name=f"data-contract:{result.dataset_name}",
        tests=str(max(1, len(result.findings))),
        failures=str(result.summary.errors + result.summary.critical),
        skipped=str(result.summary.warnings + result.summary.info),
        time=f"{result.duration_ms / 1000:.3f}",
    )
    if not result.findings:
        ET.SubElement(suite, "testcase", name="contract_validation", classname=result.dataset_name)
    for finding in result.findings:
        case = ET.SubElement(suite, "testcase", name=finding.rule_id, classname=finding.category)
        if finding.severity in {Severity.ERROR, Severity.CRITICAL}:
            failure = ET.SubElement(case, "failure", message=finding.title, type=finding.severity.value)
            failure.text = finding.message
        else:
            skipped = ET.SubElement(case, "skipped", message=finding.title)
            skipped.text = finding.message
    ET.indent(suite, space="  ")
    path.write_text(ET.tostring(suite, encoding="unicode") + "\n", encoding="utf-8")


def write_sarif(result: ValidationResult, path: Path) -> None:
    unique_rules: dict[str, Finding] = {}
    for finding in result.findings:
        unique_rules.setdefault(finding.rule_id, finding)
    rules = [
        {
            "id": rule_id,
            "name": finding.title,
            "shortDescription": {"text": finding.title},
            "fullDescription": {"text": finding.message},
            "help": {"text": finding.remediation or "Review the data contract finding."},
            "properties": {"category": finding.category},
        }
        for rule_id, finding in sorted(unique_rules.items())
    ]
    level = {
        Severity.INFO: "note",
        Severity.WARNING: "warning",
        Severity.ERROR: "error",
        Severity.CRITICAL: "error",
    }
    results = []
    for finding in result.findings:
        item: dict[str, object] = {
            "ruleId": finding.rule_id,
            "level": level[finding.severity],
            "message": {"text": finding.message},
            "properties": {
                "severity": finding.severity.value,
                "category": finding.category,
                "affectedRows": finding.affected_rows,
            },
        }
        if finding.sample_rows:
            item["locations"] = [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": result.data_label},
                        "region": {"startLine": finding.sample_rows[0] + 1},
                    }
                }
            ]
        results.append(item)
    payload = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Data Contract Monitor",
                        "version": result.tool_version,
                        "rules": rules,
                    }
                },
                "automationDetails": {"id": f"data-contract/{result.dataset_name}"},
                "results": results,
            }
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_reports(result: ValidationResult, output_dir: Path, formats: list[str]) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    writers = {"json": write_json, "html": write_html, "junit": write_junit, "sarif": write_sarif}
    written: list[Path] = []
    for value in formats:
        normalized = value.strip().lower()
        if normalized not in writers:
            raise ReportFormatError(f"Unsupported report format: {value}")
        suffix = "xml" if normalized == "junit" else normalized
        path = output_dir / f"data_contract_report.{suffix}"
        writers[normalized](result, path)
        written.append(path)
    return written
