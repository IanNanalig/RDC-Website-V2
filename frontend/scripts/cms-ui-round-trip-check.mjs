import assert from "node:assert/strict";
import { chromium } from "playwright-core";

const frontendUrl = process.env.CMS_TEST_FRONTEND_URL || "http://127.0.0.1:5173";
const apiUrl = process.env.CMS_TEST_API_URL || "http://127.0.0.1:8000/api";
const email = process.env.CMS_TEST_EMAIL;
const password = process.env.CMS_TEST_PASSWORD;
const edgePath = process.env.CMS_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";

if (!email || !password) {
  throw new Error("Set CMS_TEST_EMAIL and CMS_TEST_PASSWORD for the disposable CMS test account.");
}

const listFromResponse = (value) => {
  if (Array.isArray(value)) return value;
  return Array.isArray(value?.results) ? value.results : [];
};

const loginResponse = await fetch(`${apiUrl}/auth/login/`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email, password }),
});
if (!loginResponse.ok) throw new Error(`Disposable CMS login failed (${loginResponse.status}).`);
const login = await loginResponse.json();
const authHeaders = { Authorization: `Bearer ${login.access}` };

const fetchJson = async (path) => {
  const response = await fetch(`${apiUrl}/${path}`, { headers: authHeaders });
  if (!response.ok) throw new Error(`CMS request failed for ${path} (${response.status}).`);
  return response.json();
};

const pages = listFromResponse(await fetchJson("admin/cms/pages/"));
const sections = listFromResponse(await fetchJson("admin/cms/sections/"))
  .filter((section) => section.status !== "archived")
  .sort((left, right) => left.page - right.page || left.order - right.order || left.id - right.id);
const settings = listFromResponse(await fetchJson("admin/cms/settings/"));
const registeredTypes = new Set([
  "hero_carousel",
  "publication_catalog",
  "document_group",
  "dashboard_teaser",
  "news_preview",
  "events_preview",
  "contact_info",
  "location_map",
  "form_intro",
  "text",
  "image_text",
  "cards",
  "faq",
]);

const browser = await chromium.launch({ executablePath: edgePath, headless: true });
const page = await browser.newPage();
page.on("dialog", async (dialog) => dialog.accept());

await page.addInitScript((session) => {
  localStorage.setItem("accessToken", session.access);
  localStorage.setItem("refreshToken", session.refresh);
  localStorage.setItem("user", JSON.stringify(session.user));
  localStorage.setItem("isLoggedIn", "true");
  localStorage.setItem("username", session.user.username);
}, login);

await page.goto(`${frontendUrl}/admin/content`, { waitUntil: "networkidle" });
await page.getByRole("heading", { name: "Website CMS" }).waitFor();
assert.equal(await page.locator("pre").count(), 0, "Raw JSON preview boxes are visible in normal mode.");
assert.equal(await page.locator('textarea[aria-label*="source"]').count(), 0, "Raw source editor is visible in normal mode.");
assert.equal(await page.getByRole("button", { name: /Developer Tools/ }).count(), 0, "Developer Tools control is visible.");

let activePageId = null;
for (const section of sections) {
  const cmsPage = pages.find((candidate) => candidate.id === section.page);
  assert.ok(cmsPage, `Missing page ${section.page} for section ${section.id}.`);

  if (activePageId !== section.page) {
    const pageCard = page.locator(`[data-cms-page-id="${section.page}"]`);
    await pageCard.waitFor();
    await pageCard.getByRole("button", { name: "Edit", exact: true }).click();
    activePageId = section.page;
  }

  const before = await fetchJson(`admin/cms/sections/${section.id}/`);
  const sectionCard = page.locator(`[data-cms-section-id="${section.id}"]`);
  await sectionCard.waitFor();
  await sectionCard.getByRole("button", { name: "Edit", exact: true }).click();
  await page.getByRole("heading", { name: "Edit Section Block" }).waitFor();
  assert.equal(await page.locator("pre").count(), 0, `Raw JSON preview visible for ${section.section_type}/${section.section_key}.`);
  assert.equal(await page.locator('textarea[aria-label*="source"]').count(), 0, `Raw source visible for ${section.section_type}/${section.section_key}.`);
  assert.equal(
    await page.getByRole("heading", { name: "Unsupported Section", exact: true }).count(),
    registeredTypes.has(section.section_type) ? 0 : 1,
    `Visual-editor registration mismatch for ${section.section_type}/${section.section_key}.`,
  );

  const [saveResponse] = await Promise.all([
    page.waitForResponse((response) =>
      response.url().includes(`/admin/cms/sections/${section.id}/`) &&
      response.request().method() === "PUT",
    ),
    page.getByRole("button", { name: "Save Section Draft", exact: true }).click(),
  ]);
  if (!saveResponse.ok()) {
    throw new Error(
      `${section.section_type}/${section.section_key} save failed (${saveResponse.status()}): ${await saveResponse.text()}`,
    );
  }
  await page.getByText("Section updated. Publish the page when ready.").waitFor();

  const after = await fetchJson(`admin/cms/sections/${section.id}/`);
  assert.deepStrictEqual(
    after.content_json,
    before.content_json,
    `${section.section_type}/${section.section_key} changed content_json during a no-change visual save.`,
  );
  console.log(`PASS ${cmsPage.slug}: ${section.section_type}/${section.section_key}`);
}

await page.getByRole("button", { name: "Site Settings", exact: true }).click();
await page.getByRole("heading", { name: "Branding and Contact" }).waitFor();
assert.equal(await page.locator('textarea[aria-label*="source"]').count(), 0, "Raw setting source is visible in normal mode.");
for (const setting of settings) {
  const settingCard = page.locator(`[data-cms-setting-key="${setting.key}"]`);
  await settingCard.waitFor();
  const [saveResponse] = await Promise.all([
    page.waitForResponse((response) =>
      response.url().includes(`/admin/cms/settings/${setting.key}/`) &&
      response.request().method() === "PATCH",
    ),
    settingCard.getByRole("button", { name: "Save Setting", exact: true }).click(),
  ]);
  if (!saveResponse.ok()) {
    throw new Error(`Setting ${setting.key} save failed (${saveResponse.status()}): ${await saveResponse.text()}`);
  }
  const after = await fetchJson(`admin/cms/settings/${setting.key}/`);
  assert.deepStrictEqual(after.value_json, setting.value_json, `${setting.key} changed value_json during a no-change visual save.`);
  console.log(`PASS setting: ${setting.key}`);
}

await browser.close();
console.log(`PASS ${sections.length}/${sections.length} isolated test sections preserved through the visual CMS open/save flow.`);
console.log(`PASS ${settings.length}/${settings.length} existing settings preserved through the grouped visual form save flow.`);
console.log(`Covered section types: ${[...new Set(sections.map((section) => section.section_type))].sort().join(", ")}`);
