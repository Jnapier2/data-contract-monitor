from __future__ import annotations

import json
import os
import secrets
import sys
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path

import typer
import uvicorn

from . import __build_id__, __version__
from rich.console import Console
from rich.table import Table

from .artifacts import publish_run_artifacts
from .contract_loader import ContractLoadError, load_contract
from .demo import write_demo_dataset
from .diagnostics import DiagnosticManager, install_exception_hooks
from .drift import compare_profile, load_baseline, snapshot_from_profile, write_baseline
from .engine import ValidationExecutionError, validate_files
from .identity import find_project_root, verify_release_integrity
from .io import DataReadError, read_dataset
from .local_server import (
    DEFAULT_PORT,
    DEFAULT_PORT_SEARCH_LIMIT,
    PortReservationError,
    open_browser_when_ready,
    record_endpoint,
    reserve_endpoint,
)
from .models import SEVERITY_ORDER, Severity
from .profiler import profile_dataset
from .reporters import ReportFormatError, write_reports
from .runtime import bundled_demo_contract, ensure_runtime_directories, runtime_root
from .state_store import StateStore

app = typer.Typer(
    name="data-contract-monitor",
    help="Validate datasets against executable contracts and produce privacy-conscious evidence.",
    no_args_is_help=True,
    add_completion=False,
)
baseline_app = typer.Typer(help="Create and compare schema baselines.", no_args_is_help=True)
app.add_typer(baseline_app, name="baseline")
console = Console()


def _default_output_dir(contract_path: Path, run_id: str) -> Path:
    return contract_path.parent / ".dcm" / "reports" / run_id


def _print_summary(result: object) -> None:
    summary = result.summary
    table = Table(title=f"Data Contract Monitor — {result.dataset_name}")
    table.add_column("Status")
    table.add_column("Rows", justify="right")
    table.add_column("Critical", justify="right")
    table.add_column("Errors", justify="right")
    table.add_column("Warnings", justify="right")
    table.add_column("Runtime", justify="right")
    style = "green" if summary.passed else "red bold"
    table.add_row(
        f"[{style}]{summary.status.upper()}[/{style}]",
        f"{result.profile.row_count:,}",
        str(summary.critical),
        str(summary.errors),
        str(summary.warnings),
        f"{result.duration_ms} ms",
    )
    console.print(table)
    for finding in result.findings[:10]:
        console.print(
            f"[{finding.severity.value.upper()}] {finding.title}"
            f"{f' — {finding.column}' if finding.column else ''}: {finding.message}",
            markup=False,
        )
    if len(result.findings) > 10:
        console.print(f"…and {len(result.findings) - 10} additional finding(s).")


@app.command("validate")
def validate_command(
    contract: Path = typer.Option(..., "--contract", "-c", exists=True, file_okay=True, dir_okay=False, readable=True),
    data: Path = typer.Option(..., "--data", "-d", exists=True, file_okay=True, dir_okay=False, readable=True),
    baseline: Path | None = typer.Option(None, "--baseline", exists=True, file_okay=True, dir_okay=False),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o"),
    formats: str = typer.Option("html,json", "--formats", help="Comma-separated: html,json,junit,sarif"),
    fail_on: Severity = typer.Option(Severity.ERROR, "--fail-on", case_sensitive=False),
    object_name: str | None = typer.Option(None, "--object", help="ODCS schema object name or physicalName"),
    sheet: str = typer.Option("0", "--sheet", help="Excel sheet name or zero-based index"),
    no_history: bool = typer.Option(False, "--no-history"),
) -> None:
    """Validate one dataset and emit CI-friendly reports."""
    try:
        sheet_value: str | int = int(sheet) if sheet.isdigit() else sheet
        root = find_project_root()
        history_path = None
        if root and not no_history:
            history_path = ensure_runtime_directories(root) / "state" / "dcm_state.sqlite3"
        result = validate_files(
            contract_path=contract.resolve(),
            data_path=data.resolve(),
            baseline_path=baseline.resolve() if baseline else None,
            fail_on=fail_on,
            object_name=object_name,
            sheet_name=sheet_value,
            record_history=not no_history,
            history_path=history_path,
        )
        if root and output_dir is None:
            destination = publish_run_artifacts(result, root=root, formats=formats.split(","))
            report_paths = sorted(path for path in destination.iterdir() if path.is_file())
        else:
            destination = (output_dir or _default_output_dir(contract.resolve(), result.run_id)).resolve()
            report_paths = write_reports(result, destination, formats.split(","))
        _print_summary(result)
        console.print("Reports:")
        for path in report_paths:
            console.print(f"  {path}")
        raise typer.Exit(code=0 if result.summary.passed else 2)
    except (ContractLoadError, DataReadError, ReportFormatError, ValidationExecutionError) as exc:
        console.print(f"[red]Validation could not run:[/red] {exc}")
        raise typer.Exit(code=3) from exc


@app.command("profile")
def profile_command(
    data: Path = typer.Option(..., "--data", "-d", exists=True, file_okay=True, dir_okay=False, readable=True),
    output: Path | None = typer.Option(None, "--output", "-o"),
    sheet: str = typer.Option("0", "--sheet"),
) -> None:
    """Create an aggregate dataset profile without exposing raw values."""
    try:
        sheet_value: str | int = int(sheet) if sheet.isdigit() else sheet
        profile = profile_dataset(read_dataset(data.resolve(), sheet_name=sheet_value))
    except DataReadError as exc:
        console.print(f"[red]Profile failed:[/red] {exc}")
        raise typer.Exit(code=3) from exc
    payload = profile.model_dump_json(indent=2) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        console.print(f"Profile written to {output.resolve()}")
    else:
        console.print_json(payload)


@baseline_app.command("create")
def baseline_create(
    contract: Path = typer.Option(..., "--contract", "-c", exists=True, file_okay=True, dir_okay=False),
    data: Path = typer.Option(..., "--data", "-d", exists=True, file_okay=True, dir_okay=False),
    output: Path = typer.Option(..., "--output", "-o"),
    object_name: str | None = typer.Option(None, "--object"),
) -> None:
    """Create an approved schema snapshot from a reviewed dataset."""
    try:
        loaded = load_contract(contract.resolve(), object_name=object_name)
        profile = profile_dataset(read_dataset(data.resolve()), include_pii=False)
        write_baseline(output.resolve(), snapshot_from_profile(loaded.dataset.name, profile))
        console.print(f"Baseline written to {output.resolve()}")
    except (ContractLoadError, DataReadError) as exc:
        console.print(f"[red]Baseline creation failed:[/red] {exc}")
        raise typer.Exit(code=3) from exc


@baseline_app.command("compare")
def baseline_compare(
    data: Path = typer.Option(..., "--data", "-d", exists=True, file_okay=True, dir_okay=False),
    baseline: Path = typer.Option(..., "--baseline", "-b", exists=True, file_okay=True, dir_okay=False),
) -> None:
    """Compare a dataset's observed schema with an approved baseline."""
    try:
        profile = profile_dataset(read_dataset(data.resolve()), include_pii=False)
        drift = compare_profile(profile, load_baseline(baseline.resolve()), baseline.resolve())
    except (DataReadError, ValueError) as exc:
        console.print(f"[red]Baseline comparison failed:[/red] {exc}")
        raise typer.Exit(code=3) from exc
    if not drift.changes:
        console.print("[green]No schema drift detected.[/green]")
        return
    table = Table("Severity", "Change", "Column", "Before", "After")
    for change in drift.changes:
        table.add_row(
            change.severity.value,
            change.change_type,
            change.column,
            str(change.before or "—"),
            str(change.after or "—"),
        )
    console.print(table)
    failed = any(SEVERITY_ORDER[item.severity] >= SEVERITY_ORDER[Severity.ERROR] for item in drift.changes)
    raise typer.Exit(code=2 if failed else 0)


@app.command("demo")
def demo_command(
    scenario: str = typer.Option("bad", "--scenario", help="good or bad"),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o"),
) -> None:
    """Run a credential-free demonstration with dynamically generated data."""
    if scenario not in {"good", "bad"}:
        console.print("[red]Scenario must be 'good' or 'bad'.[/red]")
        raise typer.Exit(code=3)
    root = ensure_runtime_directories(runtime_root())
    temp_dir = root / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dcm_demo_", dir=temp_dir) as directory:
        data_path = write_demo_dataset(Path(directory) / f"customer_orders_{scenario}.csv", valid=scenario == "good")
        result = validate_files(
            contract_path=bundled_demo_contract(),
            data_path=data_path,
            history_path=root / "state" / "dcm_state.sqlite3",
        )
        if output_dir:
            destination = output_dir.resolve()
            report_paths = write_reports(result, destination, ["html", "json", "junit", "sarif"])
        else:
            destination = publish_run_artifacts(result, root=root)
            report_paths = sorted(path for path in destination.iterdir() if path.is_file())
        _print_summary(result)
        for path in report_paths:
            console.print(f"  {path.resolve()}")
        raise typer.Exit(code=0 if result.summary.passed else 2)


@app.command("serve")
def serve_command(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(DEFAULT_PORT, "--port", min=1, max=65535),
    port_search_limit: int = typer.Option(
        DEFAULT_PORT_SEARCH_LIMIT,
        "--port-search-limit",
        min=0,
        max=100,
        help="Number of higher ports to try before using an operating-system-assigned port.",
    ),
    open_browser: bool = typer.Option(True, "--open-browser/--no-open-browser"),
) -> None:
    """Start the collision-safe local FastAPI and reviewer dashboard."""
    root = ensure_runtime_directories(runtime_root())
    integrity = verify_release_integrity(root)
    if integrity.mode == "release" and not integrity.passed:
        manager = DiagnosticManager(root)
        manager.capture_critical("runtime-identity-failure", RuntimeError("; ".join(integrity.errors)))
        console.print("[red]Release integrity verification failed.[/red]")
        for error in integrity.errors:
            console.print(f"  {error}")
        raise typer.Exit(code=4)

    try:
        endpoint = reserve_endpoint(host, port, search_limit=port_search_limit)
    except (PortReservationError, OSError, ValueError) as exc:
        console.print(f"[red]Dashboard port reservation failed:[/red] {exc}")
        raise typer.Exit(code=4) from exc

    launch_id = secrets.token_hex(16)
    os.environ["DCM_LAUNCH_ID"] = launch_id
    os.environ["DCM_API_TOKEN"] = secrets.token_hex(32)
    note = None
    if endpoint.fallback_used:
        note = (
            f"Preferred port {endpoint.preferred_port} was already in use; "
            f"Data Contract Monitor reserved {endpoint.port} instead."
        )
        console.print(f"[yellow]{note}[/yellow]")

    loopback_browser_allowed = host in {"127.0.0.1", "localhost", "::1"}
    browser_status = (
        "waiting-for-verified-identity"
        if open_browser and loopback_browser_allowed
        else "disabled"
    )
    record_endpoint(
        root,
        endpoint,
        version=__version__,
        build_id=__build_id__,
        state="reserved",
        launch_id=launch_id,
        browser_status=browser_status,
        note=note,
    )
    shutdown_event = threading.Event()

    def browser_readiness_worker() -> None:
        opened = open_browser_when_ready(
            endpoint.url,
            expected_version=__version__,
            expected_build_id=__build_id__,
            expected_launch_id=launch_id,
        )
        if shutdown_event.is_set():
            return
        record_endpoint(
            root,
            endpoint,
            version=__version__,
            build_id=__build_id__,
            state="running",
            launch_id=launch_id,
            browser_status=(
                "opened-after-verified-identity"
                if opened
                else "not-opened-health-or-browser-timeout"
            ),
            note=note,
        )

    if open_browser and loopback_browser_allowed:
        threading.Thread(
            target=browser_readiness_worker,
            name="dcm-browser-readiness",
            daemon=True,
        ).start()

    console.print(f"Data Contract Monitor is starting at {endpoint.url}")
    console.print("The browser opens only after this exact process passes its health identity check.")
    config = uvicorn.Config(
        "data_contract_monitor.api:app",
        host=endpoint.host,
        port=endpoint.port,
        log_level="info",
        workers=1,
    )
    server = uvicorn.Server(config)
    record_endpoint(
        root,
        endpoint,
        version=__version__,
        build_id=__build_id__,
        state="starting",
        launch_id=launch_id,
        browser_status=browser_status,
        note=note,
    )
    try:
        server.run(sockets=[endpoint.socket])
    finally:
        shutdown_event.set()
        try:
            endpoint.socket.close()
        except OSError:
            pass
        record_endpoint(
            root,
            endpoint,
            version=__version__,
            build_id=__build_id__,
            state="stopped",
            launch_id=launch_id,
            browser_status="closed",
            note=note,
        )


@app.command("doctor")
def doctor_command(json_output: bool = typer.Option(False, "--json")) -> None:
    """Run read-only environment, release-integrity, and demonstration checks."""
    root = ensure_runtime_directories(runtime_root())
    checks: list[dict[str, object]] = []
    integrity = verify_release_integrity(root)
    checks.append({"name": "release_integrity", "passed": integrity.passed, "detail": integrity.model_dump(mode="json")})
    checks.append({"name": "python_version", "passed": sys.version_info >= (3, 11), "detail": sys.version.split()[0]})
    for relative in ("logs", "state", "temp", "exports", "diagnostics", "reports"):
        path = root / relative
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            passed = True
            detail = str(path)
        except OSError as exc:
            passed = False
            detail = str(exc)
        checks.append({"name": f"writable_{relative}", "passed": passed, "detail": detail})
    state_health = StateStore(root / "state" / "dcm_state.sqlite3").health_check()
    checks.append({"name": "state_database", "passed": bool(state_health.get("passed")), "detail": state_health})
    try:
        with tempfile.TemporaryDirectory(prefix="dcm_doctor_", dir=root / "temp") as directory:
            data_path = write_demo_dataset(Path(directory) / "good.csv", valid=True)
            result = validate_files(
                contract_path=bundled_demo_contract(),
                data_path=data_path,
                record_history=False,
            )
            checks.append({"name": "demo_validation", "passed": result.summary.passed, "detail": result.summary.model_dump(mode="json")})
    except Exception as exc:
        checks.append({"name": "demo_validation", "passed": False, "detail": str(exc)})
    passed = all(bool(item["passed"]) for item in checks)
    if json_output:
        console.print_json(json.dumps({"passed": passed, "checks": checks}))
    else:
        table = Table("Check", "Result", "Detail")
        for item in checks:
            table.add_row(str(item["name"]), "PASS" if item["passed"] else "FAIL", str(item["detail"])[:100])
        console.print(table)
    raise typer.Exit(code=0 if passed else 4)


@app.command("export-support")
def export_support_command() -> None:
    """Create a bounded, redacted, project-local support export."""
    manager = DiagnosticManager()
    path = manager.create_manual_export()
    if path:
        console.print(f"Support export created: {path}")
    else:
        console.print("[red]Support export could not be created.[/red]")
        raise typer.Exit(code=4)


@app.command("version")
def version_command() -> None:
    """Print the installed version."""
    console.print(f"Data Contract Monitor {__version__} ({__build_id__})")


def main() -> None:
    manager = DiagnosticManager()
    install_exception_hooks(manager)
    try:
        app()
    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print("\nCancelled.")
        raise SystemExit(130) from None
    except Exception as exc:
        manager.capture_critical("terminal-cli-crash", exc)
        console.print(f"[red]Unexpected failure:[/red] {exc}")
        raise SystemExit(4) from None


if __name__ == "__main__":
    main()
