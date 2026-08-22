"use strict";

const state = { rows: [], selected: null, filter: "all", limit: 120, period: "5m", chartData: null, hoverIndex: -1, requestId: 0, snapshotRequestId: 0, snapshotLoading: 0, candleLoading: 0, nextSnapshotAt: 0, nextCandlesAt: 0, lastRefreshAt: 0 };
const SNAPSHOT_REFRESH_MS = 15000;
const INTRADAY_REFRESH_MS = 15000;
const DAILY_REFRESH_MS = 60000;
const $ = (id) => document.getElementById(id);
const number = (value, digits = 2) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toLocaleString("zh-CN", { maximumFractionDigits: digits, minimumFractionDigits: digits }) : "--";
};
const compact = (value) => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "--";
  if (parsed >= 1e8) return `${number(parsed / 1e8, 2)}亿`;
  if (parsed >= 1e4) return `${number(parsed / 1e4, 1)}万`;
  return number(parsed, 0);
};
const truthy = (value) => String(value).toLowerCase() === "true";
const EVIDENCE_LABELS = {
  mhpg_inflow_confirmed: "MHPG 资金流确认", mhpg_outflow_warning: "MHPG 资金流出",
  mhpg_bull_kd_cross: "MHPG KD 金叉", dxbd_extreme_overbought: "DXBD 极端过热",
  dxbd_strong_breakout: "DXBD 强势突破", dxbd_high_risk: "DXBD 高位风险",
  dxbd_cross_zero: "DXBD 上穿零轴", dxbd_extreme_accumulation: "DXBD 极弱区回升",
  dxbd_weak_rebound: "DXBD 弱势区回升", dxbd_persistent_weakness: "DXBD 持续弱势",
  bullcluster_oversold: "多周期动量低位", bullcluster_overbought: "多周期动量过热",
  mfk4_low_zone_start: "MFK4 低位启动", mfk4_ma_dispersion: "MFK4 均线扩散",
  dingdi_rising: "顶底线回升", dingdi_falling: "顶底线回落",
  dingdi_high_risk: "顶底线高位", dingdi_safe_zone: "顶底线低位",
  dingdi_safe_up: "顶底线低位回升", bull_divergence: "看涨背离",
  bear_divergence: "看跌背离", gding_strong_pull: "GDing 强拉升观察",
  bbuy_cross: "BBUY 金叉", clear_signal: "DXBD 极端过热",
  overbought_risk: "超买风险", high_position_risk: "高位风险",
  hanging_man: "吊颈线", shooting_star: "流星线", bearish_engulfing: "看跌吞没",
  dark_cloud_cover: "乌云盖顶", evening_star: "黄昏星"
};
const evidenceText = (value) => String(value || "").split("|").filter(Boolean).map((code) => EVIDENCE_LABELS[code] || code.replaceAll("_", " ")).join(" · ") || "无";

async function getJSON(url) {
  const response = await fetch(url, { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || payload.error || "数据请求失败");
  return payload;
}

async function postJSON(url, payload) {
  const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || data.error || "更新失败");
  return data;
}

async function loadDashboard() {
  try {
    const [data, health] = await Promise.all([getJSON("/api/dashboard"), getJSON("/api/health")]);
    state.rows = data.watchlist;
    $("runId").textContent = data.latest.run_id;
    $("asOf").textContent = `T日 ${data.summary.as_of}`;
    renderBoundary(health);
    renderWatchlist();
    await Promise.allSettled([loadDemoPortfolio(), loadPaperMonitor(), loadPmkfPanel()]);
    if (state.rows.length) selectRow(state.rows[0]);
  } catch (error) {
    $("watchlist").innerHTML = `<div class="empty">${escapeHTML(error.message)}</div>`;
    $("chartLoading").textContent = error.message;
  }
}

function filteredRows() {
  return state.rows;
}

function renderWatchlist() {
  const rows = filteredRows();
  $("rowCount").textContent = rows.length;
  $("watchlist").innerHTML = rows.map((row) => `
    <button class="watch-row ${state.selected?.code === row.code ? "active" : ""}" data-code="${escapeHTML(row.code)}" role="option" aria-selected="${state.selected?.code === row.code}">
      <span class="rank">${escapeHTML(row.rank)}</span>
      <span><strong>${escapeHTML(row.code)}</strong><small>${escapeHTML(row.cnstock_pool || row.watch_stage || "研究观察")}</small></span>
      <span class="row-action"><b>${Number.isFinite(Number(row.edge_score)) ? number(row.edge_score, 1) : "自选"}</b><button class="remove-stock" data-remove-code="${escapeHTML(row.code)}" type="button">移除</button></span>
    </button>`).join("") || '<div class="empty">没有符合当前条件的观察项</div>';
  document.querySelectorAll(".watch-row").forEach((button) => button.addEventListener("click", () => {
    const row = state.rows.find((item) => item.code === button.dataset.code);
    if (row) selectRow(row);
  }));
  document.querySelectorAll(".remove-stock").forEach((button) => button.addEventListener("click", async (event) => {
    event.stopPropagation();
    await removeStock(button.dataset.removeCode);
  }));
}

async function selectRow(row) {
  state.selected = row;
  renderWatchlist();
  $("codeLabel").textContent = row.code;
  $("poolLabel").textContent = (row.cnstock_pool || "RESEARCH OBSERVATION").replaceAll("_", " ").toUpperCase();
  $("stageLabel").textContent = row.watch_stage || "研究观察";
  $("lastClose").textContent = number(row.research_close || row.close, 2);
  const change = Number(row.pct_chg);
  $("changeLabel").textContent = Number.isFinite(change) ? `${change >= 0 ? "+" : ""}${number(change, 2)}% / T日` : "T日研究价";
  $("changeLabel").className = Number.isFinite(change) ? (change >= 0 ? "up" : "down") : "";
  $("snapshotTime").textContent = "本地研究参考价";
  renderEvidence(row);
  scheduleImmediateRefresh();
  await Promise.allSettled([loadCandles(), loadSnapshot(row.code), loadPmkfPanel()]);
}

async function loadCandles({ silent = false } = {}) {
  if ((silent && state.candleLoading > 0) || !state.selected) return;
  state.candleLoading += 1;
  const requestId = ++state.requestId;
  state.hoverIndex = -1;
  $("tooltip").hidden = true;
  if (!silent || !state.chartData) {
    $("chartLoading").hidden = false;
    $("chartLoading").textContent = `加载 ${state.period === "1d" ? "日线" : state.period} 研究数据`;
  }
  setRefreshActivity(true);
  try {
    const data = await getJSON(`/api/candles?code=${encodeURIComponent(state.selected.code)}&period=${state.period}&limit=${state.limit}`);
    if (requestId !== state.requestId) return;
    state.chartData = data;
    $("chartLoading").hidden = true;
    renderPatterns(state.chartData.annotations);
    renderSource(data);
    renderResearchAlert(data.research_alert);
    drawChart();
    state.lastRefreshAt = Date.now();
  } catch (error) {
    if (requestId !== state.requestId) return;
    if (!silent || !state.chartData) {
      state.chartData = null;
      $("chartLoading").hidden = false;
      $("chartLoading").textContent = error.message;
      renderPatterns([]);
    } else {
      $("freshnessStatus").className = "freshness stale";
      $("freshnessStatus").textContent = "刷新失败";
      $("freshnessStatus").title = error.message;
    }
  } finally {
    state.candleLoading = Math.max(0, state.candleLoading - 1);
    state.nextCandlesAt = Date.now() + (state.period === "1d" ? DAILY_REFRESH_MS : INTRADAY_REFRESH_MS);
    setRefreshActivity(false);
  }
}

function renderResearchAlert(alert) {
  const value = alert || { state: "unavailable", title: "研究证据不足", detail: "等待数据", evidence: [] };
  $("researchAlert").className = `research-alert ${value.state}`;
  $("alertTitle").textContent = value.title;
  $("alertDetail").textContent = value.detail;
  $("alertEvidence").textContent = (value.evidence || []).join(" · ") || "提醒仅用于人工研究复核";
}

async function addStock(event) {
  event.preventDefault();
  const input = $("manualCode");
  const rawCode = input.value.trim();
  if (!rawCode) return;
  try {
    await postJSON("/api/research-watchlist/add", { code: rawCode });
    input.value = "";
    setWatchlistMessage("已加入研究监控", "success");
    await reloadManualWatchlist();
  } catch (error) {
    setWatchlistMessage(error.message, "error");
  }
}

async function removeStock(code) {
  try {
    await postJSON("/api/research-watchlist/remove", { code });
    setWatchlistMessage(`已移除 ${code}`, "success");
    await reloadManualWatchlist();
  } catch (error) {
    setWatchlistMessage(error.message, "error");
  }
}

async function reloadManualWatchlist() {
  const previousCode = state.selected?.code;
  const data = await getJSON("/api/dashboard");
  state.rows = data.watchlist;
  state.selected = state.rows.find((row) => row.code === previousCode) || null;
  renderWatchlist();
  if (!state.selected && state.rows.length) await selectRow(state.rows[0]);
  if (!state.rows.length) clearSelection();
}

function clearSelection() {
  state.selected = null; state.chartData = null; state.requestId += 1;
  $("codeLabel").textContent = "--"; $("lastClose").textContent = "--";
  $("chartLoading").hidden = false; $("chartLoading").textContent = "请先输入股票代码加入研究监控";
  renderResearchAlert(null);
}

function setWatchlistMessage(message, className = "") {
  $("watchlistMessage").textContent = message;
  $("watchlistMessage").className = className;
}

async function loadSnapshot(code) {
  if (!code) return;
  const requestId = ++state.snapshotRequestId;
  state.snapshotLoading += 1;
  setRefreshActivity(true);
  try {
    const data = await getJSON(`/api/snapshot?code=${encodeURIComponent(code)}`);
    if (requestId !== state.snapshotRequestId || state.selected?.code !== code) return;
    const snapshot = data.snapshot;
    $("lastClose").textContent = number(snapshot.price, 2);
    $("changeLabel").textContent = `${snapshot.pct_chg >= 0 ? "+" : ""}${number(snapshot.pct_chg, 2)}% / 快照`;
    $("changeLabel").className = snapshot.pct_chg >= 0 ? "up" : "down";
    const fallback = (data.warnings || []).includes("provider_refresh_failed_using_last_observation");
    $("snapshotTime").textContent = `新浪 ${formatTimestamp(snapshot.source_timestamp)}${fallback ? " · 沿用上次观测" : ""}`;
    state.lastRefreshAt = Date.now();
  } catch (error) {
    if (state.selected?.code === code) $("snapshotTime").textContent = `快照不可用 · ${error.message}`;
  } finally {
    state.snapshotLoading = Math.max(0, state.snapshotLoading - 1);
    state.nextSnapshotAt = Date.now() + SNAPSHOT_REFRESH_MS;
    setRefreshActivity(false);
  }
}

function scheduleImmediateRefresh() {
  state.nextSnapshotAt = 0;
  state.nextCandlesAt = 0;
}

function setRefreshActivity(active) {
  const refreshing = active || state.snapshotLoading > 0 || state.candleLoading > 0;
  $("refreshStatus").className = refreshing ? "refresh-status refreshing" : "refresh-status";
  if (refreshing) $("refreshStatus").textContent = "正在更新";
}

function updateRefreshStatus() {
  if (document.hidden || !state.selected) {
    $("refreshStatus").className = "refresh-status";
    $("refreshStatus").textContent = document.hidden ? "后台暂停" : "自动刷新准备中";
    return;
  }
  if (state.snapshotLoading > 0 || state.candleLoading > 0) {
    setRefreshActivity(true);
    return;
  }
  const nextAt = Math.min(state.nextSnapshotAt || Date.now(), state.nextCandlesAt || Date.now());
  const seconds = Math.max(0, Math.ceil((nextAt - Date.now()) / 1000));
  const last = state.lastRefreshAt ? new Date(state.lastRefreshAt).toLocaleTimeString("zh-CN", { hour12: false }) : "--";
  $("refreshStatus").className = "refresh-status";
  $("refreshStatus").textContent = `自动更新 ${seconds}s · 最近 ${last}`;
}

function refreshScheduler() {
  updateRefreshStatus();
  if (document.hidden || !state.selected) return;
  const now = Date.now();
  if (state.snapshotLoading === 0 && now >= state.nextSnapshotAt) loadSnapshot(state.selected.code);
  if (state.candleLoading === 0 && now >= state.nextCandlesAt) loadCandles({ silent: true });
}

function renderSource(data) {
  const status = data.freshness?.status || "unavailable";
  const labels = { fresh: "数据新鲜", delayed: "数据延迟", stale: "数据过期", market_closed: "市场休市", local_close: "本地收盘", unavailable: "不可用" };
  $("freshnessStatus").className = `freshness ${status}`;
  $("freshnessStatus").textContent = labels[status] || status;
  $("freshnessStatus").title = data.freshness?.detail || "";
  $("sourceLabel").textContent = `来源：${data.provenance?.provider || "未知"} · ${data.provenance?.adjustment || ""}`;
  $("sourceTime").textContent = `数据时间：${formatTimestamp(data.provenance?.source_timestamp)}`;
}

function renderPatterns(items) {
  $("patternCount").textContent = `${items.length} 项`;
  $("patternList").innerHTML = items.length ? items.slice().reverse().map((item) => {
    if (item.kind === "risk") {
      return `<div class="pattern-item risk"><time>${escapeHTML(item.date)}</time><span><strong>${escapeHTML(item.label)}</strong><small>顶部或上涨后的趋势变化风险，不构成做空结论</small></span><b class="status-dot risk">风险观察</b></div>`;
    }
    const unit = state.period === "1d" ? "一日" : "一根";
    const status = item.status === "confirmed" ? "已获量价确认" : item.status === "pending" ? `等待后${unit}` : `未获后${unit}确认`;
    const detail = item.volume_ratio ? `确认日量比 ${number(item.volume_ratio, 2)}` : "形态观察，不独立构成结论";
    return `<div class="pattern-item"><time>${escapeHTML(item.date)}</time><span><strong>${escapeHTML(item.label)}</strong><small>${escapeHTML(detail)}</small></span><b class="status-dot ${item.status === "confirmed" ? "ok" : ""}">${status}</b></div>`;
  }).join("") : '<div class="empty">当前区间未识别到启用的看涨形态或看跌风险形态</div>';
}

function renderBoundary(health) {
  $("auditRisk").innerHTML = [
    ["Mode", health.mode],
    ["Demo portfolio", health.allow_demo_portfolio ? "enabled" : "disabled"],
    ["Paper trading", health.allow_paper_trading ? "enabled" : "disabled"],
    ["Live orders", health.allow_live_order_submission ? "ON" : "off"],
    ["Broker connection", health.live_broker_enabled ? "connected" : "none"],
    ["Production", health.production_enabled ? "ON" : "off"]
  ].map(([label, value]) => `<div class="ops-row"><span>${escapeHTML(label)}</span><strong>${escapeHTML(value)}</strong></div>`).join("");
}

async function loadDemoPortfolio() {
  const data = await getJSON("/api/demo-portfolio/status?portfolio_id=default");
  const portfolio = data.portfolio;
  const positions = Object.values(portfolio.positions || {});
  $("demoPortfolio").className = "ops-list";
  $("demoPortfolio").innerHTML = `
    <div class="metric-strip"><span>Demo cash <b>${number(portfolio.demo_cash, 2)}</b></span><span>Max equity high <b>${number(portfolio.demo_max_equity_high, 2)}</b></span><span>Positions <b>${positions.length}/${portfolio.settings.max_positions}</b></span></div>
    ${positions.length ? positions.map((item) => `<div class="ops-row"><span><b>${escapeHTML(item.code)}</b><small>${escapeHTML(item.state)} · ${escapeHTML(item.note || "Paper-only review")}</small></span><strong>${number(item.reference_price, 2)}</strong></div>`).join("") : '<div class="empty">暂无 demo positions</div>'}
    <div class="factor-line">Factors: ${(data.factors || []).map((item) => escapeHTML(item.filename)).join(" · ") || "none"}</div>`;
}

async function addDemoPosition(event) {
  event.preventDefault();
  const code = $("demoCode").value.trim();
  if (!code) return;
  try {
    await postJSON("/api/demo-portfolio/add", { portfolio_id: "default", code, state: $("demoState").value });
    $("demoCode").value = "";
    await Promise.allSettled([loadDemoPortfolio(), loadPaperMonitor()]);
  } catch (error) {
    $("demoPortfolio").innerHTML = `<div class="empty">${escapeHTML(error.message)}</div>`;
  }
}

async function loadPaperMonitor() {
  const data = await getJSON("/api/paper/status?portfolio_id=default");
  $("paperMonitor").className = "ops-list";
  $("paperMonitor").innerHTML = `
    <div class="metric-strip"><span>Sim cash <b>${number(data.simulated_cash, 2)}</b></span><span>Positions <b>${data.simulated_positions.length}</b></span><span>Broker <b>${escapeHTML(data.broker_connection)}</b></span></div>
    <div class="ops-row"><span>Risk controls</span><strong>${escapeHTML(Math.round(data.risk_controls.max_position_pct * 100))}% max position</strong></div>
    <div class="ops-row"><span>Freshness</span><strong>${escapeHTML((data.freshness_warnings || []).join(" · ") || "research data checked")}</strong></div>
    ${(data.recent_events || []).slice(-5).reverse().map((item) => `<div class="ops-row"><span>${escapeHTML(item.event_type)}</span><strong>${formatTimestamp(item.created_at)}</strong></div>`).join("") || '<div class="empty">暂无 paper history</div>'}`;
}

async function loadPmkfPanel() {
  const [summary, codeData] = await Promise.allSettled([
    getJSON("/api/pmkf-mkf/summary"),
    state.selected?.code ? getJSON(`/api/pmkf-mkf/code?code=${encodeURIComponent(state.selected.code)}`) : Promise.resolve(null)
  ]);
  const summaryData = summary.status === "fulfilled" ? summary.value : { latest_reports: [], warnings: [summary.reason.message] };
  const codePayload = codeData.status === "fulfilled" ? codeData.value : null;
  $("pmkfPanel").className = "ops-list";
  $("pmkfPanel").innerHTML = `
    <div class="ops-row"><span>Reports</span><strong>${summaryData.report_count || 0}</strong></div>
    <div class="ops-row"><span>Warnings</span><strong>${escapeHTML((summaryData.warnings || []).join(" · "))}</strong></div>
    ${codePayload ? `<div class="ops-row"><span>${escapeHTML(codePayload.code)} PMKF slope</span><strong>${number(codePayload.pmkf_slope, 4)}</strong></div><div class="ops-row"><span>MKF red/blue</span><strong>${number(codePayload.mkf_lines.momentum, 2)} / ${number(codePayload.mkf_lines.near, 2)}</strong></div>` : '<div class="empty">选择股票后显示单代码 PMKF/MKF</div>'}`;
}

function renderEvidence(row) {
  const evidence = [
    ["Edge 分数", number(row.edge_score, 1)], ["基础质量", `${number(row.base_quality_score, 1)} / 45`],
    ["时机评分", `${number(row.timing_score, 1)} / 35`], ["风险评分", `${number(row.risk_score, 1)} / 20`],
    ["CNstock 基础分", number(row.cnstock_base_score, 1)], ["Futu 调整", number(row.futu_bonus, 1)],
    ["启动信号", evidenceText(row.start_signals)], ["Futu 状态", evidenceText(row.futu_status_codes)],
    ["Futu 风险", evidenceText(row.futu_risk_codes)], ["蜡烛风险", evidenceText(row.candle_bearish_risk_patterns)],
    ["5日变化", `${number(row.ret_5d, 2)}%`],
    ["成交额", compact(row.amount_cny)], ["20日量比", number(row.volume_ratio_20, 2)],
    ["T日形态", row.t_day_patterns?.replaceAll("|", " · ") || "无"], ["量价确认", truthy(row.price_volume_confirmed) ? "是" : "否"],
    ["研究参考区间", `${number(row.stop_reference, 2)} - ${number(row.take_profit_reference, 2)}`], ["风险距离", `${number(Number(row.risk_distance_pct) * 100, 2)}%`]
  ];
  $("evidenceList").innerHTML = evidence.map(([term, value]) => `<div><dt>${escapeHTML(term)}</dt><dd>${escapeHTML(value)}</dd></div>`).join("");
}

function drawChart() {
  if (!state.chartData?.bars.length) return;
  const canvas = $("chart");
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.round(rect.width * ratio)); canvas.height = Math.max(1, Math.round(rect.height * ratio));
  const ctx = canvas.getContext("2d"); ctx.scale(ratio, ratio);
  const bars = state.chartData.bars, width = rect.width, height = rect.height;
  const margin = { left: 12, right: 58, top: 48, bottom: 24 }, volumeHeight = 92, gap = 18;
  const priceBottom = height - margin.bottom - volumeHeight - gap;
  const minPrice = Math.min(...bars.flatMap((b) => [b.low, b.ma20 ?? Infinity, b.ma60 ?? Infinity]));
  const maxPrice = Math.max(...bars.flatMap((b) => [b.high, b.ma20 ?? -Infinity, b.ma60 ?? -Infinity]));
  const pricePad = Math.max((maxPrice - minPrice) * .07, maxPrice * .005);
  const low = minPrice - pricePad, high = maxPrice + pricePad;
  const plotWidth = width - margin.left - margin.right, step = plotWidth / bars.length;
  const x = (i) => margin.left + step * (i + .5), y = (p) => margin.top + (high - p) / (high - low) * (priceBottom - margin.top);
  const maxVolume = Math.max(1, ...bars.map((b) => b.volume));
  ctx.clearRect(0, 0, width, height); ctx.font = '10px "Avenir Next", sans-serif'; ctx.textAlign = "left";
  for (let i = 0; i <= 5; i++) {
    const yy = margin.top + (priceBottom - margin.top) * i / 5, price = high - (high - low) * i / 5;
    ctx.strokeStyle = "#e8e5da"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(margin.left, yy); ctx.lineTo(width - margin.right, yy); ctx.stroke();
    ctx.fillStyle = "#66716b"; ctx.fillText(number(price, 2), width - margin.right + 8, yy + 3);
  }
  bars.forEach((bar, i) => {
    const xx = x(i), rising = bar.close >= bar.open, color = rising ? "#c43d31" : "#137a5c";
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 1; ctx.globalAlpha = bar.is_forming ? .58 : 1;
    ctx.beginPath(); ctx.moveTo(xx, y(bar.high)); ctx.lineTo(xx, y(bar.low)); ctx.stroke();
    const bodyTop = y(Math.max(bar.open, bar.close)), bodyBottom = y(Math.min(bar.open, bar.close));
    const candleWidth = Math.max(1.5, Math.min(8, step * .62));
    if (bar.is_forming) { ctx.setLineDash([2, 2]); ctx.strokeRect(xx - candleWidth / 2, bodyTop, candleWidth, Math.max(1, bodyBottom - bodyTop)); ctx.setLineDash([]); }
    else ctx.fillRect(xx - candleWidth / 2, bodyTop, candleWidth, Math.max(1, bodyBottom - bodyTop));
    const volumeY = height - margin.bottom - bar.volume / maxVolume * volumeHeight;
    ctx.globalAlpha = bar.is_forming ? .3 : .55; ctx.fillRect(xx - candleWidth / 2, volumeY, candleWidth, height - margin.bottom - volumeY); ctx.globalAlpha = 1;
  });
  drawLine(ctx, bars, "ma20", x, y, "#397a94"); drawLine(ctx, bars, "ma60", x, y, "#c68b27");
  (state.chartData.annotations || []).forEach((item) => {
    const bar = bars[item.index]; if (!bar) return;
    const risk = item.kind === "risk";
    ctx.fillStyle = risk ? "#c43d31" : item.status === "confirmed" ? "#137a5c" : "#c68b27";
    ctx.beginPath(); ctx.arc(x(item.index), risk ? y(bar.high) - 9 : y(bar.low) + 9, 3.5, 0, Math.PI * 2); ctx.fill();
  });
  const dateStride = Math.max(1, Math.ceil(bars.length / 7)); ctx.fillStyle = "#66716b"; ctx.textAlign = "center";
  bars.forEach((bar, i) => { if (i % dateStride === 0 || i === bars.length - 1) ctx.fillText(formatAxisTime(bar.timestamp || bar.date), x(i), height - 6); });
  if (state.hoverIndex >= 0 && state.hoverIndex < bars.length) { ctx.strokeStyle = "#66716b"; ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(x(state.hoverIndex), margin.top); ctx.lineTo(x(state.hoverIndex), height - margin.bottom); ctx.stroke(); ctx.setLineDash([]); }
  canvas.dataset.step = step; canvas.dataset.left = margin.left;
}

function drawLine(ctx, bars, key, x, y, color) {
  ctx.strokeStyle = color; ctx.lineWidth = 1.4; ctx.beginPath(); let started = false;
  bars.forEach((bar, i) => { if (bar[key] == null) return; if (!started) { ctx.moveTo(x(i), y(bar[key])); started = true; } else ctx.lineTo(x(i), y(bar[key])); }); ctx.stroke();
}

function escapeHTML(value) { const node = document.createElement("span"); node.textContent = String(value ?? ""); return node.innerHTML; }
function formatTimestamp(value) { if (!value) return "--"; const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("zh-CN", { hour12: false, month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }); }
function formatAxisTime(value) { if (state.period === "1d") return String(value).slice(5, 10); const text = formatTimestamp(value); return text.slice(-5); }

$("addStockForm").addEventListener("submit", addStock);
$("demoAddForm").addEventListener("submit", addDemoPosition);
$("refreshDemo").addEventListener("click", loadDemoPortfolio);
$("refreshPaper").addEventListener("click", loadPaperMonitor);
$("refreshPmkf").addEventListener("click", loadPmkfPanel);
document.querySelectorAll(".range-control button").forEach((button) => button.addEventListener("click", () => { document.querySelectorAll(".range-control button").forEach((b) => b.classList.remove("active")); button.classList.add("active"); state.limit = Number(button.dataset.limit); state.nextCandlesAt = 0; loadCandles(); }));
document.querySelectorAll(".period-control button").forEach((button) => button.addEventListener("click", () => { document.querySelectorAll(".period-control button").forEach((b) => b.classList.remove("active")); button.classList.add("active"); state.period = button.dataset.period; state.nextCandlesAt = 0; loadCandles(); }));
$("chart").addEventListener("mousemove", (event) => { if (!state.chartData) return; const rect = event.currentTarget.getBoundingClientRect(), step = Number(event.currentTarget.dataset.step), left = Number(event.currentTarget.dataset.left); const index = Math.max(0, Math.min(state.chartData.bars.length - 1, Math.floor((event.clientX - rect.left - left) / step))); state.hoverIndex = index; const bar = state.chartData.bars[index]; const tip = $("tooltip"); tip.hidden = false; tip.style.left = `${Math.min(rect.width - 145, event.clientX - rect.left + 12)}px`; tip.style.top = `${Math.max(48, event.clientY - rect.top - 52)}px`; tip.innerHTML = `${formatTimestamp(bar.timestamp || bar.date)}${bar.is_forming ? " · 形成中" : ""}<br>开 ${number(bar.open)}　高 ${number(bar.high)}<br>低 ${number(bar.low)}　收 ${number(bar.close)}<br>量 ${compact(bar.volume)}`; drawChart(); });
$("chart").addEventListener("mouseleave", () => { state.hoverIndex = -1; $("tooltip").hidden = true; drawChart(); });
window.addEventListener("resize", () => requestAnimationFrame(drawChart));
document.addEventListener("visibilitychange", () => { if (!document.hidden) { scheduleImmediateRefresh(); refreshScheduler(); } else updateRefreshStatus(); });
setInterval(refreshScheduler, 1000);
loadDashboard();
