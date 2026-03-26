#!/usr/bin/env python3
"""
One-time migration script: imports all existing scrape_history/*.json files
into the SQLite database (history.db).
"""
import json
import glob
import os
from pathlib import Path
from db import get_connection, init_db, insert_scrape_run, get_stats

HISTORY_DIR = Path(__file__).parent / "scrape_history"


def extract_date(filename):
    """Extract date from filename like dashboard_data_20260326_075637.json"""
    base = os.path.basename(filename)
    parts = base.replace("dashboard_data_", "").replace(".json", "").split("_")
    if len(parts) >= 1 and len(parts[0]) == 8:
        return parts[0][:4] + "-" + parts[0][4:6] + "-" + parts[0][6:8]
    return None


def main():
    conn = get_connection()
    init_db(conn)

    # Check if we already have data
    stats = get_stats(conn)
    if stats["total_runs"] > 0:
        print(f"Database already has {stats['total_runs']} runs. Skipping migration.")
        print(f"  Date range: {stats['first_date']} to {stats['last_date']}")
        print(f"  Total listings: {stats['total_listings']:,}")
        conn.close()
        return

    files = sorted(glob.glob(str(HISTORY_DIR / "dashboard_data_*.json")))
    print(f"Found {len(files)} history files to import")

    # Group by date, keep latest per date
    by_date = {}
    for f in files:
        date = extract_date(f)
        if date:
            by_date[date] = f

    imported = 0
    for date in sorted(by_date.keys()):
        filepath = by_date[date]
        try:
            with open(filepath) as fh:
                data = json.load(fh)

            listings = data.get("listings", [])
            if not listings:
                print(f"  Skipping {os.path.basename(filepath)} (no listings)")
                continue

            run_id = insert_scrape_run(conn, data)
            imported += 1
            print(f"  Imported {os.path.basename(filepath)}: run_id={run_id}, "
                  f"{len(listings)} listings")

        except Exception as e:
            print(f"  Error importing {os.path.basename(filepath)}: {e}")

    stats = get_stats(conn)
    print(f"\nMigration complete!")
    print(f"  Runs imported: {imported}")
    print(f"  Total listings in DB: {stats['total_listings']:,}")
    print(f"  Date range: {stats['first_date']} to {stats['last_date']}")

    conn.close()


if __name__ == "__main__":
    main()
