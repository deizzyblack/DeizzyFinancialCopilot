import type {
  ExecuteResult,
  PaginatedAudit,
  PaginatedRecords,
  PipelineResult,
  RecordDetail,
} from "./types";

const BASE = "/api";

export async function ingestFile(
  file: File,
  companyId: string,
): Promise<PipelineResult> {
  const form = new FormData();
  form.append("file", file);
  const params = new URLSearchParams({ company_id: companyId });
  const res = await fetch(`${BASE}/ingest?${params}`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getPendingRecords(
  decision?: string,
  page = 1,
  perPage = 50,
): Promise<PaginatedRecords> {
  const params = new URLSearchParams({
    page: String(page),
    per_page: String(perPage),
  });
  if (decision) params.set("decision", decision);
  const res = await fetch(`${BASE}/records/pending?${params}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getRecordDetail(id: string): Promise<RecordDetail> {
  const res = await fetch(`${BASE}/records/${id}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function executeAction(
  id: string,
  action: "APPROVE" | "REJECT" | "INVESTIGATE",
): Promise<ExecuteResult> {
  const params = new URLSearchParams({ action });
  const res = await fetch(`${BASE}/execute/${id}?${params}`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getAuditLog(opts: {
  fileId?: string;
  recordId?: string;
  eventType?: string;
  page?: number;
  perPage?: number;
}): Promise<PaginatedAudit> {
  const params = new URLSearchParams({
    page: String(opts.page ?? 1),
    per_page: String(opts.perPage ?? 50),
  });
  if (opts.fileId) params.set("file_id", opts.fileId);
  if (opts.recordId) params.set("record_id", opts.recordId);
  if (opts.eventType) params.set("event_type", opts.eventType);
  const res = await fetch(`${BASE}/audit?${params}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
