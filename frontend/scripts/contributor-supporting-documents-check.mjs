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
  "access-control-allow-methods": "GET, POST, PUT, DELETE, OPTIONS",
  "access-control-allow-headers": "authorization, content-type",
};
const schema = {
  format_version: 1,
  title: "Simplified RDIP Contributor Form",
  sections: [{
    key: "project_information",
    title: "Project Information",
    description: "",
    visible: true,
    fields: [{
      key: "program",
      label: "Program",
      type: "text",
      visible: true,
      required: false,
    }],
  }, {
    key: "supporting_documents",
    title: "Supporting Documents",
    description: "Attach evidence for this project.",
    visible: true,
    fields: [{
      key: "custom_supporting_documents",
      label: "Supporting Documents",
      type: "document_upload",
      visible: true,
      required: true,
      min_files: 1,
      max_files: 10,
      max_file_bytes: 20 * 1024 * 1024,
      allowed_extensions: ["pdf", "docx", "xlsx", "csv", "png", "jpg", "jpeg"],
      help_text: "Upload evidence that supports the project.",
    }],
  }],
};

const context = await browser.newContext({ viewport: { width: 1080, height: 800 } });
const page = await context.newPage();
let projectCreates = 0;
let uploads = 0;
let removals = 0;
let retries = 0;
let existingDocument = null;
await page.addInitScript(() => {
  localStorage.setItem("isLoggedIn", "true");
  localStorage.setItem("accessToken", "supporting-documents-test");
  localStorage.setItem("user", JSON.stringify({
    id: 21,
    username: "document-contributor",
    role: "employee",
    agency: "DENR",
  }));
  localStorage.setItem("simplified_submission_draft_v3_document-contributor_new", JSON.stringify({
    savedAt: new Date().toISOString(),
    form: { program: "THIS STALE VALUE MUST NOT APPEAR" },
  }));
});
page.on("dialog", async (dialog) => dialog.accept());
await page.route("**/api/**", async (route) => {
  const request = route.request();
  const url = request.url();
  const method = request.method();
  if (method === "OPTIONS") return route.fulfill({ status: 204, headers });
  if (url.includes("contributor-forms/simplified-rdip/current")) {
    return route.fulfill({
      status: 200,
      headers,
      contentType: "application/json",
      body: JSON.stringify({ key: "simplified-rdip", version: 2, schema }),
    });
  }
  if (url.includes("contributor-forms/simplified-rdip/versions/2/")) {
    return route.fulfill({
      status: 200,
      headers,
      contentType: "application/json",
      body: JSON.stringify({ key: "simplified-rdip", version: 2, schema }),
    });
  }
  if (url.includes("encoding-window/")) {
    return route.fulfill({
      status: 200,
      headers,
      contentType: "application/json",
      body: JSON.stringify({ enabled: true, is_open: true, can_encode: true, status_code: "open", message: "Open" }),
    });
  }
  if (url.includes("employee/projects/") && method === "POST") {
    projectCreates += 1;
    return route.fulfill({
      status: 201,
      headers,
      contentType: "application/json",
      body: JSON.stringify({ id: 99, status: "planning" }),
    });
  }
  if (url.endsWith("/api/employee/projects/99/") && method === "GET") {
    return route.fulfill({
      status: 200,
      headers,
      contentType: "application/json",
      body: JSON.stringify({
        id: 99,
        name: "Document action test",
        title: "Document action test",
        agency: "DENR",
        status: "planning",
        workflow_status: "draft",
        updated_at: new Date().toISOString(),
        form_version: 2,
        current_form_version: 2,
        profile_data: {
          submission_type: "simplified",
          form_schema: { key: "simplified-rdip", version: 2 },
          simplified_form: { agencyName: "DENR", projectActivity: "Document action test" },
        },
      }),
    });
  }
  if (url.includes("project-supporting-documents/assessment-status/") && method === "GET") {
    return route.fulfill({
      status: 200,
      headers,
      contentType: "application/json",
      body: JSON.stringify(existingDocument
        ? existingDocument.extraction_status === "ready"
          ? { status: "pending", required: true, document_results: [] }
          : existingDocument.processing_error
            ? { status: "unavailable", required: true, document_results: [], summary: "Failed to upload. Retry or remove the affected file." }
            : { status: "processing", required: true, document_results: [], summary: "Supporting documents are being prepared." }
        : { status: "missing", required: true, document_results: [] }),
    });
  }
  if (url.includes("project-supporting-documents/?project=99") && method === "GET") {
    return route.fulfill({
      status: 200,
      headers,
      contentType: "application/json",
      body: JSON.stringify(existingDocument ? [existingDocument] : []),
    });
  }
  if (url.endsWith("/api/project-supporting-documents/501/retry/") && method === "POST") {
    retries += 1;
    await new Promise((resolve) => setTimeout(resolve, 150));
    existingDocument = { ...existingDocument, extraction_status: "ready", processing_error: "" };
    return route.fulfill({ status: 200, headers, contentType: "application/json", body: JSON.stringify(existingDocument) });
  }
  if (url.endsWith("/api/project-supporting-documents/") && method === "POST") {
    uploads += 1;
    return route.fulfill({
      status: 201,
      headers,
      contentType: "application/json",
      body: JSON.stringify({
        id: 501,
        project: 99,
        field_key: "custom_supporting_documents",
        form_key: "simplified-rdip",
        form_version: 2,
        original_filename: "proposal.csv",
        content_type: "text/csv",
        extension: "csv",
        size_bytes: 25,
        checksum_sha256: "a".repeat(64),
        extraction_status: "queued",
        download_url: "/api/project-supporting-documents/501/download/",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }),
    });
  }
  if (url.includes("project-supporting-documents/") && method === "DELETE") {
    removals += 1;
    existingDocument = null;
    return route.fulfill({ status: 204, headers });
  }
  return route.fulfill({ status: 200, headers, contentType: "application/json", body: "{}" });
});

try {
  await page.goto(`${origin}/employee/projects/new/simplified`, { waitUntil: "networkidle" });
  assert.equal(await page.getByLabel("Program", { exact: true }).inputValue(), "", "A new submission ignores and removes stale browser draft values.");
  assert.equal(await page.getByText("Recovered your unsaved local inputs", { exact: false }).count(), 0, "A new submission does not show a recovery notice.");
  await page.getByRole("heading", { name: "Supporting Documents", exact: true }).waitFor();
  await page.getByText("File bytes are never sent to Groq.", { exact: false }).waitFor();
  const picker = page.locator('input[type="file"][multiple]');
  await picker.setInputFiles({ name: "proposal.csv", mimeType: "text/csv", buffer: Buffer.from("item,value\nscope,river\n") });
  await page.getByText("proposal.csv", { exact: true }).waitFor();
  assert.equal(await page.getByText("proposal.csv", { exact: true }).count(), 1, "One selected file appears once in the queue.");

  await picker.setInputFiles({ name: "proposal.csv", mimeType: "text/csv", buffer: Buffer.from("item,value\nscope,river\n") });
  await page.getByRole("status").getByText("already selected", { exact: false }).waitFor();
  assert.equal(await page.getByText("proposal.csv", { exact: true }).count(), 1, "Selecting a duplicate does not add another row.");

  await picker.setInputFiles({ name: "unsafe.exe", mimeType: "application/octet-stream", buffer: Buffer.from("unsafe") });
  await page.getByRole("status").getByText("unsupported format", { exact: false }).waitFor();
  assert.equal(await page.getByText("unsafe.exe", { exact: true }).count(), 0, "Unsupported files are rejected before upload.");

  await page.getByRole("button", { name: "Remove proposal.csv" }).click();
  assert.equal(await page.getByText("proposal.csv", { exact: true }).count(), 0);
  assert.equal(removals, 0, "Removing a queued file does not call the document delete endpoint.");

  await picker.setInputFiles({ name: "proposal.csv", mimeType: "text/csv", buffer: Buffer.from("item,value\nscope,river\n") });
  await page.getByRole("button", { name: "Save Draft", exact: true }).click();
  await page.waitForURL("**/employee/projects");
  assert.equal(projectCreates, 1, "The project draft is created once.");
  assert.equal(uploads, 1, "The queued document uploads once after the project draft exists.");

  existingDocument = {
    id: 501,
    project: 99,
    field_key: "custom_supporting_documents",
    form_key: "simplified-rdip",
    form_version: 2,
    original_filename: "uploaded-evidence.pdf",
    content_type: "application/pdf",
    extension: "pdf",
    size_bytes: 166399,
    checksum_sha256: "b".repeat(64),
    extraction_status: "queued",
    processing_error: "The document worker is unavailable. Retry processing when it is online.",
    download_url: "/api/project-supporting-documents/501/download/",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  await page.goto(`${origin}/employee/projects/99/edit/simplified`, { waitUntil: "networkidle" });
  await page.getByText("uploaded-evidence.pdf", { exact: true }).waitFor();
  await page.getByText("Failed to upload", { exact: true }).first().waitFor();
  await page.getByText("Document processing must finish before the AI assessment can run.", { exact: true }).waitFor({ state: "detached" });

  const retryButton = page.getByRole("button", { name: "Retry processing uploaded-evidence.pdf" });
  assert.equal(await retryButton.isEnabled(), true, "Retry is an enabled native button.");
  const retryBox = await retryButton.boundingBox();
  assert.ok(retryBox && retryBox.height >= 32, "Retry has a usable click target.");
  const retryClick = retryButton.click();
  await page.getByRole("button", { name: "Retry processing uploaded-evidence.pdf" }).getByText("Retrying...", { exact: true }).waitFor();
  await retryClick;
  await page.getByText("Document processing completed.", { exact: true }).waitFor();
  await page.getByText("Ready", { exact: true }).waitFor();
  assert.equal(retries, 1, "Retry sends exactly one processing request.");

  const removeButton = page.getByRole("button", { name: "Remove uploaded-evidence.pdf" });
  assert.equal(await removeButton.isEnabled(), true, "Remove is an enabled native button.");
  const removeBox = await removeButton.boundingBox();
  assert.ok(removeBox && removeBox.height >= 32, "Remove has a usable click target.");
  await removeButton.click();
  await page.getByText("uploaded-evidence.pdf", { exact: true }).waitFor({ state: "detached" });
  assert.equal(removals, 1, "Remove sends exactly one delete request after confirmation.");

  console.log("PASS supporting-document queue, upload, Retry, and Remove interactions");
} finally {
  await context.close();
  await browser.close();
  await new Promise((resolve, reject) => server.httpServer.close((error) => error ? reject(error) : resolve()));
}
