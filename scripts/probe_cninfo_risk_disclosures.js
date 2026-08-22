#!/usr/bin/env node

"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const SOURCE_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query";
const CATEGORIES = {
  correction: "category_bcgz_szsh",
  clarification: "category_cqdq_szsh",
  risk_warning: "category_fxts_szsh",
  special_treatment_delisting: "category_tbclts_szsh",
};
const CODES = [
  "600000", "600021", "600025", "600031", "600052", "600055", "600085", "600096",
  "600100", "600105", "600132", "600148", "600161", "600162", "600166", "600169",
  "600176", "600192", "600196", "600216", "600223", "600229", "600248", "600255",
  "600276", "600282", "600284", "600295", "600301", "600307", "600323", "600339",
  "600340", "600348", "600354", "600356", "600360", "600368", "600375", "600397",
];

function parseArgs(argv) {
  const result = { retries: 2, timeoutMs: 10000 };
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (flag === "--stock-map") result.stockMap = value;
    else if (flag === "--output") result.output = value;
    else if (flag === "--retries") result.retries = Number(value);
    else if (flag === "--timeout-ms") result.timeoutMs = Number(value);
    else throw new Error(`unknown or incomplete argument: ${flag}`);
  }
  if (!result.stockMap || !result.output) {
    throw new Error("usage: probe_cninfo_risk_disclosures.js --stock-map PATH --output PATH");
  }
  return result;
}

function hash(value) {
  return crypto.createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

async function requestPage(code, orgId, category, pageNum, timeoutMs) {
  const payload = new URLSearchParams({
    pageNum: String(pageNum), pageSize: "30", column: "szse", tabName: "fulltext",
    plate: "", stock: `${code},${orgId}`, searchkey: "", secid: "", category,
    trade: "", seDate: "2021-01-01~2026-08-15", sortName: "", sortType: "",
    isHLtitle: "true",
  });
  const response = await fetch(SOURCE_URL, {
    method: "POST",
    headers: {
      "content-type": "application/x-www-form-urlencoded",
      referer: "https://www.cninfo.com.cn/",
      "user-agent": "Mozilla/5.0",
    },
    body: payload,
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const value = await response.json();
  if (!Number.isInteger(Number(value.totalAnnouncement))) throw new Error("invalid totalAnnouncement");
  if (value.announcements !== null && !Array.isArray(value.announcements)) throw new Error("invalid announcements");
  return value;
}

async function retry(operation, retries) {
  let error;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try { return await operation(); }
    catch (caught) { error = caught; }
  }
  throw error;
}

async function queryCategory(code, orgId, categoryName, category, args) {
  const first = await retry(() => requestPage(code, orgId, category, 1, args.timeoutMs), args.retries);
  const total = Number(first.totalAnnouncement);
  const pages = Math.ceil(total / 30);
  const rows = [...(first.announcements || [])];
  for (let pageNum = 2; pageNum <= pages; pageNum += 1) {
    const page = await retry(() => requestPage(code, orgId, category, pageNum, args.timeoutMs), args.retries);
    rows.push(...(page.announcements || []));
  }
  if (rows.length !== total) throw new Error(`pagination mismatch ${rows.length}/${total}`);
  return rows.map((row) => ({
    announcement_id: String(row.announcementId || ""),
    code: String(row.secCode || ""),
    org_id: String(row.orgId || ""),
    title: String(row.announcementTitle || "").replace(/<[^>]+>/g, ""),
    timestamp_ms: Number(row.announcementTime),
    category: categoryName,
    category_id: category,
  })).sort((left, right) => left.announcement_id.localeCompare(right.announcement_id));
}

function validate(rows, code) {
  return rows.every((row) => row.announcement_id && row.code === code && row.org_id
    && Number.isFinite(row.timestamp_ms) && row.timestamp_ms > 0 && row.category && row.category_id);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const stockList = JSON.parse(fs.readFileSync(args.stockMap, "utf8")).stockList;
  const organizations = new Map(stockList.map((item) => [String(item.code), String(item.orgId)]));
  const missingCodes = CODES.filter((code) => !organizations.has(code));
  const queryResults = [];
  for (const code of CODES) {
    const orgId = organizations.get(code);
    if (!orgId) continue;
    for (const [categoryName, category] of Object.entries(CATEGORIES)) {
      try {
        const rows = await queryCategory(code, orgId, categoryName, category, args);
        queryResults.push({ code, category: categoryName, valid: validate(rows, code), rows, hash: hash(rows) });
      } catch (error) {
        queryResults.push({ code, category: categoryName, valid: false, error: error.message, rows: [], hash: hash([]) });
      }
    }
  }
  const repeatCategory = CATEGORIES.correction;
  const repeatRows = await queryCategory(CODES[0], organizations.get(CODES[0]), "correction", repeatCategory, args);
  const firstQuery = queryResults.find((item) => item.code === CODES[0] && item.category === "correction");
  const repeatHashEqual = Boolean(firstQuery && hash(repeatRows) === firstQuery.hash);
  const distinct = new Map();
  for (const query of queryResults) {
    for (const row of query.rows) distinct.set(row.announcement_id, row);
  }
  const announcements = [...distinct.values()].sort((left, right) => left.announcement_id.localeCompare(right.announcement_id));
  const codesWithAnnouncements = new Set(announcements.map((row) => row.code));
  const years = [...new Set(announcements.map((row) => new Date(row.timestamp_ms).getUTCFullYear()))].sort();
  const requiredYears = [2021, 2022, 2023, 2024, 2025];
  const allQueriesValid = queryResults.length === 160 && queryResults.every((item) => item.valid);
  const passed = missingCodes.length === 0 && allQueriesValid && repeatHashEqual
    && announcements.length >= 40 && codesWithAnnouncements.size >= 15
    && requiredYears.every((year) => years.includes(year));
  const report = {
    probe: "cninfo_fixed_risk_disclosure_coverage",
    source_url: SOURCE_URL,
    source_adapter: "AKShare stock_zh_a_disclosure_report_cninfo",
    source_adapter_commit: "1248fdd05a2dda92937d4cd39c0957825f2f7f6e",
    retrieved_at: new Date().toISOString(),
    request_range: ["2021-01-01", "2026-08-15"],
    categories: CATEGORIES,
    codes: CODES,
    stock_map_hash: hash(stockList),
    missing_codes: missingCodes,
    all_queries_valid: allQueriesValid,
    repeated_query_hash_equal: repeatHashEqual,
    distinct_announcements: announcements.length,
    codes_with_announcements: codesWithAnnouncements.size,
    observed_years: years,
    required: { announcements: 40, codes: 15, years: requiredYears },
    passed,
    query_results: queryResults,
  };
  fs.mkdirSync(path.dirname(args.output), { recursive: true });
  const temporary = `${args.output}.${process.pid}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(report, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  fs.renameSync(temporary, args.output);
  console.log(JSON.stringify({ passed, announcements: announcements.length, codes: codesWithAnnouncements.size, years, allQueriesValid, repeatHashEqual }));
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
