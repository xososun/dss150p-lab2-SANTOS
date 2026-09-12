"""Starter validation checks for raw outputs."""
from pathlib import Path
from datetime import datetime
import json
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT / 'raw'
STATE=ROOT / 'state'

def validate_file_existence():
    """Assert expected raw files exist."""
    expected_files = [
        RAW / 'files' / 'customers.csv',
        RAW / 'files' / 'orders.json',
        RAW / 'files' / 'products.parquet',
        RAW / 'files' / 'manifest.csv',
        RAW / 'api' / 'events.jsonl',
        STATE / 'api_watermark.json'
    ]
    for file_path in expected_files:
        assert file_path.exists(), f"❌ Missing expected raw file: {file_path}"
    print("✅ File existence checks passed.")


def validate_api_records_and_watermark():
    """Assert unique event_ids, required metadata, parseable timestamps, and watermark consistency."""
    events_file = RAW / 'api' / 'events.jsonl'
    watermark_file = STATE / 'api_watermark.json'

    records = []
    with events_file.open('r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    raise AssertionError(f"❌ Malformed JSON on line {line_num} in {events_file}: {e}")

    assert len(records) > 0, "❌ No records found in events.jsonl"

    event_ids = set()
    max_updated_at = None

    for record in records:
        # 1. Required metadata fields present
        assert '_ingested_at' in record, "❌ Missing '_ingested_at' metadata field in record"
        assert '_source' in record, "❌ Missing '_source' metadata field in record"
        assert record['_source'] == 'rest_api', f"❌ Unexpected _source value: {record['_source']}"

        # 2. API event_ids unique
        e_id = record.get('event_id')
        assert e_id is not None, "❌ Record missing 'event_id'"
        assert e_id not in event_ids, f"❌ Duplicate event_id detected in raw output: {e_id}"
        event_ids.add(e_id)

        # 3. updated_at parseable
        updated_at_str = record.get('updated_at')
        assert updated_at_str is not None, "❌ Record missing 'updated_at'"
        try:
            # Parse ISO 8601 timestamp string
            parsed_ts = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
        except ValueError:
            raise AssertionError(f"❌ Unparseable 'updated_at' timestamp format: {updated_at_str}")

        if max_updated_at is None or updated_at_str > max_updated_at:
            max_updated_at = updated_at_str

    print(f"✅ Unique event_ids check passed ({len(event_ids)} records verified).")
    print("✅ Metadata and timestamp format checks passed.")

    # 4. Watermark equals max updated_at after ingestion
    watermark_data = json.loads(watermark_file.read_text(encoding='utf-8'))
    saved_watermark = watermark_data.get('updated_at')

    assert saved_watermark == max_updated_at, (
        f"❌ Watermark mismatch! Saved: {saved_watermark}, Expected max updated_at: {max_updated_at}"
    )
    print(f"✅ Watermark consistency check passed ({saved_watermark}).")

def main():
    try:
        validate_file_existence()
        validate_api_records_and_watermark()
        print("\n🎉 ALL RAW VALIDATION CHECKS PASSED SUCCESSFULLY!")
    except AssertionError as e:
        print(f"\n{e}")
        exit(1)

if __name__=='__main__': main()
