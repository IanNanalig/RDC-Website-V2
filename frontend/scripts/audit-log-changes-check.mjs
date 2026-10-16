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
        event: "project_update", target_label: "contributor@example.com", project_title: "Sample Project", ip_address: "", location_hint: "",
        created_at: "2026-10-10T10:00:00Z",
        details: {
          email: "contributor@example.com", session_version: 7, replaced_previous_session: true,
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
  const row = page.getByRole("row").filter({ hasText: "Contributor" });
  const target = row.locator("td").nth(2);
  assert.equal((await target.innerText()).trim(), "contributor@example.com", "Target shows only the human-readable label");
  assert.equal(await row.getByText("Changes and details").count(), 0);
  assert.doesNotMatch(await row.innerText(), /session_version|replaced_previous_session|Before:|After:/);
  assert.equal(await target.isVisible(), true, "Audit target is accessible in the mobile table");
  console.log("PASS audit target hides raw details on mobile");
  await context.close();
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
