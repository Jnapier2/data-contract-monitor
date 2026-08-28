# Recruiter and Hiring-Team Review

## Fast path

1. Use **Extract All** and open the complete extracted folder; do not launch from the compressed-folder preview.
2. Double-click `START_DATA_CONTRACT_MONITOR.bat` on Windows, or run `./tools/start.sh` on Linux/macOS.
3. Run the passing and failing demos.
4. Open `docs/assets/sample-report.png` and `examples/reports/bad/data_contract_report.html` when a live launch is not convenient.
5. Review `VERIFICATION_REPORT.md` for the exact tests and environments exercised.

## What to evaluate

| Evidence | Capability shown |
|---|---|
| YAML contract | Data modeling and clear operational requirements |
| Shared rule engine | Maintainable API and domain design |
| HTML/JSON/JUnit/SARIF | Human and CI integration |
| Drift baseline | Change control and downstream-risk awareness |
| Privacy-safe profile | Security and data-governance judgment |
| TypeScript dashboard | Accessible product interface |
| FastAPI endpoints | Service design and input boundaries |
| GitHub Action and workflows | CI/CD readiness |
| Tests and verification report | Correctness and transparent limits |
| Manifest and diagnostics | Defensive release engineering |

## Safe evaluation

The bundled demos use generated data and need no private credentials. The first launch can install locked binary-wheel dependencies from the configured package index. Persistent status and bootstrap logs remain in the extracted project folder if setup fails. Reviewers who do not want a networked installation can inspect the included screenshots, reports, tests, wheel artifact, and verification receipt.
