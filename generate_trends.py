#!/usr/bin/env python3
"""
Generates price_trends.json for the dashboard's trend charts.
Primary source: SQLite database (history.db).
Fallback: scrape_history/*.json files (for backwards compatibility).

Includes:
- Anomaly gating: flags data points where scraping likely failed
- 7-day rolling averages: smooths out noise for reliable trendlines
- Per-source health data for the latest run
"""
import json
import os
import glob
from collections import defaultdict
from datetime import datetime
from pathlib import Path

OUTPUT_FILE = Path(__file__).parent / "price_trends.json"
HISTORY_DIR = Path(__file__).parent / "scrape_history"

# Anomaly threshold: if today's scraped_count drops below this fraction of 7-day avg, flag it
ANOMALY_DROP_THRESHOLD = 0.5  # 50% drop = suspect


def _compute_rolling_avg(trends, window=7):
    """Add 7-day rolling averages to each trend point per platform."""
    platforms = set()
    for t in trends:
        platforms.update(t["platforms"].keys())

    for i, t in enumerate(trends):
        start = max(0, i - window + 1)
        window_points = trends[start:i + 1]

        for plat in platforms:
            pd = t["platforms"].get(plat)
            if not pd:
                continue

            # Collect non-suspect values in the window
            avg_prices = []
            med_prices = []
            counts = []
            for wp in window_points:
                wpd = wp["platforms"].get(plat)
                if wpd and not wpd.get("is_suspect", False):
                    if wpd.get("avg_price", 0) > 0:
                        avg_prices.append(wpd["avg_price"])
                    if wpd.get("median_price", 0) > 0:
                        med_prices.append(wpd["median_price"])
                    if wpd.get("count", 0) > 0:
                        counts.append(wpd["count"])

            pd["rolling_avg_price"] = round(sum(avg_prices) / len(avg_prices), 2) if avg_prices else None
            pd["rolling_median_price"] = round(sum(med_prices) / len(med_prices), 2) if med_prices else None
            pd["rolling_count"] = round(sum(counts) / len(counts)) if counts else None


def _flag_anomalies(trends):
    """Flag data points where scraping likely failed (suspect data)."""
    platforms = set()
    for t in trends:
        platforms.update(t["platforms"].keys())

    for i, t in enumerate(trends):
        if i < 3:
            # Not enough history to detect anomalies
            continue

        # Compute recent average from non-suspect points
        lookback = trends[max(0, i - 7):i]
        for plat in platforms:
            pd = t["platforms"].get(plat)
            if not pd:
                continue

            recent_counts = [
                wp["platforms"][plat]["count"]
                for wp in lookback
                if plat in wp["platforms"]
                and not wp["platforms"][plat].get("is_suspect", False)
                and wp["platforms"][plat].get("count", 0) > 0
            ]

            if not recent_counts:
                continue

            avg_recent = sum(recent_counts) / len(recent_counts)
            current_count = pd.get("count", 0)

            if avg_recent > 5 and current_count < avg_recent * ANOMALY_DROP_THRESHOLD:
                pd["is_suspect"] = True
                pd["suspect_reason"] = (
                    f"Count dropped to {current_count} from 7-day avg of {round(avg_recent)}"
                )


def generate_from_sqlite():
    """Generate trends from SQLite database. Returns (trends, health) or (None, None) if DB unavailable."""
    try:
        from db import get_connection, init_db, get_daily_trends, get_scrape_health, get_stats
        conn = get_connection()
        init_db(conn)

        stats = get_stats(conn)
        if stats["total_runs"] == 0:
            conn.close()
            return None, None

        trends = get_daily_trends(conn, limit=90)
        health = get_scrape_health(conn)
        conn.close()

        print(f"Generated from SQLite: {len(trends)} data points "
              f"({stats['total_listings']:,} total listings in DB, "
              f"{stats['unique_dates']} unique dates)")
        return trends, health

    except Exception as e:
        print(f"SQLite unavailable ({e}), falling back to JSON files")
        return None, None


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
    health = None
    result = generate_from_sqlite()
    if result[0] is not None:
        trend_data, health = result
    else:
        trend_data = generate_from_json_files()

    # Flag suspect data points (anomaly gating)
    if len(trend_data) >= 4:
        _flag_anomalies(trend_data)
        suspect_count = sum(
            1 for t in trend_data
            for pd in t["platforms"].values()
            if pd.get("is_suspect")
        )
        if suspect_count:
            print(f"  Flagged {suspect_count} suspect data point(s)")

    # Compute 7-day rolling averages
    _compute_rolling_avg(trend_data, window=7)

    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "data_points": len(trend_data),
        "trends": trend_data
    }

    # Include latest scrape health if available
    if health:
        output["scrape_health"] = health

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {OUTPUT_FILE} with {len(trend_data)} data points")


if __name__ == "__main__":
    main()
