from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from data_contract_monitor.cli import app
from data_contract_monitor.demo import write_demo_dataset


runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "0.2.2" in result.stdout


def test_validate_exit_codes(project_root: Path, tmp_path: Path) -> None:
    contract = project_root / "examples" / "contracts" / "customer_orders.yml"
    good = write_demo_dataset(tmp_path / "good.csv", valid=True)
    bad = write_demo_dataset(tmp_path / "bad.csv", valid=False)
    good_result = runner.invoke(
        app,
        ["validate", "--contract", str(contract), "--data", str(good), "--output-dir", str(tmp_path / "good-out"), "--no-history"],
    )
    bad_result = runner.invoke(
        app,
        ["validate", "--contract", str(contract), "--data", str(bad), "--output-dir", str(tmp_path / "bad-out"), "--no-history"],
    )
    assert good_result.exit_code == 0
    assert bad_result.exit_code == 2
    assert (tmp_path / "good-out" / "data_contract_report.html").is_file()
    assert "FAILED" in bad_result.stdout
