#!/usr/bin/env node

"use strict";

const crypto = require("crypto");
const fs = require("fs");
const https = require("https");
const path = require("path");
const vm = require("vm");

const SOURCE_URL = "https://webapi.cninfo.com.cn/api/stock/p_stock2110";
const CLASSIFICATION_CODE = "008001";
const CODES = [
  "600000", "600021", "600025", "600031", "600052", "600055", "600085", "600096",
  "600100", "600105", "600132", "600148", "600161", "600162", "600166", "600169",
  "600176", "600192", "600196", "600216", "600223", "600229", "600248", "600255",
  "600276", "600282", "600284", "600295", "600301", "600307", "600323", "600339",
  "600340", "600348", "600354", "600356", "600360", "600368", "600375", "600397",
];

function parseArgs(argv) {
  const values = { retries: 2, timeoutMs: 10000 };
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (flag === "--cninfo-js") values.cninfoJs = value;
    else if (flag === "--output") values.output = value;
    else if (flag === "--retries") values.retries = Number(value);
    else if (flag === "--timeout-ms") values.timeoutMs = Number(value);
    else throw new Error(`unknown or incomplete argument: ${flag}`);
  }
  if (!values.cninfoJs || !values.output) {
    throw new Error("usage: probe_cninfo_industry_coverage.js --cninfo-js PATH --output PATH");
  }
  if (!Number.isInteger(values.retries) || values.retries < 0 || values.retries > 3) {
    throw new Error("--retries must be from 0 through 3");
  }
  return values;
}

function loadSignatureFunction(file) {
  const context = { Date, Math };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
  if (typeof context.getResCode1 !== "function") throw new Error("getResCode1 not found");
  return context.getResCode1;
}

function requestCode(code, signature, timeoutMs) {
  const query = new URLSearchParams({ scode: code, sdate: "2015-01-01", edate: "2026-08-15" });
  return new Promise((resolve, reject) => {
    const request = https.request(`${SOURCE_URL}?${query}`, {
      method: "POST",
      headers: {
        Accept: "*/*",
        "Accept-Enckey": signature(),
        "Content-Length": "0",
        Origin: "https://webapi.cninfo.com.cn",
        Referer: "https://webapi.cninfo.com.cn/",
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
      },
      timeout: timeoutMs,
    }, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => { body += chunk; });
      response.on("end", () => {
        if (response.statusCode !== 200) return reject(new Error(`HTTP ${response.statusCode}`));
        try { resolve({ body, value: JSON.parse(body) }); }
        catch (error) { reject(new Error(`invalid JSON: ${error.message}`)); }
      });
    });
    request.on("timeout", () => request.destroy(new Error("request timeout")));
    request.on("error", reject);
    request.end();
  });
}

async function withRetries(code, signature, timeoutMs, retries) {
  let error;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try { return await requestCode(code, signature, timeoutMs); }
    catch (caught) { error = caught; }
  }
  throw error;
}

function normalizedRecords(value) {
  return (Array.isArray(value.records) ? value.records : [])
    .filter((record) => record.F001V === CLASSIFICATION_CODE)
    .map((record) => ({
      code: String(record.SECCODE || ""),
      effective_date: String(record.VARYDATE || ""),
      classification_code: String(record.F001V || ""),
      classification_name: String(record.F002V || ""),
      industry_code: String(record.F003V || ""),
      industry_section: String(record.F004V || ""),
      industry_subclass: String(record.F005V || ""),
      industry_major: String(record.F006V || ""),
      industry_middle: String(record.F007V || ""),
    }))
    .sort((left, right) => JSON.stringify(left).localeCompare(JSON.stringify(right)));
}

function hash(value) {
  return crypto.createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const signature = loadSignatureFunction(args.cninfoJs);
  const results = [];
  for (const code of CODES) {
    try {
      const response = await withRetries(code, signature, args.timeoutMs, args.retries);
      const records = normalizedRecords(response.value);
      const eligible = records.filter((record) => /^\d{4}-\d{2}-\d{2}$/.test(record.effective_date)
        && record.effective_date <= "2021-01-01" && record.industry_code && record.classification_name);
      results.push({ code, records, normalized_hash: hash(records), valid_at_2021_start: eligible.length > 0 });
    } catch (error) {
      results.push({ code, error: error.message, records: [], normalized_hash: hash([]), valid_at_2021_start: false });
    }
  }
  const repeat = await withRetries(CODES[0], signature, args.timeoutMs, args.retries);
  const repeatHash = hash(normalizedRecords(repeat.value));
  const valid = results.filter((item) => item.valid_at_2021_start).length;
  const report = {
    probe: "cninfo_csrc_industry_coverage",
    source_url: SOURCE_URL,
    source_adapter: "AKShare stock_industry_change_cninfo",
    source_adapter_commit: "1248fdd05a2dda92937d4cd39c0957825f2f7f6e",
    retrieved_at: new Date().toISOString(),
    classification_code: CLASSIFICATION_CODE,
    request_range: ["2015-01-01", "2026-08-15"],
    codes: CODES,
    valid_at_2021_start: valid,
    required_valid: 38,
    repeated_first_code_hash_equal: repeatHash === results[0].normalized_hash,
    passed: valid >= 38 && repeatHash === results[0].normalized_hash,
    results,
  };
  fs.mkdirSync(path.dirname(args.output), { recursive: true });
  const temporary = `${args.output}.${process.pid}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(report, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  fs.renameSync(temporary, args.output);
  console.log(JSON.stringify({ passed: report.passed, valid, required: 38, repeat: report.repeated_first_code_hash_equal }));
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
