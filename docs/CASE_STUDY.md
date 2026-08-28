# Case Study: Customer Order Feed

## User story

A data-operations team publishes a customer-order extract used by operational and finance reporting. The file remains readable even when it is incomplete, stale, or structurally unsafe. The team needs a reviewable contract that can also stop a CI job.

## Contract expectations

- Stable, unique, non-null order identifier
- Non-null customer identifier with no more than 1% missing values
- Order timestamp no older than 48 hours
- Non-negative numeric amount
- Approved status enumeration
- Valid optional customer email
- No unapproved columns without review
- Review signal when a potentially sensitive category is introduced

## Passing scenario

The generated passing dataset contains three current, unique, conforming rows. Result:

```text
Status: PASSED
Rows: 3
Findings: 0
```

## Failing scenario

The generated failing dataset introduces:

- one null order identifier;
- a duplicate order identifier affecting two rows;
- one null customer identifier;
- a 33.33% customer-ID null ratio;
- one timestamp older than the freshness limit;
- one unapproved status;
- one negative amount;
- one invalid email;
- one invalid datetime;
- one nonnumeric amount;
- an undeclared `customer_ssn` column;
- a high-confidence unapproved government-ID signal.

Measured result in the verified release:

```text
Status: FAILED
Rows: 3
Critical: 2
Errors: 8
Warnings: 2
Total findings: 12
Raw source values in result: 0
```

## Decision value

A consumer can stop the dataset before it reaches a dashboard while still distinguishing the two warning-level review items from critical business-key failures. The HTML report supports human review; JSON supports downstream automation; JUnit supports common test dashboards; SARIF supports code-scanning-style evidence.

## Limit of the result

The privacy signal does not prove the field contains legally regulated data. It creates a visible review obligation. Likewise, the tool proves that the configured checks ran against a specific file hash; it does not prove that the contract is complete or that the source system is correct.
