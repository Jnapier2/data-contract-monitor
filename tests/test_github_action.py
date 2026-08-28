"""Keep published integration metadata parseable and exercise its data fixtures."""
from pathlib import Path

import pytest
import yaml

from data_contract_monitor.engine import validate_files

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("path", ["action.yml", ".github/workflows/ci.yml", ".github/workflows/release.yml", ".github/dependabot.yml"])
def test_github_yaml_parses(path):
    assert isinstance(yaml.safe_load((ROOT / path).read_text(encoding="utf-8")), dict)


def test_composite_action_is_caller_independent():
    action = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
    assert action["runs"]["using"] == "composite"
    setup, install, validate = action["runs"]["steps"]
    assert setup["with"]["cache-dependency-path"] == "${{ github.action_path }}/requirements.lock"
    assert 'requirements.lock' in install["run"]
    assert '--no-deps' in install["run"]
    assert validate["env"]["DCM_HOME"] == "${{ github.workspace }}/.dcm/runtime"


@pytest.mark.parametrize("scenario,passed,count", [("good", True, 0), ("bad", False, 1)])
def test_action_smoke_fixture(scenario, passed, count):
    fixtures = ROOT / "tests" / "fixtures"
    result = validate_files(contract_path=fixtures / "action-contract.yml",
                            data_path=fixtures / f"action-{scenario}.csv", record_history=False)
    assert result.summary.passed is passed
    assert result.summary.findings_total == count
