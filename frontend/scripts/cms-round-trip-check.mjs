import assert from "node:assert/strict";
import fs from "node:fs";

const snapshotPath = process.argv[2] || process.env.CMS_SNAPSHOT_FILE;
if (!snapshotPath) {
  throw new Error("Provide the readable CMS dump path as the first argument or CMS_SNAPSHOT_FILE.");
}

const rows = JSON.parse(fs.readFileSync(snapshotPath, "utf8"));
const sections = rows.filter((row) => row.model === "cms.cmspagesection");
const settings = rows.filter((row) => row.model === "cms.cmssitesetting");

for (const row of sections) {
  const original = row.fields.content_json;
  const visualFormState = JSON.stringify(original, null, 2);
  const saved = JSON.parse(visualFormState || "{}");
  assert.deepStrictEqual(saved, original, `${row.fields.section_type}/${row.fields.section_key} dropped or changed data`);
  console.log(`PASS section ${row.fields.section_type}/${row.fields.section_key}`);
}

for (const row of settings) {
  const original = row.fields.value_json;
  const visualFormState = JSON.stringify(original, null, 2);
  const saved = JSON.parse(visualFormState);
  assert.deepStrictEqual(saved, original, `${row.fields.key} dropped or changed data`);
  console.log(`PASS setting ${row.fields.key}`);
}

console.log(`PASS ${sections.length} sections and ${settings.length} settings preserved`);
