import assert from "node:assert/strict";
import { chromium } from "playwright-core";
import { preview } from "vite";

const server = await preview({ preview: { host: "127.0.0.1", port: 0 } });
const address = server.httpServer.address();
assert.ok(address && typeof address !== "string");
const origin = `http://127.0.0.1:${address.port}`;
const browser = await chromium.launch({
  executablePath: process.env.CONCERN_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  headless: true,
});

const cors = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET,POST,OPTIONS",
  "access-control-allow-headers": "authorization,content-type,x-portal-user-activity",
  "access-control-expose-headers": "content-disposition",
};

const project = {
  id: 41,
  title: "NCR River Rehabilitation",
  agency: "DENR",
  implementation_status: "Ongoing",
  budget: 50000000,
  year: 2026,
  lgu: "Manila",
  description: "A public project description.",
  updated_at: "2026-10-28T02:00:00Z",
};
const options = {
  categories: [
    { code: "delay_discrepancy", label: "Suspected project delay or discrepancy" },
    { code: "other", label: "Other project-related concern" },
  ],
  upload_policy: {
    allowed_extensions: ["pdf", "docx", "xlsx", "csv", "png", "jpg", "jpeg"],
    max_files: 5,
    max_file_bytes: 5242880,
    max_total_bytes: 15728640,
    malware_scanned: false,
  },
  turnstile_required: false,
};

const json = (route, body, status = 200) => route.fulfill({
  status,
  headers: cors,
  contentType: "application/json",
  body: JSON.stringify(body),
});

async function publicRoutes(page, responseStatus = 201) {
  let submissions = 0;
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    const url = new URL(request.url());
    if (url.pathname.endsWith("/public/project-concerns/options/")) return json(route, options);
    if (url.pathname.endsWith("/public/project-concerns/") && request.method() === "POST") {
      submissions += 1;
      await new Promise((resolve) => setTimeout(resolve, 150));
      return json(route, {
        accepted: true,
        reference: "PCR-20261028-TEST123456",
        notification_status: responseStatus === 201 ? "sent" : "failed",
        acknowledgement_status: "not_applicable",
        message: responseStatus === 201
          ? "Your report was accepted and sent to the receiving office."
          : "Your report was accepted. Email notification delivery is pending retry.",
      }, responseStatus);
    }
    if (url.pathname.endsWith("/public/projects/41/")) return json(route, project);
    if (url.pathname.endsWith("/public/projects/") && url.searchParams.get("q")) {
      return json(route, [{ ...project, id: 42, title: "NCR Coastal Protection" }]);
    }
    if (url.pathname.includes("/public/cms/")) return json(route, {});
    return json(route, {});
  });
  return () => submissions;
}

async function adminRoutes(page) {
  await page.addInitScript(() => {
    localStorage.setItem("user", JSON.stringify({ role: "admin", username: "Concern Admin", agency: "RDC-NCR" }));
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "concern-admin-token");
  });
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    const path = new URL(request.url()).pathname;
    if (path.endsWith("/notifications/")) return json(route, { results: [], unread_count: 0 });
    if (path.endsWith("/admin/project-concerns/")) return json(route, {
      count: 1, next: null, previous: null, results: [{
        reference: "PCR-20261028-TEST123456", project_id: 41, project_title: project.title,
        project_agency: "DENR", reporting_mode: "email", category_code: "delay_discrepancy",
        category_label: "Suspected project delay or discrepancy", receiver_delivery_status: "failed",
        acknowledgement_delivery_status: "sent", receiver_delivery_attempts: 1,
        acknowledgement_delivery_attempts: 1, evidence_count: 1, created_at: "2026-10-28T02:00:00Z",
      }],
    });
    if (path.endsWith("/admin/project-concerns/PCR-20261028-TEST123456/retry/")) return json(route, {
      reference: "PCR-20261028-TEST123456", project_id: 41, project_title: project.title,
      project_agency: "DENR", reporting_mode: "email", reporter_email: "reporter@example.test",
      category_code: "delay_discrepancy", category_label: "Suspected project delay or discrepancy",
      description: "Observed delay in the published project schedule.", receiver_delivery_status: "sent",
      acknowledgement_delivery_status: "sent", receiver_delivery_attempts: 2,
      acknowledgement_delivery_attempts: 1, evidence_count: 1, evidence: [{ id: 8, filename: "proof.pdf", extension: "pdf", content_type: "application/pdf", size_bytes: 1200, checksum_sha256: "a".repeat(64) }],
      created_at: "2026-10-28T02:00:00Z",
    });
    if (path.endsWith("/admin/project-concerns/PCR-20261028-TEST123456/")) return json(route, {
      reference: "PCR-20261028-TEST123456", project_id: 41, project_title: project.title,
      project_agency: "DENR", reporting_mode: "email", reporter_email: "reporter@example.test",
      category_code: "delay_discrepancy", category_label: "Suspected project delay or discrepancy",
      description: "Observed delay in the published project schedule.", receiver_delivery_status: "failed",
      acknowledgement_delivery_status: "sent", receiver_delivery_attempts: 1,
      acknowledgement_delivery_attempts: 1, receiver_last_error: "RuntimeError: email delivery was unsuccessful",
      evidence_count: 1, evidence: [{ id: 8, filename: "proof.pdf", extension: "pdf", content_type: "application/pdf", size_bytes: 1200, checksum_sha256: "a".repeat(64) }],
      created_at: "2026-10-28T02:00:00Z",
    });
    if (path.includes("/evidence/8/download/")) return route.fulfill({
      status: 200,
      headers: { ...cors, "content-disposition": 'attachment; filename="PCR-Evidence-8.pdf"' },
      contentType: "application/pdf",
      body: "%PDF-1.4 evidence",
    });
    return json(route, {});
  });
}

try {
  const context = await browser.newContext({ viewport: { width: 390, height: 780 }, isMobile: true, hasTouch: true });
  const page = await context.newPage();
  const submissionCount = await publicRoutes(page);
  await page.goto(`${origin}/report-project?project=41`);
  await page.getByRole("heading", { name: "Report a Project Concern" }).waitFor();
  await page.getByRole("button", { name: "Open menu" }).click();
  assert.ok(await page.getByRole("link", { name: "Login" }).isVisible(), "Login remains visible in the expanded mobile navigation");
  await page.getByRole("button", { name: "Close menu" }).click();
  assert.equal(await page.getByText("Project ID #41").count(), 0, "The internal numeric project ID is not exposed in the public form");
  await page.getByText(project.title).waitFor();
  assert.ok(await page.getByRole("button", { name: "Change Project" }).isVisible());
  await page.getByLabel("Description").fill("Observed delay in the published project schedule.");
  await page.locator('input[type="file"]').setInputFiles({ name: "proof.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 mock") });
  await page.getByRole("button", { name: "Review Report" }).click();
  await page.getByRole("dialog", { name: "Review before submitting" }).waitFor();
  assert.equal(await page.getByText("#41", { exact: false }).count(), 0, "The review dialog does not expose the numeric project ID");
  await page.getByRole("button", { name: "Submit Report" }).dblclick();
  await page.getByText("PCR-20261028-TEST123456").waitFor();
  assert.equal(submissionCount(), 1, "Busy state prevents duplicate report submissions");
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), "Public reporting form fits a mobile viewport");
  await context.close();

  const pendingContext = await browser.newContext({ viewport: { width: 1100, height: 800 } });
  const pendingPage = await pendingContext.newPage();
  await publicRoutes(pendingPage, 202);
  await pendingPage.goto(`${origin}/report-project?project=41`);
  await pendingPage.getByLabel("Description").fill("Observed delay in the published project schedule.");
  await pendingPage.getByRole("button", { name: "Review Report" }).click();
  await pendingPage.getByRole("button", { name: "Submit Report" }).click();
  await pendingPage.getByText("Email notification delivery is pending retry.").waitFor();
  await pendingContext.close();

  const adminContext = await browser.newContext({ viewport: { width: 1280, height: 850 }, acceptDownloads: true });
  const adminPage = await adminContext.newPage();
  await adminRoutes(adminPage);
  await adminPage.goto(`${origin}/admin/dashboard`);
  await adminPage.getByRole("link", { name: "Project Concern Reports" }).first().click();
  await adminPage.waitForURL("**/admin/project-concerns");
  await adminPage.getByRole("heading", { name: "Project Concern Reports" }).waitFor();
  assert.ok(await adminPage.getByRole("link", { name: "Project Concern Reports" }).isVisible());
  assert.equal(await adminPage.getByText("#41", { exact: false }).count(), 0, "The Administrator list does not expose the numeric project ID");
  await adminPage.getByRole("button", { name: "View" }).click();
  await adminPage.getByText("Observed delay in the published project schedule.").waitFor();
  assert.equal(await adminPage.getByText("Project ID", { exact: false }).count(), 0, "Report details do not expose the numeric project ID");
  const downloadPromise = adminPage.waitForEvent("download");
  await adminPage.getByRole("button", { name: "Download" }).click();
  assert.equal((await downloadPromise).suggestedFilename(), "PCR-Evidence-8.pdf");
  await adminPage.getByRole("button", { name: "Retry Email Delivery" }).click();
  await adminPage.getByText("Delivery completed successfully.").waitFor();
  await adminContext.close();

  const deniedContext = await browser.newContext({ viewport: { width: 900, height: 700 } });
  const deniedPage = await deniedContext.newPage();
  await deniedPage.addInitScript(() => {
    localStorage.setItem("user", JSON.stringify({ role: "validator", username: "Validator" }));
    localStorage.setItem("isLoggedIn", "true");
  });
  await deniedPage.goto(`${origin}/admin/project-concerns`);
  await deniedPage.waitForURL("**/validator/dashboard");
  assert.equal(await deniedPage.getByRole("heading", { name: "Project Concern Reports" }).count(), 0);
  await deniedContext.close();

  console.log("PASS public project concern and Administrator delivery browser checks");
} finally {
  await browser.close();
  await new Promise((resolve, reject) => server.httpServer.close((error) => error ? reject(error) : resolve()));
}
