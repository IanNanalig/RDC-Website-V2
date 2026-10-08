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
const headers = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, OPTIONS",
  "access-control-allow-headers": "authorization, content-type",
};
const formSchema = { format_version: 1, title: "Legacy test form", sections: [] };
const incompleteAnalysis = {
  id: 7,
  base_score: "58.50",
  suggested_priority: "incomplete",
  summary: "Missing validator facts prevent a complete AI recommendation.",
  rule_version: "rdc-priority-v1",
  suggested_scores: {
    missing_facts: ["Readiness Level"], pap: [], rdp_outcomes: [],
    reasoning: {
      overall: "The 58.50/100 base score combines 20.00 planning points and 38.50 RDP points. Each weighted score is calculated from the raw rating and criterion weight.",
      criteria: [{
        key: "readiness", criterion: "Readiness", raw: 0, weight: 20, score: 0, maximum_score: 20,
        explanation: "No readiness level was supplied by the validator. The scorer does not infer completed studies from the project narrative. The rule assigned a raw rating of 0/10. With a weight of 20 points, the calculation is 0 points.",
      }, {
        key: "connectivity", criterion: "Connectivity", raw: 5, weight: 10, score: 5, maximum_score: 10,
        explanation: "Criterion intent: Explain transport outcomes. CMS matching guidance: Require project actions. The project narrative describes improved travel times for commuters. The rule assigned a raw rating of 5/10. With a weight of 10 points, the calculation is 5 points.",
      }],
    },
  },
  regional_scorecard: { applicable: false, message: "Not applicable" },
  flags: { negative_matches: [], risks: [] },
  latest_confirmation: null,
};

async function openReview(endorsed = false) {
  const context = await browser.newContext({ viewport: { width: 1050, height: 780 } });
  const page = await context.newPage();
  let submitted = null;
  await page.addInitScript(() => {
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "priority-override-test");
    localStorage.setItem("user", JSON.stringify({ id: 1, username: "priority-validator", role: "validator", agency: "RDC-NCR" }));
  });
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();
    if (method === "OPTIONS") return route.fulfill({ status: 204, headers });
    if (url.includes("contributor-forms/")) return route.fulfill({
      status: 200, contentType: "application/json", headers,
      body: JSON.stringify({ key: "simplified-rdip", version: 1, schema: formSchema }),
    });
    if (url.includes("priority-analysis/7/confirm/") && method === "POST") {
      submitted = JSON.parse(route.request().postData() || "{}");
      return route.fulfill({
        status: 200, contentType: "application/json", headers,
        body: JSON.stringify({ ...incompleteAnalysis, latest_confirmation: {
          final_priority: submitted.final_priority,
          override_rationale: submitted.override_rationale,
          validator_name: "Priority Validator",
        } }),
      });
    }
    if (url.includes("priority-analysis/")) return route.fulfill({
      status: 200, contentType: "application/json", headers,
      body: JSON.stringify({ eligible: true, analyses: [incompleteAnalysis] }),
    });
    if (url.includes("validator/projects/1/")) return route.fulfill({
      status: 200, contentType: "application/json", headers,
      body: JSON.stringify({
        id: 1, agency: "DENR", status: endorsed ? "completed" : "proposed",
        workflow_status: endorsed ? "validated" : "pending_validation",
        profile_data: {
          form_schema: { key: "simplified-rdip", version: 1, legacy: true },
          simplified_form: { agencyName: "DENR", projectActivity: "Environment project", startYear: "2026", endYear: "2026" },
          validator_review: { review_status: endorsed ? "endorsed" : "draft" },
        },
      }),
    });
    return route.fulfill({ status: 200, contentType: "application/json", headers, body: "{}" });
  });
  await page.goto(origin + "/validator/projects/1/review/simplified", { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "AI-Assisted Priority Scorer" }).waitFor();
  return { context, page, submitted: () => submitted };
}

try {
  const active = await openReview();
  const panel = active.page.locator(".portal-card").filter({ has: active.page.getByRole("heading", { name: "AI-Assisted Priority Scorer" }) }).first();
  await panel.getByText("The AI result is Incomplete.", { exact: false }).waitFor();
  await panel.getByRole("listitem").filter({ hasText: "Readiness Level" }).waitFor();
  const reasoning = panel.getByRole("heading", { name: "Reasoning and Explanation" }).locator("..");
  await reasoning.getByText("The AI gave this project", { exact: false }).waitFor();
  assert.equal(await reasoning.getByText("Each weighted score is calculated", { exact: false }).isVisible(), false,
    "Detailed formula is hidden by default");
  assert.equal(await reasoning.getByText("No readiness level was supplied by the validator", { exact: false }).first().isVisible(), true,
    "The main reason is visible in plain language");
  await reasoning.getByText("View full score calculation").click();
  assert.equal(await reasoning.getByText("Each weighted score is calculated", { exact: false }).isVisible(), true);
  await reasoning.getByText("View full explanation and scoring details").first().click();
  assert.equal(await reasoning.getByText("Raw rating:", { exact: false }).first().isVisible(), true);
  const confirm = panel.getByRole("button", { name: "Confirm Priority Analysis" });
  assert.equal(await confirm.isDisabled(), true, "A final priority must be chosen");
  await panel.getByLabel("Final Priority").selectOption("high");
  assert.equal(await confirm.isDisabled(), true, "Incomplete override needs a rationale");
  await panel.getByLabel("Override rationale (required)").fill("Regional impact supports high priority.");
  assert.equal(await confirm.isDisabled(), false);
  await confirm.click();
  await panel.getByText("Official validator decision:", { exact: false }).waitFor();
  assert.equal(active.submitted().final_priority, "high");
  assert.equal(active.submitted().override_rationale, "Regional impact supports high priority.");
  assert.match(await panel.innerText(), /AI result: Incomplete/);
  assert.match(await panel.innerText(), /58\.50/);
  await active.context.close();
  console.log("PASS incomplete result override and distinct AI/official display");

  const locked = await openReview(true);
  const lockedConfirm = locked.page.getByRole("button", { name: "Confirm Priority Analysis" });
  assert.equal(await lockedConfirm.isDisabled(), true, "Endorsed project priority controls remain disabled");
  await locked.context.close();
  console.log("PASS endorsed project priority controls are locked");
} finally {
  await browser.close();
  await new Promise((resolve, reject) => server.httpServer.close((error) => error ? reject(error) : resolve()));
}
