import type { ApiRequestOptions } from '#/utils/request';

import { requestClient } from '#/utils/request';

export type MonitoringScope = 'admin' | 'tenant';

export interface MonitoringActorInfo {
  avatar?: null | string;
  display_name?: null | string;
  id?: null | number;
  nickname?: null | string;
  type?: null | string;
  username?: null | string;
}

export interface MonitoringCallLogInfo {
  id: number;
  tenant_id: null | number;
  conversation_id?: null | number;
  agent_id?: null | number;
  model_name?: null | string;
  provider_name?: null | string;
  provider_icon?: null | string;
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
