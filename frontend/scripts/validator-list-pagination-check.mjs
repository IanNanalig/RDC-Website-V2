import assert from "node:assert/strict";
import { chromium } from "playwright-core";
import { preview } from "vite";

const server = await preview({ preview: { host: "127.0.0.1", port: 0 } });
const address = server.httpServer.address();
assert.ok(address && typeof address !== "string");
const origin = `http://127.0.0.1:${address.port}`;
const browser = await chromium.launch({
  executablePath: process.env.VALIDATOR_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  headless: true,
});

const initialProjects = Array.from({ length: 24 }, (_, index) => ({
  id: index + 1,
  title: `Project ${String(index + 1).padStart(2, "0")}`,
  agency: index % 2 ? "DOH" : "DENR",
  status: "completed",
  submitted_by_name: `Contributor ${index + 1}`,
  form_version: 1,
  current_form_version: 2,
  profile_data: { validator_review: { review_status: "endorsed" } },
}));

const respond = (route, body) => route.fulfill({
  status: 200,
  contentType: "application/json",
  body: JSON.stringify(body),
});

const expectFooter = async (page, first, last, total, current, pages) => {
  await page.getByText(`Showing ${first}–${last} of ${total} matching projects`).waitFor();
  await page.getByText(`Page ${current} of ${pages}`).waitFor();
  assert.equal(await page.getByRole("button", { name: "Previous" }).isDisabled(), current === 1);
  assert.equal(await page.getByRole("button", { name: "Next" }).isDisabled(), current === pages);
};

const openPage = async (path, width) => {
  const context = await browser.newContext({
    viewport: { width, height: 800 },
    isMobile: width < 600,
    hasTouch: width < 600,
  });
  const page = await context.newPage();
  let projects = [...initialProjects];
  const updatedIds = [];
  await page.addInitScript(() => {
    localStorage.setItem("user", JSON.stringify({ role: "validator", username: "Pagination Tester" }));
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "validator-pagination-test-token");
  });
  page.on("dialog", (dialog) => dialog.accept());
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const apiPath = url.pathname;
    if (apiPath.endsWith("/validator/projects/") && url.searchParams.get("scope") === "history") {
      return respond(route, projects);
    }
    if (apiPath.endsWith("/validator/projects/") && url.searchParams.get("scope") === "update_forms") {
      return respond(route, projects);
    }
    if (/\/validator\/projects\/\d+\/update-form\/$/.test(apiPath) && route.request().method() === "POST") {
      const id = Number(apiPath.match(/\/projects\/(\d+)\/update-form\/$/)?.[1]);
      updatedIds.push(id);
      projects = projects.filter((project) => project.id !== id);
      return respond(route, { detail: "Project form updated." });
    }
    if (apiPath.endsWith("/notifications/")) return respond(route, { results: [], unread_count: 0 });
    return respond(route, []);
  });
  await page.goto(`${origin}${path}`);
  return { context, page, updatedIds, setProjects: (next) => { projects = next; } };
};

try {
  for (const path of ["/validator/projects/history", "/validator/projects/update-forms"]) {
    for (const width of [320, 1280]) {
      const { context, page, updatedIds, setProjects } = await openPage(path, width);
      const isUpdate = path.endsWith("update-forms");
      const rowCount = () => page.locator("table.portal-table tbody tr").count();
      const cardCount = () => page.locator("article").count();
      try {
        await expectFooter(page, 1, 10, 24, 1, 3);
        assert.equal(await rowCount(), 10);
        assert.equal(await cardCount(), 10);
        await page.getByRole("button", { name: "Next" }).click();
        await expectFooter(page, 11, 20, 24, 2, 3);
        await page.getByRole("button", { name: "Next" }).click();
        await expectFooter(page, 21, 24, 24, 3, 3);
        assert.equal(await rowCount(), 4);
        assert.equal(await cardCount(), 4);

        if (isUpdate) {
          const lastRow = width < 600 ? page.locator("article").last() : page.locator("table.portal-table tbody tr").last();
          await lastRow.getByRole("button", { name: "Update Form" }).click();
          await expectFooter(page, 21, 23, 23, 3, 3);
          assert.deepEqual(updatedIds, [24], "The last-page Update Form action sends the correct project ID");
          assert.equal(await cardCount(), 3);
        }

        const search = page.getByPlaceholder(isUpdate
          ? "Search by project title, contributor, or agency"
          : "Search by title, agency, or contributor");
        await search.fill("Project 11");
        await expectFooter(page, 1, 1, 1, 1, 1);
        await search.fill("no matching project");
        await page.getByText(isUpdate ? "No matching projects found." : "No reviewed/endorsed projects found yet.").waitFor();
        assert.equal(await page.getByRole("button", { name: "Next" }).count(), 0);
        await search.fill("");
        await expectFooter(page, 1, 10, isUpdate ? 23 : 24, 1, 3);
        await page.getByRole("button", { name: "Next" }).click();
        await page.getByRole("button", { name: "Next" }).click();
        setProjects(initialProjects.slice(0, 11));
        await page.getByRole("button", { name: "Refresh" }).click();
        await expectFooter(page, 11, 11, 11, 2, 2);
        assert.equal(await rowCount(), 1);
        assert.equal(await cardCount(), 1);

        if (!isUpdate) {
          const lastRow = width < 600 ? page.locator("article").last() : page.locator("table.portal-table tbody tr").last();
          await lastRow.getByRole("button", { name: "View" }).click();
          await page.waitForURL("**/validator/projects/11/review");
        }

        const documentWidth = await page.evaluate(() => document.documentElement.scrollWidth);
        assert.ok(documentWidth <= width + 1, `${path} fits ${width}px: ${documentWidth}`);
      } finally {
        await context.close();
      }
    }
  }
  console.log("PASS validator history and older-form pagination browser checks");
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
