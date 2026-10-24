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
  { id: 3, username: "zoe", first_name: "Zoe", last_name: "", email: "a@example.test", agency: "DPWH", role: "validator", is_active: true },
  { id: 1, username: "amy", first_name: "Amy", last_name: "", email: "z@example.test", agency: "DENR", role: "admin", is_active: false },
  { id: 2, username: "ben", first_name: "Ben", last_name: "", email: "m@example.test", agency: "RDC-NCR", role: "staff", is_active: true },
  ...Array.from({ length: 10 }, (_, index) => ({
    id: index + 10,
    username: `member-${index + 1}`,
    first_name: "Member",
    last_name: String(index + 1).padStart(2, "0"),
    email: `member${index + 1}@example.test`,
    agency: index % 2 === 0 ? "DENR" : "DOH",
    role: "staff",
    is_active: true,
  })),
];

async function mockApi(page, onReset = () => {}, onRequest = () => {}, options = {}) {
  let users = sampleUsers.map((user) => ({ ...user }));
  let userLoads = 0;
  let failNextUsersLoad = false;
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    const path = new URL(request.url()).pathname;
    if (options.failAuxiliary && path.endsWith("/encoding-window/")) {
      return route.fulfill({ status: 503, contentType: "application/json", headers, body: '{"detail":"Temporary schedule error"}' });
    }
    if (path.endsWith("/password-reset-requests/") && request.method() === "POST") {
      onRequest(JSON.parse(request.postData() || "{}"));
      return route.fulfill({ status: 201, contentType: "application/json", headers, body: '{"detail":"Request received"}' });
    }
    if (path.endsWith("/auth/setup-password/")) {
      if (request.method() === "POST") {
        onReset(JSON.parse(request.postData() || "{}"));
        return route.fulfill({ status: 200, contentType: "application/json", headers, body: '{"status":"ok"}' });
      }
      return route.fulfill({ status: 200, contentType: "application/json", headers, body: '{"email":"tester@example.test","setup_type":"password_reset"}' });
    }
    const activeMatch = path.match(/\/admin\/users\/(\d+)\/set_active\/$/);
    if (activeMatch && request.method() === "POST") {
      const id = Number(activeMatch[1]);
      const active = Boolean(JSON.parse(request.postData() || "{}").active);
      users = users.map((user) => user.id === id ? { ...user, is_active: active } : user);
      return route.fulfill({ status: 200, contentType: "application/json", headers, body: JSON.stringify({ id, is_active: active }) });
    }
    if (path.endsWith("/admin/users/")) {
      userLoads += 1;
      if (failNextUsersLoad) {
        failNextUsersLoad = false;
        return route.fulfill({ status: 503, contentType: "application/json", headers, body: '{"detail":"Temporary user-list error"}' });
      }
    }
    const body = path.endsWith("/admin/users/") ? users
      : path.endsWith("/password-reset-requests/") ? [] : {};
    return route.fulfill({ status: 200, contentType: "application/json", headers, body: JSON.stringify(body) });
  });
  return { getUserLoads: () => userLoads, failNextUsersLoad: () => { failNextUsersLoad = true; } };
}

try {
  const mobile = await browser.newContext({ viewport: { width: 390, height: 760 }, isMobile: true, hasTouch: true });
  const page = await mobile.newPage();
  let resetPayload;
  let requestPayload;
  await mockApi(page, (payload) => { resetPayload = payload; }, (payload) => { requestPayload = payload; });
  await page.goto(`${origin}/login`);
  await page.getByRole("link", { name: "Forgot password?" }).click();
  await page.waitForURL("**/request-password-reset");
  await page.getByLabel("Email", { exact: true }).fill("tester@example.test");
  await page.getByRole("button", { name: "Send Reset Request" }).click();
  await page.getByText(/If this email is registered/).waitFor();
  assert.deepEqual(requestPayload, { email: "tester@example.test" }, "Reset request still submits the email");
  assert.ok(await page.getByRole("button", { name: "Back" }).isVisible());
  assert.equal(await page.getByText("Back to login").count(), 0);
  await page.getByRole("button", { name: "Back" }).click();
  await page.waitForURL("**/login");
  await page.goto(`${origin}/request-password-reset`);
  await page.getByRole("button", { name: "Back" }).click();
  await page.waitForURL("**/login");
  await page.goto(`${origin}/forgot-password`);
  await page.waitForURL("**/request-password-reset");
  await page.goto(`${origin}/reset-password?token=reset_browser-test`);
  await page.getByRole("heading", { name: "Reset Your Password" }).waitFor();
  assert.equal(await page.getByLabel("Account email").inputValue(), "tester@example.test");
  assert.equal(await page.getByLabel("First Name").count(), 0, "Reset page has no profile form");
  assert.equal(await page.getByLabel("Last Name").count(), 0, "Reset page has no profile form");
  await page.getByLabel("New Password", { exact: true }).fill("NewPassword123!");
  await page.getByLabel("Confirm Password", { exact: true }).fill("NewPassword123!");
  await page.getByRole("button", { name: "Save New Password" }).click();
  await page.getByText("Password updated. Redirecting to login...").waitFor();
  assert.deepEqual(resetPayload, { token: "reset_browser-test", new_password: "NewPassword123!" });
  await mobile.close();

  const direct = await browser.newContext({ viewport: { width: 320, height: 568 }, isMobile: true, hasTouch: true });
  const directPage = await direct.newPage();
  await directPage.goto(`${origin}/request-password-reset`);
  assert.ok(await directPage.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1),
    "Request Password Reset fits a 320px mobile viewport");
  await directPage.getByRole("button", { name: "Back" }).click();
  await directPage.waitForURL("**/login");
  await direct.close();

  for (const viewport of [{ width: 390, height: 760 }, { width: 1366, height: 800 }]) {
    const context = await browser.newContext({ viewport, isMobile: viewport.width < 600, hasTouch: viewport.width < 600 });
    const adminPage = await context.newPage();
    await adminPage.addInitScript(() => {
      localStorage.setItem("user", JSON.stringify({ role: "admin", username: "Test Admin" }));
      localStorage.setItem("isLoggedIn", "true");
      localStorage.setItem("accessToken", "test-token");
    });
    const apiState = await mockApi(adminPage, undefined, undefined, { failAuxiliary: viewport.width > 600 });
    await adminPage.goto(`${origin}/admin/users?tab=system-users`);
    const cards = adminPage.getByRole("list", { name: "System users" }).locator("li");
    const rows = adminPage.locator("table.portal-table tbody tr");
    const items = viewport.width < 600 ? cards : rows;
    await items.first().waitFor();
    assert.equal(await items.count(), 10, "System Users defaults to 10 rows per page");
    assert.match(await items.first().innerText(), /Zoe/, "System Users keeps the API order");
    if (viewport.width < 600) {
      const sortField = adminPage.getByLabel("Sort by field");
      await sortField.selectOption("username");
      assert.match(await items.first().innerText(), /Amy/, "Mobile username sort starts ascending");
      await adminPage.getByRole("button", { name: /Change sort direction/ }).click();
      assert.match(await items.first().innerText(), /Zoe/, "Mobile direction control reverses the order");
    } else {
      const username = adminPage.getByRole("columnheader", { name: /Username/ });
      await username.getByRole("button").click();
      assert.match(await items.first().innerText(), /Amy/, "Desktop username sort starts ascending");
      await username.getByRole("button").click();
      assert.match(await items.first().innerText(), /Zoe/, "Desktop username sort toggles descending");
      assert.equal(await adminPage.getByRole("columnheader", { name: "Actions" }).getByRole("button").count(), 0,
        "Actions is not sortable");
    }

    await adminPage.getByRole("button", { name: "Next" }).click();
    await adminPage.getByText("Page 2 of 2").waitFor();
    assert.equal(await items.count(), 3, "Second page contains the remaining users");
    await adminPage.getByLabel("Rows Per Page").selectOption("20");
    await adminPage.getByText("Page 1 of 1").waitFor();
    assert.equal(await items.count(), 13, "Page size shows all matching users when set to 20");

    await adminPage.getByLabel("Search User").fill("amy");
    await adminPage.getByText("1 of 13 system users match the filters.").waitFor();
    assert.match(await items.first().innerText(), /Amy/, "Search matches full name");
    await adminPage.getByLabel("Search User").fill("a@example.test");
    assert.match(await items.first().innerText(), /Zoe/, "Search matches email");
    await adminPage.getByLabel("Search User").fill("member-10");
    assert.match(await items.first().innerText(), /Member 10/, "Search matches username");
    await adminPage.getByLabel("Search User").fill("");
    await adminPage.getByLabel("Agency", { exact: true }).selectOption("DOH");
    await adminPage.getByText("5 of 13 system users match the filters.").waitFor();
    await adminPage.getByLabel("Agency", { exact: true }).selectOption("");
    await adminPage.getByLabel("Role", { exact: true }).selectOption("validator");
    await adminPage.getByText("1 of 13 system users match the filters.").waitFor();
    assert.match(await items.first().innerText(), /Zoe/, "Role filter works on its own");
    await adminPage.getByLabel("Role", { exact: true }).selectOption("");
    await adminPage.getByLabel("Status", { exact: true }).selectOption("inactive");
    await adminPage.getByText("1 of 13 system users match the filters.").waitFor();
    assert.match(await items.first().innerText(), /Amy/, "Status filter works on its own");
    await adminPage.getByLabel("Status", { exact: true }).selectOption("");

    await adminPage.getByLabel("Search User").fill("ben");
    await adminPage.getByLabel("Agency", { exact: true }).selectOption("RDC-NCR");
    await adminPage.getByLabel("Role", { exact: true }).selectOption("contributor");
    await adminPage.getByLabel("Status", { exact: true }).selectOption("active");
    await adminPage.getByText("1 of 13 system users match the filters.").waitFor();
    assert.equal(await items.count(), 1, "Search, agency, role, and status combine");
    assert.match(await items.first().innerText(), /Ben/);
    const loadsBeforeRefresh = apiState.getUserLoads();
    const refreshed = adminPage.waitForResponse((response) => response.url().includes("/api/admin/users/") && response.request().method() === "GET");
    await adminPage.getByRole("button", { name: "Refresh Users" }).click();
    await refreshed;
    assert.ok(apiState.getUserLoads() > loadsBeforeRefresh, "Refresh refetches System Users");
    assert.equal(await adminPage.getByLabel("Search User").inputValue(), "ben", "Refresh preserves filters");
    assert.equal(await items.count(), 1);
    apiState.failNextUsersLoad();
    const failedRefresh = adminPage.waitForResponse((response) => response.url().includes("/api/admin/users/") && response.status() === 503);
    await adminPage.getByRole("button", { name: "Refresh Users" }).click();
    await failedRefresh;
    await adminPage.getByRole("alert").filter({ hasText: "Temporary user-list error" }).waitFor();
    assert.equal(await items.count(), 1, "A failed refresh keeps the visible user list");
    const recoveredRefresh = adminPage.waitForResponse((response) => response.url().includes("/api/admin/users/") && response.status() === 200);
    await adminPage.getByRole("button", { name: "Refresh Users" }).click();
    await recoveredRefresh;
    await adminPage.getByRole("alert").filter({ hasText: "Temporary user-list error" }).waitFor({ state: "hidden" });
    await items.first().getByRole("button", { name: "Reset Password" }).click();
    await adminPage.getByText("Password reset link sent to the user's email.").waitFor();
    await items.first().getByRole("button", { name: "Deactivate" }).click();
    await adminPage.getByText("No users match the selected filters.").waitFor();
    await adminPage.getByRole("button", { name: "Clear Filters" }).click();
    await adminPage.getByText("13 of 13 system users match the filters.").waitFor();
    assert.equal(await adminPage.getByLabel("Search User").inputValue(), "");
    assert.equal(await adminPage.getByLabel("Rows Per Page").inputValue(), "10");
    assert.equal(await items.count(), 10);
    assert.match(await items.first().innerText(), /Zoe/, "Clear Filters preserves the selected sort");
    await adminPage.getByLabel("Search User").fill("no such user");
    await adminPage.getByText("No users match the selected filters.").waitFor();
    const documentWidth = await adminPage.evaluate(() => document.documentElement.scrollWidth);
    assert.ok(documentWidth <= viewport.width + 1, `System Users fits ${viewport.width}px: ${documentWidth}`);
    await context.close();
  }
  console.log("PASS password reset and System Users filter browser checks");
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
