#!/usr/bin/env python3
"""
Roblox Accounts Monitoring - Data Collection Framework & Sample Data Generator

This module defines the data schema for tracking account sales across the open web,
and generates realistic sample data for the dashboard. Replace the sample data
generation with live scraping modules for production use.
"""

import json
import random
import hashlib
from datetime import datetime, timedelta

# ============================================================
# CONFIGURATION
# ============================================================

PLATFORMS = ["Roblox", "Fortnite", "Minecraft", "Steam"]

SOURCES = {
    "marketplace": [
        "PlayerAuctions", "G2G", "Eldorado.gg", "Z2U", "IGVault",
        "AccountWarehouse", "EpicNPC", "Gameflip", "SEAgm", "Mulefactory"
    ],
    "forum": [
        "V3rmillion", "OGUsers", "Nulled.to", "Sythe.org", "MPGH",
        "UnknownCheats", "RaidForums Archive", "HackForums", "Cracked.io", "BreachForums"
    ],
    "social": [
        "Telegram", "Discord", "Twitter/X", "Reddit", "TikTok",
        "Facebook Marketplace", "WhatsApp Groups", "Instagram"
    ]
}

REGIONS = ["North America", "Europe", "Southeast Asia", "Latin America",
           "Middle East", "East Asia", "South Asia", "Africa", "Oceania"]

LANGUAGES = ["English", "Spanish", "Portuguese", "Russian", "Chinese",
             "Arabic", "Turkish", "Indonesian", "French", "German", "Vietnamese", "Korean"]

KEYWORDS = {
    "Roblox": ["robux", "limiteds", "korblox", "headless", "account dump", "rich account",
                "blox fruits", "adopt me pets", "roblox OG", "verified email", "premium",
                "voice chat enabled", "display name", "banned unban", "cookie log"],
    "Fortnite": ["og skins", "renegade raider", "black knight", "galaxy skin", "v-bucks",
                  "stacked account", "season 1", "save the world", "aerial assault",
                  "account merge", "full access"],
    "Minecraft": ["java edition", "bedrock", "hypixel rank", "optifine cape", "minecon cape",
                   "migrated", "unmigrated", "NFA", "SFA", "full access", "alt accounts"],
    "Steam": ["csgo skins", "steam wallet", "game library", "VAC clean", "prime",
              "high level", "inventory value", "rare items", "old account", "badge level"]
}

QUALITY_TIERS = ["Premium/Stacked", "Mid-Tier", "Basic/Starter", "Bulk/NFA"]

# ============================================================
# SAMPLE DATA GENERATION
# ============================================================

def generate_monthly_data(start_date, months=12):
    """Generate monthly time-series data for all platforms."""
    data = []
    base_date = datetime.strptime(start_date, "%Y-%m-%d")

    # Base metrics per platform (listings count, avg price, median price)
    platform_baselines = {
        "Roblox":   {"listings": 4200, "avg_price": 28, "median_price": 15, "growth_rate": 0.06},
        "Fortnite": {"listings": 3100, "avg_price": 45, "median_price": 25, "growth_rate": 0.03},
        "Minecraft":{"listings": 2800, "avg_price": 12, "median_price": 5,  "growth_rate": 0.02},
        "Steam":    {"listings": 1900, "avg_price": 85, "median_price": 40, "growth_rate": 0.04},
    }

    for month_offset in range(months):
        current_date = base_date + timedelta(days=30 * month_offset)
        month_str = current_date.strftime("%Y-%m")

        for platform in PLATFORMS:
            base = platform_baselines[platform]
            # Apply growth trend + seasonal variation + noise
            trend = 1 + base["growth_rate"] * month_offset
            seasonal = 1 + 0.15 * (1 if current_date.month in [6, 7, 8, 11, 12] else -0.05)
            noise = random.uniform(0.9, 1.1)

            listings = int(base["listings"] * trend * seasonal * noise)
            avg_price = round(base["avg_price"] * (1 + random.uniform(-0.15, 0.15)) * (1 + 0.01 * month_offset), 2)
            median_price = round(base["median_price"] * (1 + random.uniform(-0.1, 0.1)), 2)

            data.append({
                "month": month_str,
                "platform": platform,
                "total_listings": listings,
                "new_listings": int(listings * random.uniform(0.25, 0.45)),
                "avg_price_usd": avg_price,
                "median_price_usd": median_price,
                "max_price_usd": round(avg_price * random.uniform(8, 25), 2),
                "total_sellers": int(listings * random.uniform(0.3, 0.5)),
                "unique_sources": random.randint(15, 45),
            })

    return data


def generate_source_breakdown():
    """Generate listings breakdown by source type and specific source."""
    data = []
    for platform in PLATFORMS:
        for source_type, sources in SOURCES.items():
            for source in sources:
                # Not all sources sell all platforms
                if random.random() < 0.7:
                    weight = {"marketplace": 3, "forum": 2, "social": 1.5}[source_type]
                    listings = int(random.uniform(10, 500) * weight)
                    data.append({
                        "platform": platform,
                        "source_type": source_type,
                        "source_name": source,
                        "listings_count": listings,
                        "avg_price_usd": round(random.uniform(5, 120), 2),
                        "verified_sellers_pct": round(random.uniform(0.1, 0.9), 2),
                        "avg_account_age_days": random.randint(30, 2000),
                        "last_scraped": (datetime.now() - timedelta(hours=random.randint(1, 168))).isoformat(),
                    })
    return data


def generate_keyword_trends(months=12):
    """Generate keyword frequency trends over time."""
    data = []
    base_date = datetime(2025, 4, 1)

    for platform in PLATFORMS:
        for keyword in KEYWORDS[platform]:
            base_freq = random.randint(20, 500)
            for month_offset in range(months):
                current_date = base_date + timedelta(days=30 * month_offset)
                trend = 1 + random.uniform(-0.1, 0.15) * month_offset / 6
                freq = int(base_freq * trend * random.uniform(0.7, 1.3))
                data.append({
                    "month": current_date.strftime("%Y-%m"),
                    "platform": platform,
                    "keyword": keyword,
                    "mention_count": freq,
                    "avg_listing_price_usd": round(random.uniform(5, 150), 2),
                    "sentiment_score": round(random.uniform(-0.3, 0.8), 2),
                })
    return data


def generate_regional_data():
    """Generate regional breakdown of account sales."""
    data = []
    region_weights = {
        "North America": 0.28, "Europe": 0.25, "Southeast Asia": 0.15,
        "Latin America": 0.10, "Middle East": 0.06, "East Asia": 0.08,
        "South Asia": 0.04, "Africa": 0.02, "Oceania": 0.02
    }

    for platform in PLATFORMS:
        total_listings = random.randint(3000, 8000)
        for region, weight in region_weights.items():
            noise = random.uniform(0.7, 1.3)
            listings = int(total_listings * weight * noise)
            # Price varies by region
            price_multiplier = {"North America": 1.2, "Europe": 1.15, "Southeast Asia": 0.6,
                                "Latin America": 0.7, "Middle East": 0.9, "East Asia": 1.0,
                                "South Asia": 0.5, "Africa": 0.4, "Oceania": 1.1}[region]
            data.append({
                "platform": platform,
                "region": region,
                "listings_count": listings,
                "avg_price_usd": round(random.uniform(15, 60) * price_multiplier, 2),
                "dominant_language": random.choice(LANGUAGES[:3]) if region == "North America"
                    else random.choice(LANGUAGES),
                "seller_count": int(listings * random.uniform(0.3, 0.5)),
                "pct_of_total": round(weight * noise, 3),
            })
    return data


def generate_language_data():
    """Generate language breakdown for listings."""
    data = []
    lang_weights = {
        "English": 0.38, "Spanish": 0.10, "Portuguese": 0.07, "Russian": 0.09,
        "Chinese": 0.08, "Arabic": 0.05, "Turkish": 0.06, "Indonesian": 0.05,
        "French": 0.04, "German": 0.03, "Vietnamese": 0.03, "Korean": 0.02
    }

    for platform in PLATFORMS:
        for lang, weight in lang_weights.items():
            noise = random.uniform(0.7, 1.4)
            listings = int(random.randint(2500, 7000) * weight * noise)
            data.append({
                "platform": platform,
                "language": lang,
                "listings_count": listings,
                "avg_price_usd": round(random.uniform(10, 80), 2),
                "avg_description_length": random.randint(30, 300),
                "pct_with_images": round(random.uniform(0.2, 0.85), 2),
            })
    return data


def generate_quality_distribution():
    """Generate quality tier distribution per platform."""
    data = []
    tier_profiles = {
        "Roblox": {"Premium/Stacked": 0.12, "Mid-Tier": 0.28, "Basic/Starter": 0.35, "Bulk/NFA": 0.25},
        "Fortnite": {"Premium/Stacked": 0.18, "Mid-Tier": 0.32, "Basic/Starter": 0.30, "Bulk/NFA": 0.20},
        "Minecraft": {"Premium/Stacked": 0.08, "Mid-Tier": 0.20, "Basic/Starter": 0.30, "Bulk/NFA": 0.42},
        "Steam": {"Premium/Stacked": 0.22, "Mid-Tier": 0.30, "Basic/Starter": 0.28, "Bulk/NFA": 0.20},
    }
    price_ranges = {
        "Premium/Stacked": (80, 500),
        "Mid-Tier": (20, 80),
        "Basic/Starter": (5, 20),
        "Bulk/NFA": (0.5, 5),
    }

    for platform in PLATFORMS:
        total = random.randint(3000, 8000)
        for tier in QUALITY_TIERS:
            pct = tier_profiles[platform][tier]
            count = int(total * pct * random.uniform(0.85, 1.15))
            lo, hi = price_ranges[tier]
            data.append({
                "platform": platform,
                "quality_tier": tier,
                "listings_count": count,
                "pct_of_total": round(pct, 3),
                "avg_price_usd": round(random.uniform(lo, hi), 2),
                "median_price_usd": round(random.uniform(lo, (lo + hi) / 2), 2),
            })
    return data


def generate_alert_signals():
    """Generate recent alert signals (unusual activity, price spikes, new sources)."""
    alerts = []
    alert_types = [
        ("price_spike", "Significant price increase detected"),
        ("volume_surge", "Unusual increase in listing volume"),
        ("new_source", "New marketplace or forum detected selling accounts"),
        ("bulk_dump", "Large bulk account dump detected"),
        ("keyword_trend", "Trending keyword with rapid growth"),
        ("regional_shift", "Significant shift in regional distribution"),
    ]

    for _ in range(random.randint(8, 18)):
        atype, desc = random.choice(alert_types)
        platform = random.choice(PLATFORMS)
        alerts.append({
            "timestamp": (datetime.now() - timedelta(hours=random.randint(1, 720))).isoformat(),
            "alert_type": atype,
            "platform": platform,
            "severity": random.choice(["low", "medium", "high", "critical"]),
            "description": f"{desc} for {platform}",
            "details": {
                "source": random.choice(SOURCES["marketplace"] + SOURCES["forum"] + SOURCES["social"]),
                "metric_value": round(random.uniform(1.5, 10), 2),
                "baseline_value": round(random.uniform(0.5, 3), 2),
            }
        })
    return sorted(alerts, key=lambda x: x["timestamp"], reverse=True)


def generate_all_data():
    """Generate complete dataset for the dashboard."""
    random.seed(42)  # Reproducible sample data

    dataset = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "data_period": "2025-04 to 2026-03",
            "platforms": PLATFORMS,
            "sources_tracked": sum(len(v) for v in SOURCES.values()),
            "refresh_frequency": "Monthly",
            "version": "1.0.0",
        },
        "monthly_trends": generate_monthly_data("2025-04-01", 12),
        "source_breakdown": generate_source_breakdown(),
        "keyword_trends": generate_keyword_trends(12),
        "regional_data": generate_regional_data(),
        "language_data": generate_language_data(),
        "quality_distribution": generate_quality_distribution(),
        "alerts": generate_alert_signals(),
        "config": {
            "platforms": PLATFORMS,
            "source_types": list(SOURCES.keys()),
            "sources": SOURCES,
            "regions": REGIONS,
            "languages": LANGUAGES,
            "keywords": KEYWORDS,
            "quality_tiers": QUALITY_TIERS,
        }
    }

    return dataset


if __name__ == "__main__":
    data = generate_all_data()
    with open("dashboard_data.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Generated {len(data['monthly_trends'])} monthly records")
    print(f"Generated {len(data['source_breakdown'])} source breakdown records")
    print(f"Generated {len(data['keyword_trends'])} keyword trend records")
    print(f"Generated {len(data['regional_data'])} regional records")
    print(f"Generated {len(data['language_data'])} language records")
    print(f"Generated {len(data['quality_distribution'])} quality distribution records")
    print(f"Generated {len(data['alerts'])} alert signals")
    print("Data saved to dashboard_data.json")
