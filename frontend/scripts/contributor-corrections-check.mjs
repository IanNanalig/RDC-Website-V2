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
const year = Number(new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Manila", year: "numeric" }).format(new Date()));
const responseHeaders = { "access-control-allow-origin": "*", "access-control-allow-methods": "GET, OPTIONS", "access-control-allow-headers": "authorization, content-type" };
const schema = {
  format_version: 1, title: "Contributor test form", sections: [
    { key: "project", title: "Project Information", fields: [
      { key: "agencyName", label: "Agency Name", type: "text", required: true, visible: true },
      { key: "startYear", label: "Start Year", type: "year", required: true, visible: true },
      { key: "endYear", label: "End Year", type: "year", required: true, visible: true },
      { key: "actualFundingByYear", label: "Actual/Approved Funding (PHP)", type: "currency_by_year", visible: true },
    ] },
  ],
};

async function openForm({ fallback = false, existing = true, agency = "DENR", mobile = false, includePrior = false } = {}) {
  const context = await browser.newContext({ viewport: mobile ? { width: 390, height: 760 } : { width: 1100, height: 800 }, isMobile: mobile, hasTouch: mobile });
  const page = await context.newPage();
  await page.addInitScript((accountAgency) => {
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "contributor-corrections-test");
    localStorage.setItem("user", JSON.stringify({ id: 1, username: "corrections-tester", role: "employee", agency: accountAgency }));
  }, agency);
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: responseHeaders });
    if (url.includes("contributor-forms/")) return route.fulfill({
      status: 200, contentType: "application/json", headers: responseHeaders,
      body: JSON.stringify({ key: "simplified-rdip", version: 1, schema: fallback ? { ...schema, sections: [] } : schema }),
    });
    let body = {};
    if (url.includes("encoding-window/")) body = { enabled: true, is_open: true, can_encode: true, status_code: "open", message: "Open" };
    if (url.includes("employee/projects/1/")) body = {
      id: 1, agency: "DPWH", status: "planning", workflow_status: "draft", profile_data: {
        simplified_form: {
          agencyName: "DPWH", startYear: includePrior ? "2022" : String(year - 2), endYear: String(year + 1),
          actualFundingByYear: {
            ...(includePrior ? { "2022_prior": "50" } : {}),
            [year - 2]: "100", [year - 1]: "200", [year]: "300", [year + 1]: "400",
          },
        },
      },
    };
    return route.fulfill({ status: 200, contentType: "application/json", headers: responseHeaders, body: JSON.stringify(body) });
  });
  await page.goto(origin + (existing ? "/employee/projects/1/edit/simplified" : "/employee/projects/new/simplified"), { waitUntil: "networkidle" });
  await page.getByLabel("Agency Name *").waitFor();
  return { context, page };
}

try {
  for (const fallback of [false, true]) {
    const { context, page } = await openForm({ fallback, mobile: fallback });
    const agency = page.getByLabel("Agency Name *");
    assert.equal(await agency.inputValue(), "DPWH", "Existing form keeps its saved agency, not the current account agency");
    assert.equal(await agency.isDisabled(), true);
    const actualFunding = page.getByRole("heading", { name: "Actual/Approved Funding (PHP)" }).locator("..");
    for (const targetYear of [year - 2, year - 1, year, year + 1]) {
      const amount = actualFunding.getByLabel(String(targetYear));
      assert.equal(await amount.count(), 1, `Funding ${targetYear} remains visible`);
      assert.equal(await amount.isDisabled(), targetYear > year, `Funding ${targetYear} has correct editability`);
    }
    await page.getByRole("button", { name: "Start Year *" }).click();
    const picker = page.getByRole("dialog", { name: "Start Year year picker" });
    await picker.getByRole("button", { name: String(year + 1), exact: true }).click();
    await page.getByText("This period change would remove existing Actual/Approved Funding.", { exact: false }).waitFor();
    assert.match(await page.getByRole("button", { name: "Start Year *" }).innerText(), new RegExp(String(year - 2)), "Rejected period change does not delete historical funding");
    await context.close();
    console.log(`PASS ${fallback ? "fallback mobile" : "CMS-configured desktop"} agency, funding, and period protection`);
  }

  const prior = await openForm({ includePrior: true });
  assert.equal(await prior.page.getByLabel("2022 & Prior").isDisabled(), false, "2022 & Prior bucket is editable");
  await prior.context.close();
  console.log("PASS 2022 & Prior bucket is editable");

  const noAgency = await openForm({ existing: false, agency: "" });
  assert.equal(await noAgency.page.getByLabel("Agency Name *").inputValue(), "");
  assert.equal(await noAgency.page.getByLabel("Agency Name *").isDisabled(), true);
  await noAgency.page.getByRole("alert").getByText("Your account has no agency", { exact: false }).waitFor();
  const alertPromise = noAgency.page.waitForEvent("dialog");
  const clickPromise = noAgency.page.getByRole("button", { name: "Save Draft" }).click();
  const alert = await alertPromise;
  assert.match(alert.message(), /account has no agency/i);
  await alert.dismiss();
  await clickPromise;
  await noAgency.context.close();
  console.log("PASS new project requires account agency");

  const context = await browser.newContext({ viewport: { width: 1100, height: 800 } });
  const page = await context.newPage();
  await page.addInitScript(() => {
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "dashboard-corrections-test");
    localStorage.setItem("user", JSON.stringify({ id: 1, username: "corrections-tester", role: "employee", agency: "DENR" }));
  });
  let dashboardCalls = 0;
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: responseHeaders });
    if (url.includes("dashboard/")) {
      dashboardCalls += 1;
      if (dashboardCalls === 1) return route.fulfill({ status: 500, contentType: "application/json", headers: responseHeaders, body: '{"detail":"Unavailable"}' });
      return route.fulfill({ status: 200, contentType: "application/json", headers: responseHeaders, body: '{"my_projects":3,"draft_projects":1,"submitted_projects":1,"approved_projects":1}' });
    }
    const body = url.includes("encoding-window/")
      ? { enabled: true, is_open: true, can_encode: true, status_code: "open", message: "Open" }
      : url.includes("agency/activity/") ? { results: [], count: 0, has_previous: false, has_next: false } : {};
    return route.fulfill({ status: 200, contentType: "application/json", headers: responseHeaders, body: JSON.stringify(body) });
  });
  await page.goto(origin + "/employee/dashboard", { waitUntil: "networkidle" });
  await page.getByRole("alert").getByText("Dashboard counts could not be loaded", { exact: false }).waitFor();
  assert.equal(await page.locator(".portal-stat-value").first().innerText(), "—", "Failed request must not look like zero projects");
  await page.getByRole("button", { name: "Retry" }).click();
  await page.getByText("3", { exact: true }).first().waitFor();
  assert.equal(await page.locator(".portal-stat-value").first().innerText(), "3");
  assert.equal(await page.getByRole("alert").count(), 0);
  await context.close();
  console.log("PASS dashboard failure and retry");
} finally {
  await browser.close();
  await new Promise((resolve, reject) => server.httpServer.close((error) => error ? reject(error) : resolve()));
}
