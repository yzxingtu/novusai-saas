import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

export type MonitoringScope = 'admin' | 'tenant';

export interface MonitoringActorInfo {
  avatar?: null | string;
  display_name?: null | string;
  id?: null | number;
  is_active?: boolean;
  is_leader?: boolean;
  is_owner?: boolean;
  nickname?: null | string;
  tenant_id?: null | number;
  tenant_name?: null | string;
  org_node_id?: null | number;
  org_node_name?: null | string;
  role_name?: null | string;
  type?: null | string;
  username?: null | string;
}

export interface MonitoringCallLogInfo {
  id: number;
  tenant_id: null | number;
  conversation_id?: null | number;
  agent_id?: null | number;
  agent_avatar?: null | string;
  caller_avatar?: null | string;
  caller_display_name?: null | string;
  caller_id?: null | number;
  caller_is_active?: boolean;
  caller_is_leader?: boolean;
  caller_is_owner?: boolean;
  caller_nickname?: null | string;
  caller_org_node_id?: null | number;
  caller_org_node_name?: null | string;
  caller_role_name?: null | string;
  caller_type?: null | string;
  caller_username?: null | string;
  model_name?: null | string;
  model_id?: null | number;
  provider_name?: null | string;
  provider_icon?: null | string;
  provider_id?: null | number;
  tenant_name?: null | string;
  agent_name?: null | string;
  caller_name?: null | string;
  request_type: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost: number;
  latency_ms: null | number;
  status: string;
  trace_id?: null | string;
  error_message?: null | string;
  created_at: string;
  request_data?: null | Record<string, unknown>;
  response_data?: null | Record<string, unknown>;
}

export interface MonitoringConversationMessage {
  agent_avatar?: null | string;
  agent_id?: null | number;
  agent_name?: null | string;
  content: null | string;
  created_at: string;
  id: number;
  metadata?: null | Record<string, unknown>;
  role: string;
  sequence: number;
  token_count: null | number;
  tool_call_id?: null | string;
  tool_calls?: null | unknown[];
  tool_name?: null | string;
}

export interface MonitoringIntentPlanItem {
  id?: null | string;
  intent_id?: null | string;
  kind?: null | string;
  label?: null | string;
  status?: null | string;
  required_capabilities?: string[];
  selected_tools?: string[];
  allowed_tools?: string[];
  completed_tools?: string[];
  unfinished_reason?: null | string;
  [key: string]: unknown;
}

export interface MonitoringRetryEvent {
  attempt?: null | number;
  kind?: null | string;
  message?: null | string;
  reason?: null | string;
  unresolved_intents?: string[];
  [key: string]: unknown;
}

export interface MonitoringProviderEvent {
  kind?: null | string;
  provider_failure_kind?: null | string;
  message?: null | string;
  reason?: null | string;
  stage?: null | string;
  status_code?: null | number;
  [key: string]: unknown;
}

export interface MonitoringRuntimeDiagnostics {
  execution_path?: null | string;
  intent_plan?: MonitoringIntentPlanItem[];
  budget?: null | Record<string, unknown>;
  budget_status?: null | string;
  budget_exit_reason?: null | string;
  candidate_tool_names?: string[];
  retry_events?: MonitoringRetryEvent[];
  partial_exit_reason?: null | string;
  failure_kind?: null | string;
  provider_events?: MonitoringProviderEvent[];
  [key: string]: unknown;
}

export interface MonitoringCallTraceItem {
  cost: number;
  created_at: string;
  error_message?: null | string;
  id: number;
  latency_ms: null | number;
  model_name?: null | string;
  provider_name?: null | string;
  request_type: string;
  status: string;
  total_tokens: number;
  usage_mode?: null | string;
}

export interface MonitoringConversationInfo {
  actor?: MonitoringActorInfo | null;
  agent_avatar?: null | string;
  agent_id?: null | number;
  agent_name?: null | string;
  call_count: number;
  created_at: string;
  id: number;
  last_call_at?: null | string;
  message_count: number;
  owner_type?: null | string;
  status: string;
  tenant_id?: null | number;
  tenant_name?: null | string;
  title: null | string;
  total_cost: number;
  total_tokens: number;
  updated_at: string;
}

export interface MonitoringConversationDetail extends MonitoringConversationInfo {
  call_trace: MonitoringCallTraceItem[];
  context_diagnostics?: MonitoringRuntimeDiagnostics | null;
  last_run_summary?: MonitoringRuntimeDiagnostics | null;
  message_list: MonitoringConversationMessage[];
  metadata?: null | Record<string, unknown>;
}

export interface MonitoringUsageSummary {
  failed_calls: number;
  input_tokens: number;
  output_tokens: number;
  success_calls: number;
  success_rate: number;
  total_calls: number;
  total_cost: number;
  total_tokens: number;
}

export interface MonitoringUsageBreakdownItem {
  actor?: MonitoringActorInfo | null;
  call_count: number;
  failed_calls: number;
  key: string;
  label: string;
  success_calls: number;
  total_cost: number;
  total_tokens: number;
}

export interface MonitoringUsageSeriesPoint {
  call_count: number;
  date: string;
  failed_calls: number;
  input_tokens: number;
  output_tokens: number;
  success_calls: number;
  total_cost: number;
  total_tokens: number;
}

export interface MonitoringUsageDashboard {
  access_channel_stats: MonitoringUsageBreakdownItem[];
  daily_stats: MonitoringUsageSeriesPoint[];
  model_stats: MonitoringUsageBreakdownItem[];
  scope: string;
  summary: MonitoringUsageSummary;
  tenant_id?: null | number;
  tenant_name?: null | string;
  top_agents: MonitoringUsageBreakdownItem[];
  top_tenants: MonitoringUsageBreakdownItem[];
  top_users: MonitoringUsageBreakdownItem[];
}

interface PageResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

const CALL_LOG_PREFIX: Record<MonitoringScope, string> = {
  admin: '/admin/ai/call-logs',
  tenant: '/tenant/ai/call-logs',
};

const CONVERSATION_PREFIX: Record<MonitoringScope, string> = {
  admin: '/admin/ai/conversations',
  tenant: '/tenant/ai/conversations',
};

const USAGE_DASHBOARD_PREFIX: Record<MonitoringScope, string> = {
  admin: '/admin/ai/usage/dashboard',
  tenant: '/tenant/ai/usage/dashboard',
};

export async function getMonitoringCallLogList(
  scope: MonitoringScope,
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<MonitoringCallLogInfo>> {
  return requestClient.get<PageResponse<MonitoringCallLogInfo>>(
    CALL_LOG_PREFIX[scope],
    { params, ...options },
  );
}

export async function getMonitoringCallLogDetail(
  scope: MonitoringScope,
  id: number,
  options?: ApiRequestOptions,
): Promise<MonitoringCallLogInfo> {
  return requestClient.get<MonitoringCallLogInfo>(
    `${CALL_LOG_PREFIX[scope]}/${id}`,
    options,
  );
}

export async function getMonitoringUsageDashboard(
  scope: MonitoringScope,
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<MonitoringUsageDashboard> {
  return requestClient.get<MonitoringUsageDashboard>(
    USAGE_DASHBOARD_PREFIX[scope],
    { params, ...options },
  );
}

export async function getMonitoringConversationList(
  scope: MonitoringScope,
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<PageResponse<MonitoringConversationInfo>> {
  return requestClient.get<PageResponse<MonitoringConversationInfo>>(
    CONVERSATION_PREFIX[scope],
    { params, ...options },
  );
}

export async function getMonitoringConversationDetail(
  scope: MonitoringScope,
  id: number,
  params?: Record<string, unknown>,
  options?: ApiRequestOptions,
): Promise<MonitoringConversationDetail> {
  return requestClient.get<MonitoringConversationDetail>(
    `${CONVERSATION_PREFIX[scope]}/${id}`,
    { params, ...options },
  );
}
