#!/usr/bin/env python3
"""
Build the executive HTML dashboard for Roblox Accounts Monitoring.
Single-page, screenshot-friendly, narrative-driven.
No raw tables, no pagination — just the story the data tells.
"""

import json

with open("dashboard_data.json") as f:
    data = json.load(f)

data_js = json.dumps(data)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Account Marketplace Intelligence — Executive Summary</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root {{
  --bg: #0f1117;
  --surface: #161922;
  --surface2: #1e2231;
  --border: #272c3d;
  --text: #e8eaf2;
  --text-dim: #7d829a;
  --accent: #818cf8;
  --teal: #2dd4bf;
  --red: #f87171;
  --orange: #fb923c;
  --green: #4ade80;
  --roblox: #ef4444;
  --fortnite: #a78bfa;
  --minecraft: #34d399;
  --steam: #60a5fa;
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: var(--bg); color: var(--text); font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif; line-height: 1.6; }}

/* ===== HEADER ===== */
.header {{
  padding: 28px 40px 20px;
  border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: flex-end;
}}
.header-left h1 {{
  font-size: 18px; font-weight: 700; letter-spacing: -0.3px;
  background: linear-gradient(135deg, var(--accent), var(--teal));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}}
.header-left .subtitle {{
  font-size: 24px; font-weight: 700; color: var(--text); margin-top: 2px; letter-spacing: -0.5px;
}}
.header-right {{ text-align: right; }}
.header-right .date {{ font-size: 13px; color: var(--text); font-weight: 500; }}
.header-right .version {{ font-size: 11px; color: var(--text-dim); margin-top: 2px; }}

.page {{ max-width: 1200px; margin: 0 auto; padding: 28px 40px 48px; }}

/* ===== TOP KPI STRIP ===== */
.kpi-strip {{
  display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; margin-bottom: 32px;
}}
.kpi {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
  padding: 20px; text-align: center; position: relative;
}}
.kpi .number {{ font-size: 32px; font-weight: 800; letter-spacing: -1px; }}
.kpi .label {{ font-size: 11px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.8px; margin-top: 4px; }}
.kpi .detail {{ font-size: 11px; color: var(--text-dim); margin-top: 6px; }}
.kpi.highlight {{ border-color: var(--accent); background: linear-gradient(135deg, rgba(129,140,248,0.08), rgba(45,212,191,0.05)); }}

/* ===== SECTION TITLES ===== */
.section-title {{
  font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px;
  color: var(--text-dim); margin-bottom: 16px; margin-top: 8px;
}}

/* ===== PLATFORM COMPARISON ===== */
.platform-row {{
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 32px;
}}
.platform-card {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
  padding: 20px; position: relative; overflow: hidden;
}}
.platform-card::before {{
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
}}
.platform-card.roblox::before {{ background: var(--roblox); }}
.platform-card.fortnite::before {{ background: var(--fortnite); }}
.platform-card.minecraft::before {{ background: var(--minecraft); }}
.platform-card.steam::before {{ background: var(--steam); }}
.platform-card .name {{ font-size: 14px; font-weight: 700; margin-bottom: 12px; }}
.platform-card .stat-row {{
  display: flex; justify-content: space-between; align-items: baseline;
  padding: 4px 0; border-bottom: 1px solid var(--border);
}}
.platform-card .stat-row:last-child {{ border-bottom: none; }}
.platform-card .stat-label {{ font-size: 11px; color: var(--text-dim); }}
.platform-card .stat-value {{ font-size: 13px; font-weight: 600; }}

/* ===== CHART CARDS ===== */
.chart-grid {{
  display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 32px;
}}
.chart-card {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
  padding: 20px;
}}
.chart-card h3 {{
  font-size: 12px; font-weight: 600; color: var(--text-dim); text-transform: uppercase;
  letter-spacing: 0.5px; margin-bottom: 16px;
}}
.chart-card canvas {{ max-height: 260px; }}

/* ===== SOURCE HEALTH STRIP ===== */
.source-strip {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 32px;
}}
.source-card {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
  padding: 16px 18px; display: flex; align-items: center; gap: 14px;
}}
.source-dot {{
  width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
}}
.source-dot.good {{ background: var(--green); box-shadow: 0 0 8px rgba(74,222,128,0.4); }}
.source-dot.warn {{ background: var(--orange); box-shadow: 0 0 8px rgba(251,146,60,0.4); }}
.source-dot.bad {{ background: var(--red); box-shadow: 0 0 8px rgba(248,113,113,0.4); }}
.source-info .source-name {{ font-size: 13px; font-weight: 600; }}
.source-info .source-meta {{ font-size: 11px; color: var(--text-dim); margin-top: 2px; }}

/* ===== NOTABLE LISTINGS ===== */
.notable-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 32px;
}}
.notable-card {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
  padding: 16px 18px;
}}
.notable-card .notable-price {{
  font-size: 22px; font-weight: 800; color: var(--red); letter-spacing: -0.5px;
}}
.notable-card .notable-title {{
  font-size: 12px; color: var(--text); margin-top: 6px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}}
.notable-card .notable-meta {{
  font-size: 11px; color: var(--text-dim); margin-top: 4px;
}}

/* ===== FOOTER ===== */
.footer {{
  text-align: center; padding: 20px; font-size: 11px; color: var(--text-dim);
  border-top: 1px solid var(--border); margin-top: 12px;
}}

/* ===== PLATFORM SHARE BAR ===== */
.share-bar {{
  display: flex; height: 8px; border-radius: 4px; overflow: hidden; margin-bottom: 32px;
}}
.share-bar .segment {{ transition: width 0.3s; }}

/* responsive */
@media (max-width: 900px) {{
  .kpi-strip {{ grid-template-columns: repeat(2, 1fr); }}
  .platform-row {{ grid-template-columns: repeat(2, 1fr); }}
  .chart-grid {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1>ACCOUNT MARKETPLACE INTELLIGENCE</h1>
    <div class="subtitle">Executive Summary</div>
  </div>
  <div class="header-right">
    <div class="date" id="reportDate"></div>
    <div class="version" id="reportMeta"></div>
  </div>
</div>

<div class="page">

<!-- TOP KPIs -->
<div class="kpi-strip" id="kpiStrip"></div>

<!-- MARKET SHARE BAR -->
<div class="section-title">Platform Market Share</div>
<div class="share-bar" id="shareBar"></div>

<!-- PLATFORM COMPARISON -->
<div class="section-title">Platform Breakdown</div>
<div class="platform-row" id="platformRow"></div>

<!-- CHARTS -->
<div class="chart-grid">
  <div class="chart-card"><h3>Market Size by Source</h3><canvas id="chartSourceMarket"></canvas></div>
  <div class="chart-card"><h3>Category Distribution</h3><canvas id="chartCategory"></canvas></div>
</div>

<div class="chart-grid">
  <div class="chart-card"><h3>Average Price by Platform (USD)</h3><canvas id="chartPriceCompare"></canvas></div>
  <div class="chart-card"><h3>Price Distribution — All Platforms</h3><canvas id="chartPriceHist"></canvas></div>
</div>

<!-- SOURCE HEALTH -->
<div class="section-title">Source Health</div>
<div class="source-strip" id="sourceStrip"></div>

<!-- NOTABLE HIGH-VALUE LISTINGS -->
<div class="section-title">Notable High-Value Listings</div>
<div class="notable-grid" id="notableGrid"></div>

</div><!-- page -->

<div class="footer">
  Generated from live scrape data &middot; <span id="footerSources"></span> sources monitored &middot; <span id="footerListings"></span> listings scraped
</div>

<script>
const D = {data_js};

const PLAT_COLORS = {{
  Roblox: '#ef4444', Fortnite: '#a78bfa', Minecraft: '#34d399', Steam: '#60a5fa'
}};
const SRC_COLORS = ['#818cf8','#2dd4bf','#fb923c','#f87171','#60a5fa','#a78bfa','#34d399'];

Chart.defaults.color = '#7d829a';
Chart.defaults.borderColor = '#272c3d';
Chart.defaults.font.family = "'Inter', 'Segoe UI', system-ui, sans-serif";
Chart.defaults.font.size = 11;
Chart.defaults.plugins.legend.labels.boxWidth = 10;
Chart.defaults.plugins.legend.labels.padding = 14;

const platforms = D.metadata.platforms;
const sources = D.metadata.sources;
const listings = D.listings;

function fmt(n) {{ return n >= 1000000 ? (n/1000000).toFixed(1) + 'M' : n >= 1000 ? (n/1000).toFixed(1) + 'k' : n.toString(); }}
function fmtUSD(n) {{ return '$' + n.toFixed(2); }}

// ===== HEADER INFO =====
const scrapeDate = new Date(D.metadata.scrape_date || D.metadata.generated_at);
document.getElementById('reportDate').textContent = scrapeDate.toLocaleDateString('en-US', {{ weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }});
document.getElementById('reportMeta').textContent = D.metadata.version + ' · ' + D.metadata.data_source;
document.getElementById('footerSources').textContent = sources.length;
document.getElementById('footerListings').textContent = fmt(D.metadata.total_listings_scraped);

// ===== TOP KPIs =====
const pricedListings = listings.filter(l => l.price_usd > 0);
const avgPrice = pricedListings.length ? (pricedListings.reduce((s, l) => s + l.price_usd, 0) / pricedListings.length) : 0;
const uniqueSellers = new Set(listings.filter(l => l.seller).map(l => l.seller)).size;
const prices = pricedListings.map(l => l.price_usd).sort((a, b) => a - b);
const medianPrice = prices.length ? prices[Math.floor(prices.length / 2)] : 0;

document.getElementById('kpiStrip').innerHTML = `
  <div class="kpi highlight">
    <div class="number">${{fmt(D.metadata.total_listings_found)}}</div>
    <div class="label">Total Market Size</div>
    <div class="detail">across ${{sources.length}} marketplaces</div>
  </div>
  <div class="kpi">
    <div class="number">${{platforms.length}}</div>
    <div class="label">Platforms Monitored</div>
    <div class="detail">${{platforms.join(', ')}}</div>
  </div>
  <div class="kpi">
    <div class="number">${{uniqueSellers}}</div>
    <div class="label">Unique Sellers</div>
    <div class="detail">from ${{fmt(D.metadata.total_listings_scraped)}} scraped</div>
  </div>
  <div class="kpi">
    <div class="number">${{fmtUSD(avgPrice)}}</div>
    <div class="label">Avg Listing Price</div>
    <div class="detail">median ${{fmtUSD(medianPrice)}}</div>
  </div>
  <div class="kpi">
    <div class="number">${{fmt(pricedListings.filter(p => p.price_usd > 100).length)}}</div>
    <div class="label">High-Value (>$100)</div>
    <div class="detail">${{(pricedListings.filter(p => p.price_usd > 100).length / pricedListings.length * 100).toFixed(1)}}% of priced listings</div>
  </div>
`;

// ===== MARKET SHARE BAR =====
const totalMarket = Object.values(D.platform_summary).reduce((s, p) => s + p.total_listings_across_sources, 0);
document.getElementById('shareBar').innerHTML = platforms.map(p => {{
  const pct = D.platform_summary[p] ? (D.platform_summary[p].total_listings_across_sources / totalMarket * 100) : 0;
  return `<div class="segment" style="width:${{pct}}%;background:${{PLAT_COLORS[p]}}" title="${{p}}: ${{pct.toFixed(1)}}%"></div>`;
}}).join('');

// ===== PLATFORM CARDS =====
const platRow = document.getElementById('platformRow');
platRow.innerHTML = '';
platforms.forEach(p => {{
  const ps = D.platform_summary[p];
  if (!ps) return;
  const share = (ps.total_listings_across_sources / totalMarket * 100).toFixed(1);
  const srcCount = Object.keys(ps.sources).length;
  const topSource = Object.entries(ps.sources).sort((a, b) => b[1].total_on_site - a[1].total_on_site)[0];

  platRow.innerHTML += `
    <div class="platform-card ${{p.toLowerCase()}}">
      <div class="name" style="color:${{PLAT_COLORS[p]}}">${{p}}</div>
      <div class="stat-row"><span class="stat-label">Listings</span><span class="stat-value">${{fmt(ps.total_listings_across_sources)}}</span></div>
      <div class="stat-row"><span class="stat-label">Market Share</span><span class="stat-value">${{share}}%</span></div>
      <div class="stat-row"><span class="stat-label">Avg Price</span><span class="stat-value">${{fmtUSD(ps.avg_price_usd)}}</span></div>
      <div class="stat-row"><span class="stat-label">Price Range</span><span class="stat-value">${{fmtUSD(ps.price_min)}} – ${{fmtUSD(ps.price_max)}}</span></div>
      <div class="stat-row"><span class="stat-label">Top Source</span><span class="stat-value">${{topSource ? topSource[0] : '—'}}</span></div>
    </div>`;
}});

// ===== CHARTS =====

// Market size by source
const srcLabels = sources;
const srcData = sources.map(s => D.source_summary[s] ? D.source_summary[s].total_listings : 0);
new Chart(document.getElementById('chartSourceMarket'), {{
  type: 'bar',
  data: {{
    labels: srcLabels,
    datasets: [{{ data: srcData, backgroundColor: SRC_COLORS.slice(0, srcLabels.length).map(c => c + 'cc'), borderColor: SRC_COLORS.slice(0, srcLabels.length), borderWidth: 1, borderRadius: 6 }}]
  }},
  options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ beginAtZero: true, grid: {{ color: '#272c3d' }} }}, x: {{ grid: {{ display: false }} }} }} }}
}});

// Category distribution
const catLabels = Object.keys(D.category_summary);
const catData = catLabels.map(c => D.category_summary[c].count);
const catColors = ['#818cf8','#2dd4bf','#fb923c','#f87171','#60a5fa'];
new Chart(document.getElementById('chartCategory'), {{
  type: 'doughnut',
  data: {{ labels: catLabels, datasets: [{{ data: catData, backgroundColor: catColors.slice(0, catLabels.length), borderWidth: 0 }}] }},
  options: {{ responsive: true, cutout: '55%', plugins: {{ legend: {{ position: 'bottom' }} }} }}
}});

// Avg price comparison
new Chart(document.getElementById('chartPriceCompare'), {{
  type: 'bar',
  data: {{
    labels: platforms,
    datasets: [{{ data: platforms.map(p => D.platform_summary[p] ? D.platform_summary[p].avg_price_usd : 0),
      backgroundColor: platforms.map(p => PLAT_COLORS[p] + 'cc'), borderColor: platforms.map(p => PLAT_COLORS[p]), borderWidth: 1, borderRadius: 6 }}]
  }},
  options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ beginAtZero: true, grid: {{ color: '#272c3d' }} }}, x: {{ grid: {{ display: false }} }} }} }}
}});

// Price histogram
const buckets = [0, 5, 10, 25, 50, 100, 200, 500, Infinity];
const bucketLabels = buckets.slice(0, -1).map((b, i) => '$' + b + (buckets[i+1] === Infinity ? '+' : '–' + buckets[i+1]));
const bucketData = bucketLabels.map((_, i) => prices.filter(p => p >= buckets[i] && p < buckets[i+1]).length);
new Chart(document.getElementById('chartPriceHist'), {{
  type: 'bar',
  data: {{
    labels: bucketLabels,
    datasets: [{{ data: bucketData, backgroundColor: '#818cf8aa', borderColor: '#818cf8', borderWidth: 1, borderRadius: 4 }}]
  }},
  options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ beginAtZero: true, grid: {{ color: '#272c3d' }} }}, x: {{ grid: {{ display: false }} }} }} }}
}});

// ===== SOURCE HEALTH =====
const sourceStrip = document.getElementById('sourceStrip');
sourceStrip.innerHTML = '';
sources.forEach(s => {{
  const ss = D.source_summary[s];
  if (!ss) return;
  const scraped = listings.filter(l => l.source === s).length;
  const coverage = ss.total_listings > 0 ? (scraped / ss.total_listings * 100) : 0;
  // Health: good if we scraped something, warn if low coverage, bad if zero
  const health = scraped === 0 ? 'bad' : coverage < 1 ? 'warn' : 'good';

  sourceStrip.innerHTML += `
    <div class="source-card">
      <div class="source-dot ${{health}}"></div>
      <div class="source-info">
        <div class="source-name">${{s}}</div>
        <div class="source-meta">${{fmt(ss.total_listings)}} listings &middot; ${{scraped}} scraped (${{coverage.toFixed(1)}}%)</div>
      </div>
    </div>`;
}});

// ===== NOTABLE HIGH-VALUE LISTINGS =====
const notableGrid = document.getElementById('notableGrid');
const topListings = [...pricedListings].sort((a, b) => b.price_usd - a.price_usd).slice(0, 5);
notableGrid.innerHTML = '';
topListings.forEach(l => {{
  const title = l.title && l.title.length > 55 ? l.title.slice(0, 53) + '…' : (l.title || 'Untitled');
  notableGrid.innerHTML += `
    <div class="notable-card">
      <div class="notable-price">${{fmtUSD(l.price_usd)}}</div>
      <div class="notable-title" title="${{(l.title || '').replace(/"/g, '&quot;')}}">${{title}}</div>
      <div class="notable-meta">${{l.platform}} &middot; ${{l.source}} &middot; ${{l.seller || 'Unknown seller'}}</div>
    </div>`;
}});

</script>
</body>
</html>
"""

import os
output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exec_dashboard.html")
with open(output_path, "w") as f:
    f.write(html)
print(f"Exec dashboard written to {output_path}")
print(f"File size: {len(html):,} bytes")
