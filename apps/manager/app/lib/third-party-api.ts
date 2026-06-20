import { apiFetch } from "./api";

export interface ThirdParty {
  id: string;
  name: string;
  trade_name: string | null;
  tax_id: string | null;
  status: string;
  roles: string[];
  sector: string | null;
  activity_code: string | null;
  average_score: string | null;
}

export interface ThirdPartyContact {
  id: string;
  third_party_id: string;
  name: string;
  role: string | null;
  phone: string | null;
  email: string | null;
  is_primary: boolean;
  created_at: string;
}

export interface LedgerEntry {
  id: string;
  entry_type: "debit" | "credit";
  amount: string;
  source_type: string;
  source_id: string | null;
  description: string | null;
  entry_date: string;
  created_at: string;
}

export interface SupplierAccount {
  third_party_id: string;
  total_debits: string;
  total_credits: string;
  balance: string;
  entries: LedgerEntry[];
}

export interface EvaluationCriterion {
  name: string;
  weight: number;
  score: number;
}

export interface SupplierEvaluation {
  id: string;
  third_party_id: string;
  evaluation_date: string;
  criteria: EvaluationCriterion[];
  score: string;
  notes: string | null;
  evaluated_by: string | null;
  created_at: string;
}

export interface EvaluationsResult {
  average_score: string | null;
  evaluations: SupplierEvaluation[];
}

export interface OperationalDocument {
  id: string;
  subject_type: string;
  subject_id: string;
  document_type: string;
  file_name: string;
  file_url: string;
  issued_date: string | null;
  expiry_date: string | null;
  verification_status: string;
  created_at: string;
}

export async function loadThirdParties(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<ThirdParty[]> {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  if (params?.offset !== undefined) qs.set("offset", String(params.offset));
  const query = qs.toString() ? `?${qs}` : "";
  return apiFetch<ThirdParty[]>(`/api/v1/third-party${query}`);
}

export async function loadThirdParty(id: string): Promise<ThirdParty> {
  return apiFetch<ThirdParty>(`/api/v1/third-party/${id}`);
}

export async function loadContacts(thirdPartyId: string): Promise<ThirdPartyContact[]> {
  return apiFetch<ThirdPartyContact[]>(`/api/v1/third-party/${thirdPartyId}/contacts`);
}

export async function loadSupplierAccount(thirdPartyId: string): Promise<SupplierAccount> {
  return apiFetch<SupplierAccount>(`/api/v1/third-party/${thirdPartyId}/account`);
}

export async function loadEvaluations(thirdPartyId: string): Promise<EvaluationsResult> {
  return apiFetch<EvaluationsResult>(`/api/v1/third-party/${thirdPartyId}/evaluations`);
}

export async function loadOperationalDocuments(
  subjectType: string,
  subjectId: string,
): Promise<OperationalDocument[]> {
  return apiFetch<OperationalDocument[]>(
    `/api/v1/third-party/documents?subject_type=${subjectType}&subject_id=${subjectId}`,
  );
}
