import assert from "node:assert/strict";
import { chromium } from "playwright-core";

const frontendUrl = process.env.NOTIFICATION_TEST_FRONTEND_URL || "http://localhost:5173";
const edgePath = process.env.CMS_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const browser = await chromium.launch({ executablePath: edgePath, headless: true });

for (const viewport of [{ width: 320, height: 500 }, { width: 1100, height: 700 }]) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  await page.addInitScript(() => {
    window.__longRefreshIntervals = [];
    const nativeSetInterval = window.setInterval.bind(window);
    window.setInterval = (callback, delay, ...args) => {
      if (Number(delay) >= 60_000) window.__longRefreshIntervals.push(Number(delay));
      return nativeSetInterval(callback, delay, ...args);
    };
  });
  let notificationRequests = 0;
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    let body = {};
    if (url.includes("notifications/?")) {
      notificationRequests += 1;
      body = {
        unread_count: 1,
        results: [{
          id: 1,
          title: "Project submitted for review",
          message: "Sample notification content with the full details that should become visible after the notification is selected. This sentence continues beyond the normal two-line preview so testers can read the complete notification without navigating away.",
          link_path: "/admin/projects/",
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
      first_name: "Visual",
      last_name: "Check",
      role: "admin",
      agency: "RDC-NCR",
    }));
  });

  await page.goto(`${frontendUrl}/admin/dashboard`, { waitUntil: "networkidle" });
  assert.deepEqual(await page.evaluate(() => window.__longRefreshIntervals), [], "Portal notifications should not poll on a recurring timer.");
  await page.getByRole("button", { name: "Notifications", exact: true }).click();
  const panel = page.getByRole("dialog", { name: "Notifications" });
  const title = panel.getByText("Project submitted for review", { exact: true });
  await title.waitFor();
  const notification = title.locator("xpath=ancestor::button");
  await notification.click();
  const fullMessage = "This sentence continues beyond the normal two-line preview so testers can read the complete notification without navigating away.";
  await panel.getByText(fullMessage, { exact: false }).waitFor();
  assert.equal(await notification.getAttribute("aria-expanded"), "true", "Clicking a notification should expand its full message.");
  await panel.getByRole("link", { name: "Open notification" }).waitFor();

  await page.waitForTimeout(250);
  const requestsBeforeFocus = notificationRequests;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await page.waitForTimeout(100);
  assert.equal(notificationRequests, requestsBeforeFocus, "Regaining focus should not automatically reload notifications.");

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
