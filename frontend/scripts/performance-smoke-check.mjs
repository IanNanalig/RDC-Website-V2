import assert from "node:assert/strict";
import { chromium } from "playwright-core";

const frontendUrl = process.env.PERFORMANCE_TEST_FRONTEND_URL || "http://127.0.0.1:4173";
const edgePath = process.env.CMS_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const browser = await chromium.launch({ executablePath: edgePath, headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
const publicOptions = [];
const chatbotChunks = [];

await page.addInitScript(() => {
  window.__rdcPerformance = { lcp: 0, cls: 0 };
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) window.__rdcPerformance.lcp = entry.startTime;
  }).observe({ type: "largest-contentful-paint", buffered: true });
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      if (!entry.hadRecentInput) window.__rdcPerformance.cls += entry.value;
    }
  }).observe({ type: "layout-shift", buffered: true });
});

page.on("request", (request) => {
  const url = request.url();
  if (request.method() === "OPTIONS" && /\/api\/public\//.test(url)) publicOptions.push(url);
  if (/PublicChatbot-.*\.js/.test(url)) chatbotChunks.push(url);
});

await page.route("**/api/**", async (route) => {
  const request = route.request();
  const url = request.url();
  if (request.method() === "OPTIONS") {
    await route.fulfill({ status: 204, headers: { "access-control-allow-origin": "*" } });
    return;
  }
  let body = {};
  if (url.includes("public/cms/pages/home/")) {
    body = { title: "Home", slug: "home", publishedAt: "2026-09-09T00:00:00Z", sections: [] };
  } else if (url.includes("public/projects/stats/")) {
    body = { total_projects: 0, total_budget: 0, by_status: {}, by_agency: {}, by_lgu: {}, unspecified_location_count: 0 };
  } else if (url.includes("public/projects/")) {
    body = [];
  } else if (url.includes("public/cms/news/")) {
    body = { results: [], count: 0 };
  } else if (url.includes("public/cms/events/")) {
    body = { results: [], count: 0 };
  } else if (url.includes("analytics/")) {
    body = { pageviews: 1, avg_daily: 1, today: 1, total_visitors: 1 };
  }
  await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
});

await page.goto(frontendUrl, { waitUntil: "load" });
await page.waitForTimeout(500);
const metrics = await page.evaluate(() => {
  const fcp = performance.getEntriesByName("first-contentful-paint")[0];
  const resources = performance.getEntriesByType("resource");
  return {
    fcp: fcp?.startTime || 0,
    heroBeforeFcp: resources.filter((entry) => entry.name.includes("hero-photo") && entry.startTime <= (fcp?.startTime || 0) + 5).length,
    initialBytes: resources.reduce((total, entry) => total + (entry.transferSize || entry.encodedBodySize || 0), 0),
    lcp: window.__rdcPerformance?.lcp || 0,
    cls: window.__rdcPerformance?.cls || 0,
  };
});

assert.equal(metrics.heroBeforeFcp, 1, `Expected one hero request before FCP, got ${metrics.heroBeforeFcp}.`);
assert.ok(metrics.initialBytes <= 1.5 * 1024 * 1024, `Initial transfer exceeded 1.5 MB: ${metrics.initialBytes} bytes.`);
assert.ok(metrics.lcp > 0 && metrics.lcp < 2500, `LCP target missed: ${metrics.lcp} ms.`);
assert.ok(metrics.cls < 0.1, `CLS target missed: ${metrics.cls}.`);
assert.equal(publicOptions.length, 0, `Public GET triggered OPTIONS: ${publicOptions.join(", ")}`);
assert.equal(chatbotChunks.length, 0, "Chatbot internals loaded before the launcher was opened.");

await page.getByRole("button", { name: "Open chatbot" }).click();
await page.getByText("How can I help today?", { exact: true }).waitFor();
assert.equal(chatbotChunks.length, 1, "Chatbot internals did not load exactly once after opening.");

console.log(`PASS home performance smoke: ${metrics.initialBytes} bytes, LCP ${Math.round(metrics.lcp)} ms, CLS ${metrics.cls.toFixed(3)}`);
await browser.close();
