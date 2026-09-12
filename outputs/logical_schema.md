# Logical Schema Design

This schema separates **source representation** (the literal type/format a
field arrives in) from **logical type** (what the field actually represents
and should be modeled/stored as downstream). Source formats like CSV and
JSON are text-based and type-poor; the logical layer restores intended
semantics (dates, timestamps, enums, decimals) regardless of how loosely
the source encodes them.

---

## 1. Entity: `customers`
*Source: `customers.csv` (flat CSV, all fields arrive as text)*

| Field Name | Source Representation | Logical Type | Nullable | Key Role | Semantic Definition |
|---|---|---|---|---|---|
| `customer_id` | string (CSV text) | `string` (surrogate/business key) | No | **Primary Key** (candidate — source has duplicates, must be deduplicated) | Unique identifier assigned to a customer at signup; intended to be the stable join key to orders/events. |
| `first_name` | string (CSV text) | `string` | No | — | Customer's given name, as self-reported at signup. |
| `last_name` | string (CSV text) | `string` | No | — | Customer's family/surname, as self-reported at signup. |
| `email` | string (CSV text) | `string` (email-formatted) | Yes | Alternate/natural key candidate | Customer's contact email address; used for communication and potentially as a secondary de-duplication signal. |
| `city` | string (CSV text) | `string` (categorical/geographic) | Yes | — | Self-reported city of residence, used for geographic segmentation. |
| `signup_date` | string (CSV text, e.g. `"2024-03-11"`) | `date` | No | — | Calendar date the customer account was created; arrives as plain text in the source but logically represents a date, not free text. |
| `customer_segment` | string (CSV text) | `enum`/categorical `string` (constrained to a defined value set) | No | — | Business-assigned classification of the customer (e.g., new, loyal, high-value) used for targeting and reporting. |

**Notes:**
- `customer_id` is modeled as the primary key logically, but the *source* does not enforce uniqueness (3 duplicate values observed) — a deduplication/survivorship rule must run before this key can be trusted downstream.
- `signup_date` is a clear example of source vs. logical type divergence: CSV stores it as unstructured text, but it logically behaves as a `date` (sortable, comparable, usable in date-range filters).

---

## 2. Entity: `api_events`
*Source: paginated REST API response (JSON envelope with an `items` array of event records)*

**Source envelope (pagination wrapper — not part of the event entity itself):**
```
{ "page": ..., "per_page": ..., "total": ..., "has_more": ..., "next_page": ..., "items": [ ... ] }
```
The logical entity below models a single record from `items`; the envelope fields (`page`, `per_page`, `total`, `has_more`, `next_page`) are pagination metadata about the *response*, not attributes of an event, and are not modeled as entity fields.

| Field Name | Source Representation | Logical Type | Nullable | Key Role | Semantic Definition |
|---|---|---|---|---|---|
| `event_id` | string (JSON text, e.g. `"E0001"`) | `string` (surrogate key) | No | **Primary Key** | Unique identifier for a single customer event/interaction captured by the API. |
| `customer_id` | string (JSON text, e.g. `"C0024"`) | `string` | No | **Foreign Key** → `customers.customer_id` | Identifies which customer the event is attributed to; the join key back to the `customers` entity. |
| `event_type` | string (JSON text) | `enum`/categorical `string` (observed values: `page_view`, `add_to_cart`, `checkout`, `payment`, `support`) | No | — | The category/type of interaction the event represents, spanning both behavioral (browsing) and transactional (payment) activity. |
| `amount` | number (JSON float) | `decimal`/`numeric` (currency, fixed precision e.g. 2 decimals) | Yes* | — | Monetary value associated with the event (e.g., cart or payment value); logically only meaningful for transactional event types — see note below. |
| `updated_at` | string (JSON text, ISO-8601, e.g. `"2026-08-01T11:00:00"`, no timezone offset present) | `timestamp` (datetime; timezone to be confirmed/assumed UTC) | No | — | The date and time the event record was last created/updated; arrives as JSON text but logically represents a point-in-time timestamp usable for sequencing and time-window analysis. |
| `metadata.channel` | string (nested JSON object field) | `enum`/categorical `string` (observed values: `partner`, `mobile`, `web`) | Yes | — | The acquisition/interaction channel through which the event occurred; flattened from the nested `metadata` object. |
| `metadata.campaign` | string (nested JSON object field, `"none"` used as a sentinel) | `enum`/categorical `string`, nullable (observed values: `none`, `retarget`, `launch`) | Yes | — | The marketing campaign associated with the event, if any; flattened from the nested `metadata` object. The literal string `"none"` should be treated as a logical NULL/no-campaign value, not a distinct category, unless intentionally preserved as its own label. |

**Notes:**
- `updated_at` is another clear source-vs-logical example: it is delivered as JSON text without an explicit timezone offset, but logically represents a `timestamp` — the timezone assumption (likely UTC, given the hourly cadence in sample data) should be confirmed with the source system rather than assumed silently.
- `amount` is typed as `decimal`/`numeric` rather than a generic float to avoid floating-point rounding issues in downstream financial aggregation, even though the source JSON encodes it as a plain number. *Nullability of `amount` is marked as a design question: sample data shows a non-null `amount` on every event type, including `page_view`, which is semantically odd (a page view typically has no monetary value) — this should be confirmed with the source system; it may indicate `amount` is overloaded/mismodeled upstream (e.g., cart value at time of event) rather than truly representing "amount of the event."
- `event_type` and `metadata.channel`/`metadata.campaign` are modeled as constrained enums based on values observed in the current sample; the full set of allowed values should be confirmed against API documentation, since new/unseen values could appear in later pages.
- The nested `metadata` object is flattened into `metadata.channel` and `metadata.campaign` to fit a flat, relational logical model — the source JSON nesting does not need to be preserved 1:1 in the logical schema.
- This paginated API is a *different source* from the earlier `orders.json` file for the same conceptual "orders/events" domain; if both are meant to represent the same business events, the two schemas (order-centric fields like `subtotal`/`shipping` vs. event-centric fields like `event_type`/`metadata`) will need to be reconciled or treated as two distinct entities feeding different downstream needs.

---

## 3. Relationship Summary

- `customers.customer_id` (1) → `api_events.customer_id` (many): one customer can generate multiple events (page views, cart adds, checkouts, payments, support interactions).
- Referential integrity should be validated in both directions: every `customer_id` in `api_events` should resolve to a record in `customers`, and the `customer_id` deduplication issue in the source `customers.csv` must be resolved before this relationship can be enforced reliably as a true foreign key.
- Acquisition implication: because `api_events` is delivered via a **paginated API** (`page`/`per_page`/`has_more`/`next_page`), ingestion must page through the full result set (122 total records observed) rather than assuming a single response contains all records — unlike the flat-file sources (`customers.csv`, `products.parquet`).
