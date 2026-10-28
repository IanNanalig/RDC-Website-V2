import api from "./api";

export type ConcernCategory = { code: string; label: string };
export type ConcernOptions = {
  categories: ConcernCategory[];
  upload_policy: {
    allowed_extensions: string[];
    max_files: number;
    max_file_bytes: number;
    max_total_bytes: number;
    malware_scanned: boolean;
  };
  turnstile_required: boolean;
};

export type ConcernSubmissionResult = {
  accepted: boolean;
  reference: string;
  notification_status: string;
  acknowledgement_status: string;
  message: string;
};

export const getConcernOptions = () =>
  api.get("public/project-concerns/options/") as Promise<ConcernOptions>;

export const submitProjectConcern = (payload: FormData) =>
  api.postForm("public/project-concerns/", payload) as Promise<ConcernSubmissionResult>;

