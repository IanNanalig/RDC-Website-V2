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
    rdp_outcomes: [{ key: "outcome", criterion: "RDP Outcome", raw: 5, weight: 60, score: 30, remarks: "AI outcome summary", ai_explanation: "The plan adds two accessible crossings.", evidence: ["two accessible crossings"] }],
    rdp_total: 30,
    base_total: 50,
    recommendations: [{ key: "outcome", criterion: "RDP Outcome", recommendation: "Add supporting evidence." }],
    revision_fields: [{ key: "objective", label: "Objective", source: "contributor" }],
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
  await panel.getByText("The plan adds two accessible crossings.", { exact: true }).waitFor();
  await panel.getByText("Evidence: two accessible crossings", { exact: true }).waitFor();
  assert.equal(await panel.getByText("Recommendations to Improve the Score", { exact: true }).count(), 0);
  assert.equal(await panel.getByText("Fields Needing Review or Revision", { exact: true }).count(), 0);
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
    sector_criteria: {
      infrastructure: [{
        key: "connectivity", label: "Connectivity", weight: 50, keywords: ["transport"],
        match_mode: "contextual", context_phrases: ["improve access"],
      }],
      social: [{
        key: "public_services", label: "Public services", weight: 50, keywords: ["access"],
        match_mode: "contextual", context_phrases: ["improve access"],
      }],
    },
  };
  const oldVersion = {
    id: 1, version: "previous-scoring-rules", algorithm_version: "test", is_active: false,
    analysis_count: 3, created_at: "2026-11-20T04:30:00Z", activated_by: "Test Administrator",
    change_note: "Adjusted the high-priority threshold for review.",
  };
  const addedCriterion = {
    key: "custom_common_outcomes_1795249380617", label: "Safe and reliable transport",
    weight: 15, keywords: ["road", "bridge"], match_mode: "contextual",
    matching_guidance: "Show how the project improves access.",
  };
  const removedCriterion = {
    key: "accessibility", label: "Accessible public services",
    weight: 20, context_phrases: ["accessible transport", "connect communities"],
  };
  const versions = [oldVersion, ...Array.from({ length: 9 }, (_, index) => ({
    ...oldVersion, id: index + 2, version: `other-history-${index + 1}`, change_note: "",
  }))];
  let activeId = 2;
  await admin.route("**/api/**", (route) => {
    const requestUrl = route.request().url();
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    if (requestUrl.includes("ai-scoring/versions/1/restore/")) {
      assert.deepEqual(JSON.parse(route.request().postData()), {
        expected_active_id: 2, change_note: "Restore for the integration test.",
      });
      activeId = 3;
      return json(route, { detail: "Restored as a new active version.", result: "restored", issues: [] });
    }
    if (requestUrl.includes("ai-scoring/versions/1/")) return json(route, {
      ...oldVersion, previous_version: "baseline", input_contract: {},
      config: {
        ...adminConfig,
        keyword_dictionaries: { ...adminConfig.keyword_dictionaries, common_outcomes: [addedCriterion] },
      },
      changes: [
        { path: ["thresholds", "high"], kind: "changed", before: 80, after: 81 },
        { path: ["keyword_dictionaries", "common_outcomes", addedCriterion.key], kind: "added", before: null, after: addedCriterion },
        { path: ["sector_criteria", "infrastructure", removedCriterion.key], kind: "removed", before: removedCriterion, after: null },
      ],
    });
    if (requestUrl.includes("ai-scoring/historical-references/")) {
      const query = new URL(requestUrl).searchParams;
      const page = Number(query.get("page"));
      const search = query.get("q");
      if (search && search !== "River") return json(route, { count: 0, total_pages: 0, results: [] });
      if (search) assert.equal(page, 1, "Changing search resets the historical page");
      return json(route, {
        count: search ? 1 : 11,
        total_pages: search ? 1 : 2,
        results: [{
          confirmation_id: page, training_record_id: page, project_title: search ? "River mitigation" : page === 1 ? "Earlier page project" : "Next page project",
          agency: "DPWH", sector: "Infrastructure", submission_type: "simplified", project_status: "validated",
          base_score: 85, suggested_priority: "high", final_priority: "high", rule_version: "test-rules",
          validator_name: "Validator", confirmed_at: "2026-10-10T00:00:00Z", training_eligible: true,
        }],
      });
    }
    if (requestUrl.includes("ai-scoring/versions/?page=2")) {
      return json(route, { page: 2, total_pages: 2, results: [{ ...oldVersion, id: 50, version: "earlier-page-rules" }] });
    }
    if (requestUrl.includes("ai-scoring/versions/?page=1")) {
      return json(route, { page: 1, total_pages: 2, results: versions });
    }
    if (requestUrl.includes("admin/cms/ai-scoring/")) return json(route, {
      active_rule_set: { id: activeId, version: activeId === 3 ? "restored-scoring-rules" : "test-rules", algorithm_version: "test", config: adminConfig },
      scoring_formula: { max_raw_score: 10, regional_criterion_weight: 25, example: { base: 80, regional: 60, eligible: 70, below_cutoff: 80 } },
      committee_outcome_links: [{ code: "sceed", name: "SCEED", is_active: true, groups: ["economic", "environment"] }],
      historical_count: 11, historical_projects: [], rule_versions: versions, rule_versions_total_pages: 2,
    });
    return json(route, {});
  });
  await admin.goto(`http://127.0.0.1:${address.port}/admin/ai-scoring`, { waitUntil: "networkidle" });
  await admin.getByRole("heading", { name: "PAPs Criteria", exact: true }).waitFor();
  const configuration = admin.getByRole("button", { name: "Content & Configuration" });
  assert.equal(await configuration.getAttribute("aria-expanded"), "true");
  assert.equal(await admin.getByRole("link", { name: "A.I. and Project Criteria" }).getAttribute("aria-current"), "page");
  const operations = admin.getByRole("button", { name: "Operations" });
  assert.equal(await operations.getAttribute("aria-expanded"), "false");
  await operations.press("Enter");
  await admin.getByRole("link", { name: "Project Management" }).waitFor();
  await admin.reload();
  assert.equal(await operations.getAttribute("aria-expanded"), "true");
  await operations.press("Space");
  await admin.getByRole("link", { name: "Project Management" }).waitFor({ state: "hidden" });
  assert.equal(await admin.getByText("Form Input Compatibility", { exact: true }).count(), 0);
  assert.equal(await admin.getByText("Criterion-to-field dependencies", { exact: true }).count(), 0);
  await admin.getByText(/Weighted points = raw score/).waitFor();
  await admin.getByText(/an eligible project scores 70/).waitFor();
  await admin.getByText("Committee assignments", { exact: true }).click();
  await admin.getByText("Economic, Environment", { exact: true }).waitFor();
  await admin.getByRole("heading", { name: "Regional Prioritization Criteria", exact: true }).waitFor();
  await admin.getByRole("button", { name: "Create Draft", exact: true }).waitFor();
  assert.equal(await admin.getByLabel("Preview project ID", { exact: true }).count(), 0);
  const papScore = admin.getByLabel("1–5 cities/municipalities", { exact: true });
  const regionalScore = admin.getByLabel("Single-city score", { exact: true });
  assert.equal(await papScore.inputValue(), "3");
  await papScore.fill("5");
  assert.equal(await regionalScore.inputValue(), "4");
  await papScore.fill("6");
  await admin.getByText(/PAP Spatial Coverage scores:.*must be greater/).waitFor();
  await papScore.fill("3");
  await admin.getByText("Required change note", { exact: true }).locator("..").locator("textarea").fill("Test active weights.");
  const lowerCostBand = admin.getByRole("spinbutton", { name: /^More than PHP (500|100|200),000,000/ });
  const costBandWarning = admin.getByText("Cost bands must be at least the regional eligibility cutoff of PHP 200,000,000.", { exact: true });
  assert.equal(await lowerCostBand.getAttribute("min"), "200000000");
  await lowerCostBand.fill("100000000");
  await costBandWarning.waitFor();
  assert.equal(await admin.getByRole("button", { name: "Create Draft" }).isDisabled(), true);
  await lowerCostBand.fill("200000000");
  await costBandWarning.waitFor({ state: "hidden" });
  assert.equal(await admin.getByRole("button", { name: "Create Draft" }).isEnabled(), true);
  const eligibilityCutoff = admin.getByRole("spinbutton", { name: /^Regional eligibility and automatic-Low cutoff/ });
  await eligibilityCutoff.fill("300000000");
  assert.equal(await lowerCostBand.getAttribute("min"), "300000000");
  assert.equal(await admin.getByRole("button", { name: "Create Draft" }).isDisabled(), true);
  await eligibilityCutoff.fill("200000000");
  const readinessWeight = admin.getByRole("spinbutton", { name: /^Readiness weight/ });
  assert.equal(await readinessWeight.getAttribute("min"), "1");
  assert.equal(await readinessWeight.getAttribute("step"), "1");
  await readinessWeight.fill("0");
  const weightWarning = admin.getByText("Enter a whole-number weight from 1 to 100.", { exact: true });
  await weightWarning.waitFor();
  const priorityThresholds = admin.getByRole("heading", { name: "Priority thresholds", exact: true }).locator("..");
  assert.equal(await priorityThresholds.getByText(/weight/i).count(), 0);
  assert.equal(await weightWarning.locator("..").getByText("Enter a number from 0 to 100.", { exact: true }).count(), 0);
  assert.equal(await admin.getByRole("button", { name: "Create Draft" }).isDisabled(), true);
  await readinessWeight.fill("1.5");
  assert.equal(await readinessWeight.getAttribute("aria-invalid"), "true");
  await readinessWeight.fill("1");
  assert.equal(await readinessWeight.getAttribute("aria-invalid"), "false");
  const totalWarning = admin.getByText("Combined weights must total 100. Each sector currently totals 81.", { exact: true });
  await totalWarning.waitFor();
  const warningBelowHeading = admin.getByRole("heading", { name: "RDP outcome criteria and matching words", exact: true })
    .locator("xpath=following-sibling::p[1]");
  assert.match(await warningBelowHeading.innerText(), /Each sector currently totals 81/);
  const committeeHeading = admin.getByRole("heading", { name: "Committee-specific outcome criteria", exact: true });
  assert.match(await committeeHeading.locator("xpath=preceding-sibling::*[1]").locator("summary").innerText(), /Common outcomes/);
  assert.match(await committeeHeading.locator("xpath=following-sibling::*[1]").locator("summary").innerText(), /Infrastructure outcomes/);
  assert.equal(await admin.locator("summary").getByText(/Combined weights must total/).count(), 0);
  assert.equal(await priorityThresholds.getByText(/weight/i).count(), 0);
  assert.equal(await admin.getByRole("button", { name: "Create Draft" }).isDisabled(), true);
  const referencePages = admin.getByRole("navigation", { name: "Historical reference pages" });
  await admin.getByText("Earlier page project", { exact: true }).waitFor();
  await referencePages.getByText("Page 1 of 2", { exact: true }).waitFor();
  assert.ok(await referencePages.getByRole("button", { name: "Previous" }).isDisabled());
  await referencePages.getByRole("button", { name: "Next" }).click();
  await admin.getByText("Next page project", { exact: true }).waitFor();
  await referencePages.getByText("Page 2 of 2", { exact: true }).waitFor();
  assert.ok(await referencePages.getByRole("button", { name: "Next" }).isDisabled());
  assert.equal(await admin.getByRole("button", { name: "Exclude", exact: true }).count(), 0);
  await admin.getByPlaceholder(/Search project, agency/).fill("River");
  await admin.getByText("River mitigation", { exact: true }).waitFor();
  await referencePages.getByText("Page 1 of 1", { exact: true }).waitFor();
  const versionPages = admin.getByRole("navigation", { name: "Rule version history pages" });
  await versionPages.getByText("Page 1 of 2", { exact: true }).waitFor();
  await versionPages.getByRole("button", { name: "Next" }).click();
  await admin.getByText("earlier-page-rules", { exact: true }).waitFor();
  await versionPages.getByText("Page 2 of 2", { exact: true }).waitFor();
  assert.ok(await versionPages.getByRole("button", { name: "Next" }).isDisabled());
  await versionPages.getByRole("button", { name: "Previous" }).click();
  await admin.getByText(oldVersion.change_note, { exact: true }).waitFor();
  await admin.getByRole("button", { name: "View version previous-scoring-rules" }).click();
  const versionRow = admin.getByText(oldVersion.change_note, { exact: true }).locator("..");
  await versionRow.getByText("Changes since baseline").waitFor();
  await admin.getByText("Thresholds / High-priority cutoff", { exact: false }).waitFor();
  const addedRow = admin.getByRole("row").filter({ hasText: "Scoring rules / Common outcomes / Safe and reliable transport" });
  await addedRow.getByRole("cell").nth(2).getByText("road, bridge", { exact: true }).waitFor();
  await addedRow.getByText("Contextual sentence matching", { exact: true }).waitFor();
  assert.equal(await addedRow.getByText(addedCriterion.key, { exact: false }).count(), 0);
  const removedRow = admin.getByRole("row").filter({ hasText: "Sector outcomes / Infrastructure / Accessible public services" });
  await removedRow.getByRole("cell").nth(1).getByText("accessible transport, connect communities", { exact: true }).waitFor();
  await admin.getByText("Configuration snapshot", { exact: true }).click();
  assert.equal(await admin.getByText(/"key":|"matching_guidance":/).count(), 0);
  await admin.getByLabel("Restore change note").fill("Restore for the integration test.");
  admin.once("dialog", (dialog) => dialog.accept());
  await admin.getByRole("button", { name: "Restore version", exact: true }).click();
  await admin.getByText("Restored as a new active version.", { exact: true }).waitFor();
  await admin.getByText("restored-scoring-rules", { exact: true }).waitFor();
  console.log("PASS Administrator groups, independent Spatial Coverage, positive weights, version notes, differences, and restore");
} finally {
  await context.close();
  await browser.close();
  await new Promise((resolve) => server.httpServer.close(resolve));
}
