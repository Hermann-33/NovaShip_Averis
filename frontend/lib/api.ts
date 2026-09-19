"use client";

/**
 * Typed API client. Auth: demo mode sends X-User-Id (switchable in the header);
 * production sends the Supabase JWT as Authorization: Bearer.
 */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export const SEVEN_FIELDS = ["shipper", "consignee", "notify_party", "port_of_loading", "port_of_discharge", "container_count", "gross_weight_kg"] as const;
export const FIELD_LABELS: Record<string, string> = {
  shipper: "Shipper", consignee: "Consignee", notify_party: "Notify Party", port_of_loading: "Port of Loading",
  port_of_discharge: "Port of Discharge", container_count: "Container Count", gross_weight_kg: "Gross Weight (kg)",
};

export function currentUserId(): string {
  if (typeof window === "undefined") return "u_sup_1";
  try { return localStorage.getItem("novaship.user") || "u_sup_1"; } catch { return "u_sup_1"; }
}
export function setCurrentUserId(id: string) {
  try { localStorage.setItem("novaship.user", id); } catch {}
}

export class ApiError extends Error {
  status: number; detail: any;
  constructor(status: number, detail: any) { super(typeof detail === "string" ? detail : detail?.error || `HTTP ${status}`); this.status = status; this.detail = detail; }
}

export async function api<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { "X-User-Id": currentUserId(), ...(init.headers as any) };
  let token: string | null = null;
  try { token = localStorage.getItem("novaship.jwt"); } catch {}
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (init.body && !(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers, cache: "no-store" });
  const text = await res.text();
  let data: any = text;
  try { data = text ? JSON.parse(text) : null; } catch {}
  if (!res.ok) throw new ApiError(res.status, data?.detail ?? data);
  return data as T;
}

export const post = <T = any>(path: string, body?: any) => api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
export const put = <T = any>(path: string, body?: any) => api<T>(path, { method: "PUT", body: JSON.stringify(body) });

// ------------------------------------------------------------------ types (mirror backend contracts)
export type Evidence = { document_id?: string | null; page?: number | null; snippet: string; label_found?: string | null; line?: number | null };
export type ComparisonField = {
  field: string; label: string; si_original: string | null; bl_original: string | null; si_normalized: any; bl_normalized: any;
  result: "MATCH" | "MISMATCH" | "MISSING_IN_SI" | "MISSING_IN_BL" | "LOW_CONFIDENCE_REVIEW"; confidence: number; reason: string; attention: string;
  si_evidence: Evidence; bl_evidence: Evidence;
};
export type Comparison = { comparison_status: string; mismatch_count: number; required_field_count: number; message: string; fields: ComparisonField[]; mismatch_fields: string[]; review_fields: string[]; review_reason: string | null; compared_at: string };
export type Draft = { id: string; draft_type: string; to: string[]; cc: string[]; subject: string; body: string; status: string; version: number; requires_external_approval: boolean; generated_by: string; evidence_refs: string[] };
export type Attachment = { id: string; file_name: string; file_type: string; size_bytes: number; checksum: string; detected_type: string; detection_confidence: number; extraction_status: string; extraction_confidence: number; raw_text: string | null; page_count: number | null; is_duplicate_of: string | null };
export type CaseView = {
  id: string; source_email_id: string; intent: string; hackathon_category: string; action_required: boolean; priority: string; status: string;
  security: { outcome: string; score: number; signals: { signal: string; severity: string; evidence: string; recommended_action: string }[]; rationale: string };
  classification: { intent: string; confidence: number; rationale: string; decided_by: string };
  mismatch_count: number; comparison_status: string | null; review_reason: string | null; confidence: number; si_available: boolean; bl_available: boolean;
  si_document_id: string | null; bl_document_id: string | null; assigned_user_id: string | null; assigned_team_id: string | null; shared_with: string[];
  summary: { text: string; generated_by: string; evidence_refs: string[] } | null;
  recommendation: { action_required: boolean; action_type: string; priority: string; reason: string; recommended_action: string; responsible_role: string; confidence: number } | null;
  comparison: Comparison | null; drafts: Draft[]; anomalies: { signal: string; severity: string; evidence: string; recommended_action: string }[];
  errors: { id: string; category: string; step: string; message: string; recovery: string; retryable: boolean; resolved: boolean }[];
  trace: { node: string; actor_type: string; started_at: string; finished_at: string; output: any }[]; processing_ms: number; created_at: string; updated_at: string;
  email: { id: string; sender: string; subject: string; body: string; received_at: string; language: string; attachments: Attachment[]; recipients: string[]; cc: string[] } | null;
};
export type CaseRow = {
  id: string; email_id: string; subject: string; sender: string; received_at: string | null; intent: string; category: string; security: string; action_required: boolean; priority: string;
  si_available: boolean; bl_available: boolean; attachments: number; mismatch_count: number; comparison_status: string | null; review_reason: string | null; confidence: number;
  assigned_user_id: string | null; shared_with: string[]; status: string; updated_at: string; summary: string; errors: number; drafts: number;
};
export type Metrics = Record<string, any>;
