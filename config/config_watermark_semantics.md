# Watermark Semantics and Failure Scenarios (Task 2.5)

## 1. Premature Watermark Persistence Risk
If the watermark state is saved to `state/api_watermark.json` **before** writing raw output to `raw/api/events.jsonl` succeeds, any crash, disk write failure, network timeout, or process termination occurring during the write phase will result in **permanent data loss**. 

On subsequent execution, the pipeline reads the advanced watermark and queries only records updated after that timestamp. Consequently, the fetched batch that failed to persist is permanently skipped without ever landing in raw storage.

**Engineering Requirement**: Watermark advancement must be atomic and strictly executed only **after** the raw payload is durably written to storage.

---

## 2. Shared Timestamp Collisions (`updated_after > watermark`)
When using `updated_after > watermark` filtering logic, if multiple distinct records share the exact same `updated_at` timestamp equal to the max timestamp of a batch:
- Records with that exact timestamp processed in batch $N$ set the watermark $W$.
- Batch $N+1$ requests records where `updated_at > W`.
- Any remaining uningested records sharing timestamp $W$ that were not included in batch $N$ (e.g., due to pagination boundaries or concurrent transaction commits) will be excluded from retrieval.

---

## 3. Watermark Limitations & Production Mitigations

| System Limitation | Production-Grade Mitigation |
| :--- | :--- |
| **Data Loss on Failure** | Implement **two-phase commit / atomic renames**: Write output to a temporary file (`events.jsonl.tmp`), flush to disk, rename to final output destination, and then persist updated state. |
| **Timestamp Collisions / Late Data** | Use **inclusive bounds with deduplication** (`updated_at >= watermark`) or track state using a monotonically increasing sequence ID / transaction log sequence number (LSN / Change Data Capture) rather than non-unique wall-clock timestamps. |
| **Clock Skew / Distributed Writes** | Implement a **watermark lookback window** (e.g., query `updated_after > (watermark - 5 minutes)`) coupled with downstream deterministic deduplication on `event_id`. |
