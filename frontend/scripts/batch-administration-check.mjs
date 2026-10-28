import assert from "node:assert/strict";
import { chromium } from "playwright-core";
import { preview } from "vite";

const server = await preview({ preview: { host: "127.0.0.1", port: 0 } });
const address = server.httpServer.address();
assert.ok(address && typeof address !== "string");
const origin = `http://127.0.0.1:${address.port}`;
const browser = await chromium.launch({
  executablePath: process.env.BATCH_ADMIN_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  headless: true,
});
const headers = { "access-control-allow-origin": "*", "access-control-allow-headers": "authorization,content-type,x-portal-user-activity" };

async function configure(page) {
  await page.addInitScript(() => {
    localStorage.setItem("user", JSON.stringify({ id: 1, role: "admin", username: "Administrator", agency: "RDC-NCR" }));
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "test-token");
  });
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    const path = new URL(request.url()).pathname;
    const json = (value) => route.fulfill({ status: 200, headers, contentType: "application/json", body: JSON.stringify(value) });
    if (path.endsWith("/notifications/")) return json({ results: [], unread_count: 0 });
    if (path.endsWith("/admin/projects/") && new URL(request.url()).searchParams.get("scope") === "update_forms") return json(
      Array.from({ length: 12 }, (_, index) => ({
        id: 41 + index,
        title: index === 0 ? "Old DENR Form" : `Older Project ${String(index + 1).padStart(2, "0")}`,
        agency: "DENR",
        submitted_by_name: "Contributor",
        form_version: 1,
        current_form_version: 3,
      })),
    );
    if (path.endsWith("/admin/projects/form-migration-preview/")) return json({ preview_token: "migration-token", rows: [{ id: 41, title: "Old DENR Form", agency: "DENR", source_version: 1, target_version: 3, attention_fields: ["custom_new_field"], eligible: true, reason: "" }] });
    if (path.endsWith("/admin/projects/migrate-forms/")) {
      await new Promise((resolve) => setTimeout(resolve, 150));
      return json({ migrated: 0, prepared: 1, blocked: 0, skipped: 0 });
    }
    if (path.endsWith("/progress-update-window/")) {
      const body = request.method() === "POST" ? JSON.parse(request.postData() || "{}") : {};
      return json({ enabled: body.action !== "close", manual_open: body.action === "open", is_open: body.action === "open", status_code: body.action === "open" ? "open_by_admin" : "closed_by_admin", message: body.action === "open" ? "Project updating is open." : "Project updating is closed.", start_at: "2026-11-01T08:00:00+08:00", end_at: "2026-11-30T17:00:00+08:00", eligible_project_count: 7 });
    }
    if (path.endsWith("/admin/projects/")) return json([
      { id: 41, title: "Archive Candidate", agency: "DENR", status: "completed", workflow_status: "validated", validated: true, updated_at: "2026-10-26T00:00:00Z" },
      { id: 42, title: "Pending Candidate", agency: "DENR", status: "proposed", workflow_status: "pending_validation", updated_at: "2026-10-26T00:00:00Z" },
    ]);
    if (path.endsWith("/project-revisions/")) return json([
      { id: 141, project: 41, project_title: "Archive Candidate", project_agency: "DENR", revision_number: 1, revision_type: "progress", state: "endorsed", submitted_by_name: "DENR Contributor", updated_at: "2026-10-27T00:00:00Z" },
    ]);
    if (path.endsWith("/admin/projects/batch-archive-preview/")) return json({ preview_token: "archive-token", rows: [{ id: 41, title: "Archive Candidate", agency: "DENR", eligible: true, reason: "" }, { id: 42, title: "Pending Candidate", agency: "DENR", eligible: false, reason: "Projects pending validation cannot be archived." }] });
    if (path.endsWith("/admin/projects/batch-archive/")) return json({ archived: 1, skipped: 1, failed: 0 });
    if (path.endsWith("/admin/users/batch-invitations/options/")) return json({ roles: [{ value: "contributor", label: "Contributor" }, { value: "validator", label: "Validator" }], agencies: [{ code: "DENR", name: "Department of Environment and Natural Resources" }] });
    if (path.endsWith("/admin/users/batch-invitations/preview/")) return json({ preview_token: "invite-token", rows: [{ row: 1, email: "new@example.com", role: "contributor", agency: "DENR", status: "valid", reason: "" }] });
    if (path.endsWith("/admin/users/batch-invitations/send/")) return json({ sent: 1, skipped: 0, failed: 0 });
    if (path.endsWith("/admin/users/")) return json([]);
    if (path.endsWith("/encoding-window/")) return json({ enabled: false, is_open: false, status_code: "closed_by_admin", message: "Closed", start_at: "", end_at: "" });
    if (path.endsWith("/admin/activity/")) return json({ results: [], count: 0 });
    return json({});
  });
}

try {
  const context = await browser.newContext({ viewport: { width: 1366, height: 850 } });
  const page = await context.newPage();
  await configure(page);

  await page.goto(`${origin}/admin/projects/update-forms`);
  await page.getByRole("heading", { name: "Update Older Project Forms" }).waitFor();
  assert.equal(await page.locator("#portal-navigation .portal-nav-item-active").count(), 1, "Only one navigation item is active");
  await page.locator("#portal-navigation .portal-nav-item-active").getByText("Update Older Forms", { exact: true }).waitFor();
  assert.equal(await page.locator("table.portal-table tbody tr").count(), 10, "Migration list shows ten projects per page");
  await page.getByText(/Showing 1.*10 of 12 matching projects/).waitFor();
  await page.getByRole("button", { name: "Next" }).click();
  assert.equal(await page.locator("table.portal-table tbody tr").count(), 2, "Migration list paginates remaining projects");
  await page.getByRole("button", { name: "Previous" }).click();
  await page.getByLabel("Select Old DENR Form").check();
  await page.getByRole("button", { name: "Preview Migration" }).click();
  await page.getByText("Safe to prepare").waitFor();
  await page.getByRole("button", { name: "Confirm Migration" }).click();
  await page.getByRole("dialog", { name: "Confirm project form migration" }).waitFor();
  await page.getByRole("button", { name: "Migrate 1 Project" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Migrating..." }).waitFor();
  await page.getByText(/validated project update draft/).waitFor();

  await page.goto(`${origin}/admin/project-update-period`);
  await page.getByText("Eligible projects").waitFor();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Open Update Period" }).click();
  await page.getByText("The update period is open.").waitFor();

  await page.goto(`${origin}/admin/projects`);
  await page.getByRole("heading", { name: "Projects Governance" }).waitFor();
  assert.equal(await page.locator("tbody input[type=checkbox]").count(), 3, "Base and progress-revision project rows all have archive-selection checkboxes");
  await page.getByRole("button", { name: /Select all 2 matching projects/ }).click();
  await page.getByText("2 selected", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Archive Selected" }).click();
  await page.getByText("Will skip").waitFor();
  await page.getByRole("button", { name: "Confirm Batch Archive" }).click();
  await page.getByText(/1 project\(s\) archived/).waitFor();

  await page.goto(`${origin}/admin/users?tab=create-account`);
  await page.getByRole("heading", { name: "Batch Registration" }).waitFor();
  await page.getByPlaceholder(/person@example.com/).fill("new@example.com, contributor, DENR");
  await page.getByRole("button", { name: "Preview Batch" }).click();
  await page.getByText("Ready to send").waitFor();
  await page.getByRole("button", { name: "Send 1 Valid Invitation" }).click();
  await page.getByText(/1 invitation\(s\) sent/).waitFor();

  assert.ok(await page.getByRole("link", { name: "Project Update Period" }).isVisible());
  assert.ok(await page.getByRole("link", { name: "Update Older Forms" }).isVisible());
  await context.close();
  console.log("PASS batch administration browser checks");
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
