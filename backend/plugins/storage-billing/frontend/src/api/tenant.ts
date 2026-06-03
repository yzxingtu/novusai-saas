import type {
  PeriodType,
  TenantStatementChargesResponse,
  TenantPrerequisitesResponse,
  TenantStatementsResponse,
  TenantStatementResponse,
} from '../types';

import { requestClient } from '@novus/plugin-shared';

import { unwrapApiData } from './shared';

const PLUGIN_API_BASE = '/tenant/plugins/storage-billing/api';

export async function getTenantPrerequisitesApi(): Promise<TenantPrerequisitesResponse> {
  return requestClient
    .get<unknown>(`${PLUGIN_API_BASE}/me/prerequisites`)
    .then((res) => unwrapApiData<TenantPrerequisitesResponse>(res));
}

export async function getCurrentStatementApi(
  billingDate?: string,
  periodType?: PeriodType | string,
): Promise<TenantStatementResponse> {
  const query = new URLSearchParams();
  if (billingDate) {
    query.set('billing_date', billingDate);
  }
  if (periodType) {
    query.set('period_type', periodType);
  }
  const path = query.size > 0
    ? `${PLUGIN_API_BASE}/statement/current?${query.toString()}`
    : `${PLUGIN_API_BASE}/statement/current`;
  return requestClient
    .get<unknown>(path)
    .then((res) => unwrapApiData<TenantStatementResponse>(res));
}

export async function getTenantStatementsApi(limit = 30): Promise<TenantStatementsResponse> {
  return requestClient
    .get<unknown>(`${PLUGIN_API_BASE}/statements?limit=${limit}`)
    .then((res) => unwrapApiData<TenantStatementsResponse>(res));
}

export async function getTenantStatementChargesApi(
  billingDate: string,
  periodType?: PeriodType | string,
): Promise<TenantStatementChargesResponse> {
  const query = new URLSearchParams();
  query.set('billing_date', billingDate);
  if (periodType) {
    query.set('period_type', periodType);
  }
  return requestClient
    .get<unknown>(`${PLUGIN_API_BASE}/statement/charges?${query.toString()}`)
    .then((res) => unwrapApiData<TenantStatementChargesResponse>(res));
}

type DownloadableRequestClient = typeof requestClient & {
  download?: (url: string, config?: Record<string, unknown>) => Promise<Blob>;
};

export async function exportTenantStatementChargesCsvApi(
  billingDate: string,
  periodType?: PeriodType | string,
): Promise<Blob> {
  const client = requestClient as DownloadableRequestClient;
  if (!client.download) {
    throw new Error('requestClient.download not available');
  }
  const query = new URLSearchParams();
  query.set('billing_date', billingDate);
  if (periodType) {
    query.set('period_type', periodType);
  }
  return client.download(
    `${PLUGIN_API_BASE}/statement/charges/export?${query.toString()}`,
  );
}
