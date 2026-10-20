import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";

const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
const projects = readFileSync(new URL("../src/pages/EmployesPortal/ProjectsPage.tsx", import.meta.url), "utf8");
const history = readFileSync(new URL("../src/pages/EmployesPortal/ValidatorReviewHistory.tsx", import.meta.url), "utf8");
const submission = readFileSync(new URL("../src/pages/EmployesPortal/SimplifiedProjectSubmission.tsx", import.meta.url), "utf8");

assert.ok(!app.includes('import("./pages/EmployesPortal/ProjectSubmission")'));
for (const route of [
  'path="/employee/projects/new/detailed"',
  'path="/employee/projects/:id/edit"',
  'path="/validator/projects/:id/review"',
  'path="/admin/projects/:id/view"',
]) {
  const start = app.indexOf(route);
  assert.notEqual(start, -1, `Compatibility route missing: ${route}`);
  const routeBlock = app.slice(start, app.indexOf("/>\n        </Route>", start));
  assert.ok(routeBlock.includes("<SimplifiedProjectSubmissionPage />"), `${route} must mount simplified form directly`);
}
assert.ok(projects.includes("/admin/projects/${p.id}/view/simplified"));
assert.ok(projects.includes("/validator/projects/${p.id}/review/simplified"));
assert.ok(history.includes("/validator/projects/${project.id}/review/simplified"));
assert.ok(submission.includes("This project was saved using the retired detailed form"));
assert.ok(!existsSync(new URL("../src/pages/EmployesPortal/ProjectSubmission.tsx", import.meta.url)));
assert.ok(!existsSync(new URL("../src/forms/project_form_schema.json", import.meta.url)));

console.log("Detailed project form route and compatibility checks passed.");
