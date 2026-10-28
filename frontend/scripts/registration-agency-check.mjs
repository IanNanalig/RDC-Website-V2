import assert from "node:assert/strict";
import { chromium } from "playwright-core";
import { preview } from "vite";

const browserPath = process.env.CMS_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const server = await preview({ preview: { host: "127.0.0.1", port: 0 } });
const address = server.httpServer.address();
assert.ok(address && typeof address !== "string");
const frontendUrl = "http://127.0.0.1:" + address.port;
const browser = await chromium.launch({ executablePath: browserPath, headless: true });

async function newRegistration(viewport, prefilledAgency = "", agencyLocked = false, setupType = "existing_account") {
  const context = await browser.newContext({
    viewport,
    isMobile: viewport.width < 600,
    hasTouch: viewport.width < 600,
  });
  const page = await context.newPage();
  const posts = [];
  await page.route("**/auth/setup-password/**", async (route) => {
    const request = route.request();
    const headers = { "access-control-allow-origin": "*", "access-control-allow-methods": "GET, POST, OPTIONS", "access-control-allow-headers": "content-type" };
    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers });
      return;
    }
    if (request.method() === "POST") {
      posts.push(JSON.parse(request.postData() || "{}"));
      await route.fulfill({
        status: 200, contentType: "application/json", headers,
        body: JSON.stringify({ requires_admin_activation: setupType === "invitation" }),
      });
      return;
    }
    if (setupType === "invalid") {
      await route.fulfill({
        status: 400, contentType: "application/json", headers,
        body: JSON.stringify({ detail: "Invitation is invalid, expired, or replaced. Ask an administrator to resend it." }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers,
      body: JSON.stringify({
        email: "registration@example.com", setup_type: setupType,
        agency_locked: agencyLocked, profile: { agency: prefilledAgency },
        agencies: [
          { code: "DENR", name: "Department of Environment and Natural Resources" },
          { code: "DOH", name: "Department of Health" },
          { code: "DPWH", name: "Department of Public Works and Highways" },
          { code: "RDC-NCR", name: "Regional Development Council National Capital Region" },
        ],
      }),
    });
  });
  await page.goto(frontendUrl + "/setup-password?token=agency-test", { waitUntil: "networkidle" });
  const agency = page.locator("#registration-agency");
  await agency.waitFor();
  assert.equal(await page.getByLabel("Full Name").count(), 0, "The old Full Name field is removed");
  assert.equal(await page.getByLabel("First Name").count(), 1);
  assert.equal(await page.getByLabel("Last Name").count(), 1);
  assert.match(await page.getByLabel("First Name", { exact: true }).locator("..").innerText(), /Ex\. Juan/, "First name shows its example");
  assert.match(await page.getByLabel("Last Name", { exact: true }).locator("..").innerText(), /Ex\. Dela Cruz/, "Last name shows its example");
  assert.equal(await page.getByLabel("Agency / Office", { exact: true }).count(), 1);
  assert.equal(await page.getByLabel("Office", { exact: true }).count(), 0, "Agency and Office use one registration field");
  assert.match(await page.getByLabel("Current Head of Agency/Local Chief Executive", { exact: true }).locator("..").innerText(), /Ex\. Mayor Vico Sotto/, "Agency head shows its example");
  assert.match(await page.getByLabel("Division", { exact: true }).locator("..").innerText(), /Ex\. Planning Office/, "Division shows its example");
  assert.match(await page.getByLabel("Position", { exact: true }).locator("..").innerText(), /Ex\. Validator/, "Position shows its example");
  const firstBox = await page.getByLabel("First Name").boundingBox();
  const lastBox = await page.getByLabel("Last Name").boundingBox();
  assert.ok(firstBox && lastBox);
  assert.equal(viewport.width < 600 ? lastBox.y > firstBox.y : lastBox.x > firstBox.x, true, "Name fields stack on mobile and sit side-by-side on desktop");
  return { context, page, posts, agency };
}

async function fillOtherFields(page) {
  await page.locator('input[name="first_name"]').fill("Test");
  await page.locator('input[name="last_name"]').fill("User");
  await page.getByLabel("Current Head of Agency/Local Chief Executive", { exact: true }).fill("Agency Head");
  await page.getByLabel("Division", { exact: true }).fill("Planning");
  await page.getByLabel("Position", { exact: true }).fill("Officer");
  await page.getByPlaceholder("02 xxxx xxxx").fill("0212345678");
  await page.getByPlaceholder("09xx xxx xxxx").fill("09170000000");
  await page.getByLabel("New Password").fill("ValidSetup123_");
  await page.getByLabel("Confirm Password").fill("ValidSetup123_");
}

try {
  for (const viewport of [{ width: 320, height: 568 }, { width: 390, height: 650 }]) {
    const { context, page, posts, agency } = await newRegistration(viewport, "DENR");
    assert.equal(await agency.inputValue(), "DENR", "Existing agency is prefilled");
    if (viewport.width === 320) {
      const firstName = page.getByLabel("First Name");
      await firstName.fill("Name1");
      await firstName.blur();
      await page.getByText("First name may contain letters, spaces, apostrophes, and hyphens only").waitFor();
      const lastName = page.getByLabel("Last Name");
      await lastName.fill("   ");
      await lastName.blur();
      await page.getByText("Last name is required").waitFor();
    }
    await agency.tap();
    await page.getByRole("option", { name: /DPWH Department of Public Works and Highways/ }).waitFor();
    await agency.fill("environment");
    const denr = page.getByRole("option", { name: /DENR Department of Environment and Natural Resources/ });
    await denr.waitFor();
    assert.equal(await page.getByRole("option").count(), 1, "Full-name search filters results");
    await page.setViewportSize({ width: viewport.width, height: 350 });
    await page.waitForFunction(() => {
      const option = document.querySelector('[role="option"]');
      const input = document.getElementById("registration-agency");
      if (!option || !input) return false;
      const optionRect = option.getBoundingClientRect();
      const inputRect = input.getBoundingClientRect();
      return optionRect.top >= 0 && optionRect.bottom <= window.visualViewport.height && inputRect.bottom <= window.visualViewport.height;
    });
    const optionBounds = await denr.boundingBox();
    assert.ok(optionBounds && optionBounds.y >= 0 && optionBounds.y + optionBounds.height <= 350,
      "Agency result stays inside a reduced mobile viewport: " + JSON.stringify({ optionBounds, inputBounds: await agency.boundingBox() }));
    await denr.tap();
    assert.equal(await agency.inputValue(), "DENR", "Touch selection stores the acronym");
    assert.equal(await agency.getAttribute("aria-expanded"), "false", "Touch selection closes the menu");

    await agency.fill("does not exist");
    await page.getByText("No approved agencies found.").waitFor();
    await page.getByText("This is an invalid Agency", { exact: true }).waitFor();
    await fillOtherFields(page);
    await page.getByRole("button", { name: "Set Password" }).click();
    assert.equal(posts.length, 0, "Unsupported agency cannot submit");

    await agency.fill("Department of");
    await page.getByLabel("First Name").tap();
    assert.equal(await agency.getAttribute("aria-expanded"), "false", "Outside tap closes the menu");
    await page.getByText("This is an invalid Agency", { exact: true }).first().waitFor();
    await page.getByRole("button", { name: "Set Password" }).click();
    assert.equal(posts.length, 0, "Partial agency name cannot submit");

    await agency.fill("Department of Health");
    await page.getByRole("button", { name: "Set Password" }).click();
    assert.equal(posts.length, 1, "Exact full name can submit");
    assert.equal(posts[0].agency, "DOH", "Request sends canonical agency code");
    assert.equal(posts[0].office, "DOH", "The canonical agency is also saved as the office");
    assert.equal(posts[0].first_name, "Test");
    assert.equal(posts[0].last_name, "User");
    assert.equal("full_name" in posts[0], false);
    const overflows = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    assert.equal(overflows, false, "Registration must not overflow a narrow viewport");
    await context.close();
    console.log("PASS agency touch and validation at " + viewport.width + "px");
  }

  const { context, page, posts, agency } = await newRegistration({ width: 1100, height: 750 });
  await agency.fill("regional development");
  await agency.press("ArrowDown");
  await agency.press("Enter");
  assert.equal(await agency.inputValue(), "RDC-NCR", "Keyboard selection uses canonical acronym");
  await agency.click();
  await agency.press("Escape");
  assert.equal(await agency.getAttribute("aria-expanded"), "false", "Escape closes the menu");
  await agency.fill("dpwh");
  await agency.press("Tab");
  await fillOtherFields(page);
  await page.getByRole("button", { name: "Set Password" }).click();
  assert.equal(posts.length, 1, "Exact typed acronym can submit");
  assert.equal(posts[0].agency, "DPWH", "Typed acronym is normalized");
  assert.equal(posts[0].office, "DPWH", "Agency and office cannot diverge");
  assert.equal(posts[0].first_name, "Test");
  assert.equal(posts[0].last_name, "User");
  await context.close();
  console.log("PASS agency keyboard and exact typing");

  for (const [savedAgency, viewport] of [
    ["RDC-NCR", { width: 390, height: 650 }],
    ["DENR", { width: 1100, height: 750 }],
    ["", { width: 390, height: 650 }],
  ]) {
    const { context, page, posts } = await newRegistration(viewport, savedAgency, true);
    const lockedAgency = page.locator("#registration-agency");
    assert.equal(await lockedAgency.inputValue(), savedAgency, "Saved internal agency is displayed");
    assert.equal(await lockedAgency.getAttribute("readonly"), "", "Internal agency is read-only");
    await lockedAgency.click();
    assert.equal(await page.getByRole("option").count(), 0, "Internal users have no agency choices");
    await fillOtherFields(page);
    await page.getByRole("button", { name: "Set Password" }).click();
    assert.equal(posts.length, 1, "Internal setup can be submitted");
    assert.equal(posts[0].agency, savedAgency, "Internal setup preserves the saved agency");
    await context.close();
  }
  console.log("PASS internal agency lock and legacy reset values");

  const invitation = await newRegistration({ width: 390, height: 650 }, "RDC-NCR", true, "invitation");
  await fillOtherFields(invitation.page);
  const cancelDialogPromise = invitation.page.waitForEvent("dialog");
  const cancelClickPromise = invitation.page.getByRole("button", { name: "Complete Registration" }).click();
  const cancelDialog = await cancelDialogPromise;
  assert.match(cancelDialog.message(), /registration@example\.com/);
  assert.match(cancelDialog.message(), /inactive until an administrator activates it/i);
  await cancelDialog.dismiss();
  await cancelClickPromise;
  assert.equal(invitation.posts.length, 0, "Canceling registration makes no request");
  const confirmDialogPromise = invitation.page.waitForEvent("dialog");
  const confirmClickPromise = invitation.page.getByRole("button", { name: "Complete Registration" }).click();
  const confirmDialog = await confirmDialogPromise;
  await confirmDialog.accept();
  await confirmClickPromise;
  await invitation.page.getByText("Registration complete. Your account is inactive until an administrator activates it.").waitFor();
  assert.equal(invitation.posts.length, 1, "The invitation form submits once");
  await invitation.page.waitForURL(/\/login$/);
  await invitation.page.getByText("Registration complete. Your account is awaiting administrator activation before you can log in.").waitFor();
  await invitation.context.close();
  console.log("PASS invited account returns to login with activation notice");

  const invalid = await newRegistration({ width: 390, height: 650 }, "", false, "invalid");
  await invalid.page.getByText("Invitation is invalid, expired, or replaced. Ask an administrator to resend it.").waitFor();
  assert.equal(await invalid.page.getByRole("button", { name: "Set Password" }).isDisabled(), true);
  assert.equal(invalid.posts.length, 0);
  await invalid.context.close();
  console.log("PASS expired or replaced invitation cannot submit");
} finally {
  await browser.close();
  await new Promise((resolve, reject) => server.httpServer.close((error) => error ? reject(error) : resolve()));
}
