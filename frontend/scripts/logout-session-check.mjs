import assert from "node:assert/strict";
import { setTimeout as delay } from "node:timers/promises";
import { chromium } from "playwright-core";
import { preview } from "vite";

const browserPath = process.env.CMS_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const server = await preview({ preview: { host: "127.0.0.1", port: 0 } });
const address = server.httpServer.address();
assert.ok(address && typeof address !== "string");
const frontendUrl = `http://127.0.0.1:${address.port}`;
const browser = await chromium.launch({ executablePath: browserPath, headless: true });
const replacedDetail = "This session expired because this account signed in from another browser or device.";

async function createPage({ logoutStatus = 200, sessionReplaced = false, holdNotification = false, holdRefresh = false } = {}) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.addInitScript(() => {
    if (window.location.pathname === "/login") return;
    localStorage.setItem("user", JSON.stringify({ role: "admin", username: "Logout Tester" }));
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "test-access");
    localStorage.setItem("refreshToken", "test-refresh");
  });

  let notificationCount = 0;
  let releaseHeldNotification;
  const notificationHeld = new Promise((resolve) => {
    releaseHeldNotification = resolve;
  });
  let releaseHeldRefresh;
  const refreshHeld = new Promise((resolve) => {
    releaseHeldRefresh = resolve;
  });

  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (status, body) => route.fulfill({
      status, contentType: "application/json", body: JSON.stringify(body),
    });
    if (path === "/api/notifications/") {
      notificationCount += 1;
      if (holdNotification && notificationCount === 2) {
        releaseHeldNotification(route);
        return;
      }
      return json(200, { results: [], unread_count: 0 });
    }
    if (path === "/api/auth/logout/") {
      return json(logoutStatus, logoutStatus === 200 ? { status: "ok" } : { detail: replacedDetail });
    }
    if (path === "/api/auth/me/") {
      return json(sessionReplaced ? 401 : 200, sessionReplaced ? { detail: replacedDetail } : { id: 1 });
    }
    if (path === "/api/dashboard/" && sessionReplaced) {
      return json(401, { detail: replacedDetail });
    }
    if (path === "/api/token/refresh/") {
      if (holdRefresh) {
        releaseHeldRefresh(route);
        return;
      }
      return json(401, { detail: replacedDetail });
    }
    return json(200, {});
  });

  return { context, page, notificationHeld, refreshHeld };
}

try {
  {
    const { context, page, notificationHeld } = await createPage({ holdNotification: true });
    const firstNotification = page.waitForResponse((response) =>
      new URL(response.url()).pathname === "/api/notifications/" && response.status() === 200);
    await page.goto(`${frontendUrl}/admin/dashboard`);
    await firstNotification;
    await page.evaluate(() => window.dispatchEvent(new CustomEvent("portal:data-changed")));
    const heldRoute = await notificationHeld;
    await page.getByRole("button", { name: "Logout" }).click();
    await page.waitForURL("**/login");
    await heldRoute.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: replacedDetail }) });
    await delay(150);
    assert.equal(await page.evaluate(() => localStorage.getItem("sessionMessage")), null,
      "A late request from an intentional logout must not create a replacement warning");
    assert.equal(await page.getByText(/Your account was signed in from another browser/).count(), 0);
    await page.route("**/api/auth/login/", (route) => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify({
        access: "new-access", refresh: "new-refresh",
        user: { id: 1, role: "admin", username: "Logout Tester" },
      }),
    }));
    await page.getByPlaceholder("Enter email").fill("admin@example.com");
    await page.getByPlaceholder("Enter password").fill("TestPassword123!");
    const freshDashboard = page.waitForResponse((response) =>
      new URL(response.url()).pathname === "/api/dashboard/" && response.status() === 200);
    await page.getByRole("button", { name: "Login to RDC Portal" }).click();
    await page.waitForURL("**/admin/dashboard");
    await freshDashboard;
    await page.route("**/api/dashboard/", (route) => route.fulfill({
      status: 401, contentType: "application/json", body: JSON.stringify({ detail: replacedDetail }),
    }));
    await page.evaluate(() => window.dispatchEvent(new CustomEvent("portal:data-changed")));
    await page.waitForURL("**/login");
    await page.getByText("Your account was signed in from another browser or device. Please login again.").waitFor();
    await context.close();
    console.log("PASS logout ignores a late unauthorized request and a new login restores normal session checks");
  }

  {
    const { context, page } = await createPage({ logoutStatus: 401 });
    await page.goto(`${frontendUrl}/admin/dashboard`);
    await page.getByRole("button", { name: "Logout" }).click();
    await page.waitForURL("**/login");
    assert.equal(await page.evaluate(() => localStorage.getItem("sessionMessage")), null,
      "A rejected logout request must still sign out without a false warning");
    await context.close();
    console.log("PASS rejected logout signs out without a replacement warning");
  }

  {
    const { context, page, refreshHeld } = await createPage({ sessionReplaced: true, holdRefresh: true });
    await page.goto(`${frontendUrl}/admin/dashboard`);
    const heldRoute = await refreshHeld;
    await page.getByRole("button", { name: "Logout" }).click();
    await page.waitForURL("**/login");
    await heldRoute.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
      access: "late-access", refresh: "late-refresh",
    }) });
    await delay(150);
    assert.equal(await page.evaluate(() => localStorage.getItem("accessToken")), null,
      "A late refresh must not restore the access token after logout");
    assert.equal(await page.evaluate(() => localStorage.getItem("refreshToken")), null,
      "A late refresh must not restore the refresh token after logout");
    await context.close();
    console.log("PASS late token refresh cannot restore a logged-out session");
  }

  {
    const { context, page } = await createPage({ sessionReplaced: true });
    await page.goto(`${frontendUrl}/admin/dashboard`, { waitUntil: "domcontentloaded" });
    await page.waitForURL("**/login");
    await page.getByText("Your account was signed in from another browser or device. Please login again.").waitFor();
    await context.close();
    console.log("PASS genuine session replacement still shows the warning");
  }
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
