import { requestClient } from '#/utils/request';

export interface AdminExecutionDecisionItem {
  id: number;
  tenant_id: number;
  conversation_id?: null | number;
  agent_id?: null | number;
  operator_id?: null | number;
  operator_type?: null | string;
  decision_type: string;
  subject_type: string;
  status: string;
  decision_scope: string;
  tool_name?: null | string;
  action_name?: null | string;
  table_name?: null | string;
  risk_level?: null | string;
  auto_approved: boolean;
  tool_call_id?: null | string;
  correlation_key: string;
  reason?: null | string;
  evidence?: null | Record<string, unknown>;
  created_at: string;
}

interface AdminExecutionDecisionPageResponse {
  items: AdminExecutionDecisionItem[];
  page: number;
  page_size: number;
  total: number;
}

const PREFIX = '/admin/ai/execution-decisions';

export async function getAdminExecutionDecisionListApi(
  params?: Record<string, unknown>,
): Promise<AdminExecutionDecisionPageResponse> {
  return requestClient.get<AdminExecutionDecisionPageResponse>(PREFIX, { params });
}

export async function getAdminExecutionDecisionDetailApi(
  id: number,
): Promise<AdminExecutionDecisionItem> {
  return requestClient.get<AdminExecutionDecisionItem>(`${PREFIX}/${id}`);
}
