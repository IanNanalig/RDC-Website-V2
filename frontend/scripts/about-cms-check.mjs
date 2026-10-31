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
  { id: 45, section_key: "resolutions-archive", section_type: "text", content_json: { title: "CMS Resolutions", subtitle: "CMS resolution subtitle", legendTitle: "CMS Legend", categoryTitle: "CMS Categories", legendItems: [{ label: "CMS Resolution Type", color: "blue" }], categoryItems: [{ title: "CMS Category", description: "CMS category description", color: "green" }], years: [{ year: 2025, resolutions: [{ id: "resolution-2025", title: "CMS Resolution with spaces", url: "" }] }] } },
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
  await page.addInitScript(() => {
    localStorage.setItem("user", JSON.stringify({ id: 1, username: "admin", role: "admin" }));
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "about-cms-test-token");
  });
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path === "/api/public/cms/pages/about-rdc/") return respond(route, publicPage);
    if (path === "/api/admin/cms/pages/4/" || path === "/api/admin/cms/modules/about-rdc/") return respond(route, aboutPage);
    if (path === "/api/admin/cms/pages/") return respond(route, { results: [{ ...aboutPage, sections: undefined }], count: 1, next: null, total_pages: 1 });
    const lockMatch = path.match(/^\/api\/admin\/cms\/sections\/(\d+)\/(lock|unlock|heartbeat)\/$/);
    if (lockMatch) {
      const section = sections.find((row) => row.id === Number(lockMatch[1]));
      return respond(route, { ...section, is_locked: lockMatch[2] !== "unlock", locked_by_me: lockMatch[2] !== "unlock", lock_owner: 1, lock_owner_name: "Admin" });
    }
    const sectionMatch = path.match(/^\/api\/admin\/cms\/sections\/(\d+)\/$/);
    if (sectionMatch && route.request().method() === "PUT") {
      const section = sections.find((row) => row.id === Number(sectionMatch[1]));
      Object.assign(section, route.request().postDataJSON());
      return respond(route, section);
    }
    if (path === "/api/admin/cms/media/") return respond(route, { results: [], count: 0, next: null, total_pages: 1 });
    if (path === "/api/admin/cms/articles/" || path === "/api/admin/cms/sections/" || path === "/api/admin/cms/forms/" || path === "/api/admin/cms/events/" || path === "/api/admin/cms/settings/") return respond(route, []);
    if (path === "/api/notifications/") return respond(route, { results: [], unread_count: 0 });
    return respond(route, []);
  });

  await page.goto(`${origin}/employee/cms/pages`);
  await page.locator('[data-cms-page-id="4"]').getByRole("button", { name: "Manage Content" }).click();
  await page.locator('[data-cms-section-id="44"]').getByRole("button", { name: "Edit Content" }).click();
  const childLabels = page.getByLabel("Child Labels (one per line)").first();
  await childLabels.pressSequentially("First child label with spaces");
  assert.equal(await childLabels.inputValue(), "First child label with spaces", "spaces remain while typing organization child labels");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Cancel" }).click();

  await page.locator('[data-cms-section-id="43"]').getByRole("button", { name: "Edit Content" }).click();
  assert.equal(await page.getByRole("button", { name: "Add Committee" }).count(), 0, "fixed committee entries cannot be added");
  assert.equal(await page.locator("[data-section-editor]").getByRole("button", { name: "Remove", exact: true }).count(), 0, "fixed committee entries cannot be removed");
  const functions = page.getByLabel("Functions (one per line)").first();
  await functions.fill("");
  await functions.pressSequentially("Plan and coordinate regional work");
  assert.equal(await functions.inputValue(), "Plan and coordinate regional work", "spaces remain while typing committee functions");

  await page.goto(`${origin}/about`);
  await page.getByRole("heading", { name: "CMS About RDC" }).waitFor();
  await page.getByText("2025", { exact: true }).first().waitFor();
  assert.equal(await page.getByText("Archive 1", { exact: true }).count(), 0, "numeric CMS years are not replaced by an archive placeholder");
  assert.equal(await page.getByRole("button", { name: "View", exact: true }).isDisabled(), true, "legal documents without a URL cannot open a blank tab");
  await page.getByRole("button", { name: /executive committee/i }).click();
  await page.getByRole("dialog").getByRole("heading", { name: "Functions" }).waitFor();
  await page.getByRole("dialog").getByText("Coordinate regional work", { exact: true }).waitFor();
  await page.getByRole("dialog").getByRole("button", { name: "Close committee details" }).click();
  await page.getByText("CMS Resolution Type", { exact: true }).waitFor();
  await page.getByText("CMS category description", { exact: true }).waitFor();
  assert.equal(await page.getByText("-Infinity", { exact: true }).count(), 0, "resolution statistics never show -Infinity");

  await context.close();
  console.log("PASS About RDC CMS typing, fixed structure, and public rendering checks");
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
