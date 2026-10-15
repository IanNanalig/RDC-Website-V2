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
  "access-control-allow-methods": "GET, POST, OPTIONS",
  "access-control-allow-headers": "authorization,content-type",
};

const sampleUsers = [
  { id: 3, username: "zoe", full_name: "Zoe", email: "a@example.test", agency: "DPWH", role: "validator", is_active: true },
  { id: 1, username: "amy", full_name: "Amy", email: "z@example.test", agency: "DENR", role: "admin", is_active: false },
  { id: 2, username: "ben", full_name: "Ben", email: "m@example.test", agency: "RDC-NCR", role: "staff", is_active: true },
];

async function mockApi(page, onReset = () => {}) {
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    const path = new URL(request.url()).pathname;
    if (path.endsWith("/auth/setup-password/")) {
      if (request.method() === "POST") {
        onReset(JSON.parse(request.postData() || "{}"));
        return route.fulfill({ status: 200, contentType: "application/json", headers, body: '{"status":"ok"}' });
      }
      return route.fulfill({ status: 200, contentType: "application/json", headers, body: '{"email":"tester@example.test","setup_type":"password_reset"}' });
    }
    const body = path.endsWith("/admin/users/") ? sampleUsers
      : path.endsWith("/password-reset-requests/") ? [] : {};
    return route.fulfill({ status: 200, contentType: "application/json", headers, body: JSON.stringify(body) });
  });
}

try {
  const mobile = await browser.newContext({ viewport: { width: 390, height: 760 }, isMobile: true, hasTouch: true });
  const page = await mobile.newPage();
  let resetPayload;
  await mockApi(page, (payload) => { resetPayload = payload; });
  await page.goto(`${origin}/login`);
  await page.getByRole("link", { name: "Forgot password?" }).click();
  await page.waitForURL("**/request-password-reset");
  await page.goto(`${origin}/forgot-password`);
  await page.waitForURL("**/request-password-reset");
  await page.goto(`${origin}/reset-password?token=reset_browser-test`);
  await page.getByRole("heading", { name: "Reset Your Password" }).waitFor();
  assert.equal(await page.getByLabel("Account email").inputValue(), "tester@example.test");
  assert.equal(await page.getByLabel("Full Name *").count(), 0, "Reset page has no profile form");
  await page.getByLabel("New Password", { exact: true }).fill("NewPassword123!");
  await page.getByLabel("Confirm Password", { exact: true }).fill("NewPassword123!");
  await page.getByRole("button", { name: "Save New Password" }).click();
  await page.getByText("Password updated. Redirecting to login...").waitFor();
  assert.deepEqual(resetPayload, { token: "reset_browser-test", new_password: "NewPassword123!" });
  await mobile.close();

  for (const viewport of [{ width: 390, height: 760 }, { width: 1366, height: 800 }]) {
    const context = await browser.newContext({ viewport, isMobile: viewport.width < 600, hasTouch: viewport.width < 600 });
    const adminPage = await context.newPage();
    await adminPage.addInitScript(() => {
      localStorage.setItem("user", JSON.stringify({ role: "admin", username: "Test Admin" }));
      localStorage.setItem("isLoggedIn", "true");
      localStorage.setItem("accessToken", "test-token");
    });
    await mockApi(adminPage);
    await adminPage.goto(`${origin}/admin/users?tab=system-users`);
    const cards = adminPage.getByRole("list", { name: "System users" }).locator("li");
    const rows = adminPage.locator("table.portal-table tbody tr");
    const items = viewport.width < 600 ? cards : rows;
    await items.first().waitFor();
    assert.match(await items.first().innerText(), /Amy/, "Default username ascending");
    if (viewport.width < 600) {
      await adminPage.getByLabel("Sort by").selectOption("email");
      assert.match(await items.first().innerText(), /Zoe/, "Mobile email ascending");
      await adminPage.getByRole("button", { name: "Sort descending" }).click();
      assert.match(await items.first().innerText(), /Amy/, "Mobile email descending");
    } else {
      await adminPage.getByRole("columnheader", { name: /Email/ }).getByRole("button").click();
      assert.match(await items.first().innerText(), /Zoe/, "Desktop email ascending");
      await adminPage.getByRole("columnheader", { name: /Email/ }).getByRole("button").click();
      assert.match(await items.first().innerText(), /Amy/, "Desktop email descending");
      assert.equal(await adminPage.getByRole("columnheader", { name: "Actions" }).getByRole("button").count(), 0);
    }
    await context.close();
  }
  console.log("PASS password reset and System Users sorting browser checks");
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
