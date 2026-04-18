/**
 * Operation log API (tenant side) / 操作日志 API（企业端）
 * Backend: /tenant/operation-logs/* / 对接后端 /tenant/operation-logs/* 接口
 */
import type { ApiRequestOptions } from '#/utils/request';

import { $t } from '#/locales';
import { requestClient } from '#/utils/request';

// ============================================================
// Type definitions / 类型定义
// ============================================================

/** Operation log list query params / 操作日志列表查询参数 */
export type OperationLogListParams = Record<string, unknown>;

/** Operator dropdown option / 操作人下拉选项 */
export interface OperatorItem {
  user_id: number;
  user_type: string;
  display_name?: null | string;
  username: string;
  nickname?: null | string;
  avatar?: null | string;
  org_node_id?: null | number;
  org_node_name?: null | string;
  role_name?: null | string;
  is_active?: boolean;
  is_leader?: boolean;
  is_owner?: boolean;
}

interface OperatorSelectItemRaw {
  avatar?: null | string;
  display_name?: null | string;
  extra?: null | Record<string, unknown>;
  label?: null | string;
  nickname?: null | string;
  org_node_id?: null | number;
  org_node_name?: null | string;
  role_name?: null | string;
  is_active?: boolean;
  is_leader?: boolean;
  is_owner?: boolean;
  user_id?: null | number;
  user_type?: null | string;
  username?: null | string;
  value?: null | number | string;
}

export interface OperatorSelectOption {
  avatar?: null | string;
  extra?: {
    avatar?: null | string;
    displayName?: null | string;
    isActive?: boolean;
    isLeader?: boolean;
    isOwner?: boolean;
    nickname?: null | string;
    orgNodeId?: null | number;
    orgNodeName?: null | string;
    roleName?: null | string;
    username?: null | string;
    userType?: null | string;
    userTypeLabel?: null | string;
  };
  label: string;
  value: number | string;
}

interface OperatorSelectResponseRaw {
  items: OperatorSelectItemRaw[];
  page: number;
  page_size: number;
  total: number;
}

/** Operation log info (backend raw format snake_case) / 操作日志信息（后端原始格式） */
export interface OperationLogInfoRaw {
  id: number;
  trace_id?: null | string;
  tenant_id: null | number;
  user_type: string;
  user_id: null | number;
  display_name?: null | string;
  username: null | string;
  nickname?: null | string;
  avatar?: null | string;
  org_node_id?: null | number;
  org_node_name?: null | string;
  role_name?: null | string;
  is_active?: boolean;
  is_owner?: boolean;
  is_leader?: boolean;
  module: null | string;
  module_label?: null | string;
  action: null | string;
  action_label?: null | string;
  method: string;
  path: string;
  query_params: null | Record<string, unknown>;
  request_body: null | Record<string, unknown>;
  status_code: number;
  response_code: number;
  response_message?: null | string;
  ip: string;
  duration_ms: number;
  created_at: string;
}

/** Operation log info (frontend format camelCase) / 操作日志信息（前端格式） */
export interface OperationLogInfo {
  id: number;
  traceId?: null | string;
  tenantId: null | number;
  userType: string;
  userId: null | number;
  displayName?: null | string;
  username: null | string;
  nickname?: null | string;
  avatar?: null | string;
  orgNodeId?: null | number;
  orgNodeName?: null | string;
  roleName?: null | string;
  isActive?: boolean;
  isOwner?: boolean;
  isLeader?: boolean;
  module: null | string;
  moduleLabel?: null | string;
  action: null | string;
  actionLabel?: null | string;
  method: string;
  path: string;
  queryParams: null | Record<string, unknown>;
  requestBody: null | Record<string, unknown>;
  statusCode: number;
  responseCode: number;
  responseMessage?: null | string;
  ip: string;
  durationMs: number;
  createdAt: string;
}

/** Paginated list response / 分页列表响应 */
export interface OperationLogListResponse {
  items: OperationLogInfo[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================
// Transform functions / 转换函数
// ============================================================

/** Convert backend snake_case to frontend camelCase / 后端转前端格式 */
function transformOperationLogInfo(raw: OperationLogInfoRaw): OperationLogInfo {
  return {
    id: raw.id,
    traceId: raw.trace_id,
    tenantId: raw.tenant_id,
    userType: raw.user_type,
    userId: raw.user_id,
    displayName: raw.display_name,
    username: raw.username,
    nickname: raw.nickname,
    avatar: raw.avatar,
    orgNodeId: raw.org_node_id,
    orgNodeName: raw.org_node_name,
    roleName: raw.role_name,
    isActive: raw.is_active,
    isOwner: raw.is_owner,
    isLeader: raw.is_leader,
    module: raw.module,
    moduleLabel: raw.module_label,
    action: raw.action,
    actionLabel: raw.action_label,
    method: raw.method,
    path: raw.path,
    queryParams: raw.query_params,
    requestBody: raw.request_body,
    statusCode: raw.status_code,
    responseCode: raw.response_code,
    responseMessage: raw.response_message,
    ip: raw.ip,
    durationMs: raw.duration_ms,
    createdAt: raw.created_at,
  };
}

function resolveStringValue(
  ...values: Array<null | string | undefined>
): string | undefined {
  for (const value of values) {
    if (typeof value !== 'string') {
      continue;
    }
    const normalized = value.trim();
    if (normalized) {
      return normalized;
    }
  }
  return undefined;
}

function resolveBooleanValue(
  ...values: Array<boolean | undefined>
): boolean | undefined {
  for (const value of values) {
    if (typeof value === 'boolean') {
      return value;
    }
  }
  return undefined;
}

function resolveNumberValue(
  ...values: Array<null | number | undefined>
): number | undefined {
  for (const value of values) {
    if (typeof value === 'number') {
      return value;
    }
  }
  return undefined;
}

function getOperatorUserTypeLabel(
  userType: null | string | undefined,
): null | string {
  switch (userType) {
    case 'tenant_admin': {
      return $t('tenant.system.operationLog.userTypeOptions.tenantAdmin');
    }
    case 'tenant_user': {
      return $t('tenant.system.operationLog.userTypeOptions.tenantUser');
    }
    default: {
      return userType ?? null;
    }
  }
}

function transformOperatorSelectItem(
  raw: OperatorSelectItemRaw,
): OperatorSelectOption {
  const extra = raw.extra ?? {};
  const username = resolveStringValue(
    raw.username,
    typeof extra.username === 'string' ? extra.username : undefined,
  );
  const nickname = resolveStringValue(
    raw.nickname,
    typeof extra.nickname === 'string' ? extra.nickname : undefined,
  );
  const avatar = resolveStringValue(
    raw.avatar,
    typeof extra.avatar === 'string' ? extra.avatar : undefined,
  );
  const displayName = resolveStringValue(
    raw.display_name,
    typeof extra.displayName === 'string' ? extra.displayName : undefined,
    typeof extra.display_name === 'string' ? extra.display_name : undefined,
    nickname,
    username,
  );
  const orgNodeName = resolveStringValue(
    raw.org_node_name,
    typeof extra.orgNodeName === 'string' ? extra.orgNodeName : undefined,
    typeof extra.org_node_name === 'string' ? extra.org_node_name : undefined,
  );
  const roleName = resolveStringValue(
    raw.role_name,
    typeof extra.roleName === 'string' ? extra.roleName : undefined,
    typeof extra.role_name === 'string' ? extra.role_name : undefined,
  );
  const userType = resolveStringValue(
    raw.user_type,
    typeof extra.userType === 'string' ? extra.userType : undefined,
    typeof extra.user_type === 'string' ? extra.user_type : undefined,
  );
  const orgNodeId = resolveNumberValue(
    raw.org_node_id,
    typeof extra.orgNodeId === 'number' ? extra.orgNodeId : undefined,
    typeof extra.org_node_id === 'number' ? extra.org_node_id : undefined,
  );
  const isActive = resolveBooleanValue(
    raw.is_active,
    typeof extra.isActive === 'boolean' ? extra.isActive : undefined,
    typeof extra.is_active === 'boolean' ? extra.is_active : undefined,
  );
  const isLeader = resolveBooleanValue(
    raw.is_leader,
    typeof extra.isLeader === 'boolean' ? extra.isLeader : undefined,
    typeof extra.is_leader === 'boolean' ? extra.is_leader : undefined,
  );
  const isOwner = resolveBooleanValue(
    raw.is_owner,
    typeof extra.isOwner === 'boolean' ? extra.isOwner : undefined,
    typeof extra.is_owner === 'boolean' ? extra.is_owner : undefined,
  );
  const value = raw.value ?? username ?? raw.user_id ?? raw.label ?? '';
  const label =
    displayName ||
    nickname ||
    username ||
    resolveStringValue(raw.label) ||
    String(value);

  return {
    ...raw,
    avatar,
    label,
    value,
    extra: {
      ...extra,
      avatar,
      displayName,
      isActive,
      isLeader,
      isOwner,
      nickname,
      orgNodeId,
      orgNodeName,
      roleName,
      userType,
      userTypeLabel: getOperatorUserTypeLabel(userType),
      username,
    },
  };
}

// ============================================================
// API functions / API 接口
// ============================================================

const API_PREFIX = '/tenant/operation-logs';

/**
 * Get operation log list / 获取操作日志列表
 * GET /tenant/operation-logs
 */
export async function getOperationLogListApi(
  params?: OperationLogListParams,
  options?: ApiRequestOptions,
): Promise<OperationLogListResponse> {
  const response = await requestClient.get<{
    items: OperationLogInfoRaw[];
    page: number;
    page_size: number;
    total: number;
  }>(API_PREFIX, { params, ...options });

  return {
    items: response.items.map((item) => transformOperationLogInfo(item)),
    total: response.total,
    page: response.page,
    page_size: response.page_size,
  };
}

/**
 * Get operator dropdown list (with avatar, full list) / 获取操作人下拉列表（含头像，全量模式）
 * GET /tenant/operation-logs/operators
 */
export async function getOperatorsApi(): Promise<OperatorItem[]> {
  return requestClient.get<OperatorItem[]>(`${API_PREFIX}/operators`);
}

/**
 * Get operator paginated dropdown list (for ApiSelect) / 获取操作人分页下拉列表（供 ApiSelect 使用）
 * GET /tenant/operation-logs/operators?page=1&page_size=10&search=xxx&user_type=xxx
 */
export async function getOperatorsSelectApi(
  params: Record<string, unknown>,
): Promise<{
  items: OperatorSelectOption[];
  page: number;
  page_size: number;
  total: number;
}> {
  const response = await requestClient.get<OperatorSelectResponseRaw>(
    `${API_PREFIX}/operators`,
    { params },
  );

  return {
    ...response,
    items: response.items.map((item) => transformOperatorSelectItem(item)),
  };
}

/**
 * Get operation log detail / 获取操作日志详情
 * GET /tenant/operation-logs/{id}
 */
export async function getOperationLogDetailApi(
  id: number,
  options?: ApiRequestOptions,
): Promise<OperationLogInfo> {
  const raw = await requestClient.get<OperationLogInfoRaw>(
    `${API_PREFIX}/${id}`,
    options,
  );
  return transformOperationLogInfo(raw);
}
