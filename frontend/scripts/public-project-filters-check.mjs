import assert from "node:assert/strict";
import { chromium } from "playwright-core";
import { preview } from "vite";

const server = await preview({ preview: { host: "127.0.0.1", port: 0 } });
const address = server.httpServer.address();
assert.ok(address && typeof address !== "string");
const browser = await chromium.launch({
  executablePath: process.env.CMS_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  headless: true,
});
const headers = { "access-control-allow-origin": "*", "access-control-allow-methods": "GET, OPTIONS", "access-control-allow-headers": "authorization, content-type" };
const agencyRecords = {
  MMDA: { id: 1, code: "MMDA", name: "Metropolitan Manila Development Authority" },
  DPWH: { id: 2, code: "DPWH", name: "Department of Public Works and Highways" },
  DOH: { id: 3, code: "DOH", name: "Department of Health" },
  DSWD: { id: 10, code: "DSWD", name: "Department of Social Welfare and Development" },
  "Department of Social Welfare and Development": { id: 10, code: "DSWD", name: "Department of Social Welfare and Development" },
};
const project = (id, agency, city, status, year, updated = false) => ({
  id, title: `Public project ${id}`, agency, primary_agency: agencyRecords[agency], collaborating_agencies: [], implementation_status: status,
  budget: 1000, year, lgu: city || null, lgus: city ? [city] : [], location_raw: city,
  updated_at: "2026-11-01T00:00:00Z", has_public_updates: updated,
  latest_update_date: updated ? "2026-11-01T00:00:00Z" : null,
});
const records = Array.from({ length: 501 }, (_, index) => project(index + 1, "MMDA", "Manila", "New", 2026));
records.push(project(502, "DPWH", "Pasig", "Ongoing", 2028));
records.push(project(503, "DOH", "Pasig", "Ongoing", 2028, true));
records.push(project(504, "DOH", "Manila", "Completed", 2029));
records.push(project(505, "DSWD", "Manila", "New", 2027));
records.push(project(506, "Department of Social Welfare and Development", "Pasig", "Ongoing", 2028));
records.push(project(507, "DPWH", "Manila", "Not Implemented", 2027));
records.push(project(508, "DPWH", "", "New", 2027));

try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.route("**/tile.openstreetmap.org/**", (route) => route.abort());
  await page.route("**/api/**", async (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    const url = new URL(route.request().url());
    let body = {};
    if (url.pathname.endsWith("/public/projects/")) {
      const q = (url.searchParams.get("q") || "").toLowerCase();
      const matched = q ? records.filter((item) => item.title.toLowerCase().includes(q)) : records;
      const offset = Number(url.searchParams.get("offset") || 0);
      const limit = Number(url.searchParams.get("limit") || 200);
      body = matched.slice(offset, offset + limit);
    } else if (url.pathname.endsWith("/public/cms/pages/projects-dashboard/")) {
      body = { slug: "projects-dashboard", sections: [] };
    }
    await route.fulfill({ status: 200, contentType: "application/json", headers, body: JSON.stringify(body) });
  });

  await page.goto(`http://127.0.0.1:${address.port}/projects`);
  await page.getByText("508", { exact: true }).first().waitFor();
  const filters = page.locator("select");
  assert.equal(await filters.nth(1).locator('option:has-text("Not Implemented")').count(), 0);
  assert.equal(await filters.nth(4).locator('option:has-text("Unspecified")').count(), 0);
  assert.equal(await filters.nth(3).locator('option:has-text("Department of Social Welfare and Development")').count(), 1);
  await filters.nth(0).selectOption("2028");
  await filters.nth(1).selectOption("Ongoing");
  await filters.nth(3).selectOption("id:3");
  await filters.nth(4).selectOption("Pasig");
  assert.deepEqual(await Promise.all([0, 1, 3, 4].map((index) => filters.nth(index).inputValue())), ["2028", "Ongoing", "id:3", "Pasig"]);
  await page.getByRole("button", { name: /Table/ }).click();
  assert.equal(await page.locator("tbody tr").count(), 1);
  await page.locator("tbody").getByText("Public project 503").waitFor();
  await filters.nth(2).selectOption("recent");
  await page.getByRole("button", { name: /Map/ }).click();
  await page.locator(".leaflet-interactive").first().waitFor();
  assert.equal(await page.getByText("No projects match the selected filters on the map.").count(), 0);
  await page.locator(".leaflet-interactive").last().click();
  await page.locator('.leaflet-popup-content a[href="/projects/503"]').waitFor();
  const viewportBefore = await page.locator(".leaflet-map-pane").getAttribute("style");
  await filters.nth(3).selectOption("id:2");
  assert.equal(await filters.nth(4).inputValue(), "Pasig");
  await page.getByText("No projects match the selected filters on the map.").waitFor();
  assert.equal(await page.locator(".leaflet-map-pane").getAttribute("style"), viewportBefore, "filter changes should preserve the map viewport");
  await page.getByRole("button", { name: "Clear agency" }).click();
  assert.equal(await filters.nth(4).inputValue(), "Pasig");
  await page.getByRole("button", { name: "Reset all filters" }).click();
  assert.deepEqual(await Promise.all([0, 1, 2, 3, 4].map((index) => filters.nth(index).inputValue())), ["all", "all", "all", "all", "all"]);
  await page.getByText("508", { exact: true }).first().waitFor();
  await page.setViewportSize({ width: 390, height: 780 });
  await page.getByRole("button", { name: "Toggle filters" }).click();
  await filters.nth(4).selectOption("Pasig");
  assert.equal(await filters.nth(4).inputValue(), "Pasig");
  await page.getByRole("button", { name: "Reset all filters" }).click();
  await filters.nth(3).selectOption("id:10");
  await page.getByText("2", { exact: true }).first().waitFor();
  await page.getByRole("button", { name: /Table/ }).click();
  assert.equal(await page.locator("tbody tr").count(), 2);
  await page.getByRole("button", { name: "Reset all filters" }).click();
  await page.getByPlaceholder("Search projects...").fill("Public project 503");
  await page.getByRole("button", { name: /Table/ }).click();
  await page.locator("tbody").getByText("Public project 503").waitFor();
  await page.waitForFunction(() => document.querySelectorAll("tbody tr").length === 1);
  assert.equal(await page.locator("tbody tr").count(), 1);
  assert.equal(await filters.nth(4).inputValue(), "all");
  console.log("Public dashboard filter and map browser check passed.");
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
