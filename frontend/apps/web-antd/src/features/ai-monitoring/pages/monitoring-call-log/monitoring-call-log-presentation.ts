import type { MonitoringCallLogInfo, MonitoringScope } from '../../api';

import { $t } from '#/locales';

import { createMonitoringCallerDetailMeta } from '../../identity';

export interface MonitoringCallLogDetailField {
  key: string;
  label: string;
  value: string;
}

export interface MonitoringCallLogMetricCard {
  icon: string;
  key: string;
  label: string;
  value: string;
}

export interface MonitoringCallLogSummaryChip {
  key: string;
  label: string;
  value: string;
}

export function prettyMonitoringPayload(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

export function formatMonitoringCost(cost?: null | number) {
  return `$${Number(cost || 0).toFixed(4)}`;
}

export function formatMonitoringTokens(tokens?: null | number) {
  return Number(tokens || 0).toLocaleString();
}

export function formatMonitoringLatency(latency?: null | number) {
  return latency === null || latency === undefined ? '-' : `${latency} ms`;
}

export function isIconAvatar(avatar: null | string | undefined): boolean {
  return Boolean(avatar && String(avatar).includes(':'));
}

export function getInitialLetter(value: null | string | undefined): string {
  const text = String(value || '').trim();
  return text ? text.charAt(0).toUpperCase() : '?';
}

export function getMonitoringCallLogStatusColor(status?: null | string) {
  switch (status) {
    case 'failed': {
      return 'error';
    }
    case 'success': {
      return 'success';
    }
    case 'timeout': {
      return 'warning';
    }
    default: {
      return 'default';
    }
  }
}

export function getMonitoringCallLogStatusText(
  i18nPrefix: string,
  status?: null | string,
) {
  if (!status) {
    return '-';
  }
  const statusOptionKey = `${i18nPrefix}.status_options.${status}`;
  const translated = $t(statusOptionKey);
  return translated === statusOptionKey ? status : translated;
}

export function createMonitoringCallLogSummaryChips(
  detail: MonitoringCallLogInfo,
  i18nPrefix: string,
): MonitoringCallLogSummaryChip[] {
  return [
    {
      key: 'model',
      label: $t(`${i18nPrefix}.modelName`),
      value: detail.model_name || '-',
    },
    {
      key: 'provider',
      label: $t(`${i18nPrefix}.providerName`),
      value: detail.provider_name || '-',
    },
    {
      key: 'requestType',
      label: $t(`${i18nPrefix}.requestType`),
      value: detail.request_type || '-',
    },
  ];
}

export function createMonitoringCallLogMetricCards(
  detail: MonitoringCallLogInfo,
  i18nPrefix: string,
): MonitoringCallLogMetricCard[] {
  return [
    {
      key: 'inputTokens',
      icon: 'lucide:arrow-down-to-line',
      label: $t(`${i18nPrefix}.inputTokens`),
      value: formatMonitoringTokens(detail.input_tokens),
    },
    {
      key: 'outputTokens',
      icon: 'lucide:arrow-up-from-line',
      label: $t(`${i18nPrefix}.outputTokens`),
      value: formatMonitoringTokens(detail.output_tokens),
    },
    {
      key: 'totalTokens',
      icon: 'lucide:binary',
      label: $t(`${i18nPrefix}.totalTokens`),
      value: formatMonitoringTokens(detail.total_tokens),
    },
    {
      key: 'cost',
      icon: 'lucide:badge-dollar-sign',
      label: $t(`${i18nPrefix}.cost`),
      value: formatMonitoringCost(detail.cost),
    },
    {
      key: 'latency',
      icon: 'lucide:gauge',
      label: $t(`${i18nPrefix}.latency`),
      value: formatMonitoringLatency(detail.latency_ms),
    },
  ];
}

export function createMonitoringCallLogDetailFields(
  detail: MonitoringCallLogInfo,
  i18nPrefix: string,
  scope: MonitoringScope,
  createdAt: string,
  statusText: string,
): MonitoringCallLogDetailField[] {
  const fields: MonitoringCallLogDetailField[] = [
    {
      key: 'createdAt',
      label: $t(`${i18nPrefix}.createdAt`),
      value: createdAt,
    },
    {
      key: 'requestType',
      label: $t(`${i18nPrefix}.requestType`),
      value: detail.request_type || '-',
    },
    {
      key: 'modelName',
      label: $t(`${i18nPrefix}.modelName`),
      value: detail.model_name || '-',
    },
    {
      key: 'providerName',
      label: $t(`${i18nPrefix}.providerName`),
      value: detail.provider_name || '-',
    },
    {
      key: 'status',
      label: $t(`${i18nPrefix}.status`),
      value: statusText,
    },
  ];

  if (scope === 'admin') {
    fields.push({
      key: 'tenantName',
      label: $t(`${i18nPrefix}.tenantName`),
      value: detail.tenant_name || '-',
    });
  }

  return fields;
}

export function buildMonitoringCallLogCallerMeta(
  detail: MonitoringCallLogInfo,
  scope: MonitoringScope,
) {
  return createMonitoringCallerDetailMeta(detail, {
    createdAt: detail.created_at,
    scope,
    tenantId: detail.tenant_id,
    tenantName: detail.tenant_name,
  });
}
