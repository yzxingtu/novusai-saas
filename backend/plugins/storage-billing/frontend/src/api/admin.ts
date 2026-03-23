import type {
  BindingListResponse,
  BindingMutationResponse,
  BindingPayload,
  OverviewResponse,
  ReconciliationRunChargeListResponse,
  ReconciliationRunChargeFilters,
  ProviderCode,
  ProviderProfile,
  ProviderProfilesResponse,
  ProviderValidation,
  ReconciliationRunDetailResponse,
  ReconciliationRunListResponse,
  TenantSelectOption,
} from '../types';

import { requestClient } from '@novus/plugin-shared';

import { unwrapApiData } from './shared';

const PLUGIN_API_BASE = '/admin/plugins/storage-billing/api';

function buildRunChargeParams(
  filters?: ReconciliationRunChargeFilters,
): Record<string, number | string> {
  const params: Record<string, number | string> = {};
  const providerCode = filters?.provider_code?.trim();
  if (providerCode) {
    params.provider_code = providerCode;
  }
  if (typeof filters?.source_id === 'number' && Number.isFinite(filters.source_id)) {
    params.source_id = filters.source_id;
  }
  if (typeof filters?.tenant_id === 'number' && Number.isFinite(filters.tenant_id)) {
    params.tenant_id = filters.tenant_id;
  }
  return params;
}

export async function getOverviewApi(): Promise<OverviewResponse> {
  return requestClient
    .get<unknown>(`${PLUGIN_API_BASE}/overview`)
    .then((res) => unwrapApiData<OverviewResponse>(res));
}

export async function listProviderProfilesApi(): Promise<ProviderProfilesResponse> {
  return requestClient
    .get<unknown>(`${PLUGIN_API_BASE}/provider-profiles`)
    .then((res) => unwrapApiData<ProviderProfilesResponse>(res));
}

export async function saveProviderProfilesApi(
  payload: { providers: Partial<Record<ProviderCode, Partial<ProviderProfile>>> },
): Promise<ProviderProfilesResponse> {
  return requestClient
    .put<unknown>(`${PLUGIN_API_BASE}/provider-profiles`, payload)
    .then((res) => unwrapApiData<ProviderProfilesResponse>(res));
}

export async function validateProviderProfileApi(
  provider: ProviderCode,
  profile: Partial<ProviderProfile>,
): Promise<ProviderValidation & { profile: ProviderProfile }> {
  return requestClient
    .post<unknown>(`${PLUGIN_API_BASE}/provider-profiles/${provider}/validate`, {
      profile,
    })
    .then((res) =>
      unwrapApiData<ProviderValidation & { profile: ProviderProfile }>(res),
    );
}

export async function listBindingsApi(
  page = 1,
  pageSize = 100,
): Promise<BindingListResponse> {
  return requestClient
    .get<unknown>(`${PLUGIN_API_BASE}/bindings`, {
      params: {
        'page[number]': page,
        'page[size]': pageSize,
      },
    })
    .then((res) => unwrapApiData<BindingListResponse>(res));
}

export async function createBindingApi(
  payload: BindingPayload,
): Promise<BindingMutationResponse> {
  return requestClient
    .post<unknown>(`${PLUGIN_API_BASE}/bindings`, payload)
    .then((res) => unwrapApiData<BindingMutationResponse>(res));
}

export async function updateBindingApi(
  bindingId: number,
  payload: Partial<BindingPayload>,
): Promise<BindingMutationResponse> {
  return requestClient
    .put<unknown>(`${PLUGIN_API_BASE}/bindings/${bindingId}`, payload)
    .then((res) => unwrapApiData<BindingMutationResponse>(res));
}

export async function validateBindingApi(
  bindingId: number,
): Promise<BindingMutationResponse> {
  return requestClient
    .post<unknown>(`${PLUGIN_API_BASE}/bindings/${bindingId}/validate`)
    .then((res) => unwrapApiData<BindingMutationResponse>(res));
}

export async function runReconciliationApi(payload?: {
  billing_date?: string;
  provider_codes?: string[];
}): Promise<{
  run: Record<string, unknown>;
  status: string;
}> {
  return requestClient
    .post<unknown>(`${PLUGIN_API_BASE}/reconcile/run`, payload ?? {})
    .then((res) => unwrapApiData<{ run: Record<string, unknown>; status: string }>(res));
}

export async function runQiniuMonthlySettlementApi(payload?: {
  billing_month?: string;
}): Promise<{
  run: Record<string, unknown>;
  status: string;
}> {
  return requestClient
    .post<unknown>(`${PLUGIN_API_BASE}/providers/qiniu-kodo/monthly-settlement/run`, payload ?? {})
    .then((res) => unwrapApiData<{ run: Record<string, unknown>; status: string }>(res));
}

export async function listReconciliationRunsApi(
  limit = 10,
): Promise<ReconciliationRunListResponse> {
  return requestClient
    .get<unknown>(`${PLUGIN_API_BASE}/runs`, {
      params: {
        limit,
      },
    })
    .then((res) => unwrapApiData<ReconciliationRunListResponse>(res));
}

export async function getReconciliationRunApi(
  runId: number,
): Promise<ReconciliationRunDetailResponse> {
  return requestClient
    .get<unknown>(`${PLUGIN_API_BASE}/runs/${runId}`)
    .then((res) => unwrapApiData<ReconciliationRunDetailResponse>(res));
}

export async function getReconciliationRunChargesApi(
  runId: number,
  filters?: ReconciliationRunChargeFilters,
): Promise<ReconciliationRunChargeListResponse> {
  return requestClient
    .get<unknown>(`${PLUGIN_API_BASE}/runs/${runId}/charges`, {
      params: buildRunChargeParams(filters),
    })
    .then((res) => unwrapApiData<ReconciliationRunChargeListResponse>(res));
}

type DownloadableRequestClient = typeof requestClient & {
  download?: (url: string, config?: Record<string, unknown>) => Promise<Blob>;
};

export async function exportReconciliationRunChargesCsvApi(
  runId: number,
  filters?: ReconciliationRunChargeFilters,
): Promise<Blob> {
  const client = requestClient as DownloadableRequestClient;
  if (!client.download) {
    throw new Error('requestClient.download not available');
  }
  return client.download(`${PLUGIN_API_BASE}/runs/${runId}/charges/export`, {
    params: buildRunChargeParams(filters),
  });
}

export async function getTenantSelectOptionsApi(
  search = '',
): Promise<TenantSelectOption[]> {
  const response = await requestClient.get<{ items: TenantSelectOption[] }>(
    '/admin/tenants/select',
    {
      params: {
        page: 0,
        page_size: 50,
        search,
      },
    },
  );
  return response.items ?? [];
}
