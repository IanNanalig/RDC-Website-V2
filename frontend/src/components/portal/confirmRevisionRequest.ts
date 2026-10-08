export const confirmRevisionRequest = (isProgressUpdate: boolean): boolean =>
  window.confirm(
    `Request revisions for this ${isProgressUpdate ? "progress update" : "project"}?\n\n` +
    "The contributor will be notified and can edit only the fields you selected. " +
    "The review status will change to Needs Revision.\n\nContinue?",
  );
