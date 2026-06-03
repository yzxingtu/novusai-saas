import { requestClient } from '#/utils/request';

export interface AIRuntimeScopeParams {
  agent_code?: string;
  agent_id?: null | number;
  tenant_id?: null | number;
}

export interface AIRuntimeRootCauseQuery {
  call_log_id?: null | number;
  conversation_id?: null | number;
  trace_id?: null | string;
  turn?: null | number;
}

export interface AIRuntimeGenericReport {
  [key: string]: unknown;
}

export interface PluginLifecycleAuditReport {
  [key: string]: unknown;
}

const AI_RUNTIME_BASE_URL = '/admin/ai/runtime';

export function getAIRuntimeCapabilitiesApi(params?: AIRuntimeScopeParams) {
  return requestClient.get<AIRuntimeGenericReport>(
    `${AI_RUNTIME_BASE_URL}/capabilities`,
    { params },
  );
}

export function getAIRuntimeDoctorApi(params?: AIRuntimeScopeParams) {
  return requestClient.get<AIRuntimeGenericReport>(
    `${AI_RUNTIME_BASE_URL}/doctor`,
    { params },
  );
}

export function runAIRuntimeSmokeApi(payload?: AIRuntimeScopeParams) {
  return requestClient.post<AIRuntimeGenericReport>(
    `${AI_RUNTIME_BASE_URL}/smoke`,
    payload || {},
  );
}

export function getAIRuntimeRootCauseApi(params: AIRuntimeRootCauseQuery) {
  return requestClient.get<AIRuntimeGenericReport>(
    `${AI_RUNTIME_BASE_URL}/root-cause`,
    { params },
  );
}

export function getPluginLifecycleAuditApi(params?: {
  plugin?: string;
  plugin_id?: null | number;
  tenant_id?: null | number;
}) {
  return requestClient.get<PluginLifecycleAuditReport>(
    '/admin/plugins/runtime/audit',
    {
      params,
    },
  );
}

export function syncOfficialStarterPacksApi() {
  return requestClient.post<AIRuntimeGenericReport>(
    `${AI_RUNTIME_BASE_URL}/starter-pack/sync`,
    {},
  );
}
