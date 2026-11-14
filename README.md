# Data Contract Monitor 0.4.1 reviewer demo

Data Contract Monitor helps analysts and data stewards see whether an incoming dataset meets the rules its consumers expect. Compare two captured runs on fictional customer orders to see how it turns quality problems into findings someone can review.

1. Download the reviewer demo ZIP and extract it.
2. Open `index.html` in your browser. No account, connection, or installation is needed.
3. Compare **Passing demo** and **Failing demo**. The failing example separates important key and value problems from schema and privacy warnings.
4. Open the sanitized JSON from either result page to inspect how the evidence is structured. Save the JSON file from your browser if you want to keep a copy.

Both scenarios were run on Windows on November 14, 2026 using Data Contract Monitor 0.4.1. The passing fixture reported zero findings across three rows. The failing fixture reported two critical findings, eight errors, and two warnings across three rows. These are results from generated examples. The offline pages display the captured results and do not process new files.

The separate [0.3.4 application release](https://github.com/Jnapier2/data-contract-monitor/releases/tag/v0.3.4) remains available for running validation. This demo includes its own [license](LICENSE) and [notice](NOTICE).

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
