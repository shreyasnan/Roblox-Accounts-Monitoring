#!/usr/bin/env python3
"""
SQLite database layer for historical listing data.
Provides functions to initialize the DB, insert listings from a scrape run,
and query historical data for trend analysis.
"""
import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "history.db"


def get_connection(db_path=None):
    """Get a connection to the SQLite database."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn=None):
    """Create tables if they don't exist."""
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS scrape_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL,
            run_timestamp TEXT NOT NULL,
            total_listings_found INTEGER DEFAULT 0,
            total_listings_scraped INTEGER DEFAULT 0,
            sources TEXT,
            platforms TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            price_usd REAL DEFAULT 0,
            url TEXT,
            seller TEXT,
            rating TEXT,
            delivery TEXT,
            sold TEXT,
            categories TEXT,
            scraped_at TEXT,
            FOREIGN KEY (run_id) REFERENCES scrape_runs(id)
        );

        CREATE TABLE IF NOT EXISTS platform_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            total_listings_across_sources INTEGER DEFAULT 0,
            avg_price REAL DEFAULT 0,
            median_price REAL DEFAULT 0,
            min_price REAL DEFAULT 0,
            max_price REAL DEFAULT 0,
            scraped_count INTEGER DEFAULT 0,
            age_verified_count INTEGER DEFAULT 0,
            age_verified_avg_price REAL DEFAULT 0,
            FOREIGN KEY (run_id) REFERENCES scrape_runs(id)
        );

        CREATE INDEX IF NOT EXISTS idx_listings_run_id ON listings(run_id);
        CREATE INDEX IF NOT EXISTS idx_listings_platform ON listings(platform);
        CREATE INDEX IF NOT EXISTS idx_listings_categories ON listings(categories);
        CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price_usd);
        CREATE INDEX IF NOT EXISTS idx_platform_snapshots_run ON platform_snapshots(run_id);
        CREATE INDEX IF NOT EXISTS idx_scrape_runs_date ON scrape_runs(run_date);
    """)
    conn.commit()

    if close:
        conn.close()


def insert_scrape_run(conn, dashboard_data):
    """
    Insert a complete scrape run (metadata + listings + platform snapshots)
    into the database. Returns the run_id.
    """
    meta = dashboard_data.get("metadata", {})
    run_date = meta.get("scrape_date", datetime.now().strftime("%Y-%m-%d"))
    run_timestamp = meta.get("generated_at", datetime.now().isoformat())

    cursor = conn.execute("""
        INSERT INTO scrape_runs (run_date, run_timestamp, total_listings_found,
                                 total_listings_scraped, sources, platforms)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        run_date,
        run_timestamp,
        meta.get("total_listings_found", 0),
        meta.get("total_listings_scraped", 0),
        json.dumps(meta.get("sources", [])),
        json.dumps(meta.get("platforms", []))
    ))
    run_id = cursor.lastrowid

    # Insert all listings
    listings = dashboard_data.get("listings", [])
    if listings:
        conn.executemany("""
            INSERT INTO listings (run_id, platform, source, title, price_usd, url,
                                  seller, rating, delivery, sold, categories, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                run_id,
                l.get("platform", ""),
                l.get("source", ""),
                l.get("title", ""),
                l.get("price_usd", 0),
                l.get("url", ""),
                l.get("seller", ""),
                l.get("rating", ""),
                l.get("delivery", ""),
                l.get("sold", ""),
                json.dumps(l.get("categories", [])),
                l.get("scraped_at", "")
            )
            for l in listings
        ])

    # Compute and insert platform snapshots
    for platform in meta.get("platforms", []):
        plat_listings = [l for l in listings if l.get("platform") == platform]
        prices = [l["price_usd"] for l in plat_listings if l.get("price_usd", 0) > 0]
        av_listings = [l for l in plat_listings if "Age Verified" in l.get("categories", [])]
        av_prices = [l["price_usd"] for l in av_listings if l.get("price_usd", 0) > 0]

        total_across = 0
        plat_summary = dashboard_data.get("platform_summary", {}).get(platform, {})
        total_across = plat_summary.get("total_listings_across_sources", len(plat_listings))

        avg_price = sum(prices) / len(prices) if prices else 0
        sorted_prices = sorted(prices)
        median_price = sorted_prices[len(sorted_prices) // 2] if sorted_prices else 0
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        av_avg = sum(av_prices) / len(av_prices) if av_prices else 0

        conn.execute("""
            INSERT INTO platform_snapshots (run_id, platform, total_listings_across_sources,
                                            avg_price, median_price, min_price, max_price,
                                            scraped_count, age_verified_count, age_verified_avg_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id, platform, total_across,
            round(avg_price, 2), round(median_price, 2),
            round(min_price, 2), round(max_price, 2),
            len(plat_listings), len(av_listings), round(av_avg, 2)
        ))

    conn.commit()
    return run_id


def get_daily_trends(conn, limit=90):
    """
    Get daily price trends per platform for the last N days.
    Returns the latest snapshot per platform per day.
    """
    rows = conn.execute("""
        SELECT
            sr.run_date,
            ps.platform,
            ps.avg_price,
            ps.median_price,
            ps.min_price,
            ps.max_price,
            ps.scraped_count,
            ps.age_verified_count,
            ps.age_verified_avg_price,
            ps.total_listings_across_sources
        FROM platform_snapshots ps
        JOIN scrape_runs sr ON ps.run_id = sr.id
        WHERE ps.run_id IN (
            SELECT MAX(id) FROM scrape_runs GROUP BY run_date
        )
        ORDER BY sr.run_date ASC
        LIMIT ?
    """, (limit * 4,)).fetchall()  # *4 for 4 platforms

    # Group by date
    from collections import OrderedDict
    trends = OrderedDict()
    for row in rows:
        date = row["run_date"]
        if date not in trends:
            trends[date] = {"date": date, "platforms": {}}
        trends[date]["platforms"][row["platform"]] = {
            "avg_price": row["avg_price"],
            "median_price": row["median_price"],
            "min_price": row["min_price"],
            "max_price": row["max_price"],
            "count": row["scraped_count"],
            "age_verified_count": row["age_verified_count"],
            "age_verified_avg_price": row["age_verified_avg_price"],
            "total_listings": row["total_listings_across_sources"]
        }

    return list(trends.values())


def get_age_verified_history(conn, limit=90):
    """Get age-verified listing counts and avg prices over time."""
    rows = conn.execute("""
        SELECT
            sr.run_date,
            ps.platform,
            ps.age_verified_count,
            ps.age_verified_avg_price
        FROM platform_snapshots ps
        JOIN scrape_runs sr ON ps.run_id = sr.id
        WHERE ps.run_id IN (
            SELECT MAX(id) FROM scrape_runs GROUP BY run_date
        )
        AND ps.age_verified_count > 0
        ORDER BY sr.run_date ASC
        LIMIT ?
    """, (limit * 4,)).fetchall()

    return [dict(r) for r in rows]


def get_stats(conn):
    """Get summary stats about the database."""
    total_runs = conn.execute("SELECT COUNT(*) FROM scrape_runs").fetchone()[0]
    total_listings = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    date_range = conn.execute(
        "SELECT MIN(run_date), MAX(run_date) FROM scrape_runs"
    ).fetchone()
    unique_dates = conn.execute(
        "SELECT COUNT(DISTINCT run_date) FROM scrape_runs"
    ).fetchone()[0]

    return {
        "total_runs": total_runs,
        "total_listings": total_listings,
        "first_date": date_range[0],
        "last_date": date_range[1],
        "unique_dates": unique_dates
    }


if __name__ == "__main__":
    # Quick test
    conn = get_connection()
    init_db(conn)
    stats = get_stats(conn)
    print(f"Database stats: {json.dumps(stats, indent=2)}")
    conn.close()
