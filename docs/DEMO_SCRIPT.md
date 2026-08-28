# Ninety-Second Demonstration Script

## 0–15 seconds: State the problem

“Readable data can still be unsafe. A missing key, stale timestamp, duplicate row, or unapproved sensitive field can flow into reports without causing a parser error.”

## 15–30 seconds: Run the passing case

Open the dashboard and select **Run passing demo**.

Point out:

- zero credentials;
- three rows evaluated;
- zero findings;
- local run history.

## 30–60 seconds: Run the failing case

Select **Run failing demo**.

Point out:

- critical duplicate and null business-key failures;
- validity, freshness, and completeness failures;
- warning-level schema and privacy review;
- severity filter and row references;
- no raw values in the privacy section.

## 60–75 seconds: Show reusable evidence

Download the JSON result or open the generated HTML report. Mention that the same result model also produces JUnit and SARIF for CI systems.

## 75–90 seconds: Show engineering depth

Open the architecture diagram and test report. Close with:

“One validation engine powers the CLI, API, dashboard, and GitHub Action, so enforcement does not change by interface. Release files are hash-verified, and terminal Critical failures produce bounded redacted diagnostics.”
