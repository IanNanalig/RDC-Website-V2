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
const respond = (route, body) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });

const nodeIds = [
  "chairperson", "vice-chair", "secretariat", "secretary", "executive-committee",
  "voting-members", "non-voting-members", "special-non-voting", "sectoral-committees",
  "special-committees", "affiliate-committees", "advisory-committee",
];
const committees = ["executive", "sectoral", "special", "affiliate", "advisory"].map((id) => ({
  id,
  title: `${id} committee`,
  description: `${id} description`,
  overview: `${id} overview`,
  functions: ["Coordinate regional work"],
  members: ["Member One"],
  icon: "building",
  color: "from-blue-500 to-blue-600",
}));
const sections = [
  { id: 41, section_key: "about-hero", section_type: "text", content_json: { title: "CMS About RDC", subtitle: "CMS subtitle" } },
  { id: 42, section_key: "legal-basis", section_type: "document_group", content_json: { title: "CMS Legal Basis", subtitle: "CMS legal subtitle", items: [{ id: "law", title: "Law without file", description: "Description", fileType: "PDF", url: "" }] } },
  { id: 43, section_key: "committees", section_type: "document_group", content_json: { title: "CMS Committees", subtitle: "CMS committee subtitle", items: committees } },
  { id: 44, section_key: "organization-structure", section_type: "text", content_json: { title: "CMS Organization", subtitle: "CMS organization subtitle", nodes: nodeIds.map((id) => ({ id, label: "Configured Group", title: `Configured ${id}`, subtitle: "Configured office", items: [] })) } },
  { id: 45, section_key: "resolutions-archive", section_type: "text", content_json: {
    title: "CMS Resolutions", subtitle: "CMS resolution subtitle", legendTitle: "CMS Legend", categoryTitle: "CMS Categories",
    legendItems: [{ label: "CMS Resolution Type", color: "blue" }, { label: "Sectoral Committee", color: "emerald" }], categoryItems: [{ title: "CMS Category", description: "CMS category description", color: "green" }],
    years: [{ year: 2025, resolutions: [
      { id: "resolution-2025", title: "CMS Resolution with spaces", url: "", legendItems: [{ label: "Sectoral Committee", color: "blue" }] },
      { id: "legacy-resolution-2025", title: "Legacy resolution without a legend", url: "" },
    ] }],
  } },
].map((section, index) => ({
  ...section,
  page: 4,
  order: index + 1,
  schema_version: 1,
  is_visible: true,
  status: "draft",
  is_locked: false,
  locked_by_me: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
}));
const aboutPage = {
  id: 4,
  title: "About RDC",
  slug: "about-rdc",
  status: "draft",
  has_unpublished_changes: true,
  published_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  section_count: sections.length,
  sections,
};
const publicPage = {
  slug: "about-rdc",
  title: "About RDC",
  sections: sections.map((section) => ({
    sectionKey: section.section_key,
    sectionType: section.section_type,
    order: section.order,
    content: section.content_json,
  })),
};

try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const homeSections = [
    { id: 11, section_key: "development-plans", section_type: "document_group", order: 2, content_json: {} },
    { id: 12, section_key: "dashboard-teaser" },
    { id: 13, section_key: "latest-media" },
    { id: 14, section_key: "upcoming-events" },
  ].map((section) => ({ page: 1, status: "published", ...section }));
  const homePage = { id: 1, title: "Home", slug: "home", status: "published", sections: homeSections };
  let updatedFeeds = false;
  let eventRequests = 0;
  let aboutDetailRequests = 0;
  let homeSectionLock = false;
  let transferSent = false;
  const savedRevision = "2026-01-02T08:00:00+08:00";
  const upcomingForum = {
    id: 7, event_type: "forum", title: "Public test forum", location: "Manila",
    start_at: new Date(Date.now() + 86400000).toISOString(), day: 30, month: "Nov", time: "9:00 AM",
  };
  const pastForum = { ...upcomingForum, id: 8, title: "Previously held forum", start_at: "2020-01-02T09:00:00+08:00" };
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.addInitScript(() => {
    localStorage.setItem("user", JSON.stringify({ id: 1, username: "admin", role: "admin" }));
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "about-cms-test-token");
  });
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path === "/api/public/cms/pages/about-rdc/") return respond(route, publicPage);
    if (path === "/api/public/cms/pages/news/") return respond(route, { slug: "news", sections: [] });
    if (path === "/api/public/cms/pages/home/") return respond(route, {
      slug: "home", sections: [
        { sectionKey: "investment-programming", content: {
          title: "Investment Programming", items: [{ id: "resource-a", title: "Resource retained", link: "/publications?category=rdip" }, { id: "resource-b", title: "Resource retained", description: "Second record" }],
          quickLinks: [
            { label: "Project dashboard", link: "/Projects" },
            { label: "RDIP publications", link: "/publications?category=rdip" },
            { label: "Broken quick link", link: "/no-such-public-page" },
          ],
        } },
      ],
    });
    if (path === "/api/public/cms/events/") {
      eventRequests += 1;
      const forum = updatedFeeds ? { ...upcomingForum, title: "Updated public forum", location: "Taguig" } : upcomingForum;
      return respond(route, { results: [pastForum, forum] });
    }
    if (path === "/api/public/cms/news/") {
      const release = { slug: "test-release", title: "Published test release", summary: "Public release summary", category: "Media Releases" };
      return respond(route, { results: [updatedFeeds ? { ...release, slug: "updated-release", title: "Updated published release" } : release] });
    }
    if (path === "/api/public/projects/stats/") {
      const ongoing = updatedFeeds ? 23 : 17;
      return respond(route, {
        total_projects: ongoing + 2, total_budget: 250000000, by_status: { Ongoing: ongoing, Completed: 2 },
        by_agency: { DPWH: ongoing + 2 }, by_year: { 2026: ongoing + 2 }, by_lgu: { Manila: ongoing + 2 },
      });
    }
    if (path === "/api/public/cms/pages/regional-profile/") return respond(route, {
      slug: "regional-profile", sections: [
        { sectionKey: "geographic-coverage", content: { mapAssetId: 99, mapImageUrl: "/missing-custom-map.png" } },
      ],
    });
    if (path === "/api/admin/cms/pages/4/" || path === "/api/admin/cms/modules/about-rdc/") {
      aboutDetailRequests += 1;
      return respond(route, aboutPage);
    }
    if (path === "/api/admin/cms/pages/4/discard-draft/") {
      assert.equal(route.request().postDataJSON().expected_updated_at, savedRevision);
      return respond(route, { ...aboutPage, status: "published", has_unpublished_changes: false, updated_at: "2026-01-03T08:00:00+08:00" });
    }
    if (path === "/api/admin/cms/pages/1/" || path === "/api/admin/cms/modules/home/") return respond(route, homePage);
    if (path === "/api/admin/cms/pages/") return respond(route, {
      results: [homePage, aboutPage].map(({ sections, ...summary }) => summary), count: 2, next: null, total_pages: 1,
    });
    if (path === "/api/admin/cms/sections/locks/") {
      const revision = homeSectionLock ? "locked" : "unlocked";
      const locks = homeSectionLock ? [{
        id: 11, is_locked: true, locked_by_me: false, lock_owner: 2, lock_version: "editor-lock",
        lock_owner_name: "Content Editor", access_requests: [{ id: 9, name: "Requesting Editor" }],
      }] : [{ id: 11, is_locked: false, locked_by_me: false, lock_version: "", access_requests: [] }];
      return respond(route, url.searchParams.get("revision") === revision ? { revision } : { revision, locks });
    }
    if (path === "/api/admin/cms/sections/11/manage-lock/") {
      assert.deepEqual(route.request().postDataJSON(), {
        confirmed: true, lock_version: "editor-lock", operation: "transfer", request_id: 9,
      });
      transferSent = true;
      homeSectionLock = false;
      return respond(route, { ...sections.find((row) => row.id === 11), is_locked: false, locked_by_me: false });
    }
    const lockMatch = path.match(/^\/api\/admin\/cms\/sections\/(\d+)\/(lock|unlock|heartbeat)\/$/);
    if (lockMatch) {
      const section = sections.find((row) => row.id === Number(lockMatch[1]));
      return respond(route, { ...section, is_locked: lockMatch[2] !== "unlock", locked_by_me: lockMatch[2] !== "unlock", lock_owner: 1, lock_owner_name: "Admin", edit_lease: "test-lease" });
    }
    const sectionMatch = path.match(/^\/api\/admin\/cms\/sections\/(\d+)\/$/);
    if (sectionMatch && route.request().method() === "PUT") {
      const section = sections.find((row) => row.id === Number(sectionMatch[1]));
      const { edit_lease: lease, expected_updated_at: _revision, ...content } = route.request().postDataJSON();
      assert.equal(lease, "test-lease");
      Object.assign(section, content);
      return respond(route, { ...section, page_revision: { status: "published", has_unpublished_changes: true, updated_at: savedRevision } });
    }
    if (path === "/api/admin/cms/media/") return respond(route, { results: [], count: 0, next: null, total_pages: 1 });
    if (path === "/api/admin/cms/articles/" || path === "/api/admin/cms/sections/" || path === "/api/admin/cms/forms/" || path === "/api/admin/cms/events/" || path === "/api/admin/cms/settings/") return respond(route, []);
    if (path === "/api/notifications/") return respond(route, { results: [], unread_count: 0 });
    return respond(route, []);
  });

  await page.goto(`${origin}/employee/cms/pages`);
  await page.locator('[data-cms-page-id="1"]').getByRole("button", { name: "Manage Content" }).click();
  await page.getByText(/Latest Media Releases, Regional Development Dashboard, and Upcoming Events update automatically/).waitFor();
  await page.locator('[data-cms-section-id="11"]').getByRole("button", { name: "Edit Content" }).waitFor();
  homeSectionLock = true;
  const transfer = page.getByRole("button", { name: "Transfer to Requesting Editor" });
  await transfer.waitFor({ timeout: 15_000 });
  page.once("dialog", (dialog) => dialog.accept());
  await transfer.click();
  await page.getByText("Editing access granted to Requesting Editor.").waitFor();
  assert.equal(transferSent, true);
  assert.equal(await page.locator('[data-cms-section-id="12"], [data-cms-section-id="13"], [data-cms-section-id="14"]').count(), 0);
  await page.locator('[data-cms-page-id="4"]').getByRole("button", { name: "Manage Content" }).click();
  await page.locator('[data-cms-section-id="44"]').getByRole("button", { name: "Edit Content" }).click();
  const childLabels = page.getByLabel("Child Labels (one per line)").first();
  await childLabels.and(page.locator(":enabled")).waitFor();
  await childLabels.pressSequentially("First child label with spaces");
  assert.equal(await childLabels.inputValue(), "First child label with spaces", "spaces remain while typing organization child labels");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Cancel" }).click();

  await page.locator('[data-cms-section-id="43"]').getByRole("button", { name: "Edit Content" }).click();
  assert.equal(await page.getByRole("button", { name: "Add Committee", exact: true }).count(), 0, "fixed committee entries cannot be added");
  assert.equal(await page.locator("[data-section-editor]").getByRole("button", { name: "Remove", exact: true }).count(), 0, "fixed committee entries cannot be removed");
  await page.locator("[data-section-editor] summary").filter({ hasText: /executive committee/i }).first().click();
  await page.getByRole("button", { name: "Add Committee Information", exact: true }).first().click();
  const functions = page.getByLabel("Functions (one per line)").first();
  await functions.fill("");
  await functions.pressSequentially("Plan and coordinate regional work");
  assert.equal(await functions.inputValue(), "Plan and coordinate regional work", "spaces remain while typing committee functions");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Cancel" }).click();
  await page.locator('[data-cms-section-id="45"]').getByRole("button", { name: "Edit Content" }).click();
  const year = page.locator("[data-section-editor] summary").filter({ hasText: "2025 (2)" });
  await year.press("Enter");
  const typeSelection = page.locator("label").filter({ has: page.getByText("Resolution Type", { exact: true }) }).locator("select");
  assert.equal(await typeSelection.inputValue(), "sectoral committee");
  const resolutionTitle = page.getByLabel("Resolution 1 Title");
  await resolutionTitle.fill("Draft title retained while collapsed");
  await year.press("Enter");
  await resolutionTitle.waitFor({ state: "hidden" });
  await year.press("Enter");
  assert.equal(await resolutionTitle.inputValue(), "Draft title retained while collapsed");
  const readsBeforeSave = aboutDetailRequests;
  await page.getByRole("button", { name: "Save Content Draft", exact: true }).click();
  await resolutionTitle.waitFor({ state: "hidden" });
  assert.equal(aboutDetailRequests, readsBeforeSave, "Saving a resolution draft does not reload the About page details");
  const aboutCard = page.locator('[data-cms-page-id="4"]');
  page.once("dialog", (dialog) => dialog.accept());
  await aboutCard.getByRole("button", { name: "Discard Draft Changes" }).click();
  await aboutCard.getByText("unpublished changes", { exact: true }).waitFor({ state: "hidden" });

  await page.goto(`${origin}/about`);
  await page.getByRole("heading", { name: "CMS About RDC" }).waitFor();
  await page.getByText("2025", { exact: true }).first().waitFor();
  assert.equal(await page.getByText("Archive 1", { exact: true }).count(), 0, "numeric CMS years are not replaced by an archive placeholder");
  const legalDocument = page.getByRole("heading", { name: "Law without file" });
  await legalDocument.waitFor();
  const legalCard = legalDocument.locator("xpath=../..");
  assert.equal(await legalCard.getByRole("button", { name: "View", exact: true }).and(legalCard.locator(":enabled")).count(), 0, "legal documents without a URL cannot open a blank tab");
  await page.getByRole("button", { name: /executive committee/i }).click();
  await page.getByRole("dialog").getByRole("heading", { name: "Functions" }).waitFor();
  await page.getByRole("dialog").getByText("Coordinate regional work", { exact: true }).waitFor();
  await page.getByRole("dialog").getByRole("button", { name: "Close committee details" }).click();
  await page.getByText("CMS Resolution Type", { exact: true }).waitFor();
  const configuredResolution = page.getByText("CMS Resolution with spaces", { exact: true }).locator("..");
  const sectoralBadge = configuredResolution.getByText("Sectoral Committee", { exact: true });
  assert.match(await sectoralBadge.getAttribute("class"), /bg-emerald-100/, "The shared legend overrides the per-resolution color");
  assert.equal(await configuredResolution.getByText("RDC Resolution", { exact: true }).count(), 0);
  const legacyResolution = page.getByText("Legacy resolution without a legend", { exact: true }).locator("..");
  await legacyResolution.getByText("RDC Resolution", { exact: true }).waitFor();
  const publishedLegend = publicPage.sections.find((section) => section.sectionKey === "resolutions-archive").content.legendItems;
  Object.assign(publishedLegend[1], { key: "sectoral committee", label: "Sectoral Committee Action", color: "purple" });
  await page.reload();
  const renamedBadge = configuredResolution.getByText("Sectoral Committee Action", { exact: true });
  assert.match(await renamedBadge.getAttribute("class"), /bg-purple-100/, "A linked badge follows changes to the shared legend");
  assert.equal(await page.getByText("CMS category description", { exact: true }).count(), 0);
  assert.equal(await page.getByText("-Infinity", { exact: true }).count(), 0, "resolution statistics never show -Infinity");

  await page.goto(`${origin}/`);
  await page.getByRole("heading", { name: "Resource retained" }).first().waitFor();
  assert.equal(await page.getByRole("heading", { name: "Resource retained" }).count(), 2);
  assert.equal(await page.getByRole("link", { name: "Project dashboard", exact: true }).count(), 0);
  assert.equal(await page.getByRole("link", { name: /Resource retained/ }).getAttribute("href"), "/publications?category=rdip");
  assert.equal(await page.getByRole("link", { name: "Broken quick link", exact: true }).count(), 0);
  await page.getByRole("heading", { name: "Regional Development Dashboard" }).waitFor();
  const ongoingStat = page.getByText("Ongoing Projects", { exact: true }).locator("..");
  await ongoingStat.getByText("17", { exact: true }).waitFor();
  await page.getByRole("heading", { name: "Latest Media Releases" }).scrollIntoViewIfNeeded();
  const release = page.locator("article").filter({ has: page.getByRole("heading", { name: "Published test release" }) });
  assert.equal(await release.getByRole("link", { name: "Read more" }).getAttribute("href"), "/news/test-release");
  await page.getByRole("heading", { name: "Upcoming Events" }).waitFor();
  await page.getByText("Public test forum", { exact: true }).waitFor();
  assert.equal(await page.getByText("Previously held forum", { exact: true }).count(), 0);
  const previewRequests = eventRequests;
  await page.getByRole("button", { name: "View Full Calendar" }).click();
  await page.getByRole("dialog").getByRole("heading", { name: "Previously held forum" }).waitFor();
  assert.equal(eventRequests, previewRequests, "Home preview and calendar share one request");
  await page.keyboard.press("Escape");
  await page.getByRole("dialog").waitFor({ state: "hidden" });
  await page.goto(`${origin}/news#events`);
  const calendar = page.locator("#events");
  try {
    await calendar.getByRole("heading", { name: "Public test forum" }).waitFor({ timeout: 5000 });
    await calendar.getByRole("combobox", { name: "Filter by event type" }).selectOption("meeting", { timeout: 5000 });
    await calendar.getByText("No events match this filter.").waitFor({ timeout: 5000 });
  } catch (error) {
    throw new Error(`Calendar check at ${page.url()}. Errors: ${pageErrors.join("; ")}. Calendar: ${await calendar.allInnerTexts()}`, { cause: error });
  }

  let mapRequests = 0;
  await page.route("**/missing-custom-map.png", (route) => {
    mapRequests += 1;
    return route.fulfill({ status: 404 });
  });
  await page.goto(`${origin}/regional-profile`);
  await page.getByAltText("Metro Manila Map").scrollIntoViewIfNeeded();
  await page.waitForFunction(() => document.querySelector('img[alt="Metro Manila Map"]')?.currentSrc.includes("ncr-map-"));
  assert.equal(mapRequests, 1);

  updatedFeeds = true;
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${origin}/`);
  await page.getByRole("heading", { name: "Latest Media Releases" }).scrollIntoViewIfNeeded();
  await page.getByRole("heading", { name: "Updated published release" }).waitFor();
  await ongoingStat.getByText("23", { exact: true }).waitFor();
  await page.getByText("Updated public forum", { exact: true }).waitFor();
  assert.equal(await page.getByText("Public test forum", { exact: true }).count(), 0);
  assert.equal(await page.getByRole("heading", { name: "Published test release" }).count(), 0);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));

  await context.close();
  console.log("PASS About RDC CMS typing, fixed structure, and public rendering checks");
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
