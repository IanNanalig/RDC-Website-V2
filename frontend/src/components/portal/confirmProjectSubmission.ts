type SubmissionKind = "project" | "revision" | "progress";

export const confirmProjectSubmission = (kind: SubmissionKind, title: string): boolean => {
  const project = title.trim() ? `"${title.trim()}"` : "this project";
  const action = kind === "progress"
    ? `Submit the progress update for ${project} for validation?`
    : kind === "revision"
    ? `Resubmit revisions to ${project} for validation?`
    : `Submit ${project} for validation?`;

  return window.confirm(`${action}\n\nThe validator will review this submission. Continue?`);
};
