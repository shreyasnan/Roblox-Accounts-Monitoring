#!/usr/bin/env python3
"""
Generates price_trends.json for the dashboard's trend charts.
Primary source: SQLite database (history.db).
Fallback: scrape_history/*.json files (for backwards compatibility).
"""
import json
import os
import glob
from collections import defaultdict
from datetime import datetime
from pathlib import Path

OUTPUT_FILE = Path(__file__).parent / "price_trends.json"
HISTORY_DIR = Path(__file__).parent / "scrape_history"


def generate_from_sqlite():
    """Generate trends from SQLite database. Returns trend data or None if DB unavailable."""
    try:
        from db import get_connection, init_db, get_daily_trends, get_stats
        conn = get_connection()
        init_db(conn)

        stats = get_stats(conn)
        if stats["total_runs"] == 0:
            conn.close()
            return None

        trends = get_daily_trends(conn, limit=90)
        conn.close()

        print(f"Generated from SQLite: {len(trends)} data points "
              f"({stats['total_listings']:,} total listings in DB, "
              f"{stats['unique_dates']} unique dates)")
        return trends

    except Exception as e:
        print(f"SQLite unavailable ({e}), falling back to JSON files")
        return None


def generate_from_json_files():
    """Fallback: generate trends from scrape_history JSON files."""
    files = sorted(glob.glob(str(HISTORY_DIR / "dashboard_data_*.json")))
    if not files:
        return []

    by_date = {}
    for f in files:
        base = os.path.basename(f)
        parts = base.replace("dashboard_data_", "").replace(".json", "").split("_")
        if len(parts) >= 1 and len(parts[0]) == 8:
            date = parts[0][:4] + "-" + parts[0][4:6] + "-" + parts[0][6:8]
            by_date[date] = f

    trend_data = []
    for date in sorted(by_date.keys()):
        filepath = by_date[date]
        try:
            with open(filepath) as fh:
                data = json.load(fh)
            listings = data.get("listings", [])
            if not listings:
                continue

            platforms = defaultdict(lambda: {
                "prices": [], "count": 0,
                "age_verified_count": 0, "age_verified_prices": []
            })

            for l in listings:
                plat = l.get("platform", "Unknown")
                price = l.get("price_usd", 0)
                cats = l.get("categories", [])
                if price > 0:
                    platforms[plat]["prices"].append(price)
                platforms[plat]["count"] += 1
                if "Age Verified" in cats:
                    platforms[plat]["age_verified_count"] += 1
                    if price > 0:
                        platforms[plat]["age_verified_prices"].append(price)

            result = {}
            for plat, stats in platforms.items():
                prices = stats["prices"]
                av_prices = stats["age_verified_prices"]
                result[plat] = {
                    "avg_price": round(sum(prices) / len(prices), 2) if prices else 0,
                    "median_price": round(sorted(prices)[len(prices) // 2], 2) if prices else 0,
                    "min_price": round(min(prices), 2) if prices else 0,
                    "max_price": round(max(prices), 2) if prices else 0,
                    "count": stats["count"],
                    "age_verified_count": stats["age_verified_count"],
                    "age_verified_avg_price": round(sum(av_prices) / len(av_prices), 2) if av_prices else 0,
                }
            trend_data.append({"date": date, "platforms": result})
        except Exception as e:
            print(f"  Error processing {os.path.basename(filepath)}: {e}")

    print(f"Generated from JSON files: {len(trend_data)} data points")
    return trend_data


def main():
    # Try SQLite first, fall back to JSON files
    trend_data = generate_from_sqlite()
    if trend_data is None:
        trend_data = generate_from_json_files()

    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "data_points": len(trend_data),
        "trends": trend_data
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {OUTPUT_FILE} with {len(trend_data)} data points")


if __name__ == "__main__":
    main()
