import assert from "node:assert/strict";
import { chromium } from "playwright-core";
import { preview } from "vite";

const server = await preview({ preview: { host: "127.0.0.1", port: 0 } });
const address = server.httpServer.address();
assert.ok(address && typeof address !== "string");
const origin = `http://127.0.0.1:${address.port}`;
const browser = await chromium.launch({ executablePath: process.env.CMS_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", headless: true });
const respond = (route, body) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });

try {
  for (const width of [390, 1280]) {
    const context = await browser.newContext({ viewport: { width, height: 800 }, isMobile: width < 600, hasTouch: width < 600 });
    const page = await context.newPage();
    let archived = true;
    let restored = 0;
    let profileSaved = 0;
    const profile = { id: 1, username: "admin", full_name: "Admin User", email: "admin@example.com", role: "admin", agency: "RDC-NCR", agency_head: "", office: "Office", division: "", position: "", contact_number: "", phone_number: "", date_joined: "2026-01-01T00:00:00Z", recent_activity: [] };
    await page.addInitScript(() => { localStorage.setItem("user", JSON.stringify({ id: 1, username: "admin", role: "admin" })); localStorage.setItem("isLoggedIn", "true"); localStorage.setItem("accessToken", "cms-test-token"); });
    await page.route("**/api/**", async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;
      if (path === "/api/admin/cms/pages/1/restore/" && route.request().method() === "POST") { archived = false; restored += 1; return respond(route, {}); }
      if (path === "/api/admin/cms/pages/1/") return respond(route, { id: 1, title: "Home", slug: "home", status: "draft", sections: [], updated_at: "2026-01-01T00:00:00Z" });
      if (path === "/api/admin/cms/pages/") return respond(route, { results: url.searchParams.get("archived") === "1" ? archived ? [{ id: 1, title: "Archived Home", slug: "archived-home", status: "archived" }] : [] : [{ id: 1, title: "Home", slug: "home", status: "draft", updated_at: "2026-01-01T00:00:00Z", sections: [] }], count: 1, next: null, total_pages: 1 });
      if (path === "/api/admin/cms/media/") return respond(route, { results: [], count: 0, next: null, total_pages: 1 });
      if (path === "/api/profile/" && route.request().method() === "PATCH") { profileSaved += 1; Object.assign(profile, route.request().postDataJSON()); return respond(route, profile); }
      if (path === "/api/profile/") return respond(route, profile);
      if (path === "/api/admin/profiles/2/") return respond(route, { ...profile, id: 2, username: "other", full_name: "Other User" });
      if (path === "/api/profile/edit-requests/") return respond(route, [{ id: 3, status: "approved", expires_at: "2099-01-01T00:00:00Z" }]);
      if (path === "/api/admin/profile-edit-requests/") return respond(route, []);
      if (path === "/api/admin/cms/articles/") return respond(route, { results: [], count: 0, next: null, total_pages: 1 });
      if (path === "/api/admin/cms/sections/" || path === "/api/admin/cms/forms/" || path === "/api/admin/cms/events/" || path === "/api/admin/cms/settings/") return respond(route, []);
      if (path === "/api/notifications/") return respond(route, { results: [], unread_count: 0 });
      return respond(route, []);
    });

    await page.goto(`${origin}/employee/cms/pages`);
    const headings = ["Public Website Pages", "Edit Page Draft", "Sections for Page", "Edit Section"];
    const positions = [];
    for (const heading of headings) {
      const element = page.getByRole("heading", { name: new RegExp(heading) }).first();
      await element.waitFor();
      positions.push((await element.boundingBox()).y);
    }
    assert.deepEqual([...positions].sort((a, b) => a - b), positions, "CMS cards follow the requested top-to-bottom order");
    await page.getByRole("tab", { name: "Content" }).click();
    await page.getByRole("tab", { name: "Visibility / Advanced" }).click();
    await page.getByRole("tab", { name: "Basics" }).click();
    await page.getByRole("button", { name: "Archived", exact: true }).click();
    await page.getByRole("heading", { name: "Pages (1)" }).waitFor();
    await page.getByRole("button", { name: "Restore as Draft" }).click();
    await page.getByRole("heading", { name: "Pages (0)" }).waitFor();
    assert.equal(restored, 1);

    await page.goto(`${origin}/profile`);
    await page.getByRole("heading", { name: "Profile details" }).waitFor();
    await page.getByRole("button", { name: "Edit Profile" }).click();
    await page.getByLabel("Name", { exact: true }).fill("Updated Admin");
    await page.getByRole("button", { name: "Save Profile" }).click();
    await page.getByText("Profile updated. This approval has been used.").waitFor();
    assert.equal(profileSaved, 1);
    await page.goto(`${origin}/admin/profiles/2`);
    await page.getByRole("heading", { name: "Other User" }).waitFor();
    assert.equal(await page.getByRole("button", { name: "Edit Profile" }).count(), 0, "Other users' profiles remain read-only");
    await context.close();
  }
  console.log("PASS CMS card order, section tabs, archive restore, and profile browser checks");
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
