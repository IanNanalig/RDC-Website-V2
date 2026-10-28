import { api } from "./api";
import { API_BASE_URL } from "../config/api";

export type SupportingDocumentStatus = "queued" | "processing" | "ready" | "failed";

export type SupportingDocument = {
  id: number;
  project: number;
  field_key: string;
  form_key: string;
  form_version: number;
  original_filename: string;
  content_type: string;
  extension: string;
  size_bytes: number;
  checksum_sha256: string;
  extraction_status: SupportingDocumentStatus;
  extraction_metadata?: Record<string, unknown>;
  processing_error?: string;
  uploaded_by_name?: string;
  download_url: string;
  created_at: string;
  updated_at: string;
};

export type DocumentAssessment = {
  id?: number;
  status: "not_required" | "missing" | "pending" | "queued" | "processing" | "pass" | "fail" | "unavailable";
  required?: boolean;
  collective_sufficient?: boolean;
  summary?: string;
  error_message?: string;
  source_hash?: string;
  document_results?: Array<{
    document_id: number;
    filename: string;
    related: boolean;
    explanation: string;
    citations?: string[];
  }>;
};

const rows = (value: unknown): SupportingDocument[] => {
  if (Array.isArray(value)) return value as SupportingDocument[];
  if (value && typeof value === "object" && Array.isArray((value as { results?: unknown }).results)) {
    return (value as { results: SupportingDocument[] }).results;
  }
  return [];
};

export const projectDocumentsApi = {
  list: async (projectId: string | number) => rows(await api.get(`project-supporting-documents/?project=${projectId}`, true)),
  upload: (projectId: string | number, fieldKey: string, file: File) => {
    const body = new FormData();
    body.append("project", String(projectId));
    body.append("field_key", fieldKey);
    body.append("file", file, file.name);
    return api.postForm("project-supporting-documents/", body) as Promise<SupportingDocument>;
  },
  remove: (documentId: number) => api.del(`project-supporting-documents/${documentId}/`),
  retry: (documentId: number) => api.post(`project-supporting-documents/${documentId}/retry/`, {}) as Promise<SupportingDocument>,
  assessment: (projectId: string | number) => api.get(
    `project-supporting-documents/assessment-status/?project=${projectId}`,
    true,
  ) as Promise<DocumentAssessment>,
  download: async (document: SupportingDocument) => {
    const response = await fetch(`${API_BASE_URL}${document.download_url.replace(/^\/api/, "")}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem("accessToken") || ""}` },
      cache: "no-store",
    });
    if (!response.ok) throw new Error("Failed to download the supporting document.");
    const url = URL.createObjectURL(await response.blob());
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = document.original_filename;
    anchor.click();
    URL.revokeObjectURL(url);
  },
};

export default projectDocumentsApi;
