# Scalable execution and exactness

Data Contract Monitor has two execution paths with one result schema.

## Memory mode

Memory mode loads the complete dataset into pandas. It is the fastest path for modest inputs and retains exact aggregate profiling. Non-streamable formats are capped by `max_in_memory_data_bytes`.

## Streaming mode

CSV and JSON Lines inputs can be processed in bounded batches. `auto` selects streaming once the input crosses the configured threshold. The validator never silently switches a rule from exact to approximate semantics.

Exact across batches:

- nullability, logical type, ranges, lengths, patterns, allowed values, and freshness;
- conditional completeness and aggregate reconciliation;
- row counts and null ratios;
- single-column uniqueness;
- composite-key uniqueness;
- cross-file `reference_exists` rules.

Global uniqueness and reference membership use a project-local temporary SQLite index containing SHA-256 key material rather than raw cell values. The index is removed when the run completes.

## Bounded profile cardinality

General profile distinct/duplicate statistics are not validation rules. To bound memory on high-cardinality data, the profiler tracks cardinality exactly only until its declared budget is reached. A lower-bound count is then returned with `distinct_count_exact=false` / `duplicate_count_exact=false`, and the profile is labeled `bounded`.

This does not alter exact uniqueness enforcement. Validation result `exactness` fields make the distinction explicit.

## Resource policy

Default budgets include total input bytes, a stricter in-memory file cap, rows, columns, header/field lengths, regex length, JSON nesting, Excel sheet count, finding count, report bytes, execution time, free disk, batch rows, privacy sample rows, and profile-cardinality tracking.

A budget violation stops the run with an execution error rather than publishing a misleading successful result.
