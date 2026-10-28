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
    let profileSaved = 0;
    let sectionLocks = 0;
    const section = {
      id: 11, page: 1, section_key: "hero-carousel", section_type: "hero_carousel",
      order: 1, content_json: { slides: [] }, schema_version: 1, is_visible: true,
      status: "published", is_locked: false, locked_by_me: false,
      created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
    };
    const cmsPage = {
      id: 1, title: "Home", slug: "home", status: "published",
      has_unpublished_changes: false, published_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z", sections: [section],
    };
    const profile = { id: 1, username: "admin", first_name: "Admin", last_name: "User", email: "admin@example.com", role: "admin", agency: "RDC-NCR", agency_head: "Configured Council Head", office: "Office", division: "Planning", position: "Administrator", contact_number: "0212345678", phone_number: "09171234567", date_joined: "2026-01-01T00:00:00Z", recent_activity: [] };
    await page.addInitScript(() => { localStorage.setItem("user", JSON.stringify({ id: 1, username: "admin", role: "admin" })); localStorage.setItem("isLoggedIn", "true"); localStorage.setItem("accessToken", "cms-test-token"); });
    await page.route("**/api/**", async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;
      if (path === "/api/admin/cms/pages/1/") return respond(route, cmsPage);
      if (path === "/api/admin/cms/pages/") return respond(route, { results: [{ ...cmsPage, sections: undefined, section_count: 1 }], count: 1, next: null, total_pages: 1 });
      if (path === "/api/admin/cms/sections/11/lock/" && route.request().method() === "POST") {
        sectionLocks += 1;
        return respond(route, { ...section, is_locked: true, locked_by_me: true, lock_owner: 1, lock_owner_name: "Admin User" });
      }
      if (path === "/api/admin/cms/sections/11/unlock/" && route.request().method() === "POST") return respond(route, section);
      if (path === "/api/admin/cms/media/") return respond(route, { results: [], count: 0, next: null, total_pages: 1 });
      if (path === "/api/profile/" && route.request().method() === "PATCH") { profileSaved += 1; Object.assign(profile, route.request().postDataJSON()); return respond(route, profile); }
      if (path === "/api/profile/") return respond(route, profile);
      if (path === "/api/admin/profiles/2/") return respond(route, { ...profile, id: 2, username: "other", first_name: "Other", last_name: "User" });
      if (path === "/api/profile/edit-requests/") return respond(route, [{ id: 3, status: "approved", expires_at: "2099-01-01T00:00:00Z" }]);
      if (path === "/api/admin/profile-edit-requests/") return respond(route, []);
      if (path === "/api/admin/cms/articles/") return respond(route, { results: [], count: 0, next: null, total_pages: 1 });
      if (path === "/api/admin/cms/sections/" || path === "/api/admin/cms/forms/" || path === "/api/admin/cms/events/" || path === "/api/admin/cms/settings/") return respond(route, []);
      if (path === "/api/notifications/") return respond(route, { results: [], unread_count: 0 });
      return respond(route, []);
    });

    await page.goto(`${origin}/employee/cms/pages`);
    await page.getByRole("heading", { name: "Fixed Public Content Modules" }).waitFor();
    await page.getByText("The seven routes, layouts, and section order are application-controlled.").waitFor();
    assert.equal(await page.getByRole("button", { name: "Create Page" }).count(), 0, "Page creation is not exposed");
    assert.equal(await page.getByRole("button", { name: /Archive Page/i }).count(), 0, "Fixed pages cannot be archived");
    await page.getByRole("button", { name: "Edit Content" }).click();
    await page.getByRole("heading", { name: "Edit Section" }).waitFor();
    assert.equal(sectionLocks, 1, "Opening fixed content acquires its existing section lock");
    await page.getByRole("tab", { name: "Content" }).click();
    assert.equal(await page.getByRole("tab", { name: "Visibility / Advanced" }).count(), 0, "Visibility controls are removed");
    assert.equal(await page.getByRole("tab", { name: "Basics" }).count(), 0, "Structural controls are removed");

    await page.goto(`${origin}/profile`);
    await page.getByRole("heading", { name: "Profile details" }).waitFor();
    await page.getByText("Configured Council Head", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Edit Profile" }).click();
    assert.equal(await page.getByLabel("Current Head of Agency", { exact: true }).count(), 0, "Agency head is read-only on profiles");
    await page.getByLabel("First Name", { exact: true }).fill("Updated");
    await page.getByRole("button", { name: "Save Profile" }).click();
    await page.getByText("Profile updated. This approval has been used.").waitFor();
    assert.equal(profileSaved, 1);
    await page.goto(`${origin}/admin/profiles/2`);
    await page.getByRole("heading", { name: "Other User" }).waitFor();
    assert.equal(await page.getByRole("button", { name: "Edit Profile" }).count(), 0, "Other users' profiles remain read-only");
    await context.close();
  }
  console.log("PASS fixed CMS structure and authoritative profile agency-head browser checks");
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
