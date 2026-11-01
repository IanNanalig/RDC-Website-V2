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
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    const auditRows = [{
        id: 1, username: "contributor", display_name: "Contributor", role: "staff",
        event: "project_update", category: "projects", category_label: "Projects",
        action_label: "Updated a project", description: "Contributor updated a project — zulu@example.test.",
        result: "completed", result_label: "Completed", target_label: "zulu@example.test",
        created_at: "2026-10-10T10:00:00Z",
      },
      {
        id: 2, username: "second", display_name: "Second", role: "staff", event: "login",
        category: "accounts_access", category_label: "Accounts & Access", action_label: "Signed in",
        description: "Second signed in — alpha@example.test.", result: "completed", result_label: "Completed",
        target_label: "alpha@example.test", created_at: "2026-10-09T10:00:00Z",
      },
    ];
    const sortedAuditRows = [...auditRows];
    if (url.searchParams.get("sort_by") === "target" && url.searchParams.get("sort_direction") === "asc") {
      sortedAuditRows.reverse();
    }
    const detail = {
      ...auditRows[0], ip_address: "127.0.0.1", location_hint: "Manila",
      technical_details: { method: "PATCH", route: "admin-projects-detail", status_code: 200,
        changes: [{ field: "projectActivity", before: "Old title", after: "New title" }] },
    };
    const body = path === "/api/admin/activity/" ? {
      results: sortedAuditRows,
      count: sortedAuditRows.length,
      category_options: [
        { value: "accounts_access", label: "Accounts & Access" },
        { value: "projects", label: "Projects" },
      ],
      result_options: [{ value: "completed", label: "Completed" }],
    } : path === "/api/admin/activity/1/" ? detail : path === "/api/admin/users/" ? [] : {};
    await route.fulfill({ status: 200, contentType: "application/json", headers, body: JSON.stringify(body) });
  });

  await page.goto(origin + "/admin/users?tab=system-audit-log", { waitUntil: "networkidle" });
  await page.waitForURL("**/admin/audit-log");
  const row = page.getByRole("row").filter({ hasText: "Contributor" });
  const target = row.locator("td").nth(4);
  assert.equal((await target.innerText()).trim(), "zulu@example.test", "Target shows only the human-readable label");
  assert.match(await row.innerText(), /Updated a project/);
  assert.doesNotMatch(await row.innerText(), /project_update|api_action|Before:|After:/);
  assert.equal(await target.isVisible(), true, "Audit target is accessible in the mobile table");
  await page.getByLabel("Sort by field").selectOption("target");
  await page.getByText("alpha@example.test").waitFor();
  assert.equal((await page.getByRole("row").nth(1).locator("td").nth(4).innerText()).trim(), "alpha@example.test",
    "Mobile audit sorting requests and displays the full filtered dataset in ascending target order");
  const detailButton = page.getByRole("row").filter({ hasText: "Contributor" }).getByRole("button", { name: "View details for Updated a project" });
  await detailButton.click();
  const dialog = page.getByRole("dialog", { name: "Audit record details" });
  await dialog.getByText("Contributor updated a project — zulu@example.test.").waitFor();
  assert.match(await dialog.innerText(), /admin-projects-detail/);
  assert.match(await dialog.innerText(), /Old title/);
  await page.keyboard.press("Escape");
  assert.equal(await dialog.count(), 0, "Escape closes the audit detail dialog");
  assert.equal(await detailButton.evaluate((element) => element === document.activeElement), true, "Focus returns to the details button");
  console.log("PASS audit log uses readable rows and protected technical details");
  await context.close();
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
