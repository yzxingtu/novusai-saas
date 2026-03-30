import { requestClient } from '#/utils/request';

export interface ExecutionDecisionItem {
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

interface ExecutionDecisionPageResponse {
  items: ExecutionDecisionItem[];
  page: number;
  page_size: number;
  total: number;
}

const PREFIX = '/tenant/ai/execution-decisions';

export async function getExecutionDecisionListApi(
  params?: Record<string, unknown>,
): Promise<ExecutionDecisionPageResponse> {
  return requestClient.get<ExecutionDecisionPageResponse>(PREFIX, { params });
}

export async function getExecutionDecisionDetailApi(
  id: number,
): Promise<ExecutionDecisionItem> {
  return requestClient.get<ExecutionDecisionItem>(`${PREFIX}/${id}`);
}
