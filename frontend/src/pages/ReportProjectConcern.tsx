import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import TurnstileWidget from "../components/TurnstileWidget";
import { getPublicProject, getPublicProjects } from "../services/publicProjectsApi";
import {
  getConcernOptions,
  submitProjectConcern,
  type ConcernOptions,
  type ConcernSubmissionResult,
} from "../services/projectConcernsApi";
import type { PublicProject } from "../types/api";

type ReportingMode = "anonymous" | "email";

const formatBytes = (bytes: number) => {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
};

const newSubmissionId = () => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  const random = () => Math.floor(Math.random() * 16).toString(16);
  return `xxxxxxxx-xxxx-4xxx-8xxx-xxxxxxxxxxxx`.replace(/x/g, random);
};

const ReportProjectConcern: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [options, setOptions] = useState<ConcernOptions | null>(null);
  const [selectedProject, setSelectedProject] = useState<PublicProject | null>(null);
  const [projectLocked, setProjectLocked] = useState(false);
  const [projectSearch, setProjectSearch] = useState("");
  const [projectResults, setProjectResults] = useState<PublicProject[]>([]);
  const [searching, setSearching] = useState(false);
  const [reportingMode, setReportingMode] = useState<ReportingMode>("anonymous");
  const [category, setCategory] = useState("");
  const [description, setDescription] = useState("");
  const [email, setEmail] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [captchaToken, setCaptchaToken] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [result, setResult] = useState<ConcernSubmissionResult | null>(null);
  const submissionId = useRef(newSubmissionId());
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      try {
        const setup = await getConcernOptions();
        if (!active) return;
        setOptions(setup);
        setCategory(setup.categories[0]?.code || "");
        const projectId = Number(searchParams.get("project"));
        if (projectId > 0) {
          const project = await getPublicProject(projectId);
          if (!active) return;
          setSelectedProject(project);
          setProjectLocked(true);
        }
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "The reporting form could not be loaded.");
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => { active = false; };
  }, [searchParams]);

  useEffect(() => {
    if (selectedProject || projectSearch.trim().length < 2) {
      setProjectResults([]);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setSearching(true);
      try {
        const rows = await getPublicProjects({ q: projectSearch.trim(), limit: 12, view: "summary" });
        if (!controller.signal.aborted) setProjectResults(rows);
      } catch {
        if (!controller.signal.aborted) setProjectResults([]);
      } finally {
        if (!controller.signal.aborted) setSearching(false);
      }
    }, 250);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [projectSearch, selectedProject]);

  const totalFileBytes = useMemo(() => files.reduce((sum, file) => sum + file.size, 0), [files]);
  const selectedCategory = options?.categories.find((item) => item.code === category);

  const chooseProject = (project: PublicProject) => {
    setSelectedProject(project);
    setProjectLocked(true);
    setProjectResults([]);
    setProjectSearch("");
    setSearchParams({ project: String(project.id) });
    setError("");
  };

  const changeProject = () => {
    setSelectedProject(null);
    setProjectLocked(false);
    setSearchParams({});
    setError("");
  };

  const addFiles = (incoming: FileList | null) => {
    if (!incoming || !options) return;
    const next = [...files, ...Array.from(incoming)];
    if (next.length > options.upload_policy.max_files) {
      setError(`Attach no more than ${options.upload_policy.max_files} files.`);
      return;
    }
    const oversized = next.find((file) => file.size <= 0 || file.size > options.upload_policy.max_file_bytes);
    if (oversized) {
      setError(`${oversized.name} must be no larger than ${formatBytes(options.upload_policy.max_file_bytes)}.`);
      return;
    }
    if (next.reduce((sum, file) => sum + file.size, 0) > options.upload_policy.max_total_bytes) {
      setError(`Attachments cannot exceed ${formatBytes(options.upload_policy.max_total_bytes)} in total.`);
      return;
    }
    const allowed = new Set(options.upload_policy.allowed_extensions.map((item) => item.toLowerCase()));
    const unsupported = next.find((file) => !allowed.has(file.name.split(".").pop()?.toLowerCase() || ""));
    if (unsupported) {
      setError(`${unsupported.name} is not a supported file type.`);
      return;
    }
    setFiles(next);
    setError("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const validateForReview = (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    if (!selectedProject) return setError("Choose the project related to this concern.");
    if (!category) return setError("Choose a concern category.");
    if (description.trim().length < 10) return setError("Describe the concern using at least 10 characters.");
    if (reportingMode === "email" && !email.trim()) return setError("Enter your email for email-enabled reporting.");
    if (options?.turnstile_required && !captchaToken) return setError("Complete the security check before continuing.");
    setReviewOpen(true);
  };

  const submit = async () => {
    if (!selectedProject || submitting) return;
    setSubmitting(true);
    setError("");
    const payload = new FormData();
    payload.set("submission_id", submissionId.current);
    payload.set("project_id", String(selectedProject.id));
    payload.set("reporting_mode", reportingMode);
    payload.set("category", category);
    payload.set("description", description.trim());
    if (reportingMode === "email") payload.set("email", email.trim().toLowerCase());
    if (captchaToken) payload.set("captcha_token", captchaToken);
    files.forEach((file) => payload.append("evidence", file, file.name));
    try {
      const response = await submitProjectConcern(payload);
      setResult(response);
      setReviewOpen(false);
    } catch (err) {
      setReviewOpen(false);
      setError(err instanceof Error ? err.message : "The report could not be submitted. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <main className="min-h-[55vh] bg-slate-50 px-4 py-16 text-center text-slate-600">Loading the project concern form...</main>;
  }

  if (result) {
    return (
      <main className="min-h-[60vh] bg-slate-50 px-4 py-12">
        <section className="mx-auto max-w-2xl rounded-2xl border border-emerald-200 bg-white p-6 shadow-sm sm:p-8" aria-live="polite">
          <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-2xl text-emerald-700">✓</div>
          <h1 className="text-2xl font-bold text-slate-900">Project concern accepted</h1>
          <p className="mt-3 text-slate-700">{result.message}</p>
          <div className="mt-5 rounded-xl bg-slate-100 p-4">
            <p className="text-sm text-slate-600">Report reference</p>
            <p className="mt-1 break-all font-mono text-lg font-bold text-slate-900">{result.reference}</p>
          </div>
          {reportingMode === "anonymous" ? (
            <p className="mt-4 text-sm text-amber-800">This report is anonymous, so the receiving office cannot send you replies or status updates.</p>
          ) : (
            <p className="mt-4 text-sm text-slate-600">Email communication is enabled. Keep the reference above for any follow-up correspondence.{result.acknowledgement_status !== "sent" ? " Your acknowledgment email is pending retry." : ""}</p>
          )}
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/projects" className="rounded-lg bg-green-700 px-4 py-2.5 font-semibold text-white hover:bg-green-800">Return to Projects</Link>
            <Link to="/" className="rounded-lg border border-slate-300 px-4 py-2.5 font-semibold text-slate-700 hover:bg-slate-50">Return Home</Link>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="bg-slate-50 px-4 py-8 sm:py-12">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6">
          <p className="text-sm font-semibold uppercase tracking-wide text-green-700">Public project reporting</p>
          <h1 className="mt-1 text-3xl font-bold text-slate-900">Report a Project Concern</h1>
          <p className="mt-2 max-w-3xl text-slate-600">Share a potential discrepancy or implementation concern for appropriate review. A submission is a concern, not a finding of fraud or noncompliance.</p>
        </div>

        {error && <div role="alert" className="mb-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}

        <form onSubmit={validateForReview} className="space-y-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
          <section aria-labelledby="project-heading">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="project-heading" className="text-lg font-semibold text-slate-900">1. Project</h2>
              {selectedProject && projectLocked && <button type="button" onClick={changeProject} className="text-sm font-semibold text-blue-700 hover:underline">Change Project</button>}
            </div>
            {selectedProject ? (
              <div className="mt-3 rounded-xl border border-blue-200 bg-blue-50 p-4">
                <p className="mt-1 font-semibold text-slate-900">{selectedProject.title}</p>
                <p className="mt-1 text-sm text-slate-600">Primary agency: {selectedProject.agency || "Not specified"}</p>
              </div>
            ) : (
              <div className="mt-3">
                <label htmlFor="project-search" className="text-sm font-medium text-slate-700">Search public projects</label>
                <input id="project-search" value={projectSearch} onChange={(event) => setProjectSearch(event.target.value)} placeholder="Enter a project title or agency" className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5" autoComplete="off" />
                {searching && <p className="mt-2 text-sm text-slate-500">Searching...</p>}
                {projectResults.length > 0 && (
                  <div className="mt-2 max-h-72 overflow-y-auto rounded-xl border border-slate-200" role="listbox" aria-label="Matching public projects">
                    {projectResults.map((project) => (
                      <button key={project.id} type="button" onClick={() => chooseProject(project)} className="block w-full border-b border-slate-100 px-4 py-3 text-left last:border-0 hover:bg-slate-50">
                        <span className="block font-medium text-slate-900">{project.title}</span>
                        <span className="mt-0.5 block text-xs text-slate-500">{project.agency || "Agency not specified"}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="border-t border-slate-200 pt-5" aria-labelledby="concern-heading">
            <h2 id="concern-heading" className="text-lg font-semibold text-slate-900">2. Concern details</h2>
            <label className="mt-3 block">
              <span className="text-sm font-medium text-slate-700">Concern category</span>
              <select value={category} onChange={(event) => setCategory(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5" required>
                <option value="">Select a category</option>
                {options?.categories.map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}
              </select>
            </label>
            <label className="mt-4 block">
              <span className="text-sm font-medium text-slate-700">Description</span>
              <textarea value={description} onChange={(event) => setDescription(event.target.value)} maxLength={10000} rows={7} placeholder="Describe what you observed, including relevant dates or published details." className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5" required />
              <span className="mt-1 block text-right text-xs text-slate-500">{description.length.toLocaleString()} / 10,000</span>
            </label>
          </section>

          <section className="border-t border-slate-200 pt-5" aria-labelledby="evidence-heading">
            <h2 id="evidence-heading" className="text-lg font-semibold text-slate-900">3. Supporting evidence <span className="text-sm font-normal text-slate-500">(optional)</span></h2>
            <p className="mt-1 text-sm text-slate-600">Up to 5 files, 5 MB each and 15 MB total. Accepted: PDF, DOCX, XLSX, CSV, PNG, JPG, JPEG.</p>
            <p className="mt-1 text-xs text-amber-700">Files are format-validated and kept private, but they are not malware-scanned.</p>
            <input ref={fileInputRef} type="file" multiple accept=".pdf,.docx,.xlsx,.csv,.png,.jpg,.jpeg" onChange={(event) => addFiles(event.target.files)} className="mt-3 block w-full rounded-xl border border-dashed border-slate-300 p-3 text-sm" />
            {files.length > 0 && (
              <div className="mt-3 space-y-2">
                {files.map((file, index) => (
                  <div key={`${file.name}-${file.size}-${index}`} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 text-sm">
                    <span className="min-w-0 truncate text-slate-700">{file.name} <span className="text-slate-400">({formatBytes(file.size)})</span></span>
                    <button type="button" onClick={() => setFiles((current) => current.filter((_, itemIndex) => itemIndex !== index))} className="shrink-0 font-semibold text-rose-700">Remove</button>
                  </div>
                ))}
                <p className="text-right text-xs text-slate-500">Total: {formatBytes(totalFileBytes)}</p>
              </div>
            )}
          </section>

          <section className="border-t border-slate-200 pt-5" aria-labelledby="contact-heading">
            <h2 id="contact-heading" className="text-lg font-semibold text-slate-900">4. Reporting and contact</h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className={`rounded-xl border p-4 ${reportingMode === "anonymous" ? "border-green-600 bg-green-50" : "border-slate-200"}`}>
                <input type="radio" name="reporting-mode" value="anonymous" checked={reportingMode === "anonymous"} onChange={() => { setReportingMode("anonymous"); setEmail(""); }} />
                <span className="ml-2 font-semibold text-slate-900">Anonymous reporting</span>
                <span className="mt-2 block text-sm text-slate-600">No email is collected. You will not receive replies or status updates.</span>
              </label>
              <label className={`rounded-xl border p-4 ${reportingMode === "email" ? "border-green-600 bg-green-50" : "border-slate-200"}`}>
                <input type="radio" name="reporting-mode" value="email" checked={reportingMode === "email"} onChange={() => setReportingMode("email")} />
                <span className="ml-2 font-semibold text-slate-900">Email-enabled reporting</span>
                <span className="mt-2 block text-sm text-slate-600">Provide an email to receive an acknowledgment and possible follow-up.</span>
              </label>
            </div>
            {reportingMode === "email" && (
              <label className="mt-4 block">
                <span className="text-sm font-medium text-slate-700">Email address</span>
                <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5" autoComplete="email" required />
              </label>
            )}
          </section>

          <section className="rounded-xl bg-slate-100 p-4 text-sm leading-relaxed text-slate-700" aria-labelledby="privacy-heading">
            <h2 id="privacy-heading" className="font-semibold text-slate-900">Privacy and handling notice</h2>
            <p className="mt-1">The project, category, description, and evidence are stored privately and sent to authorized receiving personnel for review. Your email is stored only when email-enabled reporting is selected. Ordinary infrastructure logs and a non-reversible network fingerprint may be retained for security and abuse prevention. Absolute anonymity or confidentiality cannot be guaranteed.</p>
          </section>

          {Boolean(import.meta.env.VITE_TURNSTILE_SITE_KEY) && <TurnstileWidget onToken={setCaptchaToken} />}

          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Link to={selectedProject ? `/projects/${selectedProject.id}` : "/projects"} className="rounded-xl border border-slate-300 px-5 py-2.5 text-center font-semibold text-slate-700">Cancel</Link>
            <button type="submit" disabled={submitting} className="rounded-xl bg-green-700 px-5 py-2.5 font-semibold text-white hover:bg-green-800 disabled:opacity-60">Review Report</button>
          </div>
        </form>
      </div>

      {reviewOpen && selectedProject && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/60 p-4" role="dialog" aria-modal="true" aria-labelledby="review-title">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-xl sm:p-6">
            <h2 id="review-title" className="text-xl font-bold text-slate-900">Review before submitting</h2>
            <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
              <div><dt className="text-slate-500">Project</dt><dd className="font-medium text-slate-900">{selectedProject.title}</dd></div>
              <div><dt className="text-slate-500">Category</dt><dd className="font-medium text-slate-900">{selectedCategory?.label}</dd></div>
              <div><dt className="text-slate-500">Reporting mode</dt><dd className="font-medium capitalize text-slate-900">{reportingMode === "email" ? "Email-enabled" : "Anonymous"}</dd></div>
              <div><dt className="text-slate-500">Attachments</dt><dd className="font-medium text-slate-900">{files.length}</dd></div>
            </dl>
            <div className="mt-4 rounded-xl bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Description</p>
              <p className="mt-1 whitespace-pre-wrap break-words text-sm text-slate-800">{description.trim()}</p>
            </div>
            <p className="mt-4 text-sm text-slate-600">By submitting, you confirm that the information is provided in good faith for appropriate review.</p>
            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <button type="button" disabled={submitting} onClick={() => setReviewOpen(false)} className="rounded-xl border border-slate-300 px-5 py-2.5 font-semibold text-slate-700 disabled:opacity-60">Go Back</button>
              <button type="button" disabled={submitting} onClick={() => void submit()} className="rounded-xl bg-green-700 px-5 py-2.5 font-semibold text-white disabled:cursor-wait disabled:opacity-60">{submitting ? "Submitting..." : "Submit Report"}</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
};

export default ReportProjectConcern;
