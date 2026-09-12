# Ingestion Design Matrix (Task 2.4)

## Summary Matrix

| Source | Acquisition Method | Raw Destination | Duplicate Key / Deduplication | Incremental State Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **CSV / JSON / Parquet** | File copy + manifest generation | `raw/files/` | File SHA-256 Hash | N/A (Full snapshot load per run) |
| **REST API** | Paginated HTTP GET using `updated_after` | `raw/api/events.jsonl` | `event_id` (Keep highest `updated_at`) | `max(updated_at)` stored in `state/api_watermark.json` |
| **PostgreSQL** | Inspection / bounded query extraction | N/A (Inspection only for this lab) | `ticket_id` | Timestamp watermark or Change Data Capture (CDC) |

---

## Technical Specifications

### 1. File Ingestion (`customers.csv`, `orders.json`, `products.parquet`)
- **Method**: Atomic file copy to the raw landing area (`raw/files/`).
- **Duplicate Handling**: Prior to copy, compute the SHA-256 hash of the target source file. Check the hash against `raw/files/manifest.csv`. If a matching hash is already registered, skip the file write to guarantee idempotency.
- **Manifest Tracking**: Log `source_filename`, `ingested_at` (UTC ISO 8601), `file_size_bytes`, and `sha256_hash`.

### 2. REST API Ingestion (`http://127.0.0.1:8000/api/events`)
- **Method**: Multi-page HTTP GET loop reading `page` sequentially until `has_more` returns `false`.
- **Watermark Parameter**: Pass `updated_after=<watermark>` in query parameters when a saved watermark exists in `state/api_watermark.json`.
- **Duplicate Prevention**: Ingested records from all pages are collected in-memory or in staging. If duplicate `event_id` values exist across pages or previous runs, retain only the record possessing the greatest `updated_at` value.
- **Payload Metadata**: Append `_ingested_at` (UTC timestamp) and `_source` ("rest_api") metadata attributes to each JSON record before writing to `raw/api/events.jsonl`.

### 3. PostgreSQL Ingestion (`support_tickets`)
- **Method**: Bounded query inspection using indexed primary keys (`ticket_id`).
- **Incremental Strategy**: Production implementations would extract delta records using a `WHERE updated_at > last_watermark` query or CDC pipeline (e.g., Debezium).
