# Roblox Accounts Monitoring Dashboard

A tool for monitoring game account listings across major marketplaces (Eldorado.gg, U7Buy, and eBay) for Roblox, Fortnite, Minecraft, and Steam.

## What it does

The scraper collects account listing data from three marketplaces across four games and outputs a `dashboard_data.json` file that powers the monitoring dashboard (`dashboard.html`).

## Files

| File | Description |
|---|---|
| `scrape_listings.py` | Main scraper — fetches listings from Eldorado.gg, U7Buy, and eBay |
| `dashboard.html` | Monitoring dashboard — visualizes the scraped data |
| `dashboard_data.json` | Latest scraped data (auto-updated on each run) |
| `scrape_history/` | Timestamped backups of each scrape run |
| `scraper.log` | Log file from the most recent scraper run |

## Running locally

Install dependencies:

```bash
pip install playwright beautifulsoup4 lxml requests
playwright install chromium
```

Run the scraper:

```bash
python scrape_listings.py --verbose
```

Then open `dashboard.html` in your browser to view the results.

### Options

```
--games Roblox Fortnite   # Scrape specific games only
--max-pages 5             # Limit pages scraped per source
--output data.json        # Custom output file path
--verbose                 # Show detailed logging
```

## Automated scraping with GitHub Actions

The included workflow (`.github/workflows/daily-scrape.yml`) runs the scraper automatically every day at 8 AM UTC and commits the updated `dashboard_data.json` back to the repo.

You can also trigger a manual run anytime from the **Actions** tab in GitHub.

## Data sources

- [Eldorado.gg](https://www.eldorado.gg)
- [U7Buy](https://www.u7buy.com)
- [eBay](https://www.ebay.com)
