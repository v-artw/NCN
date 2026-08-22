#!/usr/bin/env node

"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const SOURCE_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query";
const CATEGORY_IDS = [
  "category_bcgz_szsh",
  "category_cqdq_szsh",
  "category_fxts_szsh",
  "category_tbclts_szsh",
];

function parseArgs(argv) {
  const result = { concurrency: 4, retries: 2, timeoutMs: 15000 };
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (flag === "--stock-map") result.stockMap = value;
    else if (flag === "--codes") result.codes = value;
    else if (flag === "--output") result.output = value;
    else if (flag === "--concurrency") result.concurrency = Number(value);
    else if (flag === "--retries") result.retries = Number(value);
    else if (flag === "--timeout-ms") result.timeoutMs = Number(value);
    else throw new Error(`unknown or incomplete argument: ${flag}`);
  }
  if (!result.stockMap || !result.codes || !result.output) {
    throw new Error("usage: fetch_cninfo_risk_disclosures.js --stock-map PATH --codes PATH --output PATH");
  }
  if (!Number.isInteger(result.concurrency) || result.concurrency < 1 || result.concurrency > 8) {
    throw new Error("--concurrency must be from 1 through 8");
  }
  return result;
}

function hash(value) {
  return crypto.createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

async function retry(operation, retries) {
  let error;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try { return await operation(); }
    catch (caught) { error = caught; }
  }
  throw error;
}

async function requestPage(code, orgId, pageNum, args) {
  const payload = new URLSearchParams({
    pageNum: String(pageNum), pageSize: "30", column: "szse", tabName: "fulltext",
    plate: "", stock: `${code},${orgId}`, searchkey: "", secid: "",
    category: CATEGORY_IDS.join(";"), trade: "", seDate: "2021-01-01~2026-08-15",
    sortName: "", sortType: "", isHLtitle: "true",
  });
  const response = await fetch(SOURCE_URL, {
    method: "POST",
    headers: {
      "content-type": "application/x-www-form-urlencoded",
      referer: "https://www.cninfo.com.cn/",
      "user-agent": "Mozilla/5.0",
    },
    body: payload,
    signal: AbortSignal.timeout(args.timeoutMs),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const value = await response.json();
  if (!Number.isInteger(Number(value.totalAnnouncement))) throw new Error("invalid totalAnnouncement");
  if (value.announcements !== null && !Array.isArray(value.announcements)) throw new Error("invalid announcements");
  return value;
}

async function queryCode(code, orgId, args) {
  const first = await retry(() => requestPage(code, orgId, 1, args), args.retries);
  const total = Number(first.totalAnnouncement);
  const rows = [...(first.announcements || [])];
  for (let pageNum = 2; pageNum <= Math.ceil(total / 30); pageNum += 1) {
    const page = await retry(() => requestPage(code, orgId, pageNum, args), args.retries);
    rows.push(...(page.announcements || []));
  }
  if (rows.length !== total) throw new Error(`pagination mismatch ${rows.length}/${total}`);
  const normalized = rows.map((row) => ({
    announcement_id: String(row.announcementId || ""),
    code: String(row.secCode || ""),
    org_id: String(row.orgId || ""),
    title: String(row.announcementTitle || "").replace(/<[^>]+>/g, ""),
    timestamp_ms: Number(row.announcementTime),
    category_query: [...CATEGORY_IDS],
  })).sort((left, right) => left.announcement_id.localeCompare(right.announcement_id));
  if (!normalized.every((row) => row.announcement_id && row.code === code && row.org_id
    && Number.isFinite(row.timestamp_ms) && row.timestamp_ms > 0)) {
    throw new Error("invalid announcement row");
  }
  return normalized;
}

async function pooledMap(items, concurrency, operation) {
  const results = new Array(items.length);
  let next = 0;
  async function worker() {
    while (next < items.length) {
      const index = next;
      next += 1;
      results[index] = await operation(items[index]);
    }
  }
  await Promise.all(Array.from({ length: concurrency }, worker));
  return results;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const stockList = JSON.parse(fs.readFileSync(args.stockMap, "utf8")).stockList;
  const organizations = new Map(stockList.map((item) => [String(item.code), String(item.orgId)]));
  const codes = JSON.parse(fs.readFileSync(args.codes, "utf8"));
  if (!Array.isArray(codes) || codes.length !== 400 || new Set(codes).size !== 400) {
    throw new Error("codes file must contain exactly 400 unique six-digit codes");
  }
  const missing = codes.filter((code) => !organizations.has(code));
  if (missing.length) throw new Error(`provider stock map missing codes: ${missing.join(",")}`);
  let completed = 0;
  const perCode = await pooledMap(codes, args.concurrency, async (code) => {
    const rows = await queryCode(code, organizations.get(code), args);
    completed += 1;
    if (completed % 25 === 0) console.error(`fetched ${completed}/400`);
    return { code, normalized_hash: hash(rows), announcements: rows };
  });
  const deduplicated = new Map();
  for (const item of perCode) {
    for (const row of item.announcements) deduplicated.set(row.announcement_id, row);
  }
  const report = {
    cache: "cninfo_fixed_risk_disclosures_400",
    source_url: SOURCE_URL,
    source_adapter: "AKShare stock_zh_a_disclosure_report_cninfo",
    source_adapter_commit: "1248fdd05a2dda92937d4cd39c0957825f2f7f6e",
    retrieved_at: new Date().toISOString(),
    request_range: ["2021-01-01", "2026-08-15"],
    category_ids: CATEGORY_IDS,
    codes,
    stock_map_hash: hash(stockList),
    distinct_announcements: deduplicated.size,
    per_code: perCode,
  };
  fs.mkdirSync(path.dirname(args.output), { recursive: true });
  const temporary = `${args.output}.${process.pid}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(report, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  fs.renameSync(temporary, args.output);
  console.log(JSON.stringify({ codes: codes.length, announcements: deduplicated.size }));
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
