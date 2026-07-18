export interface BackendConversation {
  id: string;
  employee_id: string;
  active_customer_id: string | null;
  active_loan_application_id: string | null;
  title: string | null;
  status: string;
  started_at: string;
  ended_at: string | null;
}

export interface BackendMessage {
  id: string;
  conversation_id: string;
  sender_type: string;
  content: string;
  created_at?: string;
  route?: Record<string, unknown> | null;
  attachment_ids?: string[];
}

export interface BackendCitation {
  number: number;
  citation_type: string;
  source_type: string;
  source_id: string;
  source_locator?: Record<string, unknown>;
  quoted_text?: string | null;
  evidence_role?: string | null;
}

export interface BackendConversationReply {
  content: string;
  route_type: string | null;
  complexity_level: number | null;
  analysis_case_id: string | null;
  metadata: Record<string, unknown> & { citations?: BackendCitation[] };
}

export interface BackendConversationTurn extends BackendMessage {
  assistant_message: BackendMessage | null;
  reply: BackendConversationReply | null;
}

export interface BackendCustomer {
  id?: string | null;
  customer_id?: string | null;
  party_id: string;
  customer_number: string;
  display_name?: string | null;
  full_name?: string | null;
  customer_segment?: string | null;
  home_branch_id: string;
  relationship_manager_id?: string | null;
  kyc_status: string;
  risk_rating?: string | null;
  status: string;
  updated_at: string;
  version: number;
}

export interface BackendLoanApplication {
  id: string;
  application_number: string;
  primary_customer_id: string;
  product_id: string;
  requested_amount: string;
  currency: string;
  requested_term_months: number;
  loan_purpose: string;
  status: string;
  version: number;
  assigned_employee_id?: string | null;
}

export interface BackendPage<T> {
  items: T[];
  meta: { page: number; page_size: number; total: number };
}

export interface BackendAssignmentLease {
  customer_id: string;
  assigned_employee_id: string;
  assignment_version: number;
  lease_token: string;
  lease_ttl_seconds: number;
  lease_expires_at: string;
}

export interface BackendUploadSession {
  upload_id: string;
  status: string;
  upload_url: string;
  headers: Record<string, string>;
  expires_at: string;
}

export interface BackendUploadComplete {
  upload_id: string;
  document_id: string;
  document_version_id: string;
  job_id: string;
  status: string;
}
