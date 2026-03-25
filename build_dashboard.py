#!/usr/bin/env python3
"""
Build the interactive HTML dashboard for Roblox Accounts Monitoring.
Embeds the data JSON directly into the HTML for a fully self-contained file.
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
<title>Roblox Accounts Monitoring Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root {{
  --bg: #0f1117;
  --surface: #1a1d27;
  --surface2: #242836;
  --border: #2e3347;
  --text: #e4e6f0;
  --text-dim: #8b8fa3;
  --accent: #6c5ce7;
  --accent2: #00cec9;
  --red: #ff6b6b;
  --orange: #ffa502;
  --green: #26de81;
  --blue: #4ecdc4;
  --roblox: #e74c3c;
  --fortnite: #9b59b6;
  --minecraft: #27ae60;
  --steam: #2980b9;
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }}

.header {{
  background: linear-gradient(135deg, #1a1d27 0%, #242836 100%);
  border-bottom: 1px solid var(--border);
  padding: 20px 32px;
  display: flex; align-items: center; justify-content: space-between;
}}
.header h1 {{ font-size: 22px; font-weight: 600; }}
.header h1 span {{ color: var(--roblox); }}
.header-meta {{ color: var(--text-dim); font-size: 13px; }}

.nav {{
  display: flex; gap: 4px; padding: 12px 32px; background: var(--surface);
  border-bottom: 1px solid var(--border); flex-wrap: wrap;
}}
.nav button {{
  background: transparent; border: 1px solid var(--border); color: var(--text-dim);
  padding: 8px 18px; border-radius: 8px; cursor: pointer; font-size: 13px;
  transition: all 0.2s;
}}
.nav button:hover {{ border-color: var(--accent); color: var(--text); }}
.nav button.active {{ background: var(--accent); border-color: var(--accent); color: #fff; }}

.container {{ max-width: 1440px; margin: 0 auto; padding: 24px 32px; }}

.section {{ display: none; }}
.section.active {{ display: block; }}

/* KPI Cards */
.kpi-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px; margin-bottom: 28px;
}}
.kpi-card {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
  padding: 20px; position: relative; overflow: hidden;
}}
.kpi-card::before {{
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
}}
.kpi-card.roblox::before {{ background: var(--roblox); }}
.kpi-card.fortnite::before {{ background: var(--fortnite); }}
.kpi-card.minecraft::before {{ background: var(--minecraft); }}
.kpi-card.steam::before {{ background: var(--steam); }}
.kpi-label {{ font-size: 12px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }}
.kpi-value {{ font-size: 28px; font-weight: 700; }}
.kpi-sub {{ font-size: 12px; color: var(--text-dim); margin-top: 4px; }}
.kpi-change {{ font-size: 12px; margin-top: 6px; }}
.kpi-change.up {{ color: var(--red); }}
.kpi-change.down {{ color: var(--green); }}

.chart-row {{
  display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px;
}}
.chart-row.full {{ grid-template-columns: 1fr; }}
.chart-row.triple {{ grid-template-columns: 1fr 1fr 1fr; }}

.chart-card {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
  padding: 20px;
}}
.chart-card h3 {{
  font-size: 14px; font-weight: 600; margin-bottom: 16px; color: var(--text);
}}
.chart-card canvas {{ max-height: 340px; }}

/* Tables */
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; padding: 10px 12px; border-bottom: 2px solid var(--border);
     color: var(--text-dim); font-weight: 600; text-transform: uppercase; font-size: 11px;
     letter-spacing: 0.5px; }}
td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); }}
tr:hover {{ background: var(--surface2); }}

/* Alerts */
.alert-item {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
  padding: 16px 20px; margin-bottom: 10px; display: flex; align-items: flex-start; gap: 14px;
}}
.alert-badge {{
  padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 600;
  text-transform: uppercase; white-space: nowrap;
}}
.alert-badge.critical {{ background: #ff6b6b33; color: var(--red); }}
.alert-badge.high {{ background: #ffa50233; color: var(--orange); }}
.alert-badge.medium {{ background: #6c5ce733; color: var(--accent); }}
.alert-badge.low {{ background: #26de8133; color: var(--green); }}
.alert-desc {{ font-size: 14px; }}
.alert-time {{ font-size: 11px; color: var(--text-dim); margin-top: 4px; }}

/* Filters */
.filters {{
  display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; align-items: center;
}}
.filters label {{ font-size: 12px; color: var(--text-dim); }}
.filters select {{
  background: var(--surface2); border: 1px solid var(--border); color: var(--text);
  padding: 6px 12px; border-radius: 6px; font-size: 13px;
}}

/* Platform tags */
.platform-tag {{
  display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;
}}
.platform-tag.Roblox {{ background: #e74c3c33; color: var(--roblox); }}
.platform-tag.Fortnite {{ background: #9b59b633; color: var(--fortnite); }}
.platform-tag.Minecraft {{ background: #27ae6033; color: var(--minecraft); }}
.platform-tag.Steam {{ background: #2980b933; color: var(--steam); }}

.source-type-tag {{
  display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px;
}}
.source-type-tag.marketplace {{ background: #4ecdc433; color: var(--blue); }}
.source-type-tag.forum {{ background: #ffa50233; color: var(--orange); }}
.source-type-tag.social {{ background: #9b59b633; color: var(--fortnite); }}

@media (max-width: 900px) {{
  .chart-row {{ grid-template-columns: 1fr; }}
  .chart-row.triple {{ grid-template-columns: 1fr; }}
  .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
}}
</style>
</head>
<body>
<div class="header">
  <h1><span>Roblox</span> Accounts Monitoring Dashboard</h1>
  <div class="header-meta">
    <div>Data Period: Apr 2025 – Mar 2026 &nbsp;|&nbsp; Refresh: Monthly &nbsp;|&nbsp; Sources Tracked: <span id="sourceCount"></span></div>
    <div style="margin-top:4px">Comparative Platforms: Fortnite, Minecraft, Steam</div>
  </div>
</div>

<div class="nav" id="nav">
  <button class="active" data-tab="overview">Overview</button>
  <button data-tab="trends">Trends &amp; Timeline</button>
  <button data-tab="sources">Sources</button>
  <button data-tab="keywords">Keywords</button>
  <button data-tab="regions">Regions</button>
  <button data-tab="languages">Languages</button>
  <button data-tab="quality">Quality Tiers</button>
  <button data-tab="alerts">Alerts</button>
</div>

<div class="container">

<!-- ========== OVERVIEW ========== -->
<div class="section active" id="sec-overview">
  <div class="kpi-grid" id="kpiGrid"></div>
  <div class="chart-row">
    <div class="chart-card"><h3>Total Listings Over Time (All Platforms)</h3><canvas id="chartOverviewListings"></canvas></div>
    <div class="chart-card"><h3>Average Price Over Time (USD)</h3><canvas id="chartOverviewPrices"></canvas></div>
  </div>
  <div class="chart-row">
    <div class="chart-card"><h3>Listings by Source Type</h3><canvas id="chartSourceType"></canvas></div>
    <div class="chart-card"><h3>Quality Tier Distribution</h3><canvas id="chartQualityOverview"></canvas></div>
  </div>
</div>

<!-- ========== TRENDS ========== -->
<div class="section" id="sec-trends">
  <div class="filters">
    <label>Platform:</label>
    <select id="trendPlatform"><option value="all">All Platforms</option></select>
  </div>
  <div class="chart-row full">
    <div class="chart-card"><h3>Monthly Listing Volume</h3><canvas id="chartTrendVolume"></canvas></div>
  </div>
  <div class="chart-row">
    <div class="chart-card"><h3>Average Price Trend</h3><canvas id="chartTrendPrice"></canvas></div>
    <div class="chart-card"><h3>New Listings vs Total</h3><canvas id="chartTrendNew"></canvas></div>
  </div>
  <div class="chart-row">
    <div class="chart-card"><h3>Unique Sellers</h3><canvas id="chartTrendSellers"></canvas></div>
    <div class="chart-card"><h3>Month-over-Month Growth (%)</h3><canvas id="chartTrendGrowth"></canvas></div>
  </div>
</div>

<!-- ========== SOURCES ========== -->
<div class="section" id="sec-sources">
  <div class="filters">
    <label>Platform:</label>
    <select id="sourcePlatform"><option value="all">All Platforms</option></select>
    <label>Source Type:</label>
    <select id="sourceType">
      <option value="all">All Types</option>
      <option value="marketplace">Marketplaces</option>
      <option value="forum">Forums</option>
      <option value="social">Social</option>
    </select>
  </div>
  <div class="chart-row">
    <div class="chart-card"><h3>Listings by Source Type</h3><canvas id="chartSourcePie"></canvas></div>
    <div class="chart-card"><h3>Top Sources by Listing Count</h3><canvas id="chartSourceBar"></canvas></div>
  </div>
  <div class="chart-card" style="margin-bottom:24px">
    <h3>Source Details</h3>
    <div class="table-wrap"><table id="sourceTable"><thead><tr>
      <th>Source</th><th>Type</th><th>Platform</th><th>Listings</th><th>Avg Price</th><th>Verified Sellers</th><th>Last Scraped</th>
    </tr></thead><tbody></tbody></table></div>
  </div>
</div>

<!-- ========== KEYWORDS ========== -->
<div class="section" id="sec-keywords">
  <div class="filters">
    <label>Platform:</label>
    <select id="kwPlatform"></select>
  </div>
  <div class="chart-row full">
    <div class="chart-card"><h3>Top Keywords by Mention Count (Latest Month)</h3><canvas id="chartKwBar"></canvas></div>
  </div>
  <div class="chart-row full">
    <div class="chart-card"><h3>Keyword Trends Over Time</h3><canvas id="chartKwTrend"></canvas></div>
  </div>
  <div class="chart-card">
    <h3>Keyword Details</h3>
    <div class="table-wrap"><table id="kwTable"><thead><tr>
      <th>Keyword</th><th>Mentions (Latest)</th><th>Avg Price</th><th>Sentiment</th><th>Trend</th>
    </tr></thead><tbody></tbody></table></div>
  </div>
</div>

<!-- ========== REGIONS ========== -->
<div class="section" id="sec-regions">
  <div class="filters">
    <label>Platform:</label>
    <select id="regionPlatform"><option value="all">All Platforms</option></select>
  </div>
  <div class="chart-row">
    <div class="chart-card"><h3>Listings by Region</h3><canvas id="chartRegionBar"></canvas></div>
    <div class="chart-card"><h3>Average Price by Region (USD)</h3><canvas id="chartRegionPrice"></canvas></div>
  </div>
  <div class="chart-card">
    <h3>Regional Breakdown</h3>
    <div class="table-wrap"><table id="regionTable"><thead><tr>
      <th>Region</th><th>Platform</th><th>Listings</th><th>Avg Price</th><th>Dominant Language</th><th>Sellers</th>
    </tr></thead><tbody></tbody></table></div>
  </div>
</div>

<!-- ========== LANGUAGES ========== -->
<div class="section" id="sec-languages">
  <div class="filters">
    <label>Platform:</label>
    <select id="langPlatform"><option value="all">All Platforms</option></select>
  </div>
  <div class="chart-row">
    <div class="chart-card"><h3>Listings by Language</h3><canvas id="chartLangBar"></canvas></div>
    <div class="chart-card"><h3>Average Price by Language (USD)</h3><canvas id="chartLangPrice"></canvas></div>
  </div>
  <div class="chart-card">
    <h3>Language Details</h3>
    <div class="table-wrap"><table id="langTable"><thead><tr>
      <th>Language</th><th>Platform</th><th>Listings</th><th>Avg Price</th><th>% with Images</th>
    </tr></thead><tbody></tbody></table></div>
  </div>
</div>

<!-- ========== QUALITY ========== -->
<div class="section" id="sec-quality">
  <div class="chart-row">
    <div class="chart-card"><h3>Quality Tier Distribution by Platform</h3><canvas id="chartQualityStacked"></canvas></div>
    <div class="chart-card"><h3>Average Price by Quality Tier</h3><canvas id="chartQualityPrice"></canvas></div>
  </div>
  <div class="chart-card">
    <h3>Quality Tier Details</h3>
    <div class="table-wrap"><table id="qualityTable"><thead><tr>
      <th>Platform</th><th>Tier</th><th>Listings</th><th>% of Total</th><th>Avg Price</th><th>Median Price</th>
    </tr></thead><tbody></tbody></table></div>
  </div>
</div>

<!-- ========== ALERTS ========== -->
<div class="section" id="sec-alerts">
  <div class="filters">
    <label>Severity:</label>
    <select id="alertSeverity">
      <option value="all">All</option>
      <option value="critical">Critical</option>
      <option value="high">High</option>
      <option value="medium">Medium</option>
      <option value="low">Low</option>
    </select>
    <label>Platform:</label>
    <select id="alertPlatform"><option value="all">All Platforms</option></select>
  </div>
  <div id="alertList"></div>
</div>

</div><!-- container -->

<script>
const D = {data_js};

const COLORS = {{
  Roblox: '#e74c3c', Fortnite: '#9b59b6', Minecraft: '#27ae60', Steam: '#2980b9'
}};
const COLORS_ARR = ['#e74c3c','#9b59b6','#27ae60','#2980b9'];

// Chart.js defaults
Chart.defaults.color = '#8b8fa3';
Chart.defaults.borderColor = '#2e3347';
Chart.defaults.font.family = "'Segoe UI', system-ui, sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.plugins.legend.labels.boxWidth = 12;
Chart.defaults.plugins.legend.labels.padding = 16;

// ============ NAVIGATION ============
document.getElementById('nav').addEventListener('click', e => {{
  if (e.target.tagName !== 'BUTTON') return;
  document.querySelectorAll('.nav button').forEach(b => b.classList.remove('active'));
  e.target.classList.add('active');
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.getElementById('sec-' + e.target.dataset.tab).classList.add('active');
}});

// ============ UTILITIES ============
function fmt(n) {{ return n >= 1000 ? (n/1000).toFixed(1) + 'k' : n.toString(); }}
function fmtUSD(n) {{ return '$' + n.toFixed(2); }}
function pct(n) {{ return (n * 100).toFixed(1) + '%'; }}

function populateSelect(id, options, includeAll) {{
  const sel = document.getElementById(id);
  if (!sel) return;
  if (includeAll && !sel.querySelector('option[value="all"]')) {{
    sel.innerHTML = '<option value="all">All Platforms</option>';
  }}
  options.forEach(o => {{
    const opt = document.createElement('option');
    opt.value = o; opt.textContent = o;
    sel.appendChild(opt);
  }});
}}

const platforms = D.config.platforms;
['trendPlatform','sourcePlatform','kwPlatform','regionPlatform','langPlatform','alertPlatform'].forEach(id => {{
  populateSelect(id, platforms, id !== 'kwPlatform');
}});
// kwPlatform starts with Roblox
const kwSel = document.getElementById('kwPlatform');
kwSel.innerHTML = '';
platforms.forEach(p => {{ const o = document.createElement('option'); o.value = p; o.textContent = p; kwSel.appendChild(o); }});

document.getElementById('sourceCount').textContent = D.metadata.sources_tracked;

// ============ CHART INSTANCES ============
const charts = {{}};
function destroyChart(id) {{ if(charts[id]) {{ charts[id].destroy(); delete charts[id]; }} }}

// ============ OVERVIEW ============
function renderOverview() {{
  // KPI cards - latest month for each platform
  const months = [...new Set(D.monthly_trends.map(r => r.month))].sort();
  const latestMonth = months[months.length - 1];
  const prevMonth = months[months.length - 2];
  const grid = document.getElementById('kpiGrid');
  grid.innerHTML = '';

  platforms.forEach(p => {{
    const latest = D.monthly_trends.find(r => r.month === latestMonth && r.platform === p);
    const prev = D.monthly_trends.find(r => r.month === prevMonth && r.platform === p);
    if (!latest) return;
    const listChange = prev ? ((latest.total_listings - prev.total_listings) / prev.total_listings * 100).toFixed(1) : 0;
    const priceChange = prev ? ((latest.avg_price_usd - prev.avg_price_usd) / prev.avg_price_usd * 100).toFixed(1) : 0;

    grid.innerHTML += `
      <div class="kpi-card ${{p.toLowerCase()}}">
        <div class="kpi-label">${{p}} Listings</div>
        <div class="kpi-value">${{fmt(latest.total_listings)}}</div>
        <div class="kpi-change ${{parseFloat(listChange) > 0 ? 'up' : 'down'}}">${{parseFloat(listChange) > 0 ? '&#9650;' : '&#9660;'}} ${{Math.abs(listChange)}}% vs prev month</div>
      </div>
      <div class="kpi-card ${{p.toLowerCase()}}">
        <div class="kpi-label">${{p}} Avg Price</div>
        <div class="kpi-value">${{fmtUSD(latest.avg_price_usd)}}</div>
        <div class="kpi-change ${{parseFloat(priceChange) > 0 ? 'up' : 'down'}}">${{parseFloat(priceChange) > 0 ? '&#9650;' : '&#9660;'}} ${{Math.abs(priceChange)}}%</div>
      </div>`;
  }});

  // Listings over time
  destroyChart('overviewListings');
  const labels = months;
  const datasets = platforms.map(p => ({{
    label: p,
    data: months.map(m => {{
      const r = D.monthly_trends.find(x => x.month === m && x.platform === p);
      return r ? r.total_listings : 0;
    }}),
    borderColor: COLORS[p],
    backgroundColor: COLORS[p] + '22',
    fill: true,
    tension: 0.3,
  }}));
  charts.overviewListings = new Chart(document.getElementById('chartOverviewListings'), {{
    type: 'line',
    data: {{ labels, datasets }},
    options: {{ responsive: true, plugins: {{ legend: {{ position: 'top' }} }}, scales: {{ y: {{ beginAtZero: true }} }} }}
  }});

  // Prices over time
  destroyChart('overviewPrices');
  charts.overviewPrices = new Chart(document.getElementById('chartOverviewPrices'), {{
    type: 'line',
    data: {{
      labels: months,
      datasets: platforms.map(p => ({{
        label: p,
        data: months.map(m => {{
          const r = D.monthly_trends.find(x => x.month === m && x.platform === p);
          return r ? r.avg_price_usd : 0;
        }}),
        borderColor: COLORS[p],
        tension: 0.3,
      }}))
    }},
    options: {{ responsive: true, plugins: {{ legend: {{ position: 'top' }} }}, scales: {{ y: {{ beginAtZero: true }} }} }}
  }});

  // Source type donut
  destroyChart('sourceType');
  const sourceAgg = {{}};
  D.source_breakdown.forEach(r => {{ sourceAgg[r.source_type] = (sourceAgg[r.source_type] || 0) + r.listings_count; }});
  charts.sourceType = new Chart(document.getElementById('chartSourceType'), {{
    type: 'doughnut',
    data: {{
      labels: Object.keys(sourceAgg).map(s => s.charAt(0).toUpperCase() + s.slice(1)),
      datasets: [{{ data: Object.values(sourceAgg), backgroundColor: ['#4ecdc4','#ffa502','#9b59b6'] }}]
    }},
    options: {{ responsive: true, plugins: {{ legend: {{ position: 'bottom' }} }} }}
  }});

  // Quality overview
  destroyChart('qualityOverview');
  const qAgg = {{}};
  D.quality_distribution.forEach(r => {{ qAgg[r.quality_tier] = (qAgg[r.quality_tier] || 0) + r.listings_count; }});
  charts.qualityOverview = new Chart(document.getElementById('chartQualityOverview'), {{
    type: 'doughnut',
    data: {{
      labels: Object.keys(qAgg),
      datasets: [{{ data: Object.values(qAgg), backgroundColor: ['#6c5ce7','#00cec9','#ffa502','#ff6b6b'] }}]
    }},
    options: {{ responsive: true, plugins: {{ legend: {{ position: 'bottom' }} }} }}
  }});
}}

// ============ TRENDS ============
function renderTrends() {{
  const plat = document.getElementById('trendPlatform').value;
  const months = [...new Set(D.monthly_trends.map(r => r.month))].sort();
  const filtered = plat === 'all' ? D.monthly_trends : D.monthly_trends.filter(r => r.platform === plat);
  const activePlats = plat === 'all' ? platforms : [plat];

  // Volume
  destroyChart('trendVolume');
  charts.trendVolume = new Chart(document.getElementById('chartTrendVolume'), {{
    type: 'bar',
    data: {{
      labels: months,
      datasets: activePlats.map(p => ({{
        label: p,
        data: months.map(m => {{
          const r = filtered.find(x => x.month === m && x.platform === p);
          return r ? r.total_listings : 0;
        }}),
        backgroundColor: COLORS[p] + 'aa',
        borderColor: COLORS[p],
        borderWidth: 1,
      }}))
    }},
    options: {{ responsive: true, plugins: {{ legend: {{ position: 'top' }} }}, scales: {{ y: {{ beginAtZero: true }} }} }}
  }});

  // Price trend
  destroyChart('trendPrice');
  charts.trendPrice = new Chart(document.getElementById('chartTrendPrice'), {{
    type: 'line',
    data: {{
      labels: months,
      datasets: activePlats.map(p => ({{
        label: p,
        data: months.map(m => {{
          const r = filtered.find(x => x.month === m && x.platform === p);
          return r ? r.avg_price_usd : 0;
        }}),
        borderColor: COLORS[p], tension: 0.3,
      }}))
    }},
    options: {{ responsive: true, scales: {{ y: {{ beginAtZero: true }} }} }}
  }});

  // New vs Total
  destroyChart('trendNew');
  const mainPlat = plat === 'all' ? 'Roblox' : plat;
  charts.trendNew = new Chart(document.getElementById('chartTrendNew'), {{
    type: 'bar',
    data: {{
      labels: months,
      datasets: [
        {{
          label: 'Total Listings',
          data: months.map(m => {{ const r = D.monthly_trends.find(x => x.month === m && x.platform === mainPlat); return r ? r.total_listings : 0; }}),
          backgroundColor: COLORS[mainPlat] + '55',
          borderColor: COLORS[mainPlat],
          borderWidth: 1,
        }},
        {{
          label: 'New Listings',
          data: months.map(m => {{ const r = D.monthly_trends.find(x => x.month === m && x.platform === mainPlat); return r ? r.new_listings : 0; }}),
          backgroundColor: COLORS[mainPlat] + 'cc',
          borderColor: COLORS[mainPlat],
          borderWidth: 1,
        }}
      ]
    }},
    options: {{ responsive: true, plugins: {{ title: {{ display: true, text: mainPlat }} }}, scales: {{ y: {{ beginAtZero: true }} }} }}
  }});

  // Sellers
  destroyChart('trendSellers');
  charts.trendSellers = new Chart(document.getElementById('chartTrendSellers'), {{
    type: 'line',
    data: {{
      labels: months,
      datasets: activePlats.map(p => ({{
        label: p,
        data: months.map(m => {{ const r = filtered.find(x => x.month === m && x.platform === p); return r ? r.total_sellers : 0; }}),
        borderColor: COLORS[p], tension: 0.3,
      }}))
    }},
    options: {{ responsive: true, scales: {{ y: {{ beginAtZero: true }} }} }}
  }});

  // Growth
  destroyChart('trendGrowth');
  charts.trendGrowth = new Chart(document.getElementById('chartTrendGrowth'), {{
    type: 'bar',
    data: {{
      labels: months.slice(1),
      datasets: activePlats.map(p => {{
        const vals = months.map(m => {{ const r = D.monthly_trends.find(x => x.month === m && x.platform === p); return r ? r.total_listings : 0; }});
        const growth = vals.slice(1).map((v, i) => vals[i] > 0 ? ((v - vals[i]) / vals[i] * 100).toFixed(1) : 0);
        return {{ label: p, data: growth, backgroundColor: COLORS[p] + '88', borderColor: COLORS[p], borderWidth: 1 }};
      }})
    }},
    options: {{ responsive: true, scales: {{ y: {{ }} }} }}
  }});
}}

document.getElementById('trendPlatform').addEventListener('change', renderTrends);

// ============ SOURCES ============
function renderSources() {{
  const plat = document.getElementById('sourcePlatform').value;
  const stype = document.getElementById('sourceType').value;
  let filtered = D.source_breakdown;
  if (plat !== 'all') filtered = filtered.filter(r => r.platform === plat);
  if (stype !== 'all') filtered = filtered.filter(r => r.source_type === stype);

  // Pie
  destroyChart('sourcePie');
  const typeAgg = {{}};
  filtered.forEach(r => {{ typeAgg[r.source_type] = (typeAgg[r.source_type] || 0) + r.listings_count; }});
  charts.sourcePie = new Chart(document.getElementById('chartSourcePie'), {{
    type: 'doughnut',
    data: {{
      labels: Object.keys(typeAgg).map(s => s.charAt(0).toUpperCase() + s.slice(1)),
      datasets: [{{ data: Object.values(typeAgg), backgroundColor: ['#4ecdc4','#ffa502','#9b59b6'] }}]
    }},
    options: {{ responsive: true, plugins: {{ legend: {{ position: 'bottom' }} }} }}
  }});

  // Top sources bar
  destroyChart('sourceBar');
  const srcAgg = {{}};
  filtered.forEach(r => {{ srcAgg[r.source_name] = (srcAgg[r.source_name] || 0) + r.listings_count; }});
  const sorted = Object.entries(srcAgg).sort((a, b) => b[1] - a[1]).slice(0, 15);
  charts.sourceBar = new Chart(document.getElementById('chartSourceBar'), {{
    type: 'bar',
    data: {{
      labels: sorted.map(s => s[0]),
      datasets: [{{ data: sorted.map(s => s[1]), backgroundColor: '#6c5ce7aa', borderColor: '#6c5ce7', borderWidth: 1 }}]
    }},
    options: {{ responsive: true, indexAxis: 'y', plugins: {{ legend: {{ display: false }} }} }}
  }});

  // Table
  const tbody = document.querySelector('#sourceTable tbody');
  tbody.innerHTML = '';
  const sortedAll = [...filtered].sort((a, b) => b.listings_count - a.listings_count);
  sortedAll.forEach(r => {{
    const ago = Math.round((Date.now() - new Date(r.last_scraped).getTime()) / 3600000);
    tbody.innerHTML += `<tr>
      <td>${{r.source_name}}</td>
      <td><span class="source-type-tag ${{r.source_type}}">${{r.source_type}}</span></td>
      <td><span class="platform-tag ${{r.platform}}">${{r.platform}}</span></td>
      <td>${{r.listings_count}}</td>
      <td>${{fmtUSD(r.avg_price_usd)}}</td>
      <td>${{pct(r.verified_sellers_pct)}}</td>
      <td>${{ago}}h ago</td>
    </tr>`;
  }});
}}

document.getElementById('sourcePlatform').addEventListener('change', renderSources);
document.getElementById('sourceType').addEventListener('change', renderSources);

// ============ KEYWORDS ============
function renderKeywords() {{
  const plat = document.getElementById('kwPlatform').value;
  const kwData = D.keyword_trends.filter(r => r.platform === plat);
  const months = [...new Set(kwData.map(r => r.month))].sort();
  const latestMonth = months[months.length - 1];
  const keywords = [...new Set(kwData.map(r => r.keyword))];

  // Latest month bar
  destroyChart('kwBar');
  const latestData = kwData.filter(r => r.month === latestMonth).sort((a, b) => b.mention_count - a.mention_count);
  charts.kwBar = new Chart(document.getElementById('chartKwBar'), {{
    type: 'bar',
    data: {{
      labels: latestData.map(r => r.keyword),
      datasets: [{{ data: latestData.map(r => r.mention_count), backgroundColor: COLORS[plat] + 'aa', borderColor: COLORS[plat], borderWidth: 1 }}]
    }},
    options: {{ responsive: true, indexAxis: 'y', plugins: {{ legend: {{ display: false }} }} }}
  }});

  // Trend lines for top 5
  destroyChart('kwTrend');
  const top5 = latestData.slice(0, 5).map(r => r.keyword);
  const trendColors = ['#e74c3c','#9b59b6','#27ae60','#2980b9','#ffa502'];
  charts.kwTrend = new Chart(document.getElementById('chartKwTrend'), {{
    type: 'line',
    data: {{
      labels: months,
      datasets: top5.map((kw, i) => ({{
        label: kw,
        data: months.map(m => {{ const r = kwData.find(x => x.month === m && x.keyword === kw); return r ? r.mention_count : 0; }}),
        borderColor: trendColors[i], tension: 0.3,
      }}))
    }},
    options: {{ responsive: true }}
  }});

  // Table
  const tbody = document.querySelector('#kwTable tbody');
  tbody.innerHTML = '';
  const firstMonth = months[0];
  latestData.forEach(r => {{
    const first = kwData.find(x => x.keyword === r.keyword && x.month === firstMonth);
    const trend = first ? ((r.mention_count - first.mention_count) / first.mention_count * 100).toFixed(1) : '—';
    const sentColor = r.sentiment_score > 0.3 ? 'var(--green)' : r.sentiment_score < -0.1 ? 'var(--red)' : 'var(--text-dim)';
    tbody.innerHTML += `<tr>
      <td>${{r.keyword}}</td>
      <td>${{r.mention_count}}</td>
      <td>${{fmtUSD(r.avg_listing_price_usd)}}</td>
      <td style="color:${{sentColor}}">${{r.sentiment_score.toFixed(2)}}</td>
      <td>${{trend}}%</td>
    </tr>`;
  }});
}}

document.getElementById('kwPlatform').addEventListener('change', renderKeywords);

// ============ REGIONS ============
function renderRegions() {{
  const plat = document.getElementById('regionPlatform').value;
  let filtered = D.regional_data;
  if (plat !== 'all') filtered = filtered.filter(r => r.platform === plat);

  // Aggregate by region
  const regAgg = {{}};
  const regPrice = {{}};
  filtered.forEach(r => {{
    regAgg[r.region] = (regAgg[r.region] || 0) + r.listings_count;
    if (!regPrice[r.region]) regPrice[r.region] = [];
    regPrice[r.region].push(r.avg_price_usd);
  }});
  const regions = Object.keys(regAgg).sort((a, b) => regAgg[b] - regAgg[a]);

  destroyChart('regionBar');
  charts.regionBar = new Chart(document.getElementById('chartRegionBar'), {{
    type: 'bar',
    data: {{
      labels: regions,
      datasets: [{{ data: regions.map(r => regAgg[r]), backgroundColor: '#6c5ce7aa', borderColor: '#6c5ce7', borderWidth: 1 }}]
    }},
    options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }} }}
  }});

  destroyChart('regionPrice');
  charts.regionPrice = new Chart(document.getElementById('chartRegionPrice'), {{
    type: 'bar',
    data: {{
      labels: regions,
      datasets: [{{ data: regions.map(r => (regPrice[r].reduce((a,b) => a+b, 0) / regPrice[r].length).toFixed(2)), backgroundColor: '#00cec9aa', borderColor: '#00cec9', borderWidth: 1 }}]
    }},
    options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }} }}
  }});

  // Table
  const tbody = document.querySelector('#regionTable tbody');
  tbody.innerHTML = '';
  [...filtered].sort((a, b) => b.listings_count - a.listings_count).forEach(r => {{
    tbody.innerHTML += `<tr>
      <td>${{r.region}}</td>
      <td><span class="platform-tag ${{r.platform}}">${{r.platform}}</span></td>
      <td>${{r.listings_count}}</td>
      <td>${{fmtUSD(r.avg_price_usd)}}</td>
      <td>${{r.dominant_language}}</td>
      <td>${{r.seller_count}}</td>
    </tr>`;
  }});
}}

document.getElementById('regionPlatform').addEventListener('change', renderRegions);

// ============ LANGUAGES ============
function renderLanguages() {{
  const plat = document.getElementById('langPlatform').value;
  let filtered = D.language_data;
  if (plat !== 'all') filtered = filtered.filter(r => r.platform === plat);

  const langAgg = {{}};
  const langPrice = {{}};
  filtered.forEach(r => {{
    langAgg[r.language] = (langAgg[r.language] || 0) + r.listings_count;
    if (!langPrice[r.language]) langPrice[r.language] = [];
    langPrice[r.language].push(r.avg_price_usd);
  }});
  const langs = Object.keys(langAgg).sort((a, b) => langAgg[b] - langAgg[a]);

  destroyChart('langBar');
  charts.langBar = new Chart(document.getElementById('chartLangBar'), {{
    type: 'bar',
    data: {{
      labels: langs,
      datasets: [{{ data: langs.map(l => langAgg[l]), backgroundColor: '#e74c3caa', borderColor: '#e74c3c', borderWidth: 1 }}]
    }},
    options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }} }}
  }});

  destroyChart('langPrice');
  charts.langPrice = new Chart(document.getElementById('chartLangPrice'), {{
    type: 'bar',
    data: {{
      labels: langs,
      datasets: [{{ data: langs.map(l => (langPrice[l].reduce((a,b) => a+b, 0) / langPrice[l].length).toFixed(2)), backgroundColor: '#9b59b6aa', borderColor: '#9b59b6', borderWidth: 1 }}]
    }},
    options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }} }}
  }});

  // Table
  const tbody = document.querySelector('#langTable tbody');
  tbody.innerHTML = '';
  [...filtered].sort((a, b) => b.listings_count - a.listings_count).forEach(r => {{
    tbody.innerHTML += `<tr>
      <td>${{r.language}}</td>
      <td><span class="platform-tag ${{r.platform}}">${{r.platform}}</span></td>
      <td>${{r.listings_count}}</td>
      <td>${{fmtUSD(r.avg_price_usd)}}</td>
      <td>${{pct(r.pct_with_images)}}</td>
    </tr>`;
  }});
}}

document.getElementById('langPlatform').addEventListener('change', renderLanguages);

// ============ QUALITY ============
function renderQuality() {{
  const tiers = D.config.quality_tiers;
  const tierColors = ['#6c5ce7','#00cec9','#ffa502','#ff6b6b'];

  destroyChart('qualityStacked');
  charts.qualityStacked = new Chart(document.getElementById('chartQualityStacked'), {{
    type: 'bar',
    data: {{
      labels: platforms,
      datasets: tiers.map((t, i) => ({{
        label: t,
        data: platforms.map(p => {{
          const r = D.quality_distribution.find(x => x.platform === p && x.quality_tier === t);
          return r ? r.listings_count : 0;
        }}),
        backgroundColor: tierColors[i] + 'aa',
        borderColor: tierColors[i],
        borderWidth: 1,
      }}))
    }},
    options: {{ responsive: true, scales: {{ x: {{ stacked: true }}, y: {{ stacked: true, beginAtZero: true }} }} }}
  }});

  destroyChart('qualityPrice');
  charts.qualityPrice = new Chart(document.getElementById('chartQualityPrice'), {{
    type: 'bar',
    data: {{
      labels: tiers,
      datasets: platforms.map((p, i) => ({{
        label: p,
        data: tiers.map(t => {{
          const r = D.quality_distribution.find(x => x.platform === p && x.quality_tier === t);
          return r ? r.avg_price_usd : 0;
        }}),
        backgroundColor: COLORS_ARR[i] + 'aa',
        borderColor: COLORS_ARR[i],
        borderWidth: 1,
      }}))
    }},
    options: {{ responsive: true, scales: {{ y: {{ beginAtZero: true }} }} }}
  }});

  // Table
  const tbody = document.querySelector('#qualityTable tbody');
  tbody.innerHTML = '';
  D.quality_distribution.forEach(r => {{
    tbody.innerHTML += `<tr>
      <td><span class="platform-tag ${{r.platform}}">${{r.platform}}</span></td>
      <td>${{r.quality_tier}}</td>
      <td>${{r.listings_count}}</td>
      <td>${{pct(r.pct_of_total)}}</td>
      <td>${{fmtUSD(r.avg_price_usd)}}</td>
      <td>${{fmtUSD(r.median_price_usd)}}</td>
    </tr>`;
  }});
}}

// ============ ALERTS ============
function renderAlerts() {{
  const sev = document.getElementById('alertSeverity').value;
  const plat = document.getElementById('alertPlatform').value;
  let filtered = D.alerts;
  if (sev !== 'all') filtered = filtered.filter(r => r.severity === sev);
  if (plat !== 'all') filtered = filtered.filter(r => r.platform === plat);

  const list = document.getElementById('alertList');
  list.innerHTML = '';
  if (filtered.length === 0) {{ list.innerHTML = '<div style="color:var(--text-dim);padding:20px;">No alerts matching filters.</div>'; return; }}

  filtered.forEach(a => {{
    const ago = Math.round((Date.now() - new Date(a.timestamp).getTime()) / 3600000);
    const agoStr = ago < 24 ? ago + 'h ago' : Math.round(ago / 24) + 'd ago';
    list.innerHTML += `<div class="alert-item">
      <span class="alert-badge ${{a.severity}}">${{a.severity}}</span>
      <div>
        <div class="alert-desc"><span class="platform-tag ${{a.platform}}">${{a.platform}}</span> ${{a.description}}</div>
        <div class="alert-time">${{agoStr}} &middot; Source: ${{a.details.source}} &middot; Value: ${{a.details.metric_value}}x (baseline: ${{a.details.baseline_value}}x)</div>
      </div>
    </div>`;
  }});
}}

document.getElementById('alertSeverity').addEventListener('change', renderAlerts);
document.getElementById('alertPlatform').addEventListener('change', renderAlerts);

// ============ INIT ============
renderOverview();
renderTrends();
renderSources();
renderKeywords();
renderRegions();
renderLanguages();
renderQuality();
renderAlerts();
</script>
</body>
</html>
"""

import os
output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
with open(output_path, "w") as f:
    f.write(html)
print(f"Dashboard written to {output_path}")
print(f"File size: {len(html):,} bytes")
