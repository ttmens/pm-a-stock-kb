"""Generate web/index.html from prototype with API wiring."""
import pathlib

base = pathlib.Path("D:/workspace/projects/pm-a-stock-kb/04-mvp")
proto = pathlib.Path("D:/workspace/projects/pm-a-stock-kb/02b-prototype/index.html").read_text(encoding="utf-8")

# Extract style section
style_start = proto.index("<style>")
style_end = proto.index("</style>") + len("</style>")
style = proto[style_start:style_end]

# Build new HTML with updated JavaScript
html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A股全量信息检索知识库</title>
""" + style + """
</head>
<body>

<nav class="nav">
  <div class="nav-brand">A股知识库</div>
  <div class="nav-tabs">
    <button class="nav-tab active" onclick="switchScreen('dashboard')">搜索</button>
    <button class="nav-tab" onclick="switchScreen('events')">事件链</button>
    <button class="nav-tab" onclick="switchScreen('search')">全文搜索</button>
    <button class="nav-tab" onclick="switchScreen('factors')">因子</button>
    <button class="nav-tab" onclick="switchScreen('system')">系统</button>
  </div>
</nav>

<!-- S1: Search Dashboard -->
<div id="screen-dashboard" class="screen active">
  <div class="container">
    <div class="hero-search">
      <h1>A股全量信息检索</h1>
      <p>输入股票代码、名称或关键词，快速检索公告、研报、舆情与事件链</p>
      <div class="search-box">
        <input class="search-input" id="main-search" type="text" placeholder="输入股票代码/名称/关键词" />
        <button class="search-btn" onclick="doSearch()">搜索</button>
      </div>
      <div class="search-hints">
        <span class="hint-tag" onclick="quickSearch('600519')">600519 贵州茅台</span>
        <span class="hint-tag" onclick="quickSearch('000001')">000001 平安银行</span>
        <span class="hint-tag" onclick="quickSearch('芯片制裁')">芯片制裁</span>
        <span class="hint-tag" onclick="quickSearch('新能源')">新能源</span>
      </div>
    </div>
    <div class="quick-access">
      <h3>最近查询</h3>
      <div class="quick-stocks" id="quick-stocks"></div>
    </div>
    <div class="status-summary" id="dash-status">
      <div class="status-card"><div class="status-dot green"></div><div><div class="status-label">数据更新</div><div class="status-value">加载中...</div></div></div>
      <div class="status-card"><div class="status-dot green"></div><div><div class="status-label">系统状态</div><div class="status-value">加载中...</div></div></div>
    </div>
  </div>
</div>

<!-- S2: Event Chain -->
<div id="screen-events" class="screen">
  <div class="container">
    <div class="event-header">
      <div><h2 id="event-stock-name">贵州茅台</h2><span class="stock-code" id="event-stock-code">600519.SH</span></div>
      <div class="time-range-selector">
        <button class="time-btn" onclick="setTimeRange(this, 7)">7天</button>
        <button class="time-btn active" onclick="setTimeRange(this, 30)">30天</button>
        <button class="time-btn" onclick="setTimeRange(this, 90)">90天</button>
      </div>
    </div>
    <div class="filter-bar">
      <button class="filter-tag active" onclick="filterType(this, 'all')">全部</button>
      <button class="filter-tag" onclick="filterType(this, 'announcement')">公告</button>
      <button class="filter-tag" onclick="filterType(this, 'financial')">财报</button>
      <button class="filter-tag" onclick="filterType(this, 'capital')">资金</button>
      <button class="filter-tag" onclick="filterType(this, 'social')">舆情</button>
    </div>
    <div id="event-loading" class="loading" style="display:none;">加载中...</div>
    <div id="event-error" class="error-msg" style="display:none;"></div>
    <div class="timeline" id="event-timeline"></div>
  </div>
</div>

<!-- S3: Search Results -->
<div id="screen-search" class="screen">
  <div class="container">
    <div class="search-results-header">
      <h2>搜索结果：<span id="search-keyword"></span></h2>
      <div class="result-count" id="search-count"></div>
    </div>
    <div id="search-loading" class="loading" style="display:none;">加载中...</div>
    <div id="search-error" class="error-msg" style="display:none;"></div>
    <div id="search-results"></div>
    <div id="search-pagination" style="text-align:center;margin-top:16px;"></div>
  </div>
</div>

<!-- S4: Factor Data -->
<div id="screen-factors" class="screen">
  <div class="container">
    <div class="factor-header">
      <div><h2>因子数据 — <span id="factor-stock-name">贵州茅台</span> <span class="stock-code" id="factor-stock-code">600519.SH</span></h2></div>
      <div style="display:flex;gap:12px;align-items:center;">
        <div class="view-toggle">
          <button class="view-btn active" onclick="toggleView(this,'table')">表格</button>
          <button class="view-btn" onclick="toggleView(this,'chart')">图表</button>
        </div>
        <button class="export-btn" onclick="exportFactors()">导出CSV</button>
      </div>
    </div>
    <div class="filter-bar">
      <button class="filter-tag active" onclick="filterFactor(this,'all')">全部因子</button>
      <button class="filter-tag" onclick="filterFactor(this,'sentiment')">情感因子</button>
      <button class="filter-tag" onclick="filterFactor(this,'momentum')">动量因子</button>
      <button class="filter-tag" onclick="filterFactor(this,'volatility')">波动率因子</button>
    </div>
    <div id="factor-loading" class="loading" style="display:none;">加载中...</div>
    <div id="factor-error" class="error-msg" style="display:none;"></div>
    <div id="factor-table-view">
      <table class="data-table"><thead><tr><th>日期</th><th>因子名称</th><th>因子值</th></tr></thead><tbody id="factor-tbody"></tbody></table>
    </div>
    <div id="factor-chart-view" style="display:none;">
      <div class="chart-container"><h3>情感因子时间序列</h3><svg class="chart-svg" id="factor-chart" viewBox="0 0 800 200"></svg></div>
    </div>
  </div>
</div>

<!-- S5: System Status -->
<div id="screen-system" class="screen">
  <div class="container">
    <h2 style="margin-bottom:20px;">系统状态</h2>
    <div class="system-grid" id="system-grid"></div>
    <div id="system-loading" class="loading" style="display:none;">加载中...</div>
    <div id="system-error" class="error-msg" style="display:none;"></div>
    <div class="etl-log"><h3>ETL运行日志</h3><div id="etl-log-entries"><div class="log-entry info">暂无ETL运行记录</div></div></div>
    <button class="trigger-btn" onclick="triggerETL()">手动触发采集</button>
    <button class="trigger-btn" style="background:#6f5a2a;margin-left:12px;" onclick="triggerReETL()">重新运行ETL</button>
  </div>
</div>

<!-- S6: Event Detail Modal -->
<div class="modal-overlay" id="event-modal" onclick="closeModal(event)">
  <div class="modal" onclick="event.stopPropagation()">
    <button class="modal-close" onclick="closeModalDirect()">&times;</button>
    <h2 id="modal-title">事件标题</h2>
    <div class="m-meta" id="modal-meta"></div>
    <div class="m-content" id="modal-content"></div>
    <div class="m-source" id="modal-source"></div>
    <div class="related-events"><h4>关联事件</h4><div id="modal-related"></div></div>
  </div>
</div>

""" + """<script>
const API_BASE = location.origin;
const TOKEN_KEY = 'astock_api_token';
const DEFAULT_TOKEN = 'demo-token-123';
function getToken() { return localStorage.getItem(TOKEN_KEY) || DEFAULT_TOKEN; }

async function apiFetch(url, options = {}) {
  const headers = { 'Authorization': 'Bearer ' + getToken(), ...options.headers };
  const resp = await fetch(API_BASE + url, { ...options, headers });
  if (!resp.ok) { const err = await resp.json().catch(() => ({})); throw new Error(err.detail || 'HTTP ' + resp.status); }
  return resp;
}

let currentStockCode = '600519.SH', currentStockName = '贵州茅台';
let currentDays = 30, currentFilterType = 'all', currentFactorType = 'all';
let currentView = 'table', searchPage = 1, lastSearchQuery = '';
let allFactors = [];

function switchScreen(name) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('screen-' + name).classList.add('active');
  const map = { dashboard: '搜索', events: '事件链', search: '全文搜索', factors: '因子', system: '系统' };
  document.querySelectorAll('.nav-tab').forEach(t => { if (t.textContent.includes(map[name] || name)) t.classList.add('active'); });
  if (name === 'system') loadHealth();
}

function show(el) { el.style.display = ''; }
function hide(el) { el.style.display = 'none'; }
function showLoading(l, e) { hide(e); show(l); }
function showError(l, e, msg) { hide(l); show(e); e.textContent = msg; }
function hideBoth(l, e) { hide(l); hide(e); }

async function loadQuickStocks() {
  try {
    const resp = await apiFetch('/api/stocks?q=茅台');
    const data = await resp.json();
    const container = document.getElementById('quick-stocks');
    const stocks = data.results.length ? data.results : [
      { stock_code: '600519.SH', stock_name: '贵州茅台' },
      { stock_code: '000858.SZ', stock_name: '五粮液' },
      { stock_code: '601318.SH', stock_name: '中国平安' },
      { stock_code: '000001.SZ', stock_name: '平安银行' },
    ];
    container.innerHTML = stocks.slice(0, 6).map(s =>
      '<div class="quick-stock" onclick="showEventChain(\\'' + s.stock_code + '\\',\\'' + s.stock_name + '\\')"><div class="name">' + s.stock_name + '</div><div class="code">' + s.stock_code + '</div></div>'
    ).join('');
  } catch(e) { document.getElementById('quick-stocks').innerHTML = '<div class="error-msg">加载失败: ' + e.message + '</div>'; }
}

async function loadDashStatus() {
  try {
    const resp = await apiFetch('/api/health');
    const data = await resp.json();
    document.getElementById('dash-status').innerHTML =
      '<div class="status-card"><div class="status-dot green"></div><div><div class="status-label">数据更新</div><div class="status-value">' + (data.data_freshness || 'T+1') + '</div></div></div>' +
      '<div class="status-card"><div class="status-dot green"></div><div><div class="status-label">系统状态</div><div class="status-value">全部正常</div></div></div>' +
      '<div class="status-card"><div class="status-dot green"></div><div><div class="status-label">运行时长</div><div class="status-value">' + Math.round(data.uptime_seconds/60) + '分钟</div></div></div>' +
      '<div class="status-card"><div class="status-dot green"></div><div><div class="status-label">内存使用</div><div class="status-value">' + data.memory_mb + ' MB</div></div></div>';
  } catch(e) { console.error('Health check failed:', e); }
}

async function loadEvents() {
  const tl = document.getElementById('event-timeline');
  const loading = document.getElementById('event-loading');
  const error = document.getElementById('event-error');
  showLoading(loading, error);
  try {
    let url = '/api/events/' + currentStockCode + '?days=' + currentDays;
    if (currentFilterType !== 'all') url += '&type=' + currentFilterType;
    const resp = await apiFetch(url);
    const data = await resp.json();
    hideBoth(loading, error);
    if (!data.events.length) { tl.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>暂无事件数据</p></div>'; return; }
    const tlabel = { announcement: '公告', financial: '财报', capital: '资金', social: '舆情' };
    tl.innerHTML = data.events.map(e => {
      const stype = e.sentiment_score > 0.1 ? 'positive' : e.sentiment_score < -0.1 ? 'negative' : 'neutral';
      const slabel = e.sentiment_score > 0.1 ? '利好 +' + e.sentiment_score.toFixed(2) : e.sentiment_score < -0.1 ? '利空 ' + e.sentiment_score.toFixed(2) : '中性 ' + e.sentiment_score.toFixed(2);
      return '<div class="timeline-item" onclick="showEventDetail(' + e.event_id + ')">' +
        '<div class="time">' + e.event_time + '</div><div class="title">' + e.title + '</div>' +
        '<div class="meta"><span class="type-badge ' + e.event_type + '">' + (tlabel[e.event_type]||e.event_type) + '</span>' +
        '<span class="sentiment-badge ' + stype + '">' + slabel + '</span></div></div>';
    }).join('');
  } catch(e) { showError(loading, error, '加载事件链失败: ' + e.message); }
}

async function loadSearchResults() {
  const container = document.getElementById('search-results');
  const loading = document.getElementById('search-loading');
  const error = document.getElementById('search-error');
  showLoading(loading, error);
  document.getElementById('search-keyword').textContent = lastSearchQuery;
  try {
    const resp = await apiFetch('/api/search?q=' + encodeURIComponent(lastSearchQuery) + '&page=' + searchPage);
    const data = await resp.json();
    hideBoth(loading, error);
    document.getElementById('search-count').textContent = '找到 ' + data.total + ' 条结果 (第 ' + data.page + '/' + data.total_pages + ' 页)';
    if (!data.results.length) { container.innerHTML = '<div class="empty-state"><div class="icon">🔍</div><p>未找到匹配结果</p></div>'; return; }
    const tlabel = { announcement: '公告', financial: '财报', capital: '资金', social: '舆情' };
    container.innerHTML = data.results.map(r =>
      '<div class="result-item" onclick="showSearchDetail(' + r.event_id + ')">' +
      '<div class="r-title">' + (r.title_snippet || r.title) + '</div>' +
      '<div class="r-snippet">' + (r.content_snippet || r.content || '') + '</div>' +
      '<div class="r-meta"><span>' + r.stock_name + ' (' + r.stock_code + ')</span><span>' + r.event_time + '</span>' +
      '<span class="type-badge ' + r.event_type + '">' + (tlabel[r.event_type]||r.event_type) + '</span></div></div>'
    ).join('');
    const pag = document.getElementById('search-pagination');
    let pagHtml = '';
    if (data.page > 1) pagHtml += '<button class="time-btn" onclick="searchPage=' + (data.page-1) + ';loadSearchResults()">上一页</button> ';
    pagHtml += '<span style="color:#8b8fa3;font-size:13px;">' + data.page + ' / ' + data.total_pages + '</span> ';
    if (data.page < data.total_pages) pagHtml += '<button class="time-btn" onclick="searchPage=' + (data.page+1) + ';loadSearchResults()">下一页</button>';
    pag.innerHTML = pagHtml;
  } catch(e) { showError(loading, error, '搜索失败: ' + e.message); }
}

async function loadFactors() {
  const tbody = document.getElementById('factor-tbody');
  const loading = document.getElementById('factor-loading');
  const error = document.getElementById('factor-error');
  showLoading(loading, error);
  try {
    let url = '/api/factors/' + currentStockCode + '?days=30';
    if (currentFactorType !== 'all') url += '&factor_type=' + currentFactorType;
    const resp = await apiFetch(url);
    const data = await resp.json();
    hideBoth(loading, error);
    allFactors = data.factors;
    if (!data.factors.length) { tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;padding:20px;color:#8b8fa3;">暂无因子数据</td></tr>'; return; }
    tbody.innerHTML = data.factors.map(f =>
      '<tr><td>' + f.factor_date + '</td><td>' + f.factor_name + '</td>' +
      '<td style="color:' + (f.factor_value >= 0 ? '#2ecc71' : '#e74c3c') + '">' + (f.factor_value >= 0 ? '+' : '') + f.factor_value.toFixed(4) + '</td></tr>'
    ).join('');
    if (currentView === 'chart') renderFactorChart();
  } catch(e) { showError(loading, error, '加载因子数据失败: ' + e.message); }
}

function renderFactorChart() {
  const svg = document.getElementById('factor-chart');
  const sentimentData = allFactors.filter(f => f.factor_name === 'sentiment').slice().reverse();
  if (!sentimentData.length) { svg.innerHTML = '<text x="400" y="100" text-anchor="middle" fill="#8b8fa3">暂无情感因子数据</text>'; return; }
  const w = 800, h = 200, pad = 40, chartW = w - pad * 2, chartH = h - pad * 2;
  const vals = sentimentData.map(d => d.factor_value);
  const maxV = Math.max(...vals, 1), minV = Math.min(...vals, -0.5);
  const points = sentimentData.map((d, i) => {
    const x = pad + (i / Math.max(sentimentData.length - 1, 1)) * chartW;
    const y = pad + chartH - ((d.factor_value - minV) / (maxV - minV || 1)) * chartH;
    return [x, y];
  });
  const linePath = points.map((p, i) => (i === 0 ? 'M' : 'L') + p[0] + ',' + p[1]).join(' ');
  const areaPath = linePath + ' L' + points[points.length-1][0] + ',' + (pad + chartH) + ' L' + points[0][0] + ',' + (pad + chartH) + ' Z';
  svg.innerHTML = '<defs><linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#4c6ef5" stop-opacity="0.3"/><stop offset="100%" stop-color="#4c6ef5" stop-opacity="0.02"/></linearGradient></defs>' +
    '<line x1="' + pad + '" y1="' + (pad + chartH) + '" x2="' + (w - pad) + '" y2="' + (pad + chartH) + '" stroke="#2a2d3e" stroke-width="1"/>' +
    '<path d="' + areaPath + '" fill="url(#areaGrad)"/>' +
    '<path d="' + linePath + '" fill="none" stroke="#4c6ef5" stroke-width="2"/>' +
    points.map(p => '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="4" fill="#4c6ef5" stroke="#0f1117" stroke-width="2"/>').join('') +
    sentimentData.map((d, i) => {
      const x = pad + (i / Math.max(sentimentData.length - 1, 1)) * chartW;
      return i % 3 === 0 ? '<text x="' + x + '" y="' + (h - 5) + '" fill="#5a5d6e" font-size="10" text-anchor="middle">' + d.factor_date.slice(5) + '</text>' : '';
    }).join('');
}

async function loadHealth() {
  const grid = document.getElementById('system-grid');
  const loading = document.getElementById('system-loading');
  const error = document.getElementById('system-error');
  showLoading(loading, error);
  try {
    const resp = await apiFetch('/api/health');
    const data = await resp.json();
    hideBoth(loading, error);
    const comp = data.components;
    const items = [
      { name: 'PostgreSQL', c: comp.postgresql, d: 'Silver层' },
      { name: 'Elasticsearch', c: comp.elasticsearch, d: 'Gold层' },
      { name: 'Redis', c: comp.redis, d: '缓存/队列' },
      { name: 'Qwen2.5-7B', c: comp.llm, d: comp.llm.model || '本地LLM' },
    ];
    grid.innerHTML = items.map(it => {
      const dot = it.c.status === 'healthy' ? 'green' : 'red';
      return '<div class="sys-card"><h3>' + it.name + '</h3><div class="sys-status"><div class="status-dot ' + dot + '"></div><span class="sys-name">' + it.c.status + '</span></div><div class="sys-detail">' + it.d + '</div></div>';
    }).join('');
  } catch(e) { showError(loading, error, '获取健康状态失败: ' + e.message); }
}

async function showEventDetail(eventId) {
  try {
    const resp = await apiFetch('/api/events/' + currentStockCode + '?days=60');
    const data = await resp.json();
    const evt = data.events.find(e => e.event_id == eventId);
    if (!evt) return;
    const stype = evt.sentiment_score > 0.1 ? 'positive' : evt.sentiment_score < -0.1 ? 'negative' : 'neutral';
    const tlabel = { announcement: '公告', financial: '财报', capital: '资金', social: '舆情' };
    document.getElementById('modal-title').textContent = evt.title;
    document.getElementById('modal-meta').innerHTML =
      '<span class="type-badge ' + evt.event_type + '">' + (tlabel[evt.event_type]||evt.event_type) + '</span>' +
      '<span class="sentiment-badge ' + stype + '">' + (evt.sentiment_score >= 0 ? '+' : '') + evt.sentiment_score.toFixed(2) + '</span>' +
      '<span style="color:#5a5d6e;font-size:12px;font-family:monospace;">' + evt.event_time + '</span>';
    document.getElementById('modal-content').textContent = evt.content || '暂无详细内容';
    document.getElementById('modal-source').textContent = '来源: ' + (evt.source || '未知') + ' | 事件ID: ' + evt.event_id;
    const related = data.events.filter(e => e.event_id != eventId).slice(0, 3);
    document.getElementById('modal-related').innerHTML = related.map(e =>
      '<div class="related-item">' + e.event_time.slice(0, 10) + ' · ' + e.title.slice(0, 40) + '</div>'
    ).join('');
    document.getElementById('event-modal').classList.add('active');
  } catch(e) { alert('加载事件详情失败: ' + e.message); }
}

function showSearchDetail(eventId) {
  document.getElementById('modal-title').textContent = '事件 #' + eventId;
  document.getElementById('modal-content').textContent = '点击事件链页面查看完整内容。';
  document.getElementById('event-modal').classList.add('active');
}

function closeModal(e) { if (e.target === document.getElementById('event-modal')) document.getElementById('event-modal').classList.remove('active'); }
function closeModalDirect() { document.getElementById('event-modal').classList.remove('active'); }

function doSearch() {
  const q = document.getElementById('main-search').value.trim();
  if (!q) return;
  lastSearchQuery = q; searchPage = 1;
  switchScreen('search');
  loadSearchResults();
}

async function quickSearch(q) {
  document.getElementById('main-search').value = q;
  if (/^\\d{6}$/.test(q)) {
    try {
      const resp = await apiFetch('/api/stocks?q=' + q);
      const data = await resp.json();
      if (data.results.length) { showEventChain(data.results[0].stock_code, data.results[0].stock_name); return; }
    } catch(e) {}
    const code = q.startsWith('6') ? q + '.SH' : q + '.SZ';
    showEventChain(code, q);
  } else {
    lastSearchQuery = q; searchPage = 1;
    switchScreen('search');
    loadSearchResults();
  }
}

function showEventChain(code, name) {
  currentStockCode = code; currentStockName = name;
  document.getElementById('event-stock-name').textContent = name;
  document.getElementById('event-stock-code').textContent = code;
  document.getElementById('factor-stock-name').textContent = name;
  document.getElementById('factor-stock-code').textContent = code;
  document.getElementById('event-timeline').innerHTML = '';
  loadEvents();
  switchScreen('events');
}

function setTimeRange(btn, days) {
  currentDays = days;
  btn.parentElement.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  loadEvents();
}

function filterType(btn, type) {
  currentFilterType = type;
  btn.parentElement.querySelectorAll('.filter-tag').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  loadEvents();
}

function filterFactor(btn, type) {
  currentFactorType = type;
  btn.parentElement.querySelectorAll('.filter-tag').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  loadFactors();
}

function toggleView(btn, view) {
  currentView = view;
  btn.parentElement.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('factor-table-view').style.display = view === 'table' ? 'block' : 'none';
  document.getElementById('factor-chart-view').style.display = view === 'chart' ? 'block' : 'none';
  if (view === 'chart') renderFactorChart();
}

function exportFactors() {
  let url = '/api/factors/export?stock_code=' + currentStockCode + '&days=30';
  if (currentFactorType !== 'all') url += '&factor_type=' + currentFactorType;
  window.open(url, '_blank');
}

async function triggerETL() {
  try {
    const resp = await apiFetch('/api/schedule/collect', { method: 'POST' });
    const data = await resp.json();
    alert('采集任务已提交: ' + data.task.task_id);
    loadHealth();
  } catch(e) { alert('提交失败: ' + e.message); }
}

async function triggerReETL() {
  try {
    const resp = await apiFetch('/api/schedule/collect?task_type=reprocess', { method: 'POST' });
    const data = await resp.json();
    alert('ETL重新运行已提交: ' + data.task.task_id);
    loadHealth();
  } catch(e) { alert('提交失败: ' + e.message); }
}

document.getElementById('main-search').addEventListener('keypress', function(e) { if (e.key === 'Enter') doSearch(); });
loadQuickStocks();
loadDashStatus();
</script>
</body>
</html>"""

(base / "web" / "index.html").write_text(html, encoding="utf-8")
print(f"Written {len(html)} bytes to web/index.html")
