import assert from "node:assert/strict";
import { chromium } from "playwright-core";
import { preview } from "vite";

const server = await preview({ preview: { host: "127.0.0.1", port: 0 } });
const address = server.httpServer.address();
assert.ok(address && typeof address !== "string");
const origin = `http://127.0.0.1:${address.port}`;
const browser = await chromium.launch({
  executablePath: process.env.CMS_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  headless: true,
});
const headers = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, OPTIONS",
  "access-control-allow-headers": "authorization, content-type",
};
const project = (id) => ({
  id, title: `History Project ${id}`, agency: "DENR", implementation_status: "Ongoing",
  budget: 1000000, year: 2026, lgu: "Manila", lgus: ["Manila"],
  updated_at: "2026-10-01T10:00:00Z", has_public_updates: false,
});
const projects = Array.from({ length: 14 }, (_, index) => project(index + 1));
const initial = {
  revision_number: 1, revision_type: "initial_submission", endorsed_at: "2026-09-01T10:00:00Z",
  status: "New", budget: "1000000", location: "Manila", changed_fields: [], change_badges: [],
};
const progress = {
  revision_number: 2, revision_type: "progress_update", endorsed_at: "2026-10-01T10:00:00Z",
  status: "Ongoing", budget: "1200000", location: "Manila",
  headline: "Approved public progress", public_note: "Approved public note",
  changed_fields: [{ label: "Project Status", category: "status", before: "New", after: "Ongoing" }],
  change_badges: ["Status updated"],
};
const historyById = { 1: [progress, initial], 2: [initial], 3: [], 4: [initial] };

async function respond(route, body, status = 200) {
  await route.fulfill({ status, contentType: "application/json", headers, body: JSON.stringify(body) });
}

try {
  const context = await browser.newContext({ viewport: { width: 390, height: 780 } });
  const page = await context.newPage();
  await page.addInitScript(() => {
    window.__longRefreshIntervals = [];
    const nativeSetInterval = window.setInterval.bind(window);
    window.setInterval = (callback, delay, ...args) => {
      if (Number(delay) >= 60_000) window.__longRefreshIntervals.push(Number(delay));
      return nativeSetInterval(callback, delay, ...args);
    };
  });
  let releaseFirstDetail;
  const firstDetailHold = new Promise((resolve) => { releaseFirstDetail = resolve; });
  let failedDetailCalls = 0;
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    if (path.endsWith("/public/projects/stats/")) return respond(route, {
      total_projects: 14, total_budget: 14000000, by_status: { Ongoing: 14 },
      by_agency: { DENR: 14 }, by_lgu: { Manila: 14 }, by_year: { 2026: 14 },
    });
    if (path.endsWith("/public/projects/")) return respond(route, projects);
    const match = path.match(/\/public\/projects\/(\d+)\/$/);
    if (match) {
      const id = Number(match[1]);
      if (id === 1) await firstDetailHold;
      if (id === 4 && failedDetailCalls++ === 0) return respond(route, { detail: "Unavailable" }, 503);
      return respond(route, {
        ...project(id), public_summary_text: `Public summary ${id}`,
        public_update_timeline: historyById[id],
      });
    }
    if (path.endsWith("/public/cms/pages/projects-dashboard/")) return respond(route, { slug: "projects-dashboard", sections: [] });
    return respond(route, {});
  });

  await page.goto(origin + "/projects", { waitUntil: "networkidle" });
  assert.deepEqual(await page.evaluate(() => window.__longRefreshIntervals), [], "Public projects should not schedule recurring data refreshes.");
  await page.getByRole("button", { name: /Table/ }).click();
  assert.equal(await page.locator("tbody tr").count(), 10, "Public table shows at most ten projects per page");
  await page.getByText("Showing 1–10 of 14 projects").waitFor();
  const open = async (id) => {
    await page.locator("tbody").getByRole("button", { name: `History Project ${id}`, exact: true }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("tab", { name: "Overview" }).waitFor();
    assert.equal(await dialog.getByRole("tab", { name: "Overview" }).getAttribute("aria-selected"), "true");
    return dialog;
  };
  const close = async (dialog) => dialog.getByRole("button", { name: "Close" }).click();

  let dialog = await open(1);
  await dialog.getByRole("tab", { name: "History" }).click();
  await dialog.getByRole("status").getByText("Loading approved project history...").waitFor();
  assert.equal(await dialog.getByText("No approved history has been recorded", { exact: false }).count(), 0);
  releaseFirstDetail();
  const historyPanel = dialog.getByRole("tabpanel", { name: "History" });
  await historyPanel.getByText("Version 2").waitFor();
  assert.deepEqual(await historyPanel.locator("span.font-semibold.text-slate-900").allTextContents(), ["Version 2", "Version 1"]);
  await historyPanel.getByText("Approved public note").waitFor();
  assert.equal(await historyPanel.getByText("New", { exact: true }).count(), 1);
  assert.equal(await historyPanel.getByText("Private pending review note").count(), 0);
  await dialog.getByRole("tab", { name: "History" }).press("ArrowLeft");
  assert.equal(await dialog.getByRole("tab", { name: "Overview" }).getAttribute("aria-selected"), "true");
  await dialog.getByRole("tab", { name: "Overview" }).press("ArrowLeft");
  assert.equal(await dialog.getByRole("tab", { name: "History" }).getAttribute("aria-selected"), "true");
  await dialog.getByRole("tab", { name: "History" }).press("Home");
  assert.equal(await dialog.getByRole("tab", { name: "Overview" }).getAttribute("aria-selected"), "true");
  assert.equal(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth + 1), true, "Mobile dialog does not overflow horizontally");
  await close(dialog);
  console.log("PASS multiple approved milestones, loading, keyboard tabs, and mobile width");

  await page.goto(origin + "/", { waitUntil: "networkidle" });
  assert.deepEqual(await page.evaluate(() => window.__longRefreshIntervals), [], "Public home should not schedule recurring data refreshes.");
  console.log("PASS public home and project dashboard do not schedule periodic data refreshes");

  await page.goto(origin + "/projects", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /Table/ }).click();

  dialog = await open(2);
  await dialog.getByRole("tab", { name: "History" }).click();
  await dialog.getByText("Version 1").waitFor();
  assert.equal(await dialog.getByText("Initial Endorsement", { exact: true }).count(), 1);
  assert.equal(await dialog.getByText("Progress Update", { exact: true }).count(), 0);
  await close(dialog);
  console.log("PASS initial-endorsement-only history");

  dialog = await open(3);
  await dialog.getByRole("tab", { name: "History" }).click();
  await dialog.getByText("No approved history has been recorded for this project yet.").waitFor();
  await dialog.getByRole("tab", { name: "History" }).press("Escape");
  assert.equal(await page.getByRole("dialog").count(), 0, "Escape closes project details");
  console.log("PASS older project honest empty state");

  dialog = await open(4);
  await dialog.getByRole("tab", { name: "History" }).click();
  await dialog.getByRole("alert").getByText("Project history could not be loaded.", { exact: false }).waitFor();
  assert.equal(await dialog.getByText("No approved history has been recorded", { exact: false }).count(), 0);
  await dialog.getByRole("button", { name: "Retry" }).click();
  await dialog.getByText("Version 1").waitFor();
  assert.equal(failedDetailCalls, 2);
  await close(dialog);
  console.log("PASS detail failure and retry");

  await page.getByRole("button", { name: "Next page" }).click();
  await page.getByText("Page 2 of 2").waitFor();
  assert.equal(await page.locator("tbody tr").count(), 4, "The final public table page shows the remaining projects");
  await page.getByRole("button", { name: "Previous page" }).click();
  await page.getByText("Page 1 of 2").waitFor();
  console.log("PASS public project table pagination");

  await context.close();
} finally {
  await browser.close();
  await new Promise((resolve, reject) => server.httpServer.close((error) => error ? reject(error) : resolve()));
}
