import assert from "node:assert/strict";
import { chromium } from "playwright-core";
import { preview } from "vite";

const server = await preview({ preview: { host: "127.0.0.1", port: 0 } });
const address = server.httpServer.address();
assert.ok(address && typeof address !== "string");
const origin = `http://127.0.0.1:${address.port}`;
const browser = await chromium.launch({
  executablePath: process.env.EXPORT_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  headless: true,
});

const cors = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, OPTIONS",
  "access-control-allow-headers": "authorization,content-type,x-portal-user-activity",
  "access-control-expose-headers": "content-disposition",
};

const projectOptions = {
  agencies: [{ value: "DENR", label: "DENR" }, { value: "DPWH", label: "DPWH" }],
  workflow_statuses: [{ value: "draft", label: "Draft" }, { value: "validated", label: "Validated" }],
  implementation_statuses: [{ value: "New", label: "New" }, { value: "Ongoing", label: "Ongoing" }],
  development_sectors: [{ value: "SCEED", label: "SCEED" }],
  convergence_programs: [{ value: "WRP", label: "WRP" }],
  funding_sources: [{ value: "Agency", label: "Agency" }],
  rdp_main_chapters: [{ value: "Chapter 16", label: "Chapter 16" }],
  archive_states: [
    { value: "active", label: "Active" },
    { value: "archived", label: "Archived" },
    { value: "all", label: "All" },
  ],
};

const userOptions = {
  agencies: [{ value: "RDC-NCR", label: "RDC-NCR" }, { value: "DENR", label: "DENR" }],
  roles: [
    { value: "admin", label: "Administrator" },
    { value: "validator", label: "Validator" },
    { value: "staff", label: "Contributor" },
    { value: "content_editor", label: "Content Editor" },
  ],
  account_statuses: [{ value: "active", label: "Active" }, { value: "inactive", label: "Inactive" }],
};

async function configure(page, role = "admin") {
  await page.addInitScript((currentRole) => {
    localStorage.setItem("user", JSON.stringify({ role: currentRole, username: "Export Tester", agency: "RDC-NCR" }));
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "export-test-token");
  }, role);
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    const url = new URL(request.url());
    const path = url.pathname;
    if (path.endsWith("/notifications/")) {
      return route.fulfill({ status: 200, headers: cors, contentType: "application/json", body: '{"results":[],"unread_count":0}' });
    }
    if (path.endsWith("/admin/exports/options/")) {
      const category = url.searchParams.get("category");
      return route.fulfill({
        status: 200, headers: cors, contentType: "application/json",
        body: JSON.stringify({ category, options: category === "users" ? userOptions : projectOptions }),
      });
    }
    if (path.endsWith("/admin/exports/count/")) {
      const category = url.searchParams.get("category");
      const noMatch = url.searchParams.get("search") === "no matching records";
      const projectCombination = category === "projects"
        && url.searchParams.get("agency") === "DENR"
        && url.searchParams.get("budget_min") === "50000000"
        && url.searchParams.get("start_year") === "2022";
      const validatorOnly = category === "users" && url.searchParams.get("role") === "validator";
      const count = noMatch ? 0 : projectCombination ? 2 : validatorOnly ? 3 : category === "users" ? 7 : 13;
      return route.fulfill({
        status: 200, headers: cors, contentType: "application/json",
        body: JSON.stringify({ category, count }),
      });
    }
    if (path.endsWith("/admin/exports/download/")) {
      await new Promise((resolve) => setTimeout(resolve, 250));
      const format = url.searchParams.get("file_format");
      const category = url.searchParams.get("category");
      return route.fulfill({
        status: 200,
        headers: {
          ...cors,
          "content-disposition": `attachment; filename="rdc-ncr-${category}-20261026-120000.${format}"`,
        },
        contentType: format === "pdf" ? "application/pdf" : "text/csv; charset=utf-8",
        body: format === "pdf" ? "%PDF-1.4 mock export" : "\ufeffID,Name\r\n1,Sample\r\n",
      });
    }
    return route.fulfill({ status: 200, headers: cors, contentType: "application/json", body: "{}" });
  });
}

try {
  const context = await browser.newContext({ viewport: { width: 1366, height: 850 }, acceptDownloads: true });
  const page = await context.newPage();
  await configure(page);
  await page.goto(`${origin}/admin/exports`);
  await page.getByRole("heading", { name: "Data Exports" }).waitFor();
  assert.ok(await page.getByRole("link", { name: "Data Exports" }).isVisible(), "Admin sidebar contains Data Exports");
  await page.getByText("13", { exact: true }).waitFor();
  assert.equal(await page.getByLabel("Archive State").inputValue(), "active", "Active projects is the default scope");

  await page.getByLabel("Agency").selectOption("DENR");
  await page.getByLabel("Minimum Budget").fill("50000000");
  await page.getByLabel("Start Year").fill("2022");
  await page.getByText("2", { exact: true }).waitFor();
  await page.getByText("Agency: DENR").waitFor();
  await page.getByText("Minimum Budget: 50000000").waitFor();
  await page.getByText("Start Year: 2022").waitFor();

  await page.getByText("PDF", { exact: true }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Generate PDF" }).click();
  await page.getByRole("button", { name: "Generating Export..." }).waitFor();
  const download = await downloadPromise;
  assert.equal(download.suggestedFilename(), "rdc-ncr-projects-20261026-120000.pdf");
  await page.getByText("Project export downloaded successfully.").waitFor();

  await page.getByRole("button", { name: "Users" }).click();
  await page.getByText("7", { exact: true }).waitFor();
  await page.getByLabel("Role").selectOption("validator");
  await page.getByText("3", { exact: true }).waitFor();
  await page.getByText("Role: Validator").waitFor();
  await page.getByRole("button", { name: "Clear Filters" }).click();
  assert.equal(await page.getByLabel("Role").inputValue(), "");
  await page.getByLabel("Search").fill("no matching records");
  await page.getByText("No records match the selected criteria.").waitFor();
  assert.ok(await page.getByRole("button", { name: "Generate CSV" }).isDisabled());
  await context.close();

  const mobile = await browser.newContext({ viewport: { width: 320, height: 700 }, isMobile: true, hasTouch: true });
  const mobilePage = await mobile.newPage();
  await configure(mobilePage);
  await mobilePage.goto(`${origin}/admin/exports`);
  await mobilePage.getByRole("heading", { name: "Data Exports" }).waitFor();
  assert.ok(await mobilePage.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1),
    "Data Exports fits a 320px viewport");
  await mobile.close();

  const denied = await browser.newContext({ viewport: { width: 900, height: 700 } });
  const validatorPage = await denied.newPage();
  await configure(validatorPage, "validator");
  await validatorPage.goto(`${origin}/admin/exports`);
  await validatorPage.waitForURL("**/validator/dashboard");
  assert.equal(await validatorPage.getByRole("heading", { name: "Data Exports" }).count(), 0,
    "Validator cannot open the Admin export page");
  await denied.close();

  console.log("PASS Administrator data export browser checks");
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
