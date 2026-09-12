# Source Profiling Report

## 1. Source Inventory

| Source | Type | Rows/Records | Key                        | Update Pattern | Quality Findings |
|---|---|---:|----------------------------|---|---|
| customers.csv | CSV (flat, text) | 250 | `customer_id` (not unique, 3 dupes) | Likely batch export/snapshot from a customer/CRM system | 2 exact duplicate rows; 3 missing `email`; 2 missing `city`; `customer_id` not unique |
| orders.json | JSON (nested, array of records) | 250 | `order_id`; references `customer_id` | Likely event/transaction export, one record per order | Nested `shipping` object (`region`, `method`); no missing-value/duplicate issues reported |
| products.parquet | Parquet (columnar, binary, typed) | 200 | `product_id`               | Likely periodic batch export from an analytics/warehouse layer | Native types preserved (`float64`, `int32`, `str`); no missing-value/duplicate issues reported |

## 2. Schema Findings

- **customers.csv** — 7 columns, all typed as plain `str` (`customer_id, first_name, last_name, email, city, signup_date, customer_segment`). CSV carries no native type system, so numeric-looking or date-looking fields (e.g. `signup_date`) are stored as text and must be parsed/cast downstream. There is no structural enforcement of uniqueness or non-nullability.
- **orders.json** — 9 top-level keys per record (`order_id, customer_id, order_timestamp, status, item_count, subtotal, shipping_fee, total_amount, shipping`). JSON preserves basic type distinctions (string/number/null) and supports **nesting** — the `shipping` field is a nested object with sub-keys `region` and `method`. However, JSON enforces no schema consistency across records; a field could technically vary in type or be absent from one record without violating the format.
- **products.parquet** — 7 columns with an embedded, enforced schema: `product_id` (str), `product_name` (str), `category` (str), `brand` (str), `unit_price` (float64), `stock_quantity` (int32), `weight_kg` (float64). Types are stored as file metadata and preserved exactly on read — no inference or casting required. Parquet is strictly tabular/columnar; it does not naturally represent nested structures the way `orders.json` does.

**Cross-source comparison:** CSV = no types, no nesting, weakest schema guarantees. JSON = loose types, supports nesting, no cross-record schema enforcement. Parquet = strict types, embedded schema, strictly flat/tabular, no nesting.

## 3. Data Quality Findings

**customers.csv**
- Missing values: `email` (3), `city` (2); all other columns complete.
- 2 exact duplicate rows.
- `customer_id` is **not unique**; 3 duplicate `customer_id` values found, which breaks its usability as a clean join key until deduplicated.

**orders.json**
- No missing values or duplicate records reported.
- Structural risk: since `shipping` is a nested object, downstream flattening (e.g., into a table) needs a defined convention (e.g., `shipping.region`, `shipping.method`) and should be checked for missing/inconsistent sub-keys across records.

**products.parquet**
- No missing values or duplicates reported.
- Because Parquet enforces schema on write, type inconsistencies are unlikely, but the file should still be checked for logical issues (e.g., negative `stock_quantity`, zero/negative `unit_price` or `weight_kg`) that a strict type system won't catch.

**Overall:** `customers.csv` is the weakest-quality source and needs deduplication and a decision on how to handle the non-unique `customer_id` before it can reliably be used as a join key against `orders.json`.

## 4. Recommended Acquisition Method

- **customers.csv** — Treat as a periodic **batch/snapshot pull** (e.g., scheduled export or file drop) rather than a live feed, since CSV has no native change-tracking. On ingestion: deduplicate exact row duplicates, resolve/investigate the 3 duplicate `customer_id` values (decide on a canonical record per ID), and explicitly cast `signup_date` to a date type.
- **orders.json** — Also suited to **batch pull**, but as an append-only or incremental extract (e.g., "orders since last run") given it likely represents transactional/event data. On ingestion: flatten the nested `shipping` object into discrete columns and validate `order_timestamp` typing.
- **products.parquet** — Given Parquet's columnar, analytics-oriented design, this is best acquired via **bulk/batch load from a warehouse or analytics layer** rather than treated as a live operational feed. Its enforced schema and native types make it the easiest of the three to load directly into an analytical store with minimal transformation.

## 5. Risks and Assumptions

- **Assumption:** `customer_id` in `orders.json` is meant to join to `customer_id` in `customers.csv`; this is not explicitly confirmed and should be validated against real referential integrity (e.g., checking for orphaned `customer_id` values in `orders.json` with no match in `customers.csv`).
- **Risk:** The non-unique `customer_id` in `customers.csv` could cause fan-out (duplicate rows) if joined directly to `orders.json` without first deduplicating.
- **Risk:** Missing `email`/`city` values in `customers.csv` may cause downstream failures in any process that assumes completeness (e.g., email marketing, geographic segmentation).
- **Risk:** No information is available on the *cadence* or *freshness* of these files — whether they are one-time exports or recurring feeds — which affects whether a batch pipeline needs full-refresh or incremental-load logic.
- **Risk:** Parquet's strict typing prevents type mismatches but does not validate business logic (e.g., invalid negative prices or quantities); it should not be assumed "clean" just because it's schema-enforced.
- **Assumption:** File sizes and row counts profiled here (250 customers, 250 orders, 200 products) represent a full and representative sample of the source systems, not a partial or filtered extract.
