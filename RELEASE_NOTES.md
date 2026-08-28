# Data Contract Monitor 0.1.5

Catch unreliable files before they reach a report, model, or business workflow. Data Contract Monitor turns readable data expectations into actionable findings, with a local dashboard and evidence that fits automated checks.

This update fixes the reusable GitHub Action so projects can validate their data during automated checks, even without their own Python dependency file. Passing and deliberately failing datasets are now exercised through the Action itself. Existing contracts, demonstrations, reports, and local launch commands remain compatible.

## Start here

Extract the complete ZIP into a new folder and run `START_DATA_CONTRACT_MONITOR.bat`. Choose the passing demo, then the failing demo, to see how the same contract distinguishes usable data from records that need attention. Both use synthetic data and require no credentials.

Standard 64-bit Python 3.11–3.14 is required. First launch installs dependencies from the configured package index; this is not a standalone Windows executable.

## Upgrade safely

Keep the earlier extraction as rollback. Do not mix source files, launchers, wheels, or manifests from different releases. Copy only reviewed configuration or reports you want to retain.

See [README.md](README.md) for capabilities and [VERIFICATION_REPORT.md](VERIFICATION_REPORT.md) for evidence and limitations.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
