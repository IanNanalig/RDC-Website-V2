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

try {
  const context = await browser.newContext({ viewport: { width: 390, height: 780 } });
  const page = await context.newPage();
  await page.addInitScript(() => {
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "audit-check-token");
    localStorage.setItem("user", JSON.stringify({ id: 1, username: "admin", role: "admin", agency: "RDC-NCR" }));
  });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    const body = path === "/api/admin/activity/" ? {
      results: [{
        id: 1, username: "contributor", full_name: "Contributor", role: "staff",
        event: "project_update", project_title: "Sample Project", ip_address: "", location_hint: "",
        created_at: "2026-10-10T10:00:00Z",
        details: {
          status: "planning", edited_fields_count: 3,
          changed_fields: ["projectActivity", "actualFundingByYear.2022_prior", "sdgSelections"],
          changes: [
            { field: "projectActivity", before: "Old title", after: "New title" },
            { field: "actualFundingByYear.2022_prior", before: "100", after: "200" },
            { field: "sdgSelections", before: "No poverty", after: "Climate action" },
          ],
        },
      }],
      count: 1,
    } : path === "/api/admin/users/" || path === "/api/password-reset-requests/" ? [] : {};
    await route.fulfill({ status: 200, contentType: "application/json", headers, body: JSON.stringify(body) });
  });

  await page.goto(origin + "/admin/users?tab=system-audit-log", { waitUntil: "networkidle" });
  await page.waitForURL("**/admin/audit-log");
  const row = page.getByRole("row").filter({ hasText: "Sample Project" });
  await row.getByText("Changes and details").click();
  await row.getByText("Changed Fields:").waitFor();
  assert.match(await row.innerText(), /Project Activity/);
  assert.match(await row.innerText(), /Actual\/Approved Funding \(PHP\) · 2022 & Prior/);
  assert.match(await row.innerText(), /Sustainable Development Goals/);
  assert.equal(await row.getByText("[object Object]").count(), 0);
  await row.getByText("Changes (3)").click();
  assert.match(await row.innerText(), /Before: Old title/);
  assert.match(await row.innerText(), /After: New title/);
  assert.match(await row.innerText(), /Before: 100/);
  assert.match(await row.innerText(), /After: 200/);
  assert.equal(await row.locator("td").nth(2).isVisible(), true, "Audit details are accessible in the mobile table");
  console.log("PASS audit changed fields and before/after changes on mobile");
  await context.close();
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
