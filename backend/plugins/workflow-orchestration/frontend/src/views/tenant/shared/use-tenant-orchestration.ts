import { computed } from 'vue';

import { enUS, zhCN } from '../../../locales/tenant';
import {
  getPluginAccessCodes,
  hasAllPluginAccess,
  hasAnyPluginAccess,
  hasPluginAccess,
} from '../../../shared/access';
import type {
  TenantDownloadOptions,
  TenantArtifactStatus,
  TenantArtifactType,
  TenantPluginSharedApi,
  TenantRunStatus,
  TenantWorkflowBuilderMode,
  TenantWorkflowStatus,
} from '../../../types/tenant';

const TENANT_LOCALE_PREFIX = 'plugin.workflow-orchestration.tenant.';
const TENANT_LOCAL_MESSAGES = {
  en: enUS,
  zh: zhCN,
} as const;

const RUN_ACTION_FALLBACK_BY_STATUS: Record<
  'pause' | 'resume' | 'retry' | 'terminate',
  string[]
> = {
  pause: ['running'],
  resume: ['paused', 'waiting_human', 'waiting_approval', 'waiting_input'],
  retry: ['failed'],
  terminate: [
    'compensating',
    'paused',
    'pending',
    'planning',
    'queued',
    'recovering',
    'running',
    'validating',
    'waiting_human',
    'waiting_approval',
    'waiting_input',
  ],
};

function readShared(): TenantPluginSharedApi | undefined {
  return (window as unknown as Record<string, unknown>)
    .NovusPluginShared as TenantPluginSharedApi | undefined;
}

function readLocale(): string {
  return (
    document.documentElement.lang ||
    navigator.language ||
    'en-US'
  ).replace('_', '-');
}

function humanizeCode(value: string): string {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (segment) => segment.toUpperCase());
}

function getRelativeLocaleKey(key: string): string {
  return key.startsWith(TENANT_LOCALE_PREFIX)
    ? key.slice(TENANT_LOCALE_PREFIX.length)
    : key;
}

function interpolateMessage(
  message: string,
  params?: Record<string, unknown>,
): string {
  if (!params) {
    return message;
  }
  return message.replace(/\{([^}]+)\}/g, (token, name: string) => {
    const value = params[name];
    if (value == null) {
      return token;
    }
    return String(value);
  });
}

function resolveLocalMessages(locale: string): Record<string, string> {
  return locale.toLowerCase().startsWith('zh')
    ? TENANT_LOCAL_MESSAGES.zh
    : TENANT_LOCAL_MESSAGES.en;
}

export function useTenantOrchestration() {
  const shared = computed(() => readShared());
  const locale = computed(() => readLocale());

  const translate = (
    key: string,
    params?: Record<string, unknown>,
    fallback?: string,
  ): string => {
    const translated = shared.value?.$t?.(key, params);
    const relativeKey = getRelativeLocaleKey(key);
    const tail = key.split('.').pop() ?? key;
    if (typeof translated === 'string') {
      const normalized = translated.trim();
      if (
        normalized &&
        normalized !== key &&
        normalized !== relativeKey &&
        normalized !== tail
      ) {
        return normalized;
      }
    }
    const localTranslation = resolveLocalMessages(locale.value)[relativeKey];
    if (localTranslation) {
      return interpolateMessage(localTranslation, params);
    }
    if (fallback && fallback.trim()) {
      return interpolateMessage(fallback, params);
    }
    return humanizeCode(tail);
  };

  const t = (key: string, params?: Record<string, unknown>): string => translate(key, params);

  const getAccessCodes = (): string[] => getPluginAccessCodes();

  const hasAccess = (
    codes: readonly string[] | string | undefined,
    options?: { mode?: 'all' | 'any' },
  ): boolean => hasPluginAccess(codes, options);

  const hasAnyAccess = (
    codes: readonly string[] | string | undefined,
  ): boolean => hasAnyPluginAccess(codes);

  const hasAllAccess = (
    codes: readonly string[] | string | undefined,
  ): boolean => hasAllPluginAccess(codes);

  const buildTenantPath = (suffix = ''): string => {
    const normalized = suffix.startsWith('/') ? suffix : `/${suffix}`;
    return `/tenant/plugins/workflow-orchestration${normalized === '/' ? '' : normalized}`;
  };

  const navigateTo = (path: string): void => {
    const target = path.startsWith('/')
      ? path
      : buildTenantPath(path);

    const router = shared.value?.router;
    if (router) {
      void router.push(target);
      return;
    }
    window.location.href = target;
  };

  const openExternal = (path: string): void => {
    if (!path) {
      return;
    }
    if (/^https?:\/\//.test(path)) {
      window.location.href = path;
      return;
    }
    navigateTo(path);
  };

  const saveBlob = (blob: Blob, options: TenantDownloadOptions): void => {
    if (shared.value?.downloadBlob) {
      shared.value.downloadBlob(blob, options);
      return;
    }

    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = options.filename;
    anchor.click();
    URL.revokeObjectURL(objectUrl);
  };

  const formatNumber = (value: null | number | string | undefined): string => {
    if (value == null || value === '') {
      return t('plugin.workflow-orchestration.tenant.common.placeholders.empty');
    }
    const numeric = typeof value === 'number' ? value : Number(value);
    if (!Number.isFinite(numeric)) {
      return String(value);
    }
    return new Intl.NumberFormat(locale.value).format(numeric);
  };

  const formatPercent = (value: null | number | undefined): string => {
    if (value == null || !Number.isFinite(value)) {
      return t('plugin.workflow-orchestration.tenant.common.placeholders.empty');
    }
    const normalized = value > 1 ? value / 100 : value;
    return new Intl.NumberFormat(locale.value, {
      maximumFractionDigits: 1,
      style: 'percent',
    }).format(normalized);
  };

  const formatDateTime = (
    value: null | string | undefined,
    fallbackKey = 'plugin.workflow-orchestration.tenant.common.placeholders.empty',
  ): string => {
    if (!value) {
      return t(fallbackKey);
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return t(fallbackKey);
    }
    return new Intl.DateTimeFormat(locale.value, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(date);
  };

  const formatRelativeTime = (value: null | string | undefined): string => {
    if (!value) {
      return t('plugin.workflow-orchestration.tenant.common.placeholders.empty');
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return t('plugin.workflow-orchestration.tenant.common.placeholders.empty');
    }

    const deltaMs = date.getTime() - Date.now();
    const minute = 60 * 1000;
    const hour = 60 * minute;
    const day = 24 * hour;
    const month = 30 * day;
    const year = 365 * day;

    const formatter = new Intl.RelativeTimeFormat(locale.value, {
      numeric: 'auto',
    });

    if (Math.abs(deltaMs) < hour) {
      return formatter.format(Math.round(deltaMs / minute), 'minute');
    }
    if (Math.abs(deltaMs) < day) {
      return formatter.format(Math.round(deltaMs / hour), 'hour');
    }
    if (Math.abs(deltaMs) < month) {
      return formatter.format(Math.round(deltaMs / day), 'day');
    }
    if (Math.abs(deltaMs) < year) {
      return formatter.format(Math.round(deltaMs / month), 'month');
    }
    return formatter.format(Math.round(deltaMs / year), 'year');
  };

  const formatBytes = (value: null | number | undefined): string => {
    if (value == null || !Number.isFinite(value) || value < 0) {
      return t('plugin.workflow-orchestration.tenant.common.placeholders.empty');
    }
    if (value < 1024) {
      return `${value} B`;
    }
    if (value < 1024 ** 2) {
      return `${(value / 1024).toFixed(1)} KB`;
    }
    if (value < 1024 ** 3) {
      return `${(value / 1024 ** 2).toFixed(1)} MB`;
    }
    return `${(value / 1024 ** 3).toFixed(1)} GB`;
  };

  const labelForWorkflowStatus = (status?: TenantWorkflowStatus): string => {
    if (!status) {
      return t('plugin.workflow-orchestration.tenant.common.placeholders.empty');
    }
    return translate(
      `plugin.workflow-orchestration.tenant.workflow.status.${status}`,
      undefined,
      humanizeCode(status),
    );
  };

  const labelForRunStatus = (status?: TenantRunStatus): string => {
    if (!status) {
      return t('plugin.workflow-orchestration.tenant.common.placeholders.empty');
    }
    return translate(
      `plugin.workflow-orchestration.tenant.run.status.${status}`,
      undefined,
      humanizeCode(status),
    );
  };

  const labelForArtifactStatus = (status?: TenantArtifactStatus): string => {
    if (!status) {
      return t('plugin.workflow-orchestration.tenant.common.placeholders.empty');
    }
    return translate(
      `plugin.workflow-orchestration.tenant.artifact.status.${status}`,
      undefined,
      humanizeCode(status),
    );
  };

  const labelForArtifactType = (type?: TenantArtifactType): string => {
    if (!type) {
      return t('plugin.workflow-orchestration.tenant.common.placeholders.empty');
    }
    return translate(
      `plugin.workflow-orchestration.tenant.artifact.type.${type}`,
      undefined,
      humanizeCode(type),
    );
  };

  const labelForBuilderMode = (mode?: TenantWorkflowBuilderMode): string => {
    if (!mode) {
      return t('plugin.workflow-orchestration.tenant.common.placeholders.empty');
    }
    return translate(
      `plugin.workflow-orchestration.tenant.workflow.builderMode.${mode}`,
      undefined,
      humanizeCode(mode),
    );
  };

  const labelForCapability = (code: string): string => {
    return translate(
      `plugin.workflow-orchestration.tenant.capability.labels.${code}`,
      undefined,
      humanizeCode(code),
    );
  };

  const labelForRisk = (risk?: string): string => {
    if (!risk) {
      return t('plugin.workflow-orchestration.tenant.common.placeholders.empty');
    }
    return translate(
      `plugin.workflow-orchestration.tenant.common.risk.${risk}`,
      undefined,
      humanizeCode(risk),
    );
  };

  const toneForWorkflowStatus = (status?: TenantWorkflowStatus): string => {
    switch (status) {
      case 'published':
        return 'success';
      case 'paused':
        return 'warning';
      case 'disabled':
      case 'archived':
        return 'neutral';
      case 'error':
        return 'danger';
      default:
        return 'info';
    }
  };

  const toneForRunStatus = (status?: TenantRunStatus): string => {
    switch (status) {
      case 'completed':
      case 'succeeded':
        return 'success';
      case 'partially_completed':
        return 'warning';
      case 'paused':
      case 'waiting_human':
      case 'waiting_approval':
      case 'waiting_input':
        return 'warning';
      case 'cancelled':
        return 'neutral';
      case 'failed':
      case 'terminated':
        return 'danger';
      case 'compensating':
      case 'recovering':
      case 'running':
        return 'info';
      case 'pending':
      case 'planning':
      case 'queued':
      case 'validating':
        return 'neutral';
      default:
        return 'neutral';
    }
  };

  const toneForArtifactStatus = (status?: TenantArtifactStatus): string => {
    switch (status) {
      case 'adopted':
      case 'ready':
        return 'success';
      case 'draft':
        return 'info';
      case 'expired':
      case 'pending_review':
        return 'warning';
      case 'rejected':
      case 'returned':
      case 'failed':
        return 'danger';
      case 'archived':
        return 'neutral';
      default:
        return 'info';
    }
  };

  const toneForRisk = (risk?: string): string => {
    switch (risk) {
      case 'high':
      case 'critical':
        return 'danger';
      case 'medium':
        return 'warning';
      case 'low':
        return 'info';
      default:
        return 'neutral';
    }
  };

  const canRunAction = (
    target:
      | null
      | undefined
      | {
          availableActions?: string[];
          canPause?: boolean;
          canResume?: boolean;
          canRetry?: boolean;
          canTerminate?: boolean;
          status?: string;
        },
    action: 'pause' | 'resume' | 'retry' | 'terminate',
  ): boolean => {
    if (!target) {
      return false;
    }

    if (Array.isArray(target.availableActions)) {
      return target.availableActions.includes(action);
    }

    const explicitFlags: Record<typeof action, boolean | undefined> = {
      pause: target.canPause,
      resume: target.canResume,
      retry: target.canRetry,
      terminate: target.canTerminate,
    };
    const explicit = explicitFlags[action];
    if (typeof explicit === 'boolean') {
      return explicit;
    }

    return RUN_ACTION_FALLBACK_BY_STATUS[action].includes(target.status ?? '');
  };

  return {
    buildTenantPath,
    canRunAction,
    formatBytes,
    formatDateTime,
    formatNumber,
    formatPercent,
    formatRelativeTime,
    getAccessCodes,
    hasAccess,
    hasAllAccess,
    hasAnyAccess,
    labelForArtifactStatus,
    labelForArtifactType,
    labelForBuilderMode,
    labelForCapability,
    labelForRisk,
    labelForRunStatus,
    labelForWorkflowStatus,
    navigateTo,
    openExternal,
    saveBlob,
    shared,
    t,
    toneForArtifactStatus,
    toneForRisk,
    toneForRunStatus,
    toneForWorkflowStatus,
  };
}
