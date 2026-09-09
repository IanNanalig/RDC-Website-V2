import assert from "node:assert/strict";
import { chromium } from "playwright-core";

const frontendUrl = process.env.NOTIFICATION_TEST_FRONTEND_URL || "http://localhost:5173";
const edgePath = process.env.CMS_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const browser = await chromium.launch({ executablePath: edgePath, headless: true });

for (const viewport of [{ width: 320, height: 500 }, { width: 1100, height: 700 }]) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    let body = {};
    if (url.includes("notifications/?")) {
      body = {
        unread_count: 1,
        results: [{
          id: 1,
          title: "Project submitted for review",
          message: "Sample notification content",
          link_path: "",
          is_read: false,
          read_at: null,
          created_at: "2026-09-07T00:00:00+08:00",
        }],
      };
    } else if (url.includes("notifications/unread-count/")) {
      body = { unread_count: 1 };
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.addInitScript(() => {
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "visual-check-token");
    localStorage.setItem("refreshToken", "visual-check-refresh");
    localStorage.setItem("user", JSON.stringify({
      id: 1,
      username: "visual-check",
      full_name: "Visual Check",
      role: "admin",
      agency: "RDC-NCR",
    }));
  });

  await page.goto(`${frontendUrl}/admin/dashboard`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Notifications", exact: true }).click();
  const panel = page.getByRole("dialog", { name: "Notifications" });
  const title = panel.getByText("Project submitted for review", { exact: true });
  await title.waitFor();

  const panelBox = await panel.boundingBox();
  assert.ok(panelBox, "Notification panel has no visible bounds.");
  assert.ok(
    panelBox.x >= -1 && panelBox.x + panelBox.width <= viewport.width + 1,
    `Notification panel overflows the viewport: ${JSON.stringify({ viewport, panelBox })}`,
  );
  const isTopmost = await title.evaluate((element) => {
    const box = element.getBoundingClientRect();
    const topmost = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    return Boolean(topmost && element.closest("[role=dialog]")?.contains(topmost));
  });
  assert.equal(isTopmost, true, "Page content is painting over the notification panel.");

  await page.keyboard.press("Escape");
  await panel.waitFor({ state: "hidden" });
  console.log(`PASS notification panel at ${viewport.width}px`);
  await context.close();
}

await browser.close();
