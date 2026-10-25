import assert from "node:assert/strict";
import { chromium } from "playwright-core";
import { preview } from "vite";

const server = await preview({ preview: { host: "127.0.0.1", port: 0 } });
const address = server.httpServer.address();
assert.ok(address && typeof address !== "string");
const origin = `http://127.0.0.1:${address.port}`;
const browser = await chromium.launch({
  executablePath: process.env.PROJECT_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  headless: true,
});

const initialProjects = Array.from({ length: 24 }, (_, index) => {
  const number = index + 1;
  return {
    id: number,
    title: `Project ${String(number).padStart(2, "0")}`,
    agency: number % 2 ? "DENR" : "DOH",
    status: number % 2 ? "proposed" : "completed",
    workflow_status: number % 2 ? "pending_validation" : "validated",
    submitted_by_name: `Contributor ${number}`,
    rdip_status: number === 24 ? "Completed" : "Ongoing",
    profile_data: {
      validator_review: {
        review_status: number % 3 === 0 ? "reviewed" : "endorsed",
        edited: number % 2 === 0,
        edited_fields_count: number % 2,
      },
    },
  };
});

const revisions = [1, 2].map((number) => ({
  id: 100 + number,
  project: number,
  project_title: `Project ${String(number).padStart(2, "0")}`,
  project_agency: number % 2 ? "DENR" : "DOH",
  revision_number: number,
  state: "submitted",
  submission_type: "simplified",
  profile_data_snapshot: { submission_type: "simplified", simplified_form: {} },
}));

const json = (route, body) => route.fulfill({
  status: 200,
  contentType: "application/json",
  body: JSON.stringify(body),
});

const expectFooter = async (page, start, end, total, noun, current, count) => {
  await page.getByText(`Showing ${start}–${end} of ${total} matching ${noun}`).waitFor();
  await page.getByText(`Page ${current} of ${count}`).waitFor();
  const previous = page.getByRole("button", { name: "Previous" });
  const next = page.getByRole("button", { name: "Next" });
  assert.equal(await previous.isDisabled(), current === 1);
  assert.equal(await next.isDisabled(), current === count);
};

const openListing = async (role, pathname, width) => {
  const context = await browser.newContext({
    viewport: { width, height: 800 },
    isMobile: width < 600,
    hasTouch: width < 600,
  });
  const page = await context.newPage();
  let projects = [...initialProjects];
  const archived = [];
  let delayNextProjectResponse = false;
  let signalDelayedProjectResponseStarted = () => {};
  let delayedProjectResponseStarted = Promise.resolve();
  await page.addInitScript((currentRole) => {
    window.__portalIntervalDelays = [];
    const originalSetInterval = window.setInterval.bind(window);
    window.setInterval = ((handler, timeout, ...arguments_) => {
      window.__portalIntervalDelays.push(Number(timeout));
      return originalSetInterval(handler, timeout, ...arguments_);
    });
    localStorage.setItem("user", JSON.stringify({ role: currentRole, username: "Pagination Tester", agency: "DENR" }));
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "pagination-test-token");
  }, role);
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path.includes("/admin/projects/") && path.endsWith("/archive/") && route.request().method() === "POST") {
      const id = Number(path.match(/\/projects\/(\d+)\/archive\/$/)?.[1]);
      const payload = route.request().postDataJSON();
      assert.equal(payload.confirm_archive, true);
      assert.equal(payload.expected_implementation_status, id === 24 ? "Completed" : "Ongoing");
      archived.push(id);
      projects = projects.filter((project) => project.id !== id);
      return json(route, {});
    }
    if (path.endsWith("/project-revisions/")) return json(route, revisions);
    if (path.endsWith("/admin/projects/") || path.endsWith("/validator/projects/") || path.endsWith("/employee/projects/")) {
      const snapshot = [...projects];
      if (delayNextProjectResponse) {
        delayNextProjectResponse = false;
        signalDelayedProjectResponseStarted();
        await new Promise((resolve) => setTimeout(resolve, 350));
      }
      return json(route, snapshot);
    }
    if (path.endsWith("/encoding-window/") || path.endsWith("/progress-update-window/")) {
      return json(route, { can_encode: true, is_open: true, enabled: true, status_code: "open" });
    }
    if (path.endsWith("/notifications/")) return json(route, { results: [], unread_count: 0 });
    return json(route, []);
  });
  await page.goto(`${origin}${pathname}`);
  return {
    context,
    page,
    archived,
    setProjects: (next) => { projects = next; },
    delayNextProjectFetch: () => {
      delayedProjectResponseStarted = new Promise((resolve) => { signalDelayedProjectResponseStarted = resolve; });
      delayNextProjectResponse = true;
      return delayedProjectResponseStarted;
    },
  };
};

try {
  for (const { role, pathname, width } of [
    { role: "admin", pathname: "/admin/projects", width: 1280 },
    { role: "validator", pathname: "/validator/projects", width: 390 },
    { role: "employee", pathname: "/employee/projects", width: 320 },
  ]) {
    const { context, page, archived, setProjects, delayNextProjectFetch } = await openListing(role, pathname, width);
    try {
      const total = role === "employee" ? 24 : 26;
      const rowCount = () => page.locator("table.portal-table tbody tr").count();
      await expectFooter(page, 1, 10, total, "projects", 1, 3);
      assert.equal(await rowCount(), 10, `${role}: first page has 10 table rows`);
      assert.equal(
        await page.evaluate(() => window.__portalIntervalDelays.includes(30_000)),
        false,
        `${role}: the project list does not start a 30-second auto-refresh timer`,
      );
      if (role === "admin") {
        await page.locator("table.portal-table tbody tr").first().getByRole("button", { name: "View" }).click();
        await page.waitForURL("**/admin/projects/1/view/simplified?revision=101");
        await page.goto(`${origin}${pathname}`);
        await expectFooter(page, 1, 10, total, "projects", 1, 3);
        const revisionRow = page.locator("table.portal-table tbody tr").first();
        await revisionRow.getByRole("button", { name: "Archive" }).click();
        await page.getByRole("heading", { name: "Archive Project 01?" }).waitFor();
        assert.equal(archived.length, 0, "Opening archive from a progress-update row sends no request");
        await page.getByRole("button", { name: "Cancel" }).click();
        assert.equal(archived.length, 0, "Canceling from a progress-update row does not archive its project");
      }
      if (role === "validator") {
        assert.equal(await page.locator("article").count(), 10, "Mobile validator cards are paginated too");
        assert.ok(await page.getByRole("heading", { name: "Project 01 - Progress Update v1" }).isVisible());
      }
      await page.getByRole("button", { name: "Next" }).click();
      await expectFooter(page, 11, 20, total, "projects", 2, 3);
      await page.getByRole("button", { name: "Next" }).click();
      await expectFooter(page, 21, total, total, "projects", 3, 3);
      assert.equal(await rowCount(), total - 20);
      if (role === "validator") {
        assert.equal(await page.locator("article").count(), 6);
        const card = page.locator("article").filter({ hasText: "Project 24" });
        await card.getByRole("button", { name: "Review" }).click();
        await page.waitForURL("**/validator/projects/24/review/simplified");
        await page.goto(`${origin}${pathname}`);
        await expectFooter(page, 1, 10, total, "projects", 1, 3);
        await page.getByRole("button", { name: "Next" }).click();
        await page.getByRole("button", { name: "Next" }).click();
      }
      if (role === "employee") {
        await page.locator("table.portal-table tbody tr").last().getByRole("button", { name: "View" }).click();
        await page.waitForURL("**/employee/projects/24/view");
        await page.goto(`${origin}${pathname}`);
        await expectFooter(page, 1, 10, total, "projects", 1, 3);
        await page.getByRole("button", { name: "Next" }).click();
        await page.getByRole("button", { name: "Next" }).click();
      }
      if (role === "admin") {
        const activeRow = page.locator("table.portal-table tbody tr").filter({ hasText: "Project 23" });
        await activeRow.getByRole("button", { name: "Archive" }).click();
        await page.getByText(/Current status: Ongoing.*still ongoing/).waitFor();
        assert.equal(archived.length, 0, "Opening an active-project warning sends no archive request");
        await page.getByRole("button", { name: "Cancel" }).click();
        assert.equal(archived.length, 0, "Cancel sends no archive request");
        const lastRow = page.locator("table.portal-table tbody tr").last();
        await lastRow.getByRole("button", { name: "Archive" }).click();
        await page.getByText(/This project is Completed.*Archived tab/).waitFor();
        assert.equal(archived.length, 0, "Opening the completed-project confirmation sends no request");
        await page.getByRole("button", { name: "Confirm Archive" }).click();
        await expectFooter(page, 21, 25, 25, "projects", 3, 3);
        assert.deepEqual(archived, [24], "Archive works on the last page and changes the count");
      }
      const search = page.getByPlaceholder(role === "employee" ? "Search by project title" : "Search by project title or agency");
      await search.fill("Project 20");
      await expectFooter(page, 1, 1, 1, "projects", 1, 1);
      await search.fill("no matching project");
      await page.getByText("No projects found.").waitFor();
      assert.equal(await page.getByRole("button", { name: "Next" }).count(), 0);
      await search.fill("");
      await expectFooter(page, 1, 10, role === "admin" ? 25 : total, "projects", 1, 3);
      await page.getByRole("button", { name: "Next" }).click();
      await page.getByRole("button", { name: "Next" }).click();
      await page.locator("select").filter({ has: page.locator('option[value="pending_validation"]') }).selectOption("pending_validation");
      await expectFooter(page, 1, 10, role === "employee" ? 12 : 14, "projects", 1, 2);
      await page.locator("select").filter({ has: page.locator('option[value="pending_validation"]') }).selectOption("all");
      await expectFooter(page, 1, 10, role === "admin" ? 25 : total, "projects", 1, 3);
      await page.getByRole("button", { name: "Next" }).click();
      await page.getByRole("button", { name: "Next" }).click();
      if (role === "admin") {
        setProjects(initialProjects.slice(0, 13));
        const delayedResponseStarted = delayNextProjectFetch();
        await page.evaluate(() => window.dispatchEvent(new CustomEvent("portal:data-changed", { detail: { path: "projects/" } })));
        await delayedResponseStarted;
        setProjects(initialProjects.slice(0, 12));
        const delayedRefreshStarted = delayNextProjectFetch();
        await page.getByRole("button", { name: "Refresh" }).click();
        await delayedRefreshStarted;
        await page.getByRole("button", { name: "Refreshing..." }).waitFor();
        await page.getByText("Loading projects...").waitFor();
        await expectFooter(page, 11, 14, 14, "projects", 2, 2);
        await page.getByRole("button", { name: "Refresh", exact: true }).waitFor();
        await new Promise((resolve) => setTimeout(resolve, 400));
        await expectFooter(page, 11, 14, 14, "projects", 2, 2);
        assert.equal(await rowCount(), 4, "A slow older response cannot overwrite a manual refresh");
      } else {
        setProjects(initialProjects.slice(0, 12));
        await page.getByRole("button", { name: "Refresh" }).click();
        await expectFooter(page, 11, role === "employee" ? 12 : 14, role === "employee" ? 12 : 14, "projects", 2, 2);
        assert.equal(await rowCount(), role === "employee" ? 2 : 4);
      }
      if (role === "admin") {
        const sortField = page.getByLabel("Sort by field");
        await sortField.selectOption("title");
        await expectFooter(page, 1, 10, 14, "projects", 1, 2);
        assert.match((await page.locator("table.portal-table tbody tr").first().innerText()), /Project 01/,
          "Changing sort resets pagination and sorts the full list ascending");
        await page.getByRole("button", { name: /Change sort direction/ }).click();
        await expectFooter(page, 1, 10, 14, "projects", 1, 2);
        assert.match((await page.locator("table.portal-table tbody tr").first().innerText()), /Project 12/,
          "Changing direction sorts the full list descending");
      }
      const documentWidth = await page.evaluate(() => document.documentElement.scrollWidth);
      assert.ok(documentWidth <= width + 1, `${role} listing fits ${width}px: ${documentWidth}`);
    } finally {
      await context.close();
    }
  }

  const { context, page, setProjects } = await openListing("admin", "/admin/validator-diffs", 390);
  try {
    await expectFooter(page, 1, 10, 24, "records", 1, 3);
    assert.equal(await page.locator("table.portal-table tbody tr").count(), 10);
    await page.getByRole("button", { name: "Next" }).click();
    await expectFooter(page, 11, 20, 24, "records", 2, 3);
    await page.getByRole("button", { name: "Next" }).click();
    await expectFooter(page, 21, 24, 24, "records", 3, 3);
    await page.locator("table.portal-table tbody tr").last().getByRole("button", { name: "View Diffs" }).click();
    await page.waitForURL("**/admin/projects/24/view?mode=diff");
    await page.goto(`${origin}/admin/validator-diffs`);
    await expectFooter(page, 1, 10, 24, "records", 1, 3);
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByPlaceholder("Search by title, contributor, agency, validator").fill("Project 22");
    await expectFooter(page, 1, 1, 1, "records", 1, 1);
    await page.getByPlaceholder("Search by title, contributor, agency, validator").fill("missing record");
    await page.getByText("No records matched the current filters.").waitFor();
    await page.getByPlaceholder("Search by title, contributor, agency, validator").fill("");
    const reviewFilter = page.getByRole("combobox").first();
    await reviewFilter.selectOption("reviewed");
    await expectFooter(page, 1, 8, 8, "records", 1, 1);
    await reviewFilter.selectOption("all");
    await page.getByLabel("Edited only").check();
    await expectFooter(page, 1, 10, 12, "records", 1, 2);
    await page.getByLabel("Edited only").uncheck();
    await page.getByRole("button", { name: "Next" }).click();
    await page.getByRole("button", { name: "Next" }).click();
    setProjects(initialProjects.slice(0, 11));
    await page.getByRole("button", { name: "Refresh" }).click();
    await expectFooter(page, 11, 11, 11, "records", 2, 2);
    const documentWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    assert.ok(documentWidth <= 391, `Validator Tracker fits 390px: ${documentWidth}`);
  } finally {
    await context.close();
  }
  console.log("PASS project and validator-tracker pagination browser checks");
} finally {
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
