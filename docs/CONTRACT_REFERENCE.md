# Contract Reference

Contracts are YAML documents validated strictly with Pydantic. Unknown keys are rejected so misspelled enforcement settings do not silently become comments.

## Root fields

| Field | Type | Default | Purpose |
|---|---|---|---|
| `contract_version` | string | `1.0` | Native contract format version |
| `dataset` | object | required | Dataset identity and schema policy |
| `rules` | mapping | empty | Per-column rules keyed by column name |
| `dataset_rules` | list | empty | Rules spanning rows or columns |
| `privacy` | object | defaults shown below | Heuristic privacy review |

## Dataset

```yaml
dataset:
  name: customer_orders
  description: Order events used by operations reporting.
  owner: Data Operations
  required_columns: [order_id, customer_id]
  allow_extra_columns: false
  extra_columns_severity: warning
```

Every key under `rules` is also normalized into `required_columns`. A rule is therefore never silently skipped because its target column disappeared.

## Column rules

| Field | Accepted values | Behavior |
|---|---|---|
| `type` | `any`, `string`, `integer`, `number`, `boolean`, `date`, `datetime`, `email`, `uuid` | Logical compatibility check |
| `nullable` | boolean | Whether null values are permitted |
| `unique` | boolean | Whether non-null values must be unique |
| `strict_type` | boolean | For strings, require values to arrive as strings rather than coercing |
| `minimum`, `maximum` | number | Numeric boundaries |
| `min_length`, `max_length` | non-negative integer | Text-length boundaries |
| `pattern` | regular expression | Full-string match; invalid expressions fail contract loading |
| `allowed_values` | list | Approved enumeration |
| `maximum_age_hours` | positive number | UTC-relative freshness limit for parseable timestamps |
| `severity` | `info`, `warning`, `error`, `critical` | Finding severity |
| `description` | string | Documentary business definition |
| `classification` | string | Documentary classification carried from the contract |

Rows in findings are one-based data-row positions. SARIF adds one line for the header when identifying a physical CSV location.

## Dataset rules

### Row count

```yaml
- name: expected_volume
  type: row_count
  minimum: 1
  maximum: 1000000
  severity: error
```

### Composite uniqueness

```yaml
- name: order_customer_key
  type: unique_combination
  columns: [order_id, customer_id]
```

### Null ratio

```yaml
- name: customer_completeness
  type: null_ratio
  column: customer_id
  max_ratio: 0.01
```

### Conditional completeness

```yaml
- name: approval_reference_required
  type: conditional_not_null
  when_column: status
  when_equals: approved
  then_column: approval_reference
```

## Privacy review

```yaml
privacy:
  detect_pii: true
  allowed_categories: [email, account_identifier]
  fail_on_unapproved: false
  severity: warning
```

Supported heuristic categories are `email`, `phone`, `government_id`, `payment_card`, `ip_address`, `date_of_birth`, `address`, `person_name`, and `account_identifier`.

Detection uses column-name patterns and at most 200 sampled non-null values per column. Results contain match counts and confidence only. A signal is not proof of personal information and should not be used as an autonomous deletion, blocking, or regulatory decision.

## ODCS v3.1 adapter

The first release supports one schema object per validation run and maps:

- `name` or `physicalName`
- `logicalType` or `physicalType`
- `required`
- `unique` or `primaryKey`
- `classification`
- property-level `nullValues` and duplicate quality checks
- schema-object `rowCount` quality checks
- team owner metadata

Unmapped ODCS metadata remains documentary and is not silently enforced. The `adapter_notes` field records this boundary in the internal contract model. Select an object with `--object` when an ODCS document has multiple schema objects.

## JSON Schemas

Editor-oriented schemas are generated into:

- `schemas/native-contract.schema.json`
- `schemas/validation-result.schema.json`

Regenerate them with:

```bash
python tools/generate_schemas.py
```
