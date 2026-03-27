// Data loaded via fetch
let dashboardData = null;
let trendData = null;

// Platform colors
const platformColors = {
  'Roblox': '#da3633',
  'Fortnite': '#7d8590',
  'Minecraft': '#7d8590',
  'Steam': '#7d8590'
};

const categoryColors = {
  'Items / Currency': '#58a6ff',
  'Age Verified': '#3fb950',
  'OG / Veteran Account': '#d29922',
  'General': '#484f58'
};

// Initialize
document.addEventListener('DOMContentLoaded', function() {
  // Fetch data from JSON file instead of using embedded data
  fetch('dashboard_data.json')
    .then(response => {
      if (!response.ok) throw new Error('Failed to load data: ' + response.status);
      return response.json();
    })
    .then(data => {
      dashboardData = data;
      updateLastUpdated();
      initializeNavigation();
      renderOverview();
      renderListings();
      renderAgeVerified();
      renderComparison();
      setupFilters();
      // Load trend data (non-blocking)
      fetch('price_trends.json')
        .then(r => r.ok ? r.json() : null)
        .then(td => { if (td) { trendData = td; renderTrendChart(); renderVolumeTrend(); renderDataQuality(); } })
        .catch(() => {});
    })
    .catch(error => {
      console.error('Error loading dashboard data:', error);
      const el = document.getElementById('last-updated');
      if (el) el.textContent = 'Error loading data. Please refresh.';
    });
});

function updateLastUpdated() {
  const el = document.getElementById('last-updated');
  if (!el || !dashboardData || !dashboardData.metadata) return;
  const dateStr = dashboardData.metadata.scrape_date || dashboardData.metadata.generated_at;
  if (dateStr) {
    // Parse YYYY-MM-DD without timezone shift by splitting manually
    const parts = dateStr.substring(0, 10).split('-');
    const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
    const formatted = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    el.textContent = 'Last Updated: ' + formatted;
  }
}

// Navigation
function initializeNavigation() {
  const navButtons = document.querySelectorAll('.nav button');
  navButtons.forEach(button => {
    button.addEventListener('click', function() {
      const tab = this.dataset.tab;
      showSection(tab);
      navButtons.forEach(b => b.classList.remove('active'));
      this.classList.add('active');
    });
  });
}

function showSection(sectionId) {
  const sections = document.querySelectorAll('.section');
  sections.forEach(s => s.classList.remove('active'));
  document.getElementById('sec-' + sectionId).classList.add('active');
}

// --- Utility: WoW change from trend data ---
function getWowChange() {
  if (!trendData || !trendData.trends || trendData.trends.length < 2) return null;
  const trends = trendData.trends;
  const latest = trends[trends.length - 1];
  const prev = trends[trends.length - 2];
  const changes = {};
  ['Roblox','Fortnite','Minecraft','Steam'].forEach(p => {
    const cur = latest.platforms[p] ? latest.platforms[p].avg_price : null;
    const old = prev.platforms[p] ? prev.platforms[p].avg_price : null;
    if (cur !== null && old !== null && old > 0) {
      const pct = ((cur - old) / old) * 100;
      changes[p] = pct;
    } else {
      changes[p] = null;
    }
  });
  return changes;
}

function wowBadge(pct) {
  if (pct === null || pct === undefined) return '';
  const cls = pct > 1 ? 'up' : pct < -1 ? 'down' : 'flat';
  const arrow = pct > 1 ? '▲' : pct < -1 ? '▼' : '→';
  return `<span class="kpi-wow ${cls}">${arrow} ${Math.abs(pct).toFixed(1)}%</span>`;
}

// Overview Section
function renderOverview() {
  const data = dashboardData;
  const pStats = getPlatformPriceStats();
  const wow = getWowChange();

  // --- Roblox-focused KPI Cards ---
  const rblx = pStats['Roblox'] || { avg: 0, median: 0, count: 0, lowerFence: 0 };
  const rblxListings = data.listings.filter(l => l.platform === 'Roblox');
  const rblxVerified = rblxListings.length;  // actual scraped + verified account listings
  const rblxMin = rblx.count ? Math.min(...rblxListings.filter(l=>l.price_usd>0).map(l=>l.price_usd)) : 0;
  const rblxWow = wow && wow['Roblox'] !== null ? wowBadge(wow['Roblox']) : '';
  const rblxAvListings = rblxListings.filter(l => l.categories.includes('Age Verified'));
  const rblxAvPrices = rblxAvListings.filter(l => l.price_usd > 0).map(l => l.price_usd);
  const rblxAvAvg = rblxAvPrices.length ? rblxAvPrices.reduce((a,b)=>a+b,0)/rblxAvPrices.length : 0;
  // Per-source verified counts for Roblox
  const rblxBySrc = {};
  data.metadata.sources.forEach(s => { rblxBySrc[s] = rblxListings.filter(l => l.source === s).length; });
  const rblxSrcBreakdown = data.metadata.sources.map(s => rblxBySrc[s] + ' ' + s).join(' · ');

  const kpiHtml = `
    <div class="kpi-card roblox">
      <div class="kpi-label">Verified Roblox Accounts for Sale</div>
      <div class="kpi-value" style="color:var(--roblox)">${rblxVerified.toLocaleString()}</div>
      <div class="price-detail">${rblxSrcBreakdown}</div>
    </div>
    <div class="kpi-card roblox">
      <div class="kpi-label">Roblox Avg Price ${rblxWow}</div>
      <div class="kpi-value" style="color:var(--roblox)">$${rblx.avg.toFixed(2)}</div>
      <div class="price-detail">Median: $${rblx.median.toFixed(2)}</div>
    </div>
    <div class="kpi-card roblox">
      <div class="kpi-label">Roblox Lowest Price</div>
      <div class="kpi-value" style="color:var(--roblox)">$${rblxMin.toFixed(2)}</div>
      <div class="price-detail">Floor price — lower = more accessible</div>
    </div>
    <div class="kpi-card roblox">
      <div class="kpi-label">Roblox Age Verified</div>
      <div class="kpi-value" style="color:var(--roblox)">${rblxAvListings.length}</div>
      <div class="price-detail">Avg: $${rblxAvAvg.toFixed(2)} · High risk</div>
    </div>
    <div class="kpi-card roblox">
      <div class="kpi-label">Marketplaces Tracked</div>
      <div class="kpi-value" style="color:var(--roblox)">${data.metadata.sources.length}</div>
      <div class="price-detail">${data.metadata.sources.join(', ')}</div>
    </div>
  `;

  document.getElementById('kpiGrid').innerHTML = kpiHtml;

  // Chart: Roblox Listings by Marketplace
  const rblxSummary = data.platform_summary['Roblox'];
  const sources = data.metadata.sources;
  const rblxBySource = sources.map(s => rblxSummary.sources[s] ? rblxSummary.sources[s].scraped_count : 0);
  const sourceColors = ['rgba(218, 54, 51, 0.7)', 'rgba(88, 166, 255, 0.7)', 'rgba(63, 185, 80, 0.7)', 'rgba(169, 142, 255, 0.7)', 'rgba(210, 153, 34, 0.7)'];
  const sourceBorders = ['#da3633', '#58a6ff', '#3fb950', '#a98eff', '#d29922'];

  const ctx1 = document.getElementById('chartListingsByPlatformSource').getContext('2d');
  new Chart(ctx1, {
    type: 'bar',
    data: {
      labels: sources,
      datasets: [{
        label: 'Roblox Listings',
        data: rblxBySource,
        backgroundColor: sourceColors,
        borderColor: sourceBorders,
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => ctx.raw + ' verified listings' } }
      },
      scales: {
        y: { ticks: { color: '#7d8590' }, grid: { color: '#30363d' }, beginAtZero: true },
        x: { ticks: { color: '#7d8590' }, grid: { color: '#30363d' } }
      }
    }
  });

  // Chart: Roblox Category Distribution
  const rblxCats = rblxSummary.categories || {};
  const catLabels = Object.keys(rblxCats);
  const catData = Object.values(rblxCats);
  const catBgColors = catLabels.map(c => categoryColors[c] || '#484f58');

  const ctx2 = document.getElementById('chartCategoryDist').getContext('2d');
  new Chart(ctx2, {
    type: 'doughnut',
    data: {
      labels: catLabels,
      datasets: [{
        data: catData,
        backgroundColor: catBgColors,
        borderColor: '#0d1117',
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { labels: { color: '#e6edf3', font: { size: 12 } } }
      }
    }
  });
}

// --- Utility: compute median ---
function computeMedian(arr) {
  if (!arr.length) return 0;
  const sorted = [...arr].sort((a,b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid-1] + sorted[mid]) / 2;
}

// --- Utility: compute platform price stats for deal detection ---
function getPlatformPriceStats() {
  const stats = {};
  const platforms = dashboardData.metadata.platforms;
  platforms.forEach(p => {
    const prices = dashboardData.listings
      .filter(l => l.platform === p && l.price_usd > 0)
      .map(l => l.price_usd);
    const median = computeMedian(prices);
    const avg = prices.length ? prices.reduce((a,b) => a+b,0) / prices.length : 0;
    // IQR-based outlier bounds
    const q1 = prices.length >= 4 ? computeMedian(prices.slice(0, Math.floor(prices.length/2))) : 0;
    const q3 = prices.length >= 4 ? computeMedian(prices.slice(Math.ceil(prices.length/2))) : median * 2;
    const iqr = q3 - q1;
    stats[p] = { median, avg, q1, q3, iqr, count: prices.length,
                 upperFence: q3 + 1.5 * iqr, lowerFence: Math.max(0, q1 - 1.5 * iqr) };
  });
  return stats;
}

// --- Utility: price alert badge HTML ---
function priceAlertBadgeHtml(price, platformStats) {
  if (!platformStats || price <= 0 || platformStats.median <= 0) return '';
  const ratio = price / platformStats.median;
  if (ratio <= 0.35) return '<span class="price-alert-badge critical">⚠ LOW PRICE</span>';
  if (ratio <= 0.55) return '<span class="price-alert-badge watch">BELOW AVG</span>';
  return '';
}

// --- Utility: outlier flag ---
function isOutlier(price, platformStats) {
  if (!platformStats || price <= 0 || platformStats.count < 5) return false;
  return price > platformStats.upperFence;
}

// Live Listings Section
function renderListings() {
  const tbody = document.getElementById('listingsTableBody');
  tbody.innerHTML = '';
  const pStats = getPlatformPriceStats();

  dashboardData.listings.forEach(listing => {
    const categories = listing.categories.map(cat => {
      const key = cat === 'OG / Veteran Account' ? 'og-veteran' :
                  cat === 'Items / Currency' ? 'items-currency' :
                  cat === 'Age Verified' ? 'age-verified' : 'general';
      return `<span class="category-tag ${key}">${cat}</span>`;
    }).join(' ');

    const ps = pStats[listing.platform];
    const badge = priceAlertBadgeHtml(listing.price_usd, ps);
    const outlier = isOutlier(listing.price_usd, ps);
    const priceStyle = outlier ? 'color:var(--text-dim);text-decoration:line-through;font-style:italic' : '';
    const outlierNote = outlier ? '<div class="price-detail" title="Price is a statistical outlier">⚠ outlier</div>' : '';

    const row = document.createElement('tr');
    row.dataset.platform = listing.platform;
    row.dataset.source = listing.source;
    row.dataset.category = listing.categories[0] || '';
    row.dataset.searchText = `${listing.title} ${listing.seller} ${listing.platform}`.toLowerCase();

    row.innerHTML = `
      <td><span class="platform-tag ${listing.platform}">${listing.platform}</span></td>
      <td>${listing.source}</td>
      <td><strong>${listing.title}</strong></td>
      <td><span style="${priceStyle}">$${listing.price_usd.toFixed(2)}</span>${badge}${outlierNote}</td>
      <td>${listing.seller}</td>
      <td>${listing.rating}</td>
      <td>${categories}</td>
      <td><a href="${listing.url}" target="_blank" class="view-link">View Listing →</a></td>
    `;

    tbody.appendChild(row);
  });
}

// Setup Filters
function setupFilters() {
  const searchInput = document.getElementById('searchInput');
  const filterPlatform = document.getElementById('filterPlatform');
  const filterSource = document.getElementById('filterSource');
  const filterCategory = document.getElementById('filterCategory');

  function applyFilters() {
    const searchTerm = searchInput.value.toLowerCase();
    const platformVal = filterPlatform.value;
    const sourceVal = filterSource.value;
    const categoryVal = filterCategory.value;

    const rows = document.querySelectorAll('#listingsTableBody tr');
    rows.forEach(row => {
      let show = true;

      if (searchTerm && !row.dataset.searchText.includes(searchTerm)) show = false;
      if (platformVal && row.dataset.platform !== platformVal) show = false;
      if (sourceVal && row.dataset.source !== sourceVal) show = false;
      if (categoryVal && row.dataset.category !== categoryVal) show = false;

      row.style.display = show ? '' : 'none';
    });
  }

  searchInput.addEventListener('input', applyFilters);
  filterPlatform.addEventListener('change', applyFilters);
  filterSource.addEventListener('change', applyFilters);
  filterCategory.addEventListener('change', applyFilters);

  // Apply default Roblox filter on load
  applyFilters();
}

// Industry Comparison Section
function renderComparison() {
  const data = dashboardData;
  const pStats = getPlatformPriceStats();
  const platforms = data.metadata.platforms;
  const rblxCount = data.listings.filter(l => l.platform === 'Roblox').length;

  // Chart: Verified listings by platform (bar)
  const platCounts = platforms.map(p => data.listings.filter(l => l.platform === p).length);
  const platColors = platforms.map(p => platformColors[p]);

  new Chart(document.getElementById('chartCompVolume').getContext('2d'), {
    type: 'bar',
    data: {
      labels: platforms,
      datasets: [{
        label: 'Verified Listings',
        data: platCounts,
        backgroundColor: platColors.map(c => c + 'cc'),
        borderColor: platColors,
        borderWidth: 1
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { ticks: { color: '#7d8590' }, grid: { color: '#30363d' }, beginAtZero: true },
        x: { ticks: { color: '#7d8590' }, grid: { color: '#30363d' } }
      }
    }
  });

  // Chart: Avg + Median price by platform (grouped bar)
  new Chart(document.getElementById('chartCompPrice').getContext('2d'), {
    type: 'bar',
    data: {
      labels: platforms,
      datasets: [
        { label: 'Avg Price', data: platforms.map(p => pStats[p].avg), backgroundColor: platColors.map(c => c + 'cc'), borderColor: platColors, borderWidth: 1 },
        { label: 'Median Price', data: platforms.map(p => pStats[p].median), backgroundColor: platColors.map(c => c + '55'), borderColor: platColors, borderWidth: 1 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: {
        legend: { labels: { color: '#e6edf3', font: { size: 12 } } },
        tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': $' + ctx.raw.toFixed(2) } }
      },
      scales: {
        y: { ticks: { color: '#7d8590', callback: v => '$' + v }, grid: { color: '#30363d' }, beginAtZero: true },
        x: { ticks: { color: '#7d8590' }, grid: { color: '#30363d' } }
      }
    }
  });

  // Platform detail cards
  const container = document.getElementById('comparisonDetails');
  let html = '';
  platforms.forEach(platform => {
    const summary = data.platform_summary[platform];
    const ps = pStats[platform];
    const isRoblox = platform === 'Roblox';
    const verified = data.listings.filter(l => l.platform === platform).length;

    html += `
      <div class="platform-detail" style="${isRoblox ? 'border-color:var(--roblox);border-width:2px;' : ''}">
        <h3 style="color: ${platformColors[platform]}">${platform} ${isRoblox ? '(Primary)' : ''}</h3>
        <div class="metric-row">
          <div class="metric-item">
            <div class="metric-label">Verified Listings</div>
            <div class="metric-value">${verified}</div>
          </div>
          <div class="metric-item">
            <div class="metric-label">Avg / Median Price</div>
            <div class="metric-value">$${ps.avg.toFixed(2)}</div>
            <div class="price-detail">Median: $${ps.median.toFixed(2)}</div>
          </div>
          <div class="metric-item">
            <div class="metric-label">Price Range</div>
            <div class="metric-value">$${summary.price_min.toFixed(2)} – $${summary.price_max.toFixed(2)}</div>
          </div>
        </div>
      </div>
    `;
  });
  container.innerHTML = html;
}

// Data Quality Banner — shows when scrape health has issues
function renderDataQuality() {
  const banner = document.getElementById('dataQualityBanner');
  if (!banner || !trendData) return;

  // Check scrape_health from trend data
  const health = trendData.scrape_health;
  if (!health) { banner.innerHTML = ''; return; }

  const issues = [];
  for (const [platform, sources] of Object.entries(health)) {
    for (const [source, info] of Object.entries(sources)) {
      if (info.is_suspect) {
        issues.push({ platform, source, status: info.status, note: info.note });
      }
    }
  }

  if (issues.length === 0) {
    // All green — show a subtle health indicator
    const allSources = [];
    for (const [platform, sources] of Object.entries(health)) {
      for (const [source, info] of Object.entries(sources)) {
        if (platform === 'Roblox') {
          allSources.push(`<span class="source-status ok">✓ ${source}</span>`);
        }
      }
    }
    if (allSources.length) {
      banner.innerHTML = `<div style="font-size:11px;color:var(--text-dim);margin-bottom:12px;">
        Roblox data quality: ${allSources.join('')}
      </div>`;
    }
    return;
  }

  // Show warning
  const sourceStatuses = issues.map(i =>
    `<span class="source-status ${i.status}">${i.status === 'failed' ? '✗' : '⚠'} ${i.platform} / ${i.source}</span>`
  ).join('');
  const noteLines = issues.filter(i => i.note).map(i => i.note).join('; ');

  banner.innerHTML = `
    <div class="data-quality-banner">
      <div class="dq-icon">⚠️</div>
      <div>
        <div class="dq-title">Data quality notice — some sources may be incomplete</div>
        <div class="dq-detail">${noteLines}</div>
        <div style="margin-top:6px">${sourceStatuses}</div>
      </div>
    </div>
  `;
}

// Trend Chart (loaded async from price_trends.json)
function renderTrendChart() {
  if (!trendData || !trendData.trends || trendData.trends.length === 0) return;
  const trends = trendData.trends;
  const dates = trends.map(t => {
    const p = t.date.split('-');
    return new Date(parseInt(p[0]), parseInt(p[1])-1, parseInt(p[2]))
      .toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  });
  // Roblox daily avg price — dim suspect points
  const datasets = [{
    label: 'Roblox Avg Price',
    data: trends.map(t => { const pd = t.platforms['Roblox']; return pd ? pd.avg_price : null; }),
    borderColor: platformColors['Roblox'],
    backgroundColor: platformColors['Roblox'] + '33',
    borderWidth: 3,
    tension: 0.3,
    pointRadius: trends.map(t => { const pd = t.platforms['Roblox']; return pd && pd.is_suspect ? 2 : (trends.length < 15 ? 5 : 3); }),
    pointStyle: trends.map(t => { const pd = t.platforms['Roblox']; return pd && pd.is_suspect ? 'crossRot' : 'circle'; }),
    pointBackgroundColor: trends.map(t => { const pd = t.platforms['Roblox']; return pd && pd.is_suspect ? '#da363388' : platformColors['Roblox']; }),
    pointHoverRadius: 7,
    fill: true
  }, {
    label: 'Roblox Median Price',
    data: trends.map(t => { const pd = t.platforms['Roblox']; return pd ? pd.median_price : null; }),
    borderColor: '#d29922',
    backgroundColor: '#d2992222',
    borderWidth: 2,
    tension: 0.3,
    pointRadius: trends.length < 15 ? 4 : 2,
    pointHoverRadius: 6,
    fill: false
  }];

  // 7-day rolling average (dashed)
  if (trends.length >= 4) {
    datasets.push({
      label: '7-day rolling avg',
      data: trends.map(t => { const pd = t.platforms['Roblox']; return pd && pd.rolling_avg_price ? pd.rolling_avg_price : null; }),
      borderColor: platformColors['Roblox'],
      borderWidth: 2,
      borderDash: [6, 3],
      tension: 0.4,
      pointRadius: 0,
      fill: false
    });
  }

  const ctx = document.getElementById('chartPriceTrend').getContext('2d');
  new Chart(ctx, {
    type: 'line',
    data: { labels: dates, datasets },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: {
        legend: { labels: { color: '#e6edf3', font: { size: 12 } } },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              const lbl = ctx.dataset.label;
              if (lbl.includes('rolling')) return lbl + ': $' + (ctx.raw ? ctx.raw.toFixed(2) : 'N/A');
              const idx = ctx.dataIndex;
              const pd = trendData.trends[idx] && trendData.trends[idx].platforms['Roblox'];
              let text = lbl + ': $' + (ctx.raw ? ctx.raw.toFixed(2) : 'N/A');
              if (pd && pd.is_suspect) text += ' ⚠ suspect data';
              return text;
            }
          }
        }
      },
      scales: {
        y: { ticks: { color: '#7d8590', callback: v => '$' + v }, grid: { color: '#30363d' }, beginAtZero: false },
        x: { ticks: { color: '#7d8590' }, grid: { color: '#30363d' } }
      }
    }
  });

  const note = document.getElementById('trendNote');
  if (trends.length < 3) {
    note.textContent = 'Trend data will become more meaningful as daily scrapes accumulate. Currently showing ' + trends.length + ' data point(s).';
  }
}

// Volume Trend Chart — listing counts over time
function renderVolumeTrend() {
  if (!trendData || !trendData.trends || trendData.trends.length === 0) return;
  const canvas = document.getElementById('chartVolumeTrend');
  if (!canvas) return;
  const trends = trendData.trends;
  const dates = trends.map(t => {
    const p = t.date.split('-');
    return new Date(parseInt(p[0]), parseInt(p[1])-1, parseInt(p[2]))
      .toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  });
  // Roblox volume only
  const datasets = [{
    label: 'Roblox Verified Listings',
    data: trends.map(t => { const pd = t.platforms['Roblox']; return pd ? (pd.count || 0) : null; }),
    borderColor: platformColors['Roblox'],
    backgroundColor: platformColors['Roblox'] + '33',
    borderWidth: 3,
    tension: 0.3,
    pointRadius: trends.map(t => { const pd = t.platforms['Roblox']; return pd && pd.is_suspect ? 2 : (trends.length < 15 ? 5 : 3); }),
    pointStyle: trends.map(t => { const pd = t.platforms['Roblox']; return pd && pd.is_suspect ? 'crossRot' : 'circle'; }),
    pointBackgroundColor: trends.map(t => { const pd = t.platforms['Roblox']; return pd && pd.is_suspect ? '#da363388' : platformColors['Roblox']; }),
    pointHoverRadius: 7,
    fill: true
  }];

  // Rolling avg line
  if (trends.length >= 4) {
    datasets.push({
      label: '7-day rolling avg',
      data: trends.map(t => { const pd = t.platforms['Roblox']; return pd && pd.rolling_count ? pd.rolling_count : null; }),
      borderColor: platformColors['Roblox'],
      borderWidth: 2,
      borderDash: [6, 3],
      tension: 0.4,
      pointRadius: 0,
      fill: false
    });
  }

  new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: { labels: dates, datasets },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: {
        legend: { labels: { color: '#e6edf3', font: { size: 12 } } },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              const lbl = ctx.dataset.label;
              if (lbl.includes('rolling')) return lbl + ': ' + (ctx.raw ? ctx.raw.toLocaleString() : 'N/A');
              let text = ctx.raw ? ctx.raw.toLocaleString() + ' verified listings' : 'N/A';
              const idx = ctx.dataIndex;
              const pd = trendData.trends[idx] && trendData.trends[idx].platforms['Roblox'];
              if (pd && pd.is_suspect) text += ' ⚠ suspect';
              return text;
            }
          }
        }
      },
      scales: {
        y: { ticks: { color: '#7d8590' }, grid: { color: '#30363d' }, beginAtZero: true },
        x: { ticks: { color: '#7d8590' }, grid: { color: '#30363d' } }
      }
    }
  });

  const note = document.getElementById('volumeNote');
  if (trends.length < 3) {
    note.textContent = 'Volume tracking will show supply growth once more daily data points accumulate.';
  }
}

// Age Verified Section
function renderAgeVerified() {
  const data = dashboardData;
  const avListings = data.listings.filter(l => l.categories.includes('Age Verified'));
  const allListings = data.listings;
  const avPrices = avListings.filter(l => l.price_usd > 0).map(l => l.price_usd);
  const generalPrices = allListings.filter(l => !l.categories.includes('Age Verified') && l.price_usd > 0).map(l => l.price_usd);
  const avAvg = avPrices.length ? avPrices.reduce((a,b) => a+b,0) / avPrices.length : 0;
  const genAvg = generalPrices.length ? generalPrices.reduce((a,b) => a+b,0) / generalPrices.length : 0;
  const avMin = avPrices.length ? Math.min(...avPrices) : 0;
  const avMax = avPrices.length ? Math.max(...avPrices) : 0;

  // Alert banner
  document.getElementById('ageVerifiedAlert').innerHTML = `
    <div class="alert-banner">
      <div class="alert-count">${avListings.length}</div>
      <div class="alert-text">
        <strong>Age Verified accounts detected</strong> across ${new Set(avListings.map(l=>l.source)).size} marketplace(s)
        and ${new Set(avListings.map(l=>l.platform)).size} platform(s).
        Price range: $${avMin.toFixed(2)} - $${avMax.toFixed(2)}.
      </div>
    </div>
  `;

  // KPI cards
  const platforms = data.metadata.platforms;
  const avByPlatform = {};
  platforms.forEach(p => {
    avByPlatform[p] = avListings.filter(l => l.platform === p);
  });

  document.getElementById('ageVerifiedKpis').innerHTML = `
    <div class="kpi-card age-verified-card">
      <div class="kpi-label">Total Age Verified</div>
      <div class="kpi-value" style="color:var(--green)">${avListings.length}</div>
      <div class="kpi-sub">Across all platforms</div>
    </div>
    <div class="kpi-card age-verified-card">
      <div class="kpi-label">Average Price</div>
      <div class="kpi-value" style="color:var(--green)">$${avAvg.toFixed(2)}</div>
      <div class="kpi-sub">vs $${genAvg.toFixed(2)} general avg</div>
    </div>
    <div class="kpi-card age-verified-card">
      <div class="kpi-label">Cheapest Available</div>
      <div class="kpi-value" style="color:var(--green)">$${avMin.toFixed(2)}</div>
      <div class="kpi-sub">${avPrices.length > 0 ? avListings.find(l => l.price_usd === avMin)?.source || '' : 'None found'}</div>
    </div>
    <div class="kpi-card age-verified-card">
      <div class="kpi-label">Most Expensive</div>
      <div class="kpi-value" style="color:var(--green)">$${avMax.toFixed(2)}</div>
      <div class="kpi-sub">${avPrices.length > 0 ? avListings.find(l => l.price_usd === avMax)?.source || '' : 'None found'}</div>
    </div>
  `;

  // Chart: Age Verified vs General avg price per platform
  const avAvgByPlat = platforms.map(p => {
    const prices = avByPlatform[p].filter(l => l.price_usd > 0).map(l => l.price_usd);
    return prices.length ? prices.reduce((a,b) => a+b,0) / prices.length : 0;
  });
  const genAvgByPlat = platforms.map(p => {
    const prices = allListings.filter(l => l.platform === p && !l.categories.includes('Age Verified') && l.price_usd > 0).map(l => l.price_usd);
    return prices.length ? prices.reduce((a,b) => a+b,0) / prices.length : 0;
  });

  new Chart(document.getElementById('chartAgeVsGeneral').getContext('2d'), {
    type: 'bar',
    data: {
      labels: platforms,
      datasets: [
        { label: 'Age Verified Avg', data: avAvgByPlat, backgroundColor: '#3fb950cc', borderColor: '#3fb950', borderWidth: 1 },
        { label: 'General Avg', data: genAvgByPlat, backgroundColor: '#484f5866', borderColor: '#484f58', borderWidth: 1 }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: {
        legend: { labels: { color: '#e6edf3', font: { size: 12 } } },
        tooltip: { callbacks: { label: ctx => ctx.dataset.label + ': $' + ctx.raw.toFixed(2) } }
      },
      scales: {
        y: { ticks: { color: '#7d8590', callback: v => '$' + v }, grid: { color: '#30363d' }, beginAtZero: true },
        x: { ticks: { color: '#7d8590' }, grid: { color: '#30363d' } }
      }
    }
  });

  // Chart: Age Verified price distribution (histogram-like)
  if (avPrices.length > 0) {
    const buckets = [0, 2, 5, 10, 20, 50, 100, 500];
    const bucketLabels = buckets.slice(0, -1).map((b, i) => '$' + b + '-$' + buckets[i+1]);
    bucketLabels.push('$500+');
    const bucketCounts = new Array(bucketLabels.length).fill(0);
    avPrices.forEach(p => {
      let placed = false;
      for (let i = 0; i < buckets.length - 1; i++) {
        if (p >= buckets[i] && p < buckets[i+1]) { bucketCounts[i]++; placed = true; break; }
      }
      if (!placed) bucketCounts[bucketCounts.length - 1]++;
    });
    new Chart(document.getElementById('chartAgePriceDist').getContext('2d'), {
      type: 'bar',
      data: {
        labels: bucketLabels,
        datasets: [{ label: 'Listings', data: bucketCounts, backgroundColor: '#3fb95099', borderColor: '#3fb950', borderWidth: 1 }]
      },
      options: {
        responsive: true, maintainAspectRatio: true,
        plugins: { legend: { display: false } },
        scales: {
          y: { ticks: { color: '#7d8590', stepSize: 1 }, grid: { color: '#30363d' }, beginAtZero: true },
          x: { ticks: { color: '#7d8590', font: { size: 10 } }, grid: { color: '#30363d' } }
        }
      }
    });
  }

  // Availability Heatmap
  const sources = data.metadata.sources;
  const cols = sources.length + 1;
  let heatHtml = `<div class="heatmap" style="grid-template-columns: 120px repeat(${sources.length}, 1fr);">`;
  heatHtml += '<div class="heatmap-header"></div>';
  sources.forEach(s => { heatHtml += `<div class="heatmap-header">${s}</div>`; });
  platforms.forEach(p => {
    heatHtml += `<div class="heatmap-row-label">${p}</div>`;
    sources.forEach(s => {
      const count = avListings.filter(l => l.platform === p && l.source === s).length;
      const cls = count === 0 ? 'empty' : count <= 1 ? 'low' : count <= 3 ? 'medium' : 'high';
      const label = count === 0 ? '-' : count + ' listing' + (count > 1 ? 's' : '');
      heatHtml += `<div class="heatmap-cell ${cls}">${label}</div>`;
    });
  });
  heatHtml += '</div>';
  document.getElementById('heatmapContainer').innerHTML = heatHtml;

  // Chart: Age Verified by Source
  const avBySource = {};
  sources.forEach(s => { avBySource[s] = avListings.filter(l => l.source === s).length; });
  new Chart(document.getElementById('chartAgeBySource').getContext('2d'), {
    type: 'doughnut',
    data: {
      labels: sources,
      datasets: [{
        data: sources.map(s => avBySource[s]),
        backgroundColor: ['rgba(218,54,51,0.7)', 'rgba(88,166,255,0.7)', 'rgba(63,185,80,0.7)', 'rgba(169,142,255,0.7)', 'rgba(210,153,34,0.7)'],
        borderColor: '#0d1117', borderWidth: 2
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: { legend: { labels: { color: '#e6edf3', font: { size: 12 } } } }
    }
  });

  // Table: All age verified listings
  const tbody = document.getElementById('ageVerifiedTableBody');
  tbody.innerHTML = '';
  avListings.sort((a,b) => a.price_usd - b.price_usd).forEach(listing => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td><span class="platform-tag ${listing.platform}">${listing.platform}</span></td>
      <td>${listing.source}</td>
      <td><strong>${listing.title}</strong></td>
      <td>$${listing.price_usd.toFixed(2)}</td>
      <td>${listing.seller}</td>
      <td><a href="${listing.url}" target="_blank" class="view-link">View Listing →</a></td>
    `;
    tbody.appendChild(row);
  });
}
