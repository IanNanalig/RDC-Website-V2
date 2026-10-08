import assert from "node:assert/strict";
import { chromium } from "playwright-core";
import { preview } from "vite";

const browserPath = process.env.CMS_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const server = await preview({ preview: { host: "127.0.0.1", port: 0 } });
const address = server.httpServer.address();
assert.ok(address && typeof address !== "string");
const frontendUrl = `http://127.0.0.1:${address.port}`;
const browser = await chromium.launch({ executablePath: browserPath, headless: true });

const sampleProject = {
  id: 1,
  title: "NCR Estero Recovery and Pollution-Control Program",
  agency: "DENR",
  submitted_by_name: "Sample Contributor",
  status: "proposed",
  workflow_status: "pending_validation",
  submission_type: "simplified",
  form_version: 1,
  current_form_version: 2,
  uses_outdated_form: true,
  budget: 250000000,
  updated_at: "2026-10-08T08:00:00Z",
};

const mobileFormSchema = {
  format_version: 1,
  title: "Simplified RDIP Contributor Form",
  sections: [
    { key: "project_information", title: "Project Information", fields: [
      { key: "agencyName", label: "Agency Name", type: "text", required: true },
      { key: "program", label: "Program", type: "text", required: true },
      { key: "projectActivity", label: "Project/Activity", type: "text", required: true },
      { key: "location", label: "Location", type: "text", required: true },
      { key: "description", label: "Description", type: "textarea", required: true },
    ] },
    { key: "classification", title: "Classification", fields: [
      { key: "developmentSector", label: "Development Sector", type: "select", options: [
        { value: "SCID", label: "SectoralCommitteeOnInfrastructureDevelopmentAndPublicTransportAccessibility" },
      ] },
    ] },
  ],
};

async function openPortal(viewport, role = "admin", path) {
  const context = await browser.newContext({
    viewport,
    isMobile: viewport.width < 768,
    hasTouch: viewport.width < 768,
  });
  const page = await context.newPage();
  await page.addInitScript((currentRole) => {
    localStorage.setItem("user", JSON.stringify({ role: currentRole, username: "Mobile Tester", agency: "RDC-NCR" }));
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "layout-test-token");
  }, role);
  await page.route("**/api/**", async (route) => {
    const headers = {
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "GET, POST, OPTIONS",
      "access-control-allow-headers": "authorization,content-type",
    };
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers });
      return;
    }
    const url = route.request().url();
    const body = url.includes("contributor-forms/simplified-rdip/versions/1/")
      ? JSON.stringify({ key: "simplified-rdip", version: 1, schema: mobileFormSchema })
      : url.includes("/validator/projects/1/") && !url.includes("/comments/")
      ? JSON.stringify({ ...sampleProject, profile_data: { submission_type: "simplified", simplified_form: {
        agencyName: "DENR", projectActivity: sampleProject.title, startYear: "2026", endYear: "2028",
      } } })
      : url.includes("/validator/projects/2/") && !url.includes("/comments/")
      ? JSON.stringify({ ...sampleProject, id: 2, submission_type: "detailed", profile_data: {
        projectTitle: sampleProject.title, officeUnit: "DENR",
      } })
      : url.includes("project-revisions/") || url.includes("/comments/") ? "[]"
      : url.includes("validator/projects/") ? JSON.stringify([sampleProject])
      : "{}";
    await route.fulfill({ status: 200, contentType: "application/json", headers, body });
  });
  const targetPath = path || (role === "admin" ? "/admin/dashboard" : "/validator/dashboard");
  await page.goto(frontendUrl + targetPath, { waitUntil: "domcontentloaded" });
  await page.locator(".portal-topbar").waitFor();
  return { context, page };
}

async function assertSimplifiedReviewFits(page, width) {
  const form = page.locator("form").first();
  await form.waitFor();
  await page.getByText("Project Information", { exact: true }).waitFor();
  assert.ok(await form.locator("section").count() >= 2, "The CMS-configured project sections have loaded");
  assert.equal(await form.locator("input").first().inputValue(), "DENR", "The project data has loaded");
  const clipped = await form.evaluate((element) =>
    Array.from(element.querySelectorAll("section, input, select, textarea, label, [role='alert']"))
      .filter((child) => {
        const rect = child.getBoundingClientRect();
        return rect.width > 0 && (rect.left < -1 || rect.right > window.innerWidth + 1);
      })
      .slice(0, 8)
      .map((child) => ({
        tag: child.tagName,
        text: child.textContent?.trim().slice(0, 45),
        left: Math.round(child.getBoundingClientRect().left),
        right: Math.round(child.getBoundingClientRect().right),
      })),
  );
  assert.deepEqual(clipped, [], `Simplified review fields must fit ${width}px: ${JSON.stringify(clipped)}`);
}

try {
  for (const viewport of [
    { width: 320, height: 568 },
    { width: 360, height: 740 },
    { width: 390, height: 844 },
    { width: 430, height: 932 },
    { width: 667, height: 375 },
  ]) {
    const { context, page } = await openPortal(viewport);
    const menu = page.getByRole("button", { name: "Menu" });
    const drawer = page.locator("#portal-navigation");
    assert.equal(await drawer.isVisible(), false, "Drawer starts closed");
    await menu.click();
    await drawer.waitFor({ state: "visible" });
    assert.equal(await menu.getAttribute("aria-expanded"), "true", "Menu reports its open state");
    assert.equal(await page.evaluate(() => document.body.style.overflow), "hidden", "Background scrolling is locked");

    const drawerBounds = await drawer.boundingBox();
    const headerBounds = await page.locator(".portal-topbar").boundingBox();
    assert.ok(drawerBounds && headerBounds);
    assert.ok(drawerBounds.x >= 0 && drawerBounds.x + drawerBounds.width <= viewport.width + 1, "Drawer fits viewport width");
    assert.ok(drawerBounds.y >= 0 && drawerBounds.y + drawerBounds.height <= viewport.height + 1, "Drawer fits viewport height");
    const drawerAboveHeader = await page.evaluate(({ x, y }) =>
      Boolean(document.elementFromPoint(x, y)?.closest("#portal-navigation")),
      { x: drawerBounds.x + 30, y: headerBounds.y + 30 });
    assert.equal(drawerAboveHeader, true, "Drawer is above the mobile header");

    const close = page.getByRole("button", { name: "Close navigation" });
    assert.equal(await close.evaluate((element) => element === document.activeElement), true, "Focus starts in the drawer");
    await page.keyboard.press("Shift+Tab");
    assert.equal(await page.getByRole("button", { name: "Logout" }).evaluate((element) => element === document.activeElement), true,
      "Keyboard focus wraps to the last drawer control");
    await page.keyboard.press("Tab");
    assert.equal(await close.evaluate((element) => element === document.activeElement), true,
      "Keyboard focus wraps back to the close button");

    await close.click();
    assert.equal(await drawer.isVisible(), false, "Close button dismisses drawer");
    assert.equal(await page.evaluate(() => document.body.style.overflow), "", "Background scrolling is restored");
    await menu.click();
    await page.keyboard.press("Escape");
    assert.equal(await drawer.isVisible(), false, "Escape dismisses drawer");
    await menu.click();
    await page.mouse.click(viewport.width - 5, viewport.height - 5);
    assert.equal(await drawer.isVisible(), false, "Backdrop dismisses drawer");
    await menu.click();
    await drawer.getByRole("link", { name: "Projects", exact: true }).click();
    await page.waitForURL("**/admin/projects");
    assert.equal(await drawer.isVisible(), false, "Choosing a route dismisses the drawer");
    const documentWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    assert.ok(documentWidth <= viewport.width + 1, `No horizontal overflow at ${viewport.width}px: ${documentWidth}`);
    await context.close();
    console.log(`PASS mobile portal ${viewport.width}x${viewport.height}`);
  }

  const { context, page } = await openPortal({ width: 768, height: 1024 });
  assert.equal(await page.getByRole("button", { name: "Menu" }).isVisible(), false, "Tablet keeps desktop navigation");
  assert.equal(await page.locator("#portal-navigation").isVisible(), true, "Tablet sidebar remains visible");
  await context.close();
  console.log("PASS tablet navigation");

  for (const path of [
    "/validator/dashboard",
    "/validator/projects",
    "/validator/projects/history",
    "/validator/projects/update-forms",
    "/validator/projects/1/review/simplified",
    "/validator/projects/2/review",
  ]) {
    const { context: validatorContext, page: validatorPage } = await openPortal(
      { width: 320, height: 568 }, "validator", path,
    );
    const menu = validatorPage.getByRole("button", { name: "Menu" });
    await menu.click();
    assert.equal(await validatorPage.locator("#portal-navigation").isVisible(), true,
      `Validator menu opens on ${path}`);
    await validatorPage.getByRole("button", { name: "Close navigation" }).click();
    const documentWidth = await validatorPage.evaluate(() => document.documentElement.scrollWidth);
    assert.ok(documentWidth <= 321, `Validator page ${path} must not overflow: ${documentWidth}`);
    const actionName = path.endsWith("update-forms") ? "Update Form"
      : path.endsWith("history") ? "View"
      : path.endsWith("projects") ? "Review" : null;
    if (actionName) {
      const action = validatorPage.getByRole("button", { name: actionName, exact: true }).first();
      await action.waitFor();
      const bounds = await action.boundingBox();
      assert.ok(bounds && bounds.x >= 0 && bounds.x + bounds.width <= 321,
        `${actionName} must be visible without horizontal scrolling on ${path}: ${JSON.stringify(bounds)}`);
      assert.ok(bounds.height >= 44, `${actionName} must have a mobile-sized touch target`);
    }
    if (path.includes("/review")) {
      await validatorPage.locator("form").first().waitFor();
      const reviewWidth = await validatorPage.evaluate(() => document.documentElement.scrollWidth);
      assert.ok(reviewWidth <= 321, `Validator review ${path} must not overflow: ${reviewWidth}`);
      if (path.endsWith("/review/simplified")) {
        await assertSimplifiedReviewFits(validatorPage, 320);
      }
    }
    await validatorContext.close();
    console.log(`PASS validator mobile ${path}`);
  }

  for (const width of [360, 390, 430]) {
    const { context, page } = await openPortal({ width, height: 800 }, "validator", "/validator/projects/1/review/simplified");
    await assertSimplifiedReviewFits(page, width);
    await context.close();
    console.log(`PASS validator simplified form ${width}px`);
  }

  for (const [kind, path] of [
    ["simplified", "/validator/projects/1/review/simplified"],
    ["detailed", "/validator/projects/2/review"],
  ]) {
    const { context, page } = await openPortal({ width: 390, height: 844 }, "validator", path);
    const submissions = [];
    await page.route("**/api/validator/projects/*/validate/", async (route) => {
      submissions.push(JSON.parse(route.request().postData() || "{}"));
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ review_status: "reviewed" }) });
    });
    if (kind === "simplified") {
      await page.getByText("Project Information", { exact: true }).waitFor();
      const revisionCheckbox = page.getByLabel("Contributor may edit this field").first();
      assert.equal(await revisionCheckbox.isEnabled(), true, "Revision selection remains editable");
      await revisionCheckbox.check();
      const notes = page.getByPlaceholder("Required when requesting revisions or rejecting");
      assert.equal(await notes.isEnabled(), true, "Validator notes remain editable");
      await notes.fill("Please update the project description.");
    } else {
      const access = page.locator("details").filter({ hasText: "Contributor Revision Access" });
      const revisionCheckbox = access.locator('input[type="checkbox"]').first();
      assert.equal(await revisionCheckbox.isEnabled(), true, "Revision selection remains editable");
      await revisionCheckbox.check();
      const notes = page.locator("#validator-notes");
      assert.equal(await notes.isEnabled(), true, "Validator notes remain editable");
      await notes.fill("Please update the project description.");
    }
    assert.equal(await page.locator("form fieldset:disabled input:not([type='checkbox'])").first().isDisabled(), true,
      `${kind} contributor answers must be read-only`);
    const requestRevision = page.getByRole("button", { name: "Request Revision" });
    let warning = "";
    page.once("dialog", async (dialog) => {
      warning = dialog.message();
      await dialog.dismiss();
    });
    await requestRevision.click();
    assert.match(warning, /Request revisions.*contributor will be notified.*Needs Revision/s);
    assert.equal(submissions.length, 0, `Cancel must not submit a ${kind} revision request`);
    assert.equal(await requestRevision.isDisabled(), false, "Cancel leaves the revision action available");

    page.on("dialog", (dialog) => dialog.accept());
    await requestRevision.click();
    await page.waitForURL("**/validator/projects");
    assert.equal(submissions.length, 1, `Confirmation submits one ${kind} revision request`);
    assert.equal(submissions[0].action, "save_reviewed");
    assert.equal("edited_profile_data" in submissions[0], false, "Validator requests must not send contributor form answers");
    await context.close();
    console.log(`PASS ${kind} revision confirmation`);
  }
} finally {
  await browser.close();
  await new Promise((resolve, reject) => server.httpServer.close((error) => error ? reject(error) : resolve()));
}
