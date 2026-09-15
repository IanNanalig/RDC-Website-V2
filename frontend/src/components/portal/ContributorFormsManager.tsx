import React, { useCallback, useEffect, useMemo, useState } from "react";
import cmsApi, {
  type CMSContributorForm,
  type CMSContributorFormVersion,
} from "../../services/cmsApi";
import {
  cloneContributorFormSchema,
  contributorFieldApplies,
  type ContributorFormField,
  type ContributorFormFieldType,
  type ContributorFormSchema,
  type ContributorFormSection,
} from "../../types/contributorForm";

type Props = { mode: "admin" | "editor" };
type EditMode = "update" | "change";

const fieldTypeOptions: Array<{ value: ContributorFormFieldType; label: string }> = [
  { value: "text", label: "Short text" },
  { value: "textarea", label: "Long text" },
  { value: "number", label: "Number / currency" },
  { value: "date", label: "Date" },
  { value: "select", label: "Single select" },
  { value: "multiselect", label: "Multiple select" },
];

const errorDetail = (error: unknown, fallback: string) => {
  if (!(error instanceof Error) || !error.message) return fallback;
  try {
    const parsed = JSON.parse(error.message) as Record<string, unknown>;
    if (typeof parsed.detail === "string") return parsed.detail;
    const schemaError = parsed.draft_schema_json;
    if (typeof schemaError === "string") return schemaError;
    if (Array.isArray(schemaError) && typeof schemaError[0] === "string") return schemaError[0];
  } catch {
    return error.message.length < 260 ? error.message : fallback;
  }
  return fallback;
};

const statusClass = (status: string) => {
  if (status === "published") return "bg-emerald-100 text-emerald-700";
  if (status === "submitted") return "bg-blue-100 text-blue-700";
  if (status === "rejected") return "bg-rose-100 text-rose-700";
  return "bg-amber-100 text-amber-700";
};

const formatDate = (value?: string | null) => {
  if (!value) return "Not yet published";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Unknown" : parsed.toLocaleString();
};

const move = <T,>(items: T[], index: number, direction: -1 | 1) => {
  const nextIndex = index + direction;
  if (nextIndex < 0 || nextIndex >= items.length) return items;
  const next = [...items];
  [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
  return next;
};

const customKey = (schema: ContributorFormSchema) => {
  const used = new Set(schema.sections.flatMap((section) => section.fields.map((field) => field.key)));
  let index = 1;
  while (used.has(`custom_field_${index}`)) index += 1;
  return `custom_field_${index}`;
};

const nextOptionValue = (field: ContributorFormField) => {
  const used = new Set((field.options || []).map((option) => option.value));
  let index = 1;
  while (used.has(`option_${index}`)) index += 1;
  return `option_${index}`;
};

const normalizeContributorSchema = (schema: ContributorFormSchema) => {
  const next = cloneContributorFormSchema(schema);
  next.sections = [
    ...next.sections.filter((section) => !section.admin_only),
    ...next.sections.filter((section) => section.admin_only),
  ];
  return next;
};

const moveContributorSection = (
  sections: ContributorFormSection[],
  sectionIndex: number,
  direction: -1 | 1,
) => {
  const editableIndexes = sections.flatMap((section, index) => section.admin_only ? [] : [index]);
  const position = editableIndexes.indexOf(sectionIndex);
  const targetIndex = editableIndexes[position + direction];
  if (position < 0 || targetIndex === undefined) return sections;
  const next = [...sections];
  [next[sectionIndex], next[targetIndex]] = [next[targetIndex], next[sectionIndex]];
  return next;
};

const schemaSummary = (schema: ContributorFormSchema) => {
  const contributorSections = schema.sections.filter((section) => !section.admin_only);
  const fields = contributorSections.flatMap((section) => section.fields);
  return `${contributorSections.length} sections · ${fields.length} fields · ${fields.filter((field) => field.key.startsWith("custom_")).length} custom`;
};

const schemaDifferences = (live: ContributorFormSchema, draft: ContributorFormSchema) => {
  const changes: string[] = [];
  if (live.title !== draft.title) changes.push(`Form title: "${live.title}" -> "${draft.title}"`);
  if ((live.description || "") !== (draft.description || "")) changes.push("Form description changed");

  const sections = (schema: ContributorFormSchema) => schema.sections.filter((section) => !section.admin_only);
  const liveSections = sections(live);
  const draftSections = sections(draft);
  const liveSectionMap = new Map(liveSections.map((section, index) => [section.key, { section, index }]));
  const draftSectionMap = new Map(draftSections.map((section, index) => [section.key, { section, index }]));
  for (const { section, index } of draftSectionMap.values()) {
    const previous = liveSectionMap.get(section.key);
    if (!previous) {
      changes.push(`Added section: ${section.title}`);
      continue;
    }
    if (previous.section.title !== section.title) changes.push(`Section title: "${previous.section.title}" -> "${section.title}"`);
    if ((previous.section.description || "") !== (section.description || "")) changes.push(`${section.title}: guidance changed`);
    if ((previous.section.visible !== false) !== (section.visible !== false)) changes.push(`${section.title}: ${section.visible === false ? "hidden" : "reactivated"}`);
    if (previous.index !== index) changes.push(`${section.title}: section order changed`);
  }
  for (const { section } of liveSectionMap.values()) {
    if (!draftSectionMap.has(section.key)) changes.push(`Removed section: ${section.title}`);
  }

  const flatten = (schema: ContributorFormSchema) => new Map(
    sections(schema).flatMap((section) => section.fields.map((fieldValue, fieldIndex) => [
      fieldValue.key,
      { field: fieldValue, sectionKey: section.key, sectionTitle: section.title, order: fieldIndex },
    ] as const)),
  );
  const liveFields = flatten(live);
  const draftFields = flatten(draft);
  for (const [key, next] of draftFields) {
    const previous = liveFields.get(key);
    if (!previous) {
      changes.push(`Added field: ${next.field.label}`);
      continue;
    }
    if (previous.field.label !== next.field.label) changes.push(`${key}: label "${previous.field.label}" -> "${next.field.label}"`);
    if ((previous.field.help_text || "") !== (next.field.help_text || "")) changes.push(`${next.field.label}: help text changed`);
    if ((previous.field.placeholder || "") !== (next.field.placeholder || "")) changes.push(`${next.field.label}: placeholder changed`);
    if (previous.field.type !== next.field.type) changes.push(`${next.field.label}: type ${previous.field.type} -> ${next.field.type}`);
    if (Boolean(previous.field.required) !== Boolean(next.field.required)) changes.push(`${next.field.label}: ${next.field.required ? "now required" : "now optional"}`);
    if ((previous.field.visible !== false) !== (next.field.visible !== false)) changes.push(`${next.field.label}: ${next.field.visible === false ? "hidden" : "reactivated"}`);
    if (previous.sectionKey !== next.sectionKey) changes.push(`${next.field.label}: moved to ${next.sectionTitle}`);
    else if (previous.order !== next.order) changes.push(`${next.field.label}: field order changed`);
    if (JSON.stringify(previous.field.options || []) !== JSON.stringify(next.field.options || [])) changes.push(`${next.field.label}: options changed`);
  }
  for (const [key, previous] of liveFields) {
    if (!draftFields.has(key)) changes.push(`Removed field: ${previous.field.label}`);
  }
  return changes;
};

const ChangeSummary = ({ live, draft }: { live?: ContributorFormSchema; draft: ContributorFormSchema }) => {
  if (!live) return <p className="text-sm text-slate-500">No published version is available for comparison.</p>;
  const changes = schemaDifferences(live, draft);
  if (!changes.length) return <p className="text-sm text-slate-500">The draft matches the live contributor form.</p>;
  return <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">{changes.map((change, index) => <li key={`${index}-${change}`}>{change}</li>)}</ul>;
};

const FormPreview = ({ schema }: { schema: ContributorFormSchema }) => {
  const [previewValues, setPreviewValues] = useState<Record<string, string | string[]>>({});
  const setValue = (key: string, value: string | string[]) => {
    setPreviewValues((current) => ({ ...current, [key]: value }));
  };
  return (
    <div data-contributor-form-preview className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-bold text-slate-900">{schema.title || "Untitled form"}</h3>
          {schema.description && <p className="mt-1 text-sm text-slate-600">{schema.description}</p>}
        </div>
        {Object.keys(previewValues).length > 0 && (
          <button type="button" className="text-xs font-semibold text-blue-700" onClick={() => setPreviewValues({})}>
            Reset preview
          </button>
        )}
      </div>
      {schema.sections.filter((section) => section.visible !== false && !section.admin_only).map((section) => (
        <section key={section.key} className="rounded-xl border border-slate-200 bg-white p-4">
          <h4 className="font-bold text-slate-800">{section.title}</h4>
          {section.description && <p className="mb-3 mt-1 text-xs text-slate-500">{section.description}</p>}
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {section.fields.filter((field) => field.visible !== false && contributorFieldApplies(field, previewValues)).map((field) => (
              <label key={field.key} className={field.type === "textarea" || field.type === "multiselect" || field.type === "currency_by_year" ? "md:col-span-2" : ""}>
                <span className="text-sm font-medium text-slate-700">{field.label}{field.required ? " *" : ""}</span>
                {field.type === "textarea" ? (
                  <textarea rows={2} className="mt-1 w-full rounded-lg border border-slate-300 bg-white p-2" placeholder={field.placeholder} value={String(previewValues[field.key] || "")} onChange={(event) => setValue(field.key, event.target.value)} />
                ) : field.type === "select" ? (
                  <select className="mt-1 w-full rounded-lg border border-slate-300 bg-white p-2" value={String(previewValues[field.key] || "")} onChange={(event) => setValue(field.key, event.target.value)}>
                    <option value="">Choose</option>
                    {field.options?.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                ) : field.type === "multiselect" ? (
                  <div className="mt-1 space-y-1 rounded-lg border border-slate-300 bg-white p-2">
                    {field.options?.map((option) => {
                      const selectedValues = Array.isArray(previewValues[field.key]) ? previewValues[field.key] as string[] : [];
                      return <span key={option.value} className="flex items-center gap-2 text-xs text-slate-700"><input type="checkbox" checked={selectedValues.includes(option.value)} onChange={(event) => setValue(field.key, event.target.checked ? [...selectedValues, option.value] : selectedValues.filter((value) => value !== option.value))} />{option.label}</span>;
                    })}
                  </div>
                ) : field.type === "currency_by_year" ? (
                  <div className="mt-1 rounded-lg border border-slate-300 bg-slate-50 p-3 text-xs text-slate-500">Funding inputs generated from the implementation period</div>
                ) : (
                  <input type={field.type === "date" ? "date" : field.type === "number" || field.type === "year" ? "number" : "text"} className="mt-1 w-full rounded-lg border border-slate-300 bg-white p-2" placeholder={field.placeholder} value={String(previewValues[field.key] || "")} onChange={(event) => setValue(field.key, event.target.value)} />
                )}
                {field.help_text && <span className="mt-1 block text-xs text-slate-500">{field.help_text}</span>}
              </label>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
};

const ContributorFormsManager: React.FC<Props> = ({ mode }) => {
  const isAdmin = mode === "admin";
  const [versions, setVersions] = useState<CMSContributorFormVersion[]>([]);
  const [selected, setSelected] = useState<CMSContributorForm | null>(null);
  const [schema, setSchema] = useState<ContributorFormSchema | null>(null);
  const [baseline, setBaseline] = useState("");
  const [editMode, setEditMode] = useState<EditMode | null>(null);
  const [preview, setPreview] = useState(false);
  const [compareVersion, setCompareVersion] = useState<CMSContributorFormVersion | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [readOnly, setReadOnly] = useState(false);

  const dirty = Boolean(schema && baseline && JSON.stringify(schema) !== baseline);
  const baselineFieldKeys = useMemo(() => {
    if (!baseline) return new Set<string>();
    try {
      const value = JSON.parse(baseline) as ContributorFormSchema;
      return new Set(value.sections.flatMap((section) => section.fields.map((fieldValue) => fieldValue.key)));
    } catch {
      return new Set<string>();
    }
  }, [baseline]);
  const publishedVersion = useMemo(
    () => versions.find((version) => version.version_number === selected?.current_published_version_number),
    [selected?.current_published_version_number, versions],
  );
  const publishedFieldKeys = useMemo(
    () => new Set(publishedVersion?.schema_json.sections.flatMap((section) => section.fields.map((field) => field.key)) || []),
    [publishedVersion],
  );
  const publishedSectionKeys = useMemo(
    () => new Set(publishedVersion?.schema_json.sections.map((section) => section.key) || []),
    [publishedVersion],
  );
  const conditionalOptionValues = useMemo(() => {
    const dependencies = new Map<string, Set<string>>();
    for (const section of schema?.sections || []) {
      for (const field of section.fields) {
        if (!field.condition?.field) continue;
        const values = dependencies.get(field.condition.field) || new Set<string>();
        if (field.condition.equals !== undefined) values.add(field.condition.equals);
        if (field.condition.not_equals !== undefined) values.add(field.condition.not_equals);
        dependencies.set(field.condition.field, values);
      }
    }
    return dependencies;
  }, [schema]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await cmsApi.listContributorForms();
      const next = rows.find((row) => row.key === selected?.key) || rows[0] || null;
      setSelected(next);
      if (next) {
        setVersions(await cmsApi.listContributorFormVersions(next.id));
        if (!editMode) {
          const nextSchema = normalizeContributorSchema(next.draft_schema_json);
          setSchema(nextSchema);
          setBaseline(JSON.stringify(nextSchema));
        }
      }
    } catch (error) {
      setNotice(errorDetail(error, "Failed to load contributor forms."));
    } finally {
      setLoading(false);
    }
  }, [editMode, selected?.key]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [dirty]);

  useEffect(() => {
    if (!selected || !editMode || readOnly) return;
    const timer = window.setInterval(() => {
      cmsApi.heartbeatContributorForm(selected.id).catch(() => {
        setReadOnly(true);
        setNotice("Your form editing lock expired. Reload and reopen the editor to continue.");
      });
    }, 120_000);
    return () => window.clearInterval(timer);
  }, [editMode, readOnly, selected]);

  const beginEdit = async (nextMode: EditMode) => {
    if (!selected) return;
    setLoading(true);
    setNotice("");
    try {
      const locked = await cmsApi.lockContributorForm(selected.id) as CMSContributorForm;
      const nextSchema = normalizeContributorSchema(locked.draft_schema_json);
      setSelected(locked);
      setSchema(nextSchema);
      setBaseline(JSON.stringify(nextSchema));
      setEditMode(nextMode);
      setReadOnly(false);
      setPreview(false);
    } catch (error) {
      setReadOnly(true);
      setNotice(errorDetail(error, `This form is currently being edited by ${selected.lock_owner_name || "another editor"}.`));
    } finally {
      setLoading(false);
    }
  };

  const requestAccess = async () => {
    if (!selected) return;
    try {
      const response = await cmsApi.requestContributorFormAccess(selected.id) as { detail?: string };
      setNotice(response.detail || "Access request sent to the current editor.");
    } catch (error) {
      setNotice(errorDetail(error, "Failed to request form access."));
    }
  };

  const closeEditor = async () => {
    if (!selected) return;
    if (dirty && !window.confirm("Discard the unsaved form changes?")) return;
    if (!readOnly) {
      try { await cmsApi.unlockContributorForm(selected.id); } catch { /* expired locks need no cleanup */ }
    }
    setEditMode(null);
    setReadOnly(false);
    setPreview(false);
    await load();
  };

  const updateSection = (sectionIndex: number, updater: (section: ContributorFormSection) => ContributorFormSection) => {
    if (!schema) return;
    const sections = [...schema.sections];
    sections[sectionIndex] = updater({ ...sections[sectionIndex], fields: [...sections[sectionIndex].fields] });
    setSchema({ ...schema, sections });
  };

  const updateField = (sectionIndex: number, fieldIndex: number, updater: (field: ContributorFormField) => ContributorFormField) => {
    updateSection(sectionIndex, (section) => {
      const fields = [...section.fields];
      fields[fieldIndex] = updater({ ...fields[fieldIndex], options: fields[fieldIndex].options?.map((option) => ({ ...option })) });
      return { ...section, fields };
    });
  };

  const addField = (sectionIndex: number) => {
    if (!schema) return;
    const key = customKey(schema);
    updateSection(sectionIndex, (section) => ({
      ...section,
      fields: [...section.fields, {
        key,
        label: "New optional field",
        type: "text",
        required: false,
        visible: true,
        protected: false,
        help_text: "",
        placeholder: "",
      }],
    }));
  };

  const removeField = (sectionIndex: number, fieldIndex: number) => {
    if (!schema) return;
    const field = schema.sections[sectionIndex]?.fields[fieldIndex];
    if (!field || publishedFieldKeys.has(field.key)) return;
    if (!window.confirm(`Remove the unpublished field "${field.label}"?`)) return;
    updateSection(sectionIndex, (section) => ({
      ...section,
      fields: section.fields.filter((_, index) => index !== fieldIndex),
    }));
  };

  const removeSection = (sectionIndex: number) => {
    if (!schema) return;
    const section = schema.sections[sectionIndex];
    if (!section || publishedSectionKeys.has(section.key) || section.admin_only) return;
    if (!window.confirm(`Remove the unpublished section "${section.title}" and its fields?`)) return;
    setSchema({ ...schema, sections: schema.sections.filter((_, index) => index !== sectionIndex) });
  };

  const addSection = () => {
    if (!schema) return;
    let index = 1;
    const used = new Set(schema.sections.map((section) => section.key));
    while (used.has(`custom_section_${index}`)) index += 1;
    const nextSection: ContributorFormSection = {
        key: `custom_section_${index}`,
        title: "New section",
        description: "",
        visible: true,
        fields: [],
    };
    const firstSystemIndex = schema.sections.findIndex((section) => section.admin_only);
    const insertAt = firstSystemIndex < 0 ? schema.sections.length : firstSystemIndex;
    const sections = [...schema.sections];
    sections.splice(insertAt, 0, nextSection);
    setSchema({ ...schema, sections });
  };

  const saveDraft = async () => {
    if (!selected || !schema || !editMode) return;
    setLoading(true);
    setNotice("");
    try {
      const saved = await cmsApi.updateContributorForm(selected.id, {
        name: schema.title.trim(),
        description: String(schema.description || "").trim(),
        draft_schema_json: schema,
        expected_updated_at: selected.updated_at,
        edit_mode: editMode,
      }) as CMSContributorForm;
      setSelected(saved);
      setEditMode(null);
      setReadOnly(false);
      const savedSchema = normalizeContributorSchema(saved.draft_schema_json);
      setBaseline(JSON.stringify(savedSchema));
      setSchema(savedSchema);
      setNotice("Contributor form draft saved. Contributors still use the published version.");
      await load();
    } catch (error) {
      setNotice(errorDetail(error, "Failed to save the contributor form draft."));
    } finally {
      setLoading(false);
    }
  };

  const workflow = async (action: "submit" | "publish" | "reject") => {
    if (!selected) return;
    if (action === "publish" && !window.confirm(`Publish ${selected.name}? New project drafts will use the next version.`)) return;
    const remarks = action === "reject" ? window.prompt("Reason for rejection:", selected.review_notes || "") : "";
    if (action === "reject" && remarks === null) return;
    setLoading(true);
    try {
      if (action === "submit") await cmsApi.submitContributorForm(selected.id);
      if (action === "publish") await cmsApi.publishContributorForm(selected.id);
      if (action === "reject") await cmsApi.rejectContributorForm(selected.id, remarks || "");
      setNotice(action === "submit" ? "Form submitted for administrator review." : action === "publish" ? "New contributor form version published." : "Form draft returned with review notes.");
      await load();
    } catch (error) {
      setNotice(errorDetail(error, `Failed to ${action} the contributor form.`));
    } finally {
      setLoading(false);
    }
  };

  const restore = async (version: CMSContributorFormVersion) => {
    if (!selected || !isAdmin) return;
    const resetToLive = version.version_number === selected.current_published_version_number;
    const prompt = resetToLive
      ? "Reset the current draft to the live published form? All unpublished form changes will be discarded."
      : `Restore published version ${version.version_number} as a new draft? The live form will not change until that draft is published.`;
    if (!window.confirm(prompt)) return;
    setLoading(true);
    try {
      await cmsApi.restoreContributorFormVersion(selected.id, version.id);
      setCompareVersion(null);
      setNotice(resetToLive ? "Draft reset to the live published form." : `Version ${version.version_number} restored as a draft. Review it before publishing.`);
      await load();
    } catch (error) {
      setNotice(errorDetail(error, "Failed to restore the selected form version."));
    } finally {
      setLoading(false);
    }
  };

  if (!selected || !schema) {
    return <div className="portal-card p-5 text-sm text-slate-600">{loading ? "Loading contributor forms..." : notice || "No contributor form definition is available."}</div>;
  }

  return (
    <div className="space-y-4">
      {notice && <div role="status" aria-live="polite" className="portal-card border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">{notice}</div>}
      <div className="portal-card overflow-hidden" data-cms-contributor-form-key={selected.key}>
        <div className="portal-card-header flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-lg font-bold text-slate-900">{selected.name}</h3>
              <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(selected.status)}`}>{selected.status.replace("_", " ")}</span>
              {selected.has_unpublished_changes && <span className="rounded-full bg-orange-100 px-2 py-1 text-xs font-semibold text-orange-700">unpublished changes</span>}
            </div>
            <p className="mt-1 text-sm text-slate-600">{selected.description}</p>
            <p className="mt-2 text-xs text-slate-500">Published version {selected.current_published_version_number || "none"} · {schemaSummary(schema)} · {formatDate(selected.published_at)}</p>
            {selected.review_notes && <p className="mt-2 text-sm font-medium text-rose-700">Review note: {selected.review_notes}</p>}
          </div>
          {!editMode && <div className="flex flex-wrap gap-2">
            {selected.is_locked && !selected.locked_by_me && <button className="portal-btn portal-btn-ghost" onClick={() => void requestAccess()}>Request Access from {selected.lock_owner_name || "Editor"}</button>}
            <button className="portal-btn portal-btn-primary" disabled={loading || selected.status === "submitted" && !isAdmin} onClick={() => void beginEdit("update")}>Update Form</button>
            <button className="portal-btn portal-btn-ghost" disabled={loading || selected.status === "submitted" && !isAdmin} onClick={() => void beginEdit("change")}>Change Form</button>
            {!isAdmin && selected.status !== "submitted" && selected.has_unpublished_changes && <button className="portal-btn portal-btn-ghost" onClick={() => void workflow("submit")}>Submit for Review</button>}
            {isAdmin && selected.has_unpublished_changes && <button className="portal-btn portal-btn-primary" onClick={() => void workflow("publish")}>Publish</button>}
            {isAdmin && selected.status === "submitted" && <button className="portal-btn portal-btn-ghost" onClick={() => void workflow("reject")}>Reject</button>}
          </div>}
        </div>
      </div>

      {(selected.has_unpublished_changes || dirty) && (
        <div className="portal-card overflow-hidden">
          <div className="portal-card-header"><h3 className="font-bold text-slate-900">Draft Changes from Live Form</h3><p className="text-xs text-slate-500">Review every contributor-facing change before publishing.</p></div>
          <div className="portal-card-body"><ChangeSummary live={publishedVersion?.schema_json} draft={schema} /></div>
        </div>
      )}

      {editMode ? (
        <div className="grid gap-4 2xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.55fr)]">
          <div className="portal-card overflow-hidden">
            <div className="portal-card-header flex flex-wrap items-center justify-between gap-3">
              <div><h3 className="font-bold text-slate-900">{editMode === "update" ? "Update Form" : "Change Form"}</h3><p className="text-xs text-slate-500">{editMode === "update" ? "Edit wording and add small fields without changing the structure." : "Reorder, hide optional items, and make controlled structural changes."}</p></div>
              <div className="flex gap-2"><button className="portal-btn portal-btn-ghost" onClick={() => setPreview((value) => !value)}>{preview ? "Hide Preview" : "Preview as Contributor"}</button><button className="portal-btn portal-btn-ghost" onClick={() => void closeEditor()}>Cancel</button></div>
            </div>
            {readOnly && <div className="border-b border-amber-200 bg-amber-50 px-5 py-3 text-sm text-amber-800">This form is locked by another editor. Your view is read-only.</div>}
            <fieldset disabled={readOnly} className="portal-card-body space-y-5 disabled:opacity-70">
              <div className="grid gap-3 md:grid-cols-2">
                <label className="block"><span className="text-sm font-medium text-slate-700">Form title</span><input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" value={schema.title} onChange={(event) => setSchema({ ...schema, title: event.target.value })} /></label>
                <label className="block"><span className="text-sm font-medium text-slate-700">Form description</span><input className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2" value={schema.description || ""} onChange={(event) => setSchema({ ...schema, description: event.target.value })} /></label>
              </div>
              {schema.sections.map((section, sectionIndex) => section.admin_only ? null : (
                <section key={section.key} data-form-section-key={section.key} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${publishedSectionKeys.has(section.key) ? "bg-blue-100 text-blue-700" : "bg-amber-100 text-amber-700"}`}>{publishedSectionKeys.has(section.key) ? "Published section" : "Unpublished section"}</span>
                        <span className="font-mono text-xs text-slate-500">{section.key}</span>
                      </div>
                      <div className="grid gap-2 md:grid-cols-2">
                        <input aria-label="Section title" className="rounded-lg border border-slate-300 px-3 py-2 font-semibold" value={section.title} onChange={(event) => updateSection(sectionIndex, (current) => ({ ...current, title: event.target.value }))} />
                        <input aria-label="Section description" className="rounded-lg border border-slate-300 px-3 py-2 text-sm" value={section.description || ""} placeholder="Optional section guidance" onChange={(event) => updateSection(sectionIndex, (current) => ({ ...current, description: event.target.value }))} />
                      </div>
                    </div>
                    {editMode === "change" && <div className="flex flex-wrap items-center gap-2 text-xs"><button type="button" onClick={() => setSchema({ ...schema, sections: moveContributorSection(schema.sections, sectionIndex, -1) })}>Up</button><button type="button" onClick={() => setSchema({ ...schema, sections: moveContributorSection(schema.sections, sectionIndex, 1) })}>Down</button>{!section.fields.some((field) => field.required || field.condition_required) && <label className="flex items-center gap-1"><input type="checkbox" checked={section.visible !== false} onChange={(event) => updateSection(sectionIndex, (current) => ({ ...current, visible: event.target.checked }))} />Visible</label>}{!publishedSectionKeys.has(section.key) && <button type="button" className="font-semibold text-rose-700" onClick={() => removeSection(sectionIndex)}>Remove section</button>}</div>}
                  </div>
                  <div className="mt-3 space-y-3">
                    {section.fields.map((item, fieldIndex) => {
                      const isCustom = item.key.startsWith("custom_");
                      const isPublished = publishedFieldKeys.has(item.key);
                      const canRemove = isCustom && !isPublished && (editMode === "change" || !baselineFieldKeys.has(item.key));
                      const canReorder = editMode === "change" || (isCustom && !baselineFieldKeys.has(item.key));
                      return (
                        <div key={item.key} data-form-field-key={item.key} className="rounded-xl border border-slate-200 bg-white p-3">
                          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                            <label><span className="text-xs font-semibold text-slate-600">Label</span><input className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-2" value={item.label} onChange={(event) => updateField(sectionIndex, fieldIndex, (fieldValue) => ({ ...fieldValue, label: event.target.value }))} /></label>
                            <label><span className="text-xs font-semibold text-slate-600">Help text</span><input className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-2" value={item.help_text || ""} onChange={(event) => updateField(sectionIndex, fieldIndex, (fieldValue) => ({ ...fieldValue, help_text: event.target.value }))} /></label>
                            <label><span className="text-xs font-semibold text-slate-600">Placeholder</span><input className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-2" value={item.placeholder || ""} onChange={(event) => updateField(sectionIndex, fieldIndex, (fieldValue) => ({ ...fieldValue, placeholder: event.target.value }))} /></label>
                            <label><span className="text-xs font-semibold text-slate-600">Field type</span><select disabled={!isCustom || publishedFieldKeys.has(item.key) || editMode === "update" && baselineFieldKeys.has(item.key)} className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-2" value={item.type} onChange={(event) => updateField(sectionIndex, fieldIndex, (fieldValue) => ({ ...fieldValue, type: event.target.value as ContributorFormFieldType, options: ["select", "multiselect"].includes(event.target.value) ? fieldValue.options || [{ value: "option_1", label: "Option 1" }] : undefined }))}>{fieldTypeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
                          </div>
                          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-600">
                            <span className={`rounded-full px-2 py-0.5 font-semibold ${!isCustom ? "bg-slate-200 text-slate-700" : isPublished ? "bg-blue-100 text-blue-700" : "bg-amber-100 text-amber-700"}`}>{!isCustom ? "Protected" : isPublished ? "Published custom" : "Unpublished custom"}</span>
                            <span className="rounded-full bg-slate-100 px-2 py-0.5 font-semibold text-slate-600">Order {fieldIndex + 1}</span>
                            <span className="font-mono">{item.key}</span>
                            {canReorder && <><button type="button" disabled={fieldIndex === 0} className="font-semibold text-blue-700 disabled:cursor-not-allowed disabled:text-slate-300" aria-label={`Move ${item.label} up`} onClick={() => updateSection(sectionIndex, (current) => ({ ...current, fields: move(current.fields, fieldIndex, -1) }))}>Move up</button><button type="button" disabled={fieldIndex === section.fields.length - 1} className="font-semibold text-blue-700 disabled:cursor-not-allowed disabled:text-slate-300" aria-label={`Move ${item.label} down`} onClick={() => updateSection(sectionIndex, (current) => ({ ...current, fields: move(current.fields, fieldIndex, 1) }))}>Move down</button></>}
                            {editMode === "change" && <>{(isCustom || !item.required && !item.condition_required) && <label className="flex items-center gap-1"><input type="checkbox" checked={item.visible !== false} onChange={(event) => updateField(sectionIndex, fieldIndex, (fieldValue) => ({ ...fieldValue, visible: event.target.checked }))} />{item.visible === false ? "Reactivate" : "Visible"}</label>}{isCustom && <label className="flex items-center gap-1"><input type="checkbox" checked={Boolean(item.required)} onChange={(event) => updateField(sectionIndex, fieldIndex, (fieldValue) => ({ ...fieldValue, required: event.target.checked }))} />Required</label>}</>}
                            {canRemove && <button type="button" className="font-semibold text-rose-700" onClick={() => removeField(sectionIndex, fieldIndex)}>Remove field</button>}
                          </div>
                          {isCustom && editMode === "update" && !baselineFieldKeys.has(item.key) && <label className="mt-2 flex items-center gap-1 text-xs text-slate-600"><input type="checkbox" checked={Boolean(item.required)} onChange={(event) => updateField(sectionIndex, fieldIndex, (fieldValue) => ({ ...fieldValue, required: event.target.checked }))} />Required for submission</label>}
                          {item.options && <div className="mt-3 space-y-2"><div className="grid gap-2 sm:grid-cols-2">{item.options.map((option, optionIndex) => {
                            const canChangeOptionOrder = editMode === "change" || !baselineFieldKeys.has(item.key);
                            const controlsCondition = conditionalOptionValues.get(item.key)?.has(option.value) === true;
                            const canRemoveOption = canChangeOptionOrder && item.options!.length > 1 && !controlsCondition;
                            return <label key={`${option.value}-${optionIndex}`} data-form-option-value={option.value}><span className="text-xs text-slate-500">Option label · Order {optionIndex + 1}</span><div className="flex gap-2"><input className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5" value={option.label} onChange={(event) => updateField(sectionIndex, fieldIndex, (fieldValue) => ({ ...fieldValue, options: (fieldValue.options || []).map((value, index) => index === optionIndex ? { ...value, label: event.target.value } : value) }))} />{canChangeOptionOrder && <div className="mt-1 flex items-center gap-1"><button type="button" disabled={optionIndex === 0} className="rounded px-1.5 py-1 text-xs font-semibold text-blue-700 disabled:text-slate-300" aria-label={`Move option ${option.label} up`} onClick={() => updateField(sectionIndex, fieldIndex, (fieldValue) => ({ ...fieldValue, options: move(fieldValue.options || [], optionIndex, -1) }))}>Up</button><button type="button" disabled={optionIndex === item.options!.length - 1} className="rounded px-1.5 py-1 text-xs font-semibold text-blue-700 disabled:text-slate-300" aria-label={`Move option ${option.label} down`} onClick={() => updateField(sectionIndex, fieldIndex, (fieldValue) => ({ ...fieldValue, options: move(fieldValue.options || [], optionIndex, 1) }))}>Down</button></div>}{canRemoveOption && <button type="button" className="text-xs font-semibold text-rose-700" aria-label={`Remove option ${option.label}`} onClick={() => updateField(sectionIndex, fieldIndex, (fieldValue) => ({ ...fieldValue, options: (fieldValue.options || []).filter((_, index) => index !== optionIndex) }))}>Remove</button>}</div>{controlsCondition && <span className="mt-1 block text-xs text-amber-700">Used by a conditional question and cannot be removed.</span>}</label>;
                          })}</div>{(editMode === "change" || !baselineFieldKeys.has(item.key)) && <button type="button" className="text-xs font-semibold text-blue-700" onClick={() => updateField(sectionIndex, fieldIndex, (fieldValue) => { const current = fieldValue.options || []; const value = nextOptionValue(fieldValue); return { ...fieldValue, options: [...current, { value, label: `Option ${value.replace("option_", "")}` }] }; })}>Add option</button>}</div>}
                        </div>
                      );
                    })}
                  </div>
                  <button type="button" className="portal-btn portal-btn-ghost mt-3" onClick={() => addField(sectionIndex)}>Add Optional Field</button>
                  <p className="mt-2 text-xs text-slate-500">New fields start as optional. Use their Move up and Move down controls to set the order shown to contributors.</p>
                </section>
              ))}
              {editMode === "change" && <button type="button" className="portal-btn portal-btn-ghost" onClick={addSection}>Add Section</button>}
              <div className="flex justify-end gap-2 border-t border-slate-200 pt-4"><button type="button" className="portal-btn portal-btn-ghost" onClick={() => void closeEditor()}>Discard</button><button type="button" className="portal-btn portal-btn-primary" disabled={loading || !dirty} onClick={() => void saveDraft()}>{loading ? "Saving..." : "Save Draft"}</button></div>
            </fieldset>
          </div>
          <div>{preview ? <FormPreview schema={schema} /> : <div className="portal-card p-4 text-sm text-slate-600"><h3 className="font-bold text-slate-800">Editing safeguards</h3><p className="mt-2">Protected workflow fields keep their stable keys, types, option values, and required rules. Published fields are hidden instead of deleted so older projects remain readable. Unpublished custom fields and sections can be removed permanently.</p><p className="mt-2">The validator AI analysis is system-managed and is intentionally excluded from this contributor-form editor.</p></div>}</div>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="portal-card overflow-hidden"><div className="portal-card-header"><h3 className="font-bold text-slate-900">Current Draft Preview</h3></div><div className="portal-card-body"><FormPreview schema={schema} /></div></div>
          <div className="portal-card overflow-hidden">
            <div className="portal-card-header"><h3 className="font-bold text-slate-900">Revert to Former Form</h3><p className="text-xs text-slate-500">Restoring creates a draft. Contributors continue using the live version until an administrator publishes again.</p></div>
            <div className="portal-card-body space-y-3">
              {versions.length === 0 ? <p className="text-sm text-slate-500">No published versions yet.</p> : versions.map((version) => (
                <div key={version.id} data-form-version={version.version_number} className="rounded-xl border border-slate-200 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-3"><div><strong>Version {version.version_number}</strong><p className="text-xs text-slate-500">{schemaSummary(version.schema_json)} · {version.published_by_name || "system"} · {formatDate(version.published_at)}</p></div><div className="flex flex-wrap gap-2"><button className="text-sm text-blue-700" onClick={() => setCompareVersion(compareVersion?.id === version.id ? null : version)}>Preview changes</button>{isAdmin && version.version_number === selected.current_published_version_number && selected.has_unpublished_changes && <button className="text-sm font-semibold text-rose-700" onClick={() => void restore(version)}>Reset Draft to Live Version</button>}{isAdmin && version.version_number !== selected.current_published_version_number && <button className="text-sm text-amber-700" onClick={() => void restore(version)}>Restore as Draft</button>}</div></div>
                  {compareVersion?.id === version.id && <div className="mt-3 border-t border-slate-200 pt-3"><p className="mb-2 text-xs font-semibold text-slate-600">Changes from Version {version.version_number} to current draft</p><div className="mb-3"><ChangeSummary live={version.schema_json} draft={schema} /></div><FormPreview schema={version.schema_json} /></div>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ContributorFormsManager;
