# Roblox Accounts Monitoring

A daily-refreshed dashboard tracking the secondary market for Roblox accounts across major resale marketplaces, with Fortnite, Minecraft, and Steam as comparative benchmarks.

**Live dashboard:** https://shreyasnan.github.io/Roblox-Accounts-Monitoring/

## What this does

Every day, a scheduled scraper visits eight marketplaces, pulls a proportional sample of current listings for each game, categorizes them, and publishes the results to a static dashboard hosted on GitHub Pages. Historical runs are persisted to SQLite so the dashboard can show trends over time.

The goal is to answer a few specific questions:

- How large is the resale market for Roblox accounts relative to other games?
- Which marketplaces account for the bulk of listings, and which are niche?
- What price ranges and account categories (OG / Veteran, Items & Currency, Age Verified, General) are most common?
- How are these signals moving week over week?

## Data sources

| Marketplace | Roblox | Fortnite | Minecraft | Steam |
|---|:---:|:---:|:---:|:---:|
| Eldorado.gg    | ✅ | ✅ | ✅ | ✅ |
| U7Buy          | ✅ | ✅ | ✅ | ✅ |
| eBay           | ✅ | ✅ | ✅ | ✅ |
| PlayerAuctions | ✅ | ✅ | ✅ | ✅ |
| Z2U            | ✅ | ✅ | ✅ | ✅ |
| G2G            | ✅ |    |    |    |
| PlayHub        | ✅ |    |    |    |
| ZeusX          | ✅ |    |    |    |

Only multi-seller account marketplaces are included. Single-vendor shops and Robux-only stores are intentionally excluded because they don't fit the comparative pipeline.

## How the scrape works

The scraper is deliberately conservative — it pulls a sample of listings rather than the entire catalog. The sample is distributed proportionally: marketplaces with more total listings receive more pages in the budget, and small marketplaces (like eBay, which reports ~800 listings) get just one page. This keeps the scrape polite to the source sites while still giving each day's snapshot a representative mix.

Allocation is driven by the previous day's reported marketplace sizes. On a cold start with no prior data, the scraper falls back to a flat page budget per source.

Each run also records the marketplace-reported total (`total_on_site`) alongside the verified scraped count, so the dashboard can show both "what we actually collected" and "market share" context without conflating the two.

## Repo layout

```
.
├── scrape_listings.py     # Main scraper (one class per marketplace)
├── db.py                  # SQLite persistence layer for historical runs
├── generate_trends.py     # Rolls history.db forward into price_trends.json
├── migrate_to_sqlite.py   # One-time migration of old JSON history into SQLite
├── index.html             # Single-file dashboard served from GitHub Pages
├── dashboard_data.json    # Latest scrape snapshot (regenerated daily)
├── price_trends.json      # Aggregated historical trends
├── history.db             # SQLite store of every run
├── scrape_history/        # Timestamped JSON backups of each run
└── .github/workflows/
    ├── daily-scrape.yml   # Cron: scrape, commit, deploy
    └── deploy-only.yml    # Push-triggered Pages redeploy
```

## Running locally

```bash
pip install playwright beautifulsoup4 lxml requests
playwright install chromium

python scrape_listings.py --verbose
```

Then open `index.html` in a browser to view the dashboard against the freshly-scraped data.

### CLI options

```
--games Roblox Fortnite   Scrape specific games only (default: all four)
--max-pages 5             Base page budget per source (default: 3). The actual
                          allocation is scaled proportionally by marketplace size.
--output data.json        Write to a custom JSON path
--fast                    Skip headless-browser mode; use requests + BeautifulSoup only
--verbose                 Debug-level logging
```

## Automation

`.github/workflows/daily-scrape.yml` runs every day at 08:00 UTC. It installs dependencies, runs the scraper, regenerates trend data, commits the updated snapshots, and deploys the dashboard to GitHub Pages. You can also kick off a run manually from the **Actions** tab.

`.github/workflows/deploy-only.yml` redeploys the dashboard on any push to `main` that touches non-data files, so fixes to `index.html` ship immediately without waiting for the next scheduled scrape.

## Notes on the numbers

The dashboard deliberately headlines **scraped listings** rather than marketplace-reported totals. Marketplace-reported counts are still shown as secondary context, labelled as such, because:

1. The scraper only samples a small fraction of each marketplace per day, so the reported "X total listings" is not something we've independently verified.
2. Different marketplaces count differently (some include sold or delisted items in their header counts).
3. Surfacing the sample coverage makes it honest about what this project actually measures.

Marketplaces are ranked and tagged with a relevance tier (HIGH / MEDIUM / LOW) based on market share, so it's easy to tell at a glance which sources matter most for the Roblox segment.
