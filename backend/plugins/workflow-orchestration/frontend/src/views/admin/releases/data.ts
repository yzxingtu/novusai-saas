import { $t } from '@novus/plugin-shared';

import { ADMIN_I18N_PREFIX } from '../shared/constants';

interface FilterOption {
  label: string;
  value: string;
}

export function getReleaseStatusOptions(): FilterOption[] {
  return [
    'draft',
    'reviewing',
    'approved',
    'published',
    'disabled',
    'deprecated',
    'rolled_back',
  ].map((value) => ({
    value,
    label: getReleaseStatusText(value),
  }));
}

export function getReleaseScopeOptions(): FilterOption[] {
  return [
    'platform_catalog',
    'selected_tenants',
    'tenant_private',
  ].map((value) => ({
    value,
    label: getReleaseScopeText(value),
  }));
}

export function getReleaseChannelOptions(): FilterOption[] {
  return ['stable', 'beta', 'internal'].map((value) => ({
    value,
    label: getReleaseChannelText(value),
  }));
}

export function getReleaseStatusColor(status: null | string | undefined): string {
  switch (status) {
    case 'published': {
      return 'success';
    }
    case 'reviewing': {
      return 'processing';
    }
    case 'approved': {
      return 'blue';
    }
    case 'disabled':
    case 'deprecated': {
      return 'default';
    }
    case 'rolled_back': {
      return 'purple';
    }
    case 'draft':
    default: {
      return 'orange';
    }
  }
}

export function getReleaseStatusText(status: null | string | undefined): string {
  if (!status) {
    return $t(`${ADMIN_I18N_PREFIX}.common.unknown`);
  }
  const key = `${ADMIN_I18N_PREFIX}.status.release.${status}`;
  const translated = $t(key);
  return translated === key ? status : translated;
}

export function getReleaseEnvironmentColor(
  environment: null | string | undefined,
): string {
  if (!environment) {
    return 'default';
  }
  if (environment.includes('prod')) {
    return 'red';
  }
  if (environment.includes('beta') || environment.includes('stage')) {
    return 'blue';
  }
  return 'default';
}

export function getReleaseEnvironmentText(
  environment: null | string | undefined,
): string {
  if (!environment) {
    return $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`);
  }
  return environment;
}

export function getReleaseScopeText(scope: null | string | undefined): string {
  if (!scope) {
    return $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`);
  }
  const key = `${ADMIN_I18N_PREFIX}.common.releaseScope.${scope}`;
  const translated = $t(key);
  return translated === key ? scope : translated;
}

export function getReleaseChannelText(channel: null | string | undefined): string {
  if (!channel) {
    return $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`);
  }
  const key = `${ADMIN_I18N_PREFIX}.common.channel.${channel}`;
  const translated = $t(key);
  return translated === key ? channel : translated;
}
