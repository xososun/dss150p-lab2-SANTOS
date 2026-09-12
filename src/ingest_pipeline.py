"""Week 3 starter: rerunnable ingestion to a raw area.
Students implement file ingestion + paginated REST API ingestion + watermark + duplicate prevention.
"""
from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, shutil
import requests
import csv
import uuid

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; RAW=ROOT/'raw'; STATE=ROOT/'state'
API_URL='http://127.0.0.1:8000/api/events'
OUTPUTS=ROOT/'outputs'

def utc_now(): return datetime.now(timezone.utc).isoformat()

def sha256_file(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def load_watermark():
    p=STATE/'api_watermark.json'
    if not p.exists(): return None
    return json.loads(p.read_text())['updated_at']

def save_watermark(value):
    STATE.mkdir(exist_ok=True)
    (STATE/'api_watermark.json').write_text(json.dumps({'updated_at':value},indent=2))

def get_existing_manifest_hashes(manifest_path):
    hashes = set()
    if manifest_path.exists():
        with manifest_path.open(mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'sha256' in row and row['sha256']:
                    hashes.add(row['sha256'])
    return hashes


def log_run_event(run_id, start_time, status, source, records_read, records_written, duplicates_removed,
                  watermark_before, watermark_after, error_msg=""):
    OUTPUTS.mkdir(exist_ok=True)
    log_path = OUTPUTS / 'pipeline_run_log.csv'
    log_exists = log_path.exists()

    fieldnames = [
        'run_id', 'start_time', 'end_time', 'status', 'source',
        'records_read', 'records_written', 'duplicates_removed',
        'watermark_before', 'watermark_after', 'error_message'
    ]

    entry = {
        'run_id': run_id,
        'start_time': start_time,
        'end_time': utc_now(),
        'status': status,
        'source': source,
        'records_read': records_read,
        'records_written': records_written,
        'duplicates_removed': duplicates_removed,
        'watermark_before': watermark_before if watermark_before else '',
        'watermark_after': watermark_after if watermark_after else '',
        'error_message': error_msg
    }

    with log_path.open(mode='a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not log_exists:
            writer.writeheader()
        writer.writerow(entry)

def ingest_files():
    run_id = str(uuid.uuid4())[:8]
    start_time = utc_now()
    raw_files_dir = RAW / 'files'
    raw_files_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_files_dir / 'manifest.csv'

    existing_hashes = get_existing_manifest_hashes(manifest_path)
    manifest_exists = manifest_path.exists()
    new_manifest_entries = []

    target_files = ['customers.csv', 'orders.json', 'products.parquet']
    read_count = 0
    written_count = 0

    try:
        for filename in target_files:
            src_path = DATA / filename
            if not src_path.exists():
                print(f"Source file missing: {src_path}")
                continue

            read_count += 1
            file_hash = sha256_file(src_path)
            file_bytes = src_path.stat().st_size

            if file_hash in existing_hashes:
                print(f"Skipping '{filename}': Hash already registered in manifest.")
                continue

            dest_path = raw_files_dir / filename
            shutil.copy2(src_path, dest_path)

            new_manifest_entries.append({
                'source_file': filename,
                'ingested_at': utc_now(),
                'sha256': file_hash,
                'bytes': file_bytes
            })
            written_count += 1
            print(f"Ingested '{filename}' -> '{dest_path}'")

        if new_manifest_entries:
            fieldnames = ['source_file', 'ingested_at', 'sha256', 'bytes']
            with manifest_path.open(mode='a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not manifest_exists:
                    writer.writeheader()
                writer.writerows(new_manifest_entries)
            print(f"Appended {len(new_manifest_entries)} entry/entries to {manifest_path}")
        else:
            print("No new files ingested.")

        log_run_event(run_id, start_time, 'SUCCESS', 'files', read_count, written_count, 0, None, None)

    except Exception as e:
        log_run_event(run_id, start_time, 'FAILED', 'files', read_count, written_count, 0, None, None, str(e))
        raise e

def fetch_api_page(page, per_page=20, updated_after=None):
    params={'page':page,'per_page':per_page}
    if updated_after: params['updated_after']=updated_after
    r=requests.get(API_URL,params=params,timeout=30); r.raise_for_status(); return r.json()

def ingest_api():
    run_id = str(uuid.uuid4())[:8]
    start_time = utc_now()
    watermark_before = load_watermark()
    watermark_after = watermark_before

    raw_api_dir = RAW / 'api'
    raw_api_dir.mkdir(parents=True, exist_ok=True)

    fetched_records = []
    page = 1
    per_page = 20

    print(f"Starting API Ingestion (Watermark before: {watermark_before})...")

    try:
        # Step 1 & 2: Paginated retrieval
        while True:
            response = fetch_api_page(page=page, per_page=per_page, updated_after=watermark_before)
            items = response.get('items', [])

            # Step 3: Metadata attachment
            ingest_time = utc_now()
            for item in items:
                item['_ingested_at'] = ingest_time
                item['_source'] = 'rest_api'
                fetched_records.append(item)

            if not response.get('has_more', False):
                break
            page = response.get('next_page', page + 1)

        records_read = len(fetched_records)
        print(f"Retrieved {records_read} total records across pages.")

        if records_read == 0:
            print("No new API events retrieved.")
            log_run_event(
                run_id, start_time, 'SUCCESS', 'rest_api',
                0, 0, 0, watermark_before, watermark_before
            )
            return

        # Step 4: Deduplicate by event_id keeping highest updated_at
        dedup_map = {}
        for record in fetched_records:
            e_id = record['event_id']
            if e_id not in dedup_map:
                dedup_map[e_id] = record
            else:
                if record['updated_at'] > dedup_map[e_id]['updated_at']:
                    dedup_map[e_id] = record

        deduplicated_records = list(dedup_map.values())
        duplicates_removed = records_read - len(deduplicated_records)
        print(f"Deduplicated: {len(deduplicated_records)} records kept ({duplicates_removed} duplicate(s) removed).")

        # Step 5: Atomic file write
        temp_file = raw_api_dir / 'events.jsonl.tmp'
        target_file = raw_api_dir / 'events.jsonl'

        # Load existing raw JSONL records if target_file exists to append without loss
        existing_records = []
        if target_file.exists():
            with target_file.open(mode='r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        existing_records.append(json.loads(line))

        # Re-deduplicate across existing file data and new data
        combined_map = {r['event_id']: r for r in existing_records}
        for r in deduplicated_records:
            e_id = r['event_id']
            if e_id not in combined_map or r['updated_at'] > combined_map[e_id]['updated_at']:
                combined_map[e_id] = r

        final_records = list(combined_map.values())

        with temp_file.open(mode='w', encoding='utf-8') as f:
            for record in final_records:
                f.write(json.dumps(record) + '\n')

        # Atomic rename
        temp_file.replace(target_file)
        print(f"Written output to {target_file}")

        # Step 6: Advance watermark after write succeeds
        max_updated_at = max(r['updated_at'] for r in deduplicated_records)
        save_watermark(max_updated_at)
        watermark_after = max_updated_at
        print(f"Watermark advanced to: {watermark_after}")

        log_run_event(
            run_id, start_time, 'SUCCESS', 'rest_api',
            records_read, len(deduplicated_records), duplicates_removed,
            watermark_before, watermark_after
        )

    except Exception as e:
        print(f"API Ingestion Failed: {e}")
        log_run_event(
            run_id, start_time, 'FAILED', 'rest_api',
            len(fetched_records), 0, 0,
            watermark_before, watermark_after, str(e)
        )
        raise e

if __name__=='__main__':
    RAW.mkdir(exist_ok=True)
    STATE.mkdir(exist_ok=True)
    OUTPUTS.mkdir(exist_ok=True)
    ingest_files()
    ingest_api()
