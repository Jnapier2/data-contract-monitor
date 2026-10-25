# Recruiter and Hiring-Team Review

## Fast path

1. Download the [v0.3.4 application ZIP](https://github.com/Jnapier2/data-contract-monitor/releases/tag/v0.3.4), use **Extract All**, and open the complete extracted folder; do not launch from the compressed-folder preview.
2. Double-click `START_DATA_CONTRACT_MONITOR.bat` on Windows, or run `./tools/start.sh` on Linux/macOS.
3. Run the passing and failing demos.
4. Open the [sample report screenshot](assets/sample-report.png) when a live launch is not convenient.
5. Read the [qualification scope](../VERIFICATION_REPORT.md), [dated package receipt](https://github.com/Jnapier2/data-contract-monitor/releases/download/v0.3.4/Data_Contract_Monitor_v0.3.4_Verification_Receipt.json), and [hosted CI runs](https://github.com/Jnapier2/data-contract-monitor/actions/workflows/ci.yml) as separate evidence. The package receipt records identity and static Windows checks; it does not establish native Windows execution.

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
| Tests, qualification scope, and dated receipts | Inspectable checks and transparent limits |
| Manifest and diagnostics | Defensive release engineering |

## Safe evaluation

The bundled demos use generated data and need no private credentials. The first launch can install locked binary-wheel dependencies from the configured package index. Persistent status and bootstrap logs remain in the extracted project folder if setup fails. Reviewers who prefer inspection without installation can explore the [sample report screenshot](assets/sample-report.png), [example contracts and data](../examples/), [tests](../tests/), and [dated package receipt](https://github.com/Jnapier2/data-contract-monitor/releases/download/v0.3.4/Data_Contract_Monitor_v0.3.4_Verification_Receipt.json).
