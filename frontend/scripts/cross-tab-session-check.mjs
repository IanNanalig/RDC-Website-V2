import assert from "node:assert/strict";
import { chromium } from "playwright-core";
import { preview } from "vite";

const browserPath = process.env.CMS_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const server = await preview({ preview: { host: "127.0.0.1", port: 0 } });
const address = server.httpServer.address();
assert.ok(address && typeof address !== "string");
const browser = await chromium.launch({ executablePath: browserPath, headless: true });

const activeUser = {
  id: 12,
  username: "active-admin",
  email: "admin@example.com",
  role: "admin",
  first_name: "Active",
  last_name: "Admin",
};

try {
  const context = await browser.newContext();
  await context.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (status, body) => route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
    if (path === "/api/auth/login/") {
      const body = route.request().postDataJSON();
      if (body.browser_refresh) {
        return json(409, { active_session: true, detail: "Already signed in", user: activeUser });
      }
      return json(200, { access: "access-admin", refresh: "refresh-admin", user: activeUser });
    }
    if (path === "/api/auth/me/") return json(200, activeUser);
    if (path === "/api/token/refresh/") {
      return json(200, { access: "access-admin-refreshed", refresh: "refresh-admin" });
    }
    return json(200, {});
  });

  const alreadyOpenTab = await context.newPage();
  await alreadyOpenTab.goto(`http://127.0.0.1:${address.port}/login`);
  await alreadyOpenTab.getByPlaceholder("Enter email").waitFor();

  const loginTab = await context.newPage();
  await loginTab.goto(`http://127.0.0.1:${address.port}/login`);
  await loginTab.getByPlaceholder("Enter email").fill(activeUser.email);
  await loginTab.getByPlaceholder("Enter password").fill("ValidPassword123!");
  await loginTab.getByRole("button", { name: "Login to RDC Portal" }).click();
  await loginTab.waitForURL("**/admin/dashboard");

  await alreadyOpenTab.waitForURL("**/admin/dashboard");
  assert.equal(await alreadyOpenTab.evaluate(() => JSON.parse(localStorage.getItem("user") || "{}").email), activeUser.email);

  const laterTab = await context.newPage();
  await laterTab.goto(`http://127.0.0.1:${address.port}/login`);
  await laterTab.waitForURL("**/admin/dashboard");
  assert.equal(await laterTab.getByPlaceholder("Enter email").count(), 0,
    "A newly opened tab should continue into the active account, not show the login form.");

  const guardedLogin = await laterTab.evaluate(async () => {
    const response = await fetch("/api/auth/login/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "different@example.com",
        password: "SomePassword123!",
        browser_refresh: localStorage.getItem("refreshToken"),
      }),
    });
    return { status: response.status, body: await response.json() };
  });
  assert.equal(guardedLogin.status, 409);
  assert.equal(guardedLogin.body.user.email, activeUser.email);
  assert.equal(await laterTab.evaluate(() => localStorage.getItem("refreshToken")), "refresh-admin");

  await context.close();

  const expiredContext = await browser.newContext();
  const expiredPage = await expiredContext.newPage();
  await expiredPage.addInitScript(() => {
    localStorage.setItem("user", JSON.stringify({ id: 12, role: "admin", username: "active-admin" }));
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "expired-access");
    localStorage.setItem("refreshToken", "revoked-refresh");
  });
  await expiredContext.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (status, body) => route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
    if (path === "/api/auth/me/" || path === "/api/token/refresh/") {
      return json(401, { detail: "This session expired because this account signed in from another browser or device." });
    }
    return json(200, {});
  });
  await expiredPage.goto(`http://127.0.0.1:${address.port}/login`);
  await expiredPage.getByText("Your account was signed in from another browser or device. Please login again.").waitFor();
  assert.equal(await expiredPage.evaluate(() => localStorage.getItem("refreshToken")), null);
  await expiredContext.close();

  console.log("PASS same-origin tabs share the active account, reject account replacement, and report revoked sessions");
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
