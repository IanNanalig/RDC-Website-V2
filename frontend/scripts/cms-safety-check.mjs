import { chromium } from "playwright-core";

const frontendUrl = process.env.CMS_TEST_FRONTEND_URL || "http://127.0.0.1:5173";
const apiUrl = process.env.CMS_TEST_API_URL || "http://127.0.0.1:8000/api";
const email = process.env.CMS_TEST_EMAIL;
const password = process.env.CMS_TEST_PASSWORD;
const edgePath = process.env.CMS_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";

if (!email || !password) {
  throw new Error("Set CMS_TEST_EMAIL and CMS_TEST_PASSWORD for the disposable CMS test account.");
}

const attacks = {
  script: "<script>alert(1)</script>",
  image: "<img src=x onerror=alert(1)>",
  link: '<a href="javascript:alert(1)">link</a>',
};
const combinedPayload = Object.values(attacks).join(",");
const slugify = (value) => value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
const slug = slugify(combinedPayload);

const loginResponse = await fetch(`${apiUrl}/auth/login/`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email, password }),
});
if (!loginResponse.ok) throw new Error(`Disposable CMS login failed (${loginResponse.status}).`);
const login = await loginResponse.json();

const browser = await chromium.launch({ executablePath: edgePath, headless: true });
const page = await browser.newPage();
const unexpectedDialogs = [];
page.on("dialog", async (dialog) => {
  if (dialog.type() === "confirm") {
    await dialog.accept();
    return;
  }
  unexpectedDialogs.push(dialog.message());
  await dialog.dismiss();
});

await page.addInitScript((session) => {
  localStorage.setItem("accessToken", session.access);
  localStorage.setItem("refreshToken", session.refresh);
  localStorage.setItem("user", JSON.stringify(session.user));
  localStorage.setItem("isLoggedIn", "true");
  localStorage.setItem("username", session.user.username);
}, login);

await page.goto(`${frontendUrl}/admin/content`, { waitUntil: "networkidle" });
await page.getByRole("heading", { name: "Website CMS" }).waitFor();

const defaultSourceCheck = {
  sectionJsonPreviewBoxes: await page.locator("pre").count(),
  rawSourceEditors: await page.locator('textarea[aria-label*="source"]').count(),
  developerToolsAbsent: await page.getByRole("button", { name: /Developer Tools/ }).count() === 0,
};

await page.getByRole("button", { name: "News", exact: true }).click();
await page.getByRole("heading", { name: "Create News Draft" }).waitFor();
await page.getByLabel("Title", { exact: true }).fill(combinedPayload);
await page.getByLabel("Short Summary", { exact: true }).fill("Automated visual CMS safety check");
await page.getByLabel("Author", { exact: true }).fill("CMS Safety Check");

const richEditor = page.locator(".cms-rich-editor .tiptap");
await richEditor.evaluate((element, payload) => {
  const clipboard = new DataTransfer();
  clipboard.setData("text/html", payload);
  clipboard.setData("text/plain", payload);
  element.focus();
  element.dispatchEvent(new ClipboardEvent("paste", { bubbles: true, cancelable: true, clipboardData: clipboard }));
}, combinedPayload);

await page.getByRole("button", { name: "Create News" }).click();
await page.getByText("News draft created.").waitFor();

const draftResponse = await fetch(`${apiUrl}/public/cms/news/${slug}/`);
const draftStayedPrivate = draftResponse.status === 404;

const publicUrlLine = page.getByText(`Public URL: /news/${slug}`, { exact: true });
await publicUrlLine.waitFor();
const articleCard = publicUrlLine.locator("xpath=ancestor::div[contains(@class, 'rounded-xl')][1]");
await articleCard.getByRole("button", { name: "Publish", exact: true }).click();
await page.getByText(`News article published at /news/${slug}.`).waitFor();

unexpectedDialogs.length = 0;
await page.goto(`${frontendUrl}/news/${slug}`, { waitUntil: "networkidle" });
const article = page.locator("article.prose");
await article.waitFor();
const articleHtml = await article.innerHTML();
const titleHtml = await page.locator("header h1.mt-7").innerHTML();

const result = {
  defaultSourceCheck,
  draftStayedPrivate,
  tiptap: {
    script: !/<script[\s>]/i.test(articleHtml),
    imageOnError: !/<img[\s>]/i.test(articleHtml) && !/onerror\s*=/i.test(articleHtml),
    javascriptLink: !(await article.locator('a[href^="javascript:"]').count()) && !/href\s*=\s*["']javascript:/i.test(articleHtml),
    unexpectedDialogs,
  },
  plainTitle: {
    script: !/<script[\s>]/i.test(titleHtml),
    imageOnError: !/<img[\s>]/i.test(titleHtml) && !/onerror\s*=/i.test(titleHtml),
    javascriptLink: !/javascript:/i.test(titleHtml),
  },
};

console.log(JSON.stringify(result, null, 2));
await browser.close();

const allPassed =
  defaultSourceCheck.sectionJsonPreviewBoxes === 0 &&
  defaultSourceCheck.rawSourceEditors === 0 &&
  defaultSourceCheck.developerToolsAbsent &&
  draftStayedPrivate &&
  Object.values(result.tiptap).every((value) => Array.isArray(value) ? value.length === 0 : value === true) &&
  Object.values(result.plainTitle).every(Boolean);

if (!allPassed) process.exitCode = 1;
