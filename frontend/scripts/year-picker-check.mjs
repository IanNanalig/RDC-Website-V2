import assert from "node:assert/strict";
import { chromium } from "playwright-core";
import { preview } from "vite";

const server = await preview({ preview: { host: "127.0.0.1", port: 0 } });
const address = server.httpServer.address();
assert.ok(address && typeof address !== "string");
const origin = "http://127.0.0.1:" + address.port;
const browser = await chromium.launch({
  executablePath: process.env.CMS_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  headless: true,
});

async function openForm(viewport, existing = false, fallback = false) {
  const context = await browser.newContext({ viewport, isMobile: viewport.width < 600, hasTouch: viewport.width < 600 });
  const page = await context.newPage();
  await page.addInitScript(() => {
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "year-picker-test");
    localStorage.setItem("user", JSON.stringify({ id: 1, username: "year-tester", full_name: "Year Tester", role: "employee", agency: "DENR" }));
  });
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    const headers = { "access-control-allow-origin": "*", "access-control-allow-methods": "GET, OPTIONS", "access-control-allow-headers": "authorization, content-type" };
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers });
      return;
    }
    if (url.includes("contributor-forms/")) {
      await route.fulfill(fallback && url.includes("/current/")
        ? { status: 200, contentType: "application/json", headers, body: JSON.stringify({ key: "simplified-rdip", version: 1, schema: { format_version: 1, title: "Fallback form", description: "", sections: [] } }) }
        : { status: 404, contentType: "application/json", headers, body: "{}" });
      return;
    }
    let body = {};
    if (url.includes("encoding-window/")) body = { enabled: true, is_open: true, can_encode: true, status_code: "open", message: "Open" };
    if (url.includes("auth/me/")) body = { id: 1, role: "employee", username: "year-tester", agency: "DENR" };
    if (url.includes("employee/projects/1/")) body = {
      id: 1, status: "proposed", workflow_status: "needs_revision", profile_data: {
        simplified_form: { startYear: "2026", endYear: "2027", agencyName: "DENR", projectActivity: "Existing Project" },
        validator_review: { editable_fields: ["startYear"] },
      },
    };
    await route.fulfill({ status: 200, contentType: "application/json", headers, body: JSON.stringify(body) });
  });
  await page.goto(origin + (existing ? "/employee/projects/1/edit/simplified" : "/employee/projects/new/simplified"), { waitUntil: "networkidle" });
  const start = page.getByRole("button", { name: "Start Year *" });
  const end = page.getByRole("button", { name: "End Year *" });
  await start.waitFor();
  return { context, page, start, end };
}

async function choose(page, trigger, year, useTouch) {
  if (useTouch) await trigger.tap();
  else await trigger.click();
  const dialog = page.getByRole("dialog", { name: /year picker/ });
  await dialog.waitFor();
  while (!(await dialog.getByRole("button", { name: String(year), exact: true }).count())) {
    const current = Number((await dialog.locator("span").first().innerText()).split("–")[0]);
    const direction = year < current ? "Previous years" : "Next years";
    await dialog.getByRole("button", { name: direction }).click();
  }
  const option = dialog.getByRole("button", { name: String(year), exact: true });
  assert.equal(await option.isDisabled(), false, "Chosen year must be enabled");
  if (useTouch) await option.tap();
  else await option.click();
}

try {
  for (const viewport of [{ width: 320, height: 568 }, { width: 1100, height: 800 }]) {
    const useTouch = viewport.width < 600;
    const { context, page, start, end } = await openForm(viewport);
    assert.equal(await end.isDisabled(), true, "End Year waits for Start Year");
    await choose(page, start, 2026, useTouch);
    assert.match(await start.innerText(), /2026/);
    assert.equal(await end.isDisabled(), false);
    await choose(page, end, 2026, useTouch);
    assert.match(await end.innerText(), /2026/, "Equal years are allowed");
    await choose(page, start, 2028, useTouch);
    assert.match(await end.innerText(), /2028/, "End Year follows a later Start Year");
    await choose(page, end, 2043, useTouch);
    await choose(page, start, 2020, useTouch);
    assert.match(await end.innerText(), /2035/, "End Year is clamped to the 15-year limit");
    await page.getByText("End Year was adjusted to 2035 to stay within the allowed range.").waitFor();
    const draft = await page.evaluate(() => JSON.parse(localStorage.getItem("simplified_submission_draft_v3_year-tester_new") || "{}"));
    assert.equal(draft.form.startYear, "2020", "Start Year remains a string in the saved form payload");
    assert.equal(draft.form.endYear, "2035", "End Year remains a string in the saved form payload");
    assert.ok(await page.getByText("2035", { exact: true }).count() > 0, "Funding fields follow the chosen years");
    await end.click();
    const dialog = page.getByRole("dialog", { name: "End Year year picker" });
    await dialog.getByRole("button", { name: "Previous years" }).click();
    assert.equal(await dialog.getByRole("button", { name: "Previous years" }).isDisabled(), true, "Years before Start Year are unavailable");
    await page.keyboard.press("Escape");
    assert.equal(await dialog.count(), 0, "Escape closes the picker");
    await start.click();
    const bounds = await page.getByRole("dialog", { name: "Start Year year picker" }).boundingBox();
    assert.ok(bounds && bounds.x >= 0 && bounds.x + bounds.width <= viewport.width + 1 && bounds.y >= -1 && bounds.y + bounds.height <= viewport.height + 1,
      "Picker stays inside viewport: " + JSON.stringify(bounds));
    await page.getByRole("heading", { name: /Simplified/ }).first().click();
    assert.equal(await page.getByRole("dialog", { name: "Start Year year picker" }).count(), 0, "Outside click closes picker");
    await context.close();
    console.log("PASS simplified year picker at " + viewport.width + "px");
  }

  const { context, page, start, end } = await openForm({ width: 1100, height: 800 }, true);
  assert.equal(await end.isDisabled(), true, "Validator-locked End Year remains disabled");
  await start.click();
  const lockedDialog = page.getByRole("dialog", { name: "Start Year year picker" });
  assert.equal(await lockedDialog.getByRole("button", { name: "2028", exact: true }).isDisabled(), true,
    "Editable Start Year cannot move beyond the locked End Year");
  await page.keyboard.press("Escape");
  await start.press("ArrowDown");
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Enter");
  assert.match(await start.innerText(), /2027/, "Keyboard navigation and Enter select a year");
  assert.match(await end.innerText(), /2027/, "Locked End Year remains unchanged");
  await context.close();
  console.log("PASS validator-locked year and keyboard selection");

  const fallback = await openForm({ width: 390, height: 650 }, false, true);
  await choose(fallback.page, fallback.start, 2025, true);
  await choose(fallback.page, fallback.end, 2025, true);
  assert.match(await fallback.end.innerText(), /2025/, "Fallback form uses the year-only picker");
  await fallback.context.close();
  console.log("PASS fallback simplified form");
} finally {
  await browser.close();
  await new Promise((resolve, reject) => server.httpServer.close((error) => error ? reject(error) : resolve()));
}
