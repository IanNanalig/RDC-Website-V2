import assert from "node:assert/strict";
import { chromium } from "playwright-core";
import { preview } from "vite";

const server = await preview({ preview: { host: "127.0.0.1", port: 0 } });
const address = server.httpServer.address();
assert.ok(address && typeof address !== "string");
const browser = await chromium.launch({
  executablePath: process.env.CMS_TEST_BROWSER || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  headless: true,
});
const context = await browser.newContext({ viewport: { width: 1050, height: 780 } });
const page = await context.newPage();
const headers = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, OPTIONS",
  "access-control-allow-headers": "authorization, content-type",
};
const json = (route, value) => route.fulfill({ status: 200, contentType: "application/json", headers, body: JSON.stringify(value) });
const analysis = {
  id: 7,
  base_score: "50.00",
  suggested_priority: "low",
  summary: "The AI suggested a low priority.",
  rule_version: "rdc-priority-v1",
  suggested_scores: {
    missing_facts: [],
    pap: [{ key: "readiness", criterion: "Readiness", raw: 5, weight: 40, score: 20, remarks: "AI evidence summary" }],
    pap_total: 20,
    rdp_outcomes: [{ key: "outcome", criterion: "RDP Outcome", raw: 5, weight: 60, score: 30, remarks: "AI outcome summary" }],
    rdp_total: 30,
    base_total: 50,
  },
  regional_scorecard: { applicable: true, total: 8, criteria: [{ key: "cost", criterion: "Project Cost", raw: 4, weight: 20, score: 8, remarks: "AI cost summary" }] },
  flags: { negative_matches: [], risks: [] },
  document_assessment: { status: "not_required", summary: "No documents required." },
  evaluation: null,
  latest_confirmation: null,
};
let savedPayload = null;
let confirmedPayload = null;
await page.addInitScript(() => {
  localStorage.setItem("isLoggedIn", "true");
  localStorage.setItem("accessToken", "validator-evaluation-test");
  localStorage.setItem("user", JSON.stringify({ id: 1, username: "validator", role: "validator", agency: "RDC-NCR" }));
});
await page.route("**/api/**", async (route) => {
  const url = route.request().url();
  const method = route.request().method();
  if (method === "OPTIONS") return route.fulfill({ status: 204, headers });
  if (url.includes("contributor-forms/")) return json(route, { key: "simplified-rdip", version: 1, schema: { format_version: 1, title: "Legacy test form", sections: [] } });
  if (/priority-analysis\/\d+\/evaluation\//.test(url) && method === "POST") {
    savedPayload = JSON.parse(route.request().postData() || "{}");
    analysis.evaluation = {
      ...savedPayload,
      effective_score: 84,
      regional_effective_score: 20,
      calculated_priority: "high",
    };
    return json(route, analysis);
  }
  if (/priority-analysis\/\d+\/confirm\//.test(url) && method === "POST") {
    confirmedPayload = JSON.parse(route.request().postData() || "{}");
    analysis.latest_confirmation = {
      final_priority: confirmedPayload.final_priority,
      adjusted_scores: confirmedPayload.adjusted_scores,
      validator_remarks: confirmedPayload.validator_remarks,
      effective_score: 84,
      validator_name: "Validator",
    };
    return json(route, analysis);
  }
  if (url.includes("priority-analysis/")) return json(route, { eligible: true, analyses: [analysis] });
  if (url.includes("validator/projects/1/")) return json(route, {
    id: 1, agency: "DENR", status: "proposed", workflow_status: "pending_validation",
    profile_data: {
      form_schema: { key: "simplified-rdip", version: 1, legacy: true },
      simplified_form: { agencyName: "DENR", projectActivity: "Sample project", startYear: "2026", endYear: "2026" },
      validator_review: { review_status: "draft" },
    },
  });
  return json(route, {});
});

try {
  await page.goto(`http://127.0.0.1:${address.port}/validator/projects/1/review/simplified`, { waitUntil: "networkidle" });
  const panel = page.locator(".portal-card").filter({ has: page.getByRole("heading", { name: "AI-Assisted Priority Scorer" }) }).first();
  await panel.getByLabel("Readiness raw score").fill("9");
  await panel.getByLabel("RDP Outcome raw score").fill("8");
  await panel.getByLabel("Project Cost raw score").fill("10");
  await panel.getByLabel("Readiness validator remarks").fill("Verified planning documents.");
  assert.equal(await panel.getByRole("button", { name: "Confirm Priority Analysis" }).isDisabled(), true, "Unsaved scores cannot be confirmed");
  await panel.getByRole("button", { name: "Save Validator Evaluation" }).click();
  await panel.getByText("Validator scores and remarks saved.").waitFor();
  assert.equal(savedPayload.adjusted_scores["pap:readiness"], 9);
  assert.equal(savedPayload.validator_remarks["pap:readiness"], "Verified planning documents.");
  await panel.getByRole("button", { name: "Confirm Priority Analysis" }).click();
  await panel.getByText("Official validator decision:", { exact: false }).waitFor();
  assert.equal(confirmedPayload.final_priority, "high");
  await page.reload({ waitUntil: "networkidle" });
  await page.getByText("Verified planning documents.").waitFor();
  assert.equal(await page.getByRole("button", { name: "Confirm Priority Analysis" }).count(), 0, "A confirmed analysis is locked");
  console.log("PASS validator score editing, persistence, confirmation, and reopen browser check");
} finally {
  await context.close();
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
