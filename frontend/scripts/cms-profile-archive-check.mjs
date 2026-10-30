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
    const mediaAssets = [
      {
        id: 1, file: "cms/manila.png", url: "data:image/png;base64,iVBORw0KGgo=", file_type: "image",
        mime_type: "image/png", size: 3145728, original_filename: "manila.png", alt_text: "Manila skyline",
        caption: "Manila", category: "Places", tags: ["capital"], is_archived: false,
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: 2, file: "cms/quezon-city.png", url: "data:image/png;base64,iVBORw0KGgo=", file_type: "image",
        mime_type: "image/png", size: 2097152, original_filename: "quezon-city.png", alt_text: "Quezon City hall",
        caption: "Quezon City", category: "Places", tags: ["government"], is_archived: false,
        created_at: "2026-01-02T00:00:00Z",
      },
    ];
    const section = {
      id: 11, page: 1, section_key: "hero-carousel", section_type: "hero_carousel",
      order: 1, content_json: { slides: [{ title: "Welcome", mediaAssetId: 1, imageAssetId: 1 }] }, schema_version: 1, is_visible: true,
      status: "published", is_locked: false, locked_by_me: false,
      created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
    };
    const cmsPage = {
      id: 1, title: "Home", slug: "home", status: "published",
      has_unpublished_changes: false, published_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z", sections: [section],
    };
    const profileSection = {
      id: 22, page: 2, section_key: "region-hero", section_type: "text",
      order: 1, content_json: { title: "Region Profile", subtitle: "NCR overview", body: "Preserved legacy body" }, schema_version: 1, is_visible: true,
      status: "published", is_locked: false, locked_by_me: false,
      created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
    };
    const profilePage = {
      id: 2, title: "Region Profile", slug: "regional-profile", status: "published",
      has_unpublished_changes: false, published_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z", sections: [profileSection],
    };
    const profile = { id: 1, username: "admin", first_name: "Admin", last_name: "User", email: "admin@example.com", role: "admin", agency: "RDC-NCR", agency_head: "Configured Council Head", office: "Office", division: "Planning", position: "Administrator", contact_number: "0212345678", phone_number: "09171234567", date_joined: "2026-01-01T00:00:00Z", recent_activity: [] };
    await page.addInitScript(() => { localStorage.setItem("user", JSON.stringify({ id: 1, username: "admin", role: "admin" })); localStorage.setItem("isLoggedIn", "true"); localStorage.setItem("accessToken", "cms-test-token"); });
    await page.route("**/api/**", async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;
      if (path === "/api/admin/cms/pages/1/") return respond(route, cmsPage);
      if (path === "/api/admin/cms/pages/2/") return respond(route, profilePage);
      if (path === "/api/admin/cms/pages/") return respond(route, { results: [{ ...cmsPage, sections: undefined, section_count: 1 }, { ...profilePage, sections: undefined, section_count: 1 }], count: 2, next: null, total_pages: 1 });
      if (path === "/api/admin/cms/sections/11/lock/" && route.request().method() === "POST") {
        sectionLocks += 1;
        return respond(route, { ...section, is_locked: true, locked_by_me: true, lock_owner: 1, lock_owner_name: "Admin User" });
      }
      if (path === "/api/admin/cms/sections/11/" && route.request().method() === "PUT") {
        Object.assign(section, route.request().postDataJSON(), { status: "draft", updated_at: "2026-01-02T00:00:00Z" });
        cmsPage.has_unpublished_changes = true;
        cmsPage.status = "draft";
        return respond(route, section);
      }
      if (path === "/api/admin/cms/sections/11/unlock/" && route.request().method() === "POST") return respond(route, section);
      if (path === "/api/admin/cms/sections/22/lock/" && route.request().method() === "POST") return respond(route, { ...profileSection, is_locked: true, locked_by_me: true, lock_owner: 1, lock_owner_name: "Admin User" });
      if (path === "/api/admin/cms/sections/22/unlock/" && route.request().method() === "POST") return respond(route, profileSection);
      if (path === "/api/admin/cms/media/") return respond(route, { results: mediaAssets, count: mediaAssets.length, next: null, total_pages: 1 });
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
    await page.getByText(/The five editable routes, layouts, and section order are application-controlled/).waitFor();
    assert.equal(await page.getByRole("button", { name: "Create Page" }).count(), 0, "Page creation is not exposed");
    assert.equal(await page.getByRole("button", { name: /Archive Page/i }).count(), 0, "Fixed pages cannot be archived");
    await page.locator('[data-cms-page-id="2"]').getByRole("button", { name: "Manage Content" }).click();
    await page.getByRole("heading", { name: /Sections for Page.*Region Profile/ }).waitFor();
    await page.locator('[data-cms-page-id="1"]').getByRole("button", { name: "Manage Content" }).click();
    await page.getByRole("heading", { name: /Sections for Page.*Home/ }).waitFor();
    await page.getByRole("button", { name: "Edit Content" }).click();
    await page.getByRole("heading", { name: "Edit Section" }).waitFor();
    assert.equal(sectionLocks, 1, "Opening fixed content acquires its existing section lock");
    await page.getByRole("tab", { name: "Content" }).click();
    assert.equal(await page.getByRole("tab", { name: "Visibility / Advanced" }).count(), 0, "Visibility controls are removed");
    assert.equal(await page.getByRole("tab", { name: "Basics" }).count(), 0, "Structural controls are removed");
    await page.getByRole("button", { name: "Choose from Media Library" }).click();
    const mediaSearch = page.getByRole("searchbox", { name: "Search Uploaded Image" });
    await mediaSearch.fill("Quezon government");
    await page.getByText("1 matching file", { exact: true }).waitFor();
    assert.equal(await page.getByRole("button", { name: /Quezon City/ }).count(), 1, "Search matches caption and tags");
    assert.equal(await page.getByRole("button", { name: /Manila/ }).count(), 0, "A selected non-match is not forced into search results");
    await page.getByRole("button", { name: /Quezon City/ }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();
    await page.getByText("Manila", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Choose from Media Library" }).click();
    await page.getByRole("searchbox", { name: "Search Uploaded Image" }).fill("Quezon government");
    await page.getByRole("button", { name: /Quezon City/ }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Confirm Selection" }).click();
    await page.getByText("Quezon City", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Choose from Media Library" }).click();
    const reopenedSearch = page.getByRole("searchbox", { name: "Search Uploaded Image" });
    await reopenedSearch.fill("missing asset");
    await page.getByText("0 matching files", { exact: true }).waitFor();
    await page.getByText("No library files match this search and filter.", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Close media library" }).click();
    await page.getByRole("button", { name: "Save Content Draft" }).click();
    await page.getByText("Section updated. Publish the page when ready.", { exact: true }).waitFor();
    await page.locator('[data-cms-page-id="1"]').getByText("unpublished changes", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Edit Content" }).click();
    await page.locator("[data-section-editor]").getByLabel("Title", { exact: true }).fill("Dirty page-switch check");
    page.once("dialog", (dialog) => dialog.accept());
    await page.locator('[data-cms-page-id="2"]').getByRole("button", { name: "Manage Content" }).click();
    await page.getByRole("heading", { name: /Sections for Page.*Region Profile/ }).waitFor();
    await page.getByRole("button", { name: "Edit Content" }).click();
    assert.equal(await page.getByLabel("Body Content").count(), 0, "Unused Region Profile hero body control is hidden");
    await page.getByRole("button", { name: "Close" }).click();

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
