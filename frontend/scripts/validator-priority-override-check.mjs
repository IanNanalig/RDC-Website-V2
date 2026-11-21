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
  "access-control-allow-methods": "GET, POST, PUT, OPTIONS",
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
let regionalTotal = "200000000.00";
let factsVersion = 0;
let scorerUnavailable = false;
let currentAnalysis = analysis;
let facts = { spatialCoverageScope: "specific_lgus" };
const priorAnalyses = [analysis];
const regionalEligibility = () => ({
  applicable: regionalTotal !== "199999999.99",
  total: regionalTotal,
  cutoff: "200000000",
});
await page.addInitScript(() => {
  localStorage.setItem("isLoggedIn", "true");
  localStorage.setItem("accessToken", "validator-evaluation-test");
  localStorage.setItem("user", JSON.stringify({ id: 1, username: "validator", role: "validator", agency: "RDC-NCR" }));
});
await page.route("**/api/**", async (route) => {
  const url = route.request().url();
  const method = route.request().method();
  if (method === "OPTIONS") return route.fulfill({ status: 204, headers });
  if (url.includes("assessment-status")) return json(route, { status: "not_required" });
  if (url.includes("priority-analysis/facts/") && method === "PUT") {
    const payload = JSON.parse(route.request().postData() || "{}");
    assert.equal(payload.facts_version, factsVersion);
    facts = payload.supplements;
    factsVersion += 1;
    return json(route, { validator_facts: facts, facts_version: factsVersion, regional_eligibility: regionalEligibility() });
  }
  if (url.includes("priority-analysis/run/") && method === "POST") {
    const payload = JSON.parse(route.request().postData() || "{}");
    assert.equal(payload.facts_version, factsVersion);
    if (scorerUnavailable) {
      return route.fulfill({
        status: 502, contentType: "application/json", headers,
        body: JSON.stringify({
          detail: "Groq rejected the scoring request because it exceeded the provider's input limits.",
          code: "ai_outcome_unavailable", reason: "request_too_large", retry_available: true,
        }),
      });
    }
    currentAnalysis = {
      ...analysis, id: analysis.id + factsVersion, base_score: "29.00", evaluation: null, latest_confirmation: null,
      suggested_scores: { ...analysis.suggested_scores, score_total_version: 3, base_total: 29 },
    };
    priorAnalyses.push(currentAnalysis);
    return json(route, { analysis: currentAnalysis, reused: false });
  }
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
  if (url.includes("priority-analysis/")) return json(route, {
    eligible: true, analyses: priorAnalyses, current_analysis_id: currentAnalysis.id,
    validator_facts: facts, facts_version: factsVersion, regional_eligibility: regionalEligibility(),
  });
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

  for (const amount of ["199999999.99", "200000000.00", "200000000.01"]) {
    regionalTotal = amount;
    await page.reload({ waitUntil: "networkidle" });
    await panel.getByLabel("Spatial Coverage", { exact: true }).waitFor();
    for (const label of ["Estimated Beneficiaries", "Contributed RDP Outcomes", "Regional Spatial Category"]) {
      assert.equal(await panel.getByLabel(label).count(), amount === "199999999.99" ? 0 : 1, label);
    }
  }
  for (const scope of ["region_wide", "specific_lgus"]) {
    await panel.getByLabel("Spatial Coverage", { exact: true }).selectOption(scope);
    await panel.getByRole("button", { name: "Run AI Scorer" }).click();
    await panel.getByText("Priority analysis completed.").waitFor();
    await page.reload({ waitUntil: "networkidle" });
    assert.equal(await panel.getByLabel("Spatial Coverage", { exact: true }).inputValue(), scope);
  }
  assert.equal(await panel.getByText("Previous analyses (2)", { exact: true }).count(), 1);
  await panel.getByLabel("Project Cost raw score").fill("10");
  await panel.getByText("Validator overall score: 35.00/100", { exact: false }).waitFor();
  scorerUnavailable = true;
  await panel.getByRole("button", { name: "Run AI Scorer" }).click();
  const warning = panel.getByText("AI outcome scoring could not return a valid result for the active criteria. Retry the scorer.", { exact: true });
  await warning.first().waitFor();
  assert.equal(await warning.count(), 2);
  await panel.getByRole("button", { name: "Retry AI Scorer" }).waitFor();
  assert.equal(await panel.getByText(/request_too_large|exceeded the provider's input limits/).count(), 0);
  console.log("PASS Validator score editing, confirmation, regional visibility, fact restoration, and history");

  const admin = await context.newPage();
  await admin.addInitScript(() => {
    localStorage.setItem("isLoggedIn", "true");
    localStorage.setItem("accessToken", "admin-scoring-test");
    localStorage.setItem("user", JSON.stringify({ id: 2, username: "admin", role: "admin", agency: "RDC-NCR" }));
  });
  const adminConfig = {
    thresholds: {
      high: 81, regional_project_cost: 200000000,
      pap_weights: { readiness: 20, gad_responsiveness: 15, spatial_coverage: 15 },
      pap_spatial_scores: { wide_coverage: 10, six_to_twelve_lgus: 6, one_to_five_lgus: 3, none: 0 },
      regional_criteria: {
        cost: { thresholds: { at_least_5b: 5000000000, over_3b: 3000000000, over_1b: 1000000000, over_500m: 500000000 }, scores: { at_least_5b: 10, over_3b: 8, over_1b: 6, over_500m: 4, otherwise: 2 } },
        spatial_coverage: { scores: { interregional: 10, region_wide: 8, eight_to_twelve_lgus: 6, single_city: 4 } },
        outcome_contribution: { thresholds: { at_least_7: 7, at_least_5: 5, at_least_3: 3, at_least_2: 2, at_least_1: 1 }, scores: { at_least_7: 10, at_least_5: 8, at_least_3: 6, at_least_2: 4, at_least_1: 2, otherwise: 0 } },
        beneficiaries: { thresholds: { over_3m: 3000000, over_1m: 1000000, at_least_1: 1 }, scores: { over_3m: 10, over_1m: 6, at_least_1: 3, otherwise: 0 } },
      },
    },
    keyword_dictionaries: {
      readiness: ["completed_documents", "ongoing_documents", "project_profile", "concept_only"].map((key, index) => ({ key, raw: [10, 6, 3, 0][index], guideline: key })),
      gad: ["gender_responsive", "gender_sensitive", "promising_prospects", "invisible"].map((key, index) => ({ key, raw: [10, 6, 3, 0][index], guideline: key })),
      common_outcomes: [], negative_rules: [], guidelines: [],
      outcome_rating: { chapter_and_two_keywords: 10, chapter_or_three_keywords: 8, one_keyword: 5, no_keywords: 0 },
    },
    sector_criteria: {},
  };
  await admin.route("**/api/**", (route) => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    if (route.request().url().includes("admin/cms/ai-scoring/")) return json(route, {
      active_rule_set: { version: "test-rules", algorithm_version: "test", config: adminConfig },
      historical_count: 0, historical_projects: [], rule_versions: [],
    });
    return json(route, {});
  });
  await admin.goto(`http://127.0.0.1:${address.port}/admin/ai-scoring`, { waitUntil: "networkidle" });
  await admin.getByRole("heading", { name: "PAPs Criterion", exact: true }).waitFor();
  await admin.getByRole("heading", { name: "Regional Prioritization Criteria", exact: true }).waitFor();
  const papScore = admin.getByLabel("1–5 cities/municipalities", { exact: true });
  const regionalScore = admin.getByLabel("Single-city score", { exact: true });
  assert.equal(await papScore.inputValue(), "3");
  await papScore.fill("5");
  assert.equal(await regionalScore.inputValue(), "4");
  await papScore.fill("6");
  await admin.getByText(/PAP Spatial Coverage scores:.*must be greater/).waitFor();
  console.log("PASS Administrator groups, independent Spatial Coverage scales, and inline hierarchy validation");
} finally {
  await context.close();
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
