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

const cover = { name: "cover.png", mimeType: "image/png", buffer: Buffer.from("sample image") };
const report = { name: "report.pdf", mimeType: "application/pdf", buffer: Buffer.from("sample document") };

try {
  for (const { width, role } of [
    { width: 320, role: "admin" },
    { width: 390, role: "content_editor" },
    { width: 1280, role: "admin" },
  ]) {
    const context = await browser.newContext({ viewport: { width, height: 800 }, isMobile: width < 600, hasTouch: width < 600 });
    const page = await context.newPage();
    const uploads = [];
    const uploadedRows = [];
    let failReportOnce = true;
    let releaseFirstUpload;
    const firstUploadGate = new Promise((resolve) => { releaseFirstUpload = resolve; });
    await page.addInitScript((currentRole) => {
      localStorage.setItem("user", JSON.stringify({ role: currentRole, username: "Media Tester" }));
      localStorage.setItem("isLoggedIn", "true");
      localStorage.setItem("accessToken", "media-test-token");
    }, role);
    await page.route("**/api/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/admin/cms/media/") && route.request().method() === "POST") {
        const body = route.request().postData() || "";
        const name = body.match(/filename="([^"]+)"/)?.[1] || "";
        uploads.push({ name, body });
        if (name === "report.pdf" && failReportOnce) {
          failReportOnce = false;
          await firstUploadGate;
          await route.fulfill({ status: 422, contentType: "application/json", body: '{"detail":"Temporary upload failure"}' });
          return;
        }
        const uploaded = {
          id: uploads.length, file: `cms/${name}`, url: `https://example.test/${name}`,
          file_type: name.endsWith(".png") ? "image" : "document",
          mime_type: name.endsWith(".png") ? "image/png" : "application/pdf",
          size: 20, alt_text: "", caption: "", is_archived: false,
          created_at: "2026-10-15T00:00:00Z",
        };
        uploadedRows.unshift(uploaded);
        await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(uploaded) });
        return;
      }
      if (path.endsWith("/admin/cms/media/") && route.request().method() === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ count: uploadedRows.length, results: uploadedRows, page: 1, page_size: 10, total_pages: 1, next: null, previous: null }) });
        return;
      }
      if (path.endsWith("/admin/cms/settings/")) {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([
          { id: 1, key: "media-upload-max-bytes", value_json: { image: 1024, document: 2048 } },
        ]) });
        return;
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });

    await page.goto(`${origin}/employee/cms/media`);
    const fileInput = page.locator('input[type="file"]');
    const queue = page.getByRole("list", { name: "Files ready to upload" });
    const chooseFiles = page.getByRole("button", { name: "Choose Files" });
    await chooseFiles.waitFor();
    assert.ok(await fileInput.evaluate((input) => input.multiple), "The picker allows multiple files");
    const chooserPromise = page.waitForEvent("filechooser");
    await chooseFiles.click();
    await (await chooserPromise).setFiles([report, cover]);
    await page.getByText("2 files queued").waitFor();
    assert.equal(await queue.locator("li").count(), 2, "Mixed image/document selection is queued");

    await fileInput.setInputFiles(cover);
    await page.getByText("cover.png: This file is already in the upload queue.").waitFor();
    assert.equal(await queue.locator("li").count(), 2, "Re-selecting a queued file does not duplicate it");
    await fileInput.setInputFiles([
      { name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("not allowed") },
      { name: "large.png", mimeType: "image/png", buffer: Buffer.alloc(1025) },
    ]);
    await page.getByText(/notes\.txt: This file type is not allowed/).waitFor();
    await page.getByText(/large\.png: This file exceeds the image upload limit/).waitFor();
    assert.equal(await queue.locator("li").count(), 2, "Invalid files are not queued");

    const coverRow = queue.locator("li").filter({ hasText: "cover.png" });
    await coverRow.getByRole("button", { name: "Remove cover.png from upload queue" }).click();
    assert.equal(await queue.locator("li").count(), 1);
    assert.equal(uploads.length, 0, "Removing a selected file does not upload it");
    assert.ok(await page.getByRole("button", { name: "Add More Files" }).evaluate((button) => button === document.activeElement),
      "Focus returns to the file picker after removal");
    await fileInput.setInputFiles(cover);
    await page.getByText("2 files queued").waitFor();
    await queue.locator("li").filter({ hasText: "cover.png" }).getByLabel("Alt Text").fill("Cover image description");
    await queue.locator("li").filter({ hasText: "cover.png" }).getByLabel("Caption").fill("Cover artwork");
    await queue.locator("li").filter({ hasText: "report.pdf" }).getByLabel("Caption").fill("Annual report");

    await page.getByRole("button", { name: "Upload 2 Files" }).click();
    try {
      await page.getByRole("button", { name: "Uploading..." }).waitFor();
      assert.ok(await page.getByRole("button", { name: "Add More Files" }).isDisabled(), "Files cannot be added during upload");
      assert.ok(await queue.locator("li").filter({ hasText: "cover.png" }).getByRole("button", { name: "Remove cover.png from upload queue" }).isDisabled(),
        "Files cannot be removed during upload");
    } finally {
      releaseFirstUpload();
    }
    await page.getByText("1 file uploaded. 1 failed; review the errors below and retry.").waitFor();
    assert.deepEqual(uploads.map((upload) => upload.name), ["report.pdf", "cover.png"], "Uploads continue after an earlier file fails");
    assert.ok(uploads[1].body.includes("Cover image description") && uploads[1].body.includes("Cover artwork"),
      "The cover upload uses its own details");
    assert.ok(uploads[0].body.includes("Annual report") && !uploads[0].body.includes("Cover artwork"),
      "The document upload uses its own caption");
    assert.equal(await queue.locator("li").count(), 1, "Failed files remain queued for retry");
    assert.ok(await page.getByText("cover.png: Uploaded").isVisible());
    assert.ok(await page.getByText("report.pdf: Temporary upload failure").isVisible());
    assert.ok(await page.getByText("1 active asset").isVisible(), "Successful files appear in the Media Library");

    await page.getByRole("button", { name: "Upload 1 File" }).click();
    await page.getByText("1 file uploaded.", { exact: true }).waitFor();
    assert.equal(uploads.length, 3, "Retry only submits the failed file");
    assert.ok(await page.getByText("No files chosen").isVisible());
    assert.ok(await page.getByText("2 active assets").isVisible());
    assert.equal(await fileInput.evaluate((input) => input.files.length), 0, "The native file input is cleared");
    const documentWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    assert.ok(documentWidth <= width + 1, `Media picker fits ${width}px: ${documentWidth}`);
    await context.close();
  }
  console.log("PASS CMS multi-file upload and partial-retry browser checks");
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
