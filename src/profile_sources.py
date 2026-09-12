"""Week 2 starter: profile CSV, JSON, Parquet, API payload, and PostgreSQL table.
Complete the TODOs. Do not hard-code expected counts.
"""
from pathlib import Path
import json, csv
import os
import pandas as pd
import pyarrow.parquet as pq

DATA_DIR=Path(__file__).resolve().parents[1]/'data'

def profile_csv(path):
    # TODO: row count, columns, missing counts, duplicate rows, duplicate customer_id, inferred types
    print("Task 1.2 - PROFILE CUSTOMERS.CSV")
    file_size = os.path.getsize(path)
    df = pd.read_csv(path)

    print(f"File Size: {file_size} bytes")
    print(f"Total Rows: {df.shape[0]}")
    print(f"Total Columns: {df.shape[1]}")
    print(df.dtypes)
    print("\nMissing Values per Column:")
    print(df.isnull().sum())
    print(f"\nExact Duplicate Rows: {df.duplicated().sum()}")

    if 'customer_id' in df.columns:
        is_unique = df['customer_id'].is_unique
        print(f"Is customer_id unique?: {is_unique}")
        if not is_unique:
            print(f"Duplicate customer_ids count: {df['customer_id'].duplicated().sum()}")
    print ("\n")
    pass

def profile_json(path):
    # TODO: record count, keys, nested fields, date/time fields, numeric fields, nulls
    print("Task 1.3 - PROFILE ORDERS.JSON")
    with open(path) as f:
        data = json.load(f)

    is_list = isinstance(data, list)
    print(f"Root structure: {is_list}")
    print(f"Total records: {len(data)}")

    if is_list and len(data) > 0:
        first_record = data[0]
        print(f"Top-level keys: {list(first_record.keys())}")

        # Check nested structure
        for key, value in first_record.items():
            if isinstance(value, dict):
                print(f"Nested Field Detected: '{key}' with sub-keys: {list(value.keys())}")
    print("\n")
    pass

def profile_parquet(path):
    # TODO: use pandas.read_parquet; report rows/columns/dtypes/nulls and file size
    # Requires pyarrow from requirements.txt
    print("Task 1.4 - PROFILE PRODUCTS.PARQUET")
    file_size = os.path.getsize(path)
    df = pd.read_parquet(path)

    print(f"File Size: {file_size} bytes")
    print(f"Total Rows: {df.shape[0]}")
    print(f"Total Columns: {df.shape[1]}")
    print(df.dtypes)
    print("\n")
    pass

if __name__=='__main__':
    profile_csv(DATA_DIR/'customers.csv')
    profile_json(DATA_DIR/'orders.json')
    profile_parquet(DATA_DIR/'products.parquet')
