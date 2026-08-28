from __future__ import annotations

from pathlib import Path

from data_contract_monitor.runtime import bundled_demo_contract, ensure_runtime_directories, runtime_root


def test_explicit_runtime_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DCM_HOME", str(tmp_path / "configured"))
    root = runtime_root()
    assert root == (tmp_path / "configured").resolve()
    ensure_runtime_directories(root)
    assert (root / "exports").is_dir()
    assert not (root / "diagnostics" / "exports").exists()
    assert (root / "reports").is_dir()


def test_bundled_demo_contract_exists() -> None:
    assert bundled_demo_contract().is_file()

def test_bootstrap_project_root_alias(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DCM_HOME", raising=False)
    monkeypatch.setenv("DCM_PROJECT_ROOT", str(tmp_path / "project-root"))
    assert runtime_root() == (tmp_path / "project-root").resolve()


def test_dcm_home_takes_precedence(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DCM_HOME", str(tmp_path / "home-root"))
    monkeypatch.setenv("DCM_PROJECT_ROOT", str(tmp_path / "project-root"))
    assert runtime_root() == (tmp_path / "home-root").resolve()

