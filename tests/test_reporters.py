from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from data_contract_monitor.demo import write_demo_dataset
from data_contract_monitor.engine import validate_files
from data_contract_monitor.reporters import write_reports


def test_all_reports_are_well_formed_and_privacy_conscious(project_root: Path, tmp_path: Path) -> None:
    data = write_demo_dataset(tmp_path / "bad.csv", valid=False)
    result = validate_files(
        contract_path=project_root / "examples" / "contracts" / "customer_orders.yml",
        data_path=data,
        record_history=False,
    )
    output = tmp_path / "reports"
    paths = write_reports(result, output, ["html", "json", "junit", "sarif"])
    assert len(paths) == 4
    json_payload = json.loads((output / "data_contract_report.json").read_text(encoding="utf-8"))
    sarif = json.loads((output / "data_contract_report.sarif").read_text(encoding="utf-8"))
    junit = ET.parse(output / "data_contract_report.xml").getroot()
    html = (output / "data_contract_report.html").read_text(encoding="utf-8")
    assert json_payload["summary"]["status"] == "failed"
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["tool"]["driver"]["name"] == "Data Contract Monitor"
    assert int(junit.attrib["failures"]) == result.summary.errors + result.summary.critical
    assert "<table" in html
    for secret_value in ("123-45-6789", "987-65-4321", "111-22-3333"):
        assert secret_value not in json.dumps(json_payload)
        assert secret_value not in html
        assert secret_value not in json.dumps(sarif)
