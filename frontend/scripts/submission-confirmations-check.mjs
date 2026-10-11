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
  "access-control-allow-methods": "GET, POST, PUT, OPTIONS",
  "access-control-allow-headers": "authorization, content-type",
};
const schema = {
  format_version: 1, title: "Confirmation test form", sections: [{
    key: "project", title: "Project Information", fields: [
      { key: "projectActivity", label: "Project/Activity", type: "text", required: true, visible: true },
      { key: "startYear", label: "Start Year", type: "year", required: true, visible: true },
      { key: "endYear", label: "End Year", type: "year", required: true, visible: true },
    ],
  }],
};

async function respond(route, body = {}) {
  await route.fulfill({
    status: 200, contentType: "application/json", headers,
    body: JSON.stringify(body),
  });
}

async function answerConfirmation(page, buttonName, accept) {
  const dialogPromise = page.waitForEvent("dialog");
  const clickPromise = page.getByRole("button", { name: buttonName }).click();
  const dialog = await dialogPromise;
  assert.equal(dialog.type(), "confirm");
  assert.match(dialog.message(), /Estero Renewal/);
  if (accept) await dialog.accept();
  else await dialog.dismiss();
  await clickPromise;
  return dialog.message();
}

async function checkSimplified(kind) {
  const context = await browser.newContext({ viewport: { width: 390, height: 760 } });
  const page = await context.newPage();
  const writes = [];
  await page.addInitScript((submissionKind) => {
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "confirmation-test");
    localStorage.setItem("user", JSON.stringify({ id: 1, username: "contributor", role: "employee", agency: "DENR" }));
    if (submissionKind === "new") localStorage.setItem(
      "simplified_submission_draft_v3_contributor_new",
      JSON.stringify({ form: { projectActivity: "Estero Renewal", startYear: "2026", endYear: "2027" } }),
    );
  }, kind);
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = request.url();
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    if (request.method() !== "GET" && /employee\/projects\/|project-revisions\/9\//.test(url)) {
      writes.push(`${request.method()} ${new URL(url).pathname}`);
      return respond(route, url.endsWith("/employee/projects/") ? { id: 7 } : {});
    }
    if (url.includes("contributor-forms/")) return respond(route, { key: "simplified-rdip", version: 1, schema });
    if (url.includes("encoding-window/") || url.includes("progress-update-window/")) {
      return respond(route, { enabled: true, is_open: true, can_encode: true, status_code: "open", message: "Open" });
    }
    const profile = {
      form_schema: { key: "simplified-rdip", version: 1 },
      simplified_form: { agencyName: "DENR", projectActivity: "Estero Renewal", startYear: "2026", endYear: "2027" },
      ...(kind === "revision" ? { validator_review: { editable_fields: ["projectActivity"] } } : {}),
    };
    if (url.includes("project-revisions/9/")) return respond(route, {
      id: 9, state: "draft", profile_data_snapshot: profile,
    });
    if (url.includes("employee/projects/7/")) return respond(route, {
      id: 7, title: "Estero Renewal", agency: "DENR",
      status: kind === "revision" ? "proposed" : "planning",
      workflow_status: kind === "revision" ? "needs_revision" : "draft",
      profile_data: profile,
    });
    return respond(route, {});
  });
  const path = kind === "new"
    ? "/employee/projects/new/simplified"
    : kind === "progress"
    ? "/employee/projects/7/edit/simplified?revision=9"
    : "/employee/projects/7/edit/simplified";
  await page.goto(origin + path, { waitUntil: "networkidle" });
  const buttonName = kind === "progress" ? "Submit Progress Update" : "Submit for Validation";
  await page.getByRole("button", { name: buttonName }).waitFor();
  const canceled = await answerConfirmation(page, buttonName, false);
  assert.match(canceled, new RegExp(kind === "progress" ? "progress update" : kind === "revision" ? "Resubmit revisions" : "Submit ", "i"));
  assert.deepEqual(writes, [], `${kind} cancellation must send no write request`);
  await answerConfirmation(page, buttonName, true);
  await page.waitForFunction(() => localStorage.getItem("projects_last_update") !== null);
  assert.equal(writes.length, 2, `${kind} confirmation saves then submits exactly once`);
  assert.match(writes[0], kind === "new" ? /^POST \/api\/employee\/projects\/$/ : /^PUT /);
  assert.match(writes[1], /^POST /);
  await context.close();
  console.log(`PASS simplified ${kind} submission confirmation`);
}

async function checkDetailed(kind) {
  const context = await browser.newContext({ viewport: { width: 1100, height: 800 } });
  const page = await context.newPage();
  const writes = [];
  const profile = {
    projectTitle: "Estero Renewal", officeUnit: "DENR NCR", programOrProject: "Program",
    objective: "Improve water quality", description: "Restore urban waterways", implementingAgency: "DENR",
    startYear: "2026", completionYear: "2027", spatialCoverageByCost: "Region-specific",
    inclusionProgramming: "Yes", physicalFinancialStatus: "Ongoing", riskAndMitigation: "Flood risks managed",
    papCode: "PAP-001", fundingSourcesAndMode: "GAA", levelOfApproval: "Not Applicable",
    mainPdpChapter: "Infrastructure", mainPdpOutcome: "No Statement applicable",
    mainPdpSubOutcome: "No Statement applicable", mainInfrastructureSector: "Water Resources",
    mainInfrastructureSubsector: "Water Supply", expectedOutputIndicator: "Improved waterways",
    gadResponsiveness: "Program/Project is gender-responsive", employmentTotal: "0",
    focalPerson: "Project Lead", alternateRepresentative: "Deputy Lead", contactDetails: "contact@example.com",
    totalProjectCost: "100", categoryStatus: "CIP", implementationReadinessLevel: "Ready",
    projectReadinessItems: ["Concept Paper"],
    projectCostRows: [{ source: "GAA", y2026: "100", overall: "100", yearValues: {} }],
    pipBudgetRows: [{ year: "2026", gaa: "100" }],
    provincialBreakdownOption: "No available breakdown information (Kindly skip)",
    ...(kind === "revision" ? { validator_review: { editable_fields: ["projectTitle"] } } : {}),
  };
  await page.addInitScript(({ submissionKind, draft }) => {
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "detailed-confirmation-test");
    localStorage.setItem("user", JSON.stringify({ id: 1, username: "contributor", role: "employee", agency: "DENR" }));
    if (submissionKind === "new") localStorage.setItem(
      "project_submission_draft_v2_contributor_new",
      JSON.stringify({ form: draft, step: 6 }),
    );
  }, { submissionKind: kind, draft: profile });
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = request.url();
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    if (request.method() !== "GET" && /employee\/projects\/|project-revisions\/9\//.test(url)) {
      writes.push(`${request.method()} ${new URL(url).pathname}`);
      return respond(route, url.endsWith("/employee/projects/") ? { id: 7 } : {});
    }
    if (url.includes("encoding-window/") || url.includes("progress-update-window/")) {
      return respond(route, { enabled: true, is_open: true, can_encode: true, status_code: "open", message: "Open" });
    }
    if (url.includes("project-revisions/9/")) return respond(route, {
      id: 9, state: "draft", profile_data_snapshot: profile,
    });
    if (url.includes("employee/projects/7/")) return respond(route, {
      id: 7, title: "Estero Renewal", agency: "DENR",
      status: kind === "revision" ? "proposed" : "planning",
      workflow_status: kind === "revision" ? "needs_revision" : "draft",
      profile_data: profile,
    });
    return respond(route, {});
  });
  const path = kind === "new"
    ? "/employee/projects/new/detailed"
    : kind === "progress" ? "/employee/projects/7/edit?revision=9" : "/employee/projects/7/edit";
  await page.goto(origin + path, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "6. Contacts & Submit" }).click();
  const buttonName = kind === "progress" ? "Submit Progress Update" : "Submit for Validation";
  await page.getByRole("button", { name: buttonName }).waitFor();
  const canceled = await answerConfirmation(page, buttonName, false);
  assert.match(canceled, new RegExp(kind === "progress" ? "progress update" : kind === "revision" ? "Resubmit revisions" : "Submit ", "i"));
  assert.deepEqual(writes, [], `${kind} cancellation must send no write request`);
  await answerConfirmation(page, buttonName, true);
  await page.waitForFunction(() => localStorage.getItem("projects_last_update") !== null);
  assert.equal(writes.length, 2, `${kind} confirmation saves then submits exactly once`);
  assert.match(writes[0], kind === "new" ? /^POST \/api\/employee\/projects\/$/ : /^PUT /);
  assert.match(writes[1], /^POST /);
  await context.close();
  console.log(`PASS detailed ${kind} submission confirmation`);
}

async function checkAdminInvitation() {
  const context = await browser.newContext({ viewport: { width: 390, height: 760 } });
  const page = await context.newPage();
  const invitations = [];
  let releaseInvitation;
  const invitationHold = new Promise((resolve) => { releaseInvitation = resolve; });
  await page.addInitScript(() => {
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "confirmation-admin-test");
    localStorage.setItem("user", JSON.stringify({ id: 2, username: "administrator", role: "admin", agency: "RDC-NCR" }));
  });
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    if (request.method() === "POST" && request.url().includes("admin/users/")) {
      invitations.push(JSON.parse(request.postData() || "{}"));
      await invitationHold;
      return respond(route, { detail: "Registration invitation sent." });
    }
    if (request.url().includes("admin/users/") || request.url().includes("password-reset-requests/")) return respond(route, []);
    return respond(route, {});
  });
  await page.goto(origin + "/admin/users?tab=create-account", { waitUntil: "networkidle" });
  await page.getByPlaceholder("Email").fill("new.user@example.com");
  await page.getByLabel("User Type").selectOption("validator");
  const button = page.getByRole("button", { name: "Send Registration Form" });
  const cancelPromise = page.waitForEvent("dialog");
  const cancelClick = button.click();
  const canceled = await cancelPromise;
  assert.match(canceled.message(), /new\.user@example\.com.*validator/s);
  await canceled.dismiss();
  await cancelClick;
  assert.equal(invitations.length, 0, "Canceling must not send an invitation");
  const confirmPromise = page.waitForEvent("dialog");
  const confirmClick = button.click();
  const confirmed = await confirmPromise;
  await confirmed.accept();
  await confirmClick;
  await page.getByRole("button", { name: "Sending Registration Form..." }).waitFor();
  assert.equal(await page.getByRole("button", { name: "Sending Registration Form..." }).isDisabled(), true);
  assert.deepEqual(invitations, [{ email: "new.user@example.com", role: "validator" }]);
  releaseInvitation();
  await page.getByText("Registration invitation sent.", { exact: false }).first().waitFor();
  assert.equal(invitations.length, 1, "Only one invitation request is sent");
  await context.close();
  console.log("PASS admin registration-link confirmation and duplicate-send guard");
}

try {
  for (const kind of ["new", "project", "revision", "progress"]) await checkSimplified(kind);
  for (const kind of ["new", "project", "revision", "progress"]) await checkDetailed(kind);
  await checkAdminInvitation();
} finally {
  await browser.close();
  await new Promise((resolve, reject) => server.httpServer.close((error) => error ? reject(error) : resolve()));
}
