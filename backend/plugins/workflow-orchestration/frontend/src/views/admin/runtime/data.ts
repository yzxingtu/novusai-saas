import type { GlobalRunSummary } from '../../../types/admin';

import { $t } from '@novus/plugin-shared';

import { ADMIN_I18N_PREFIX } from '../shared/constants';

interface FilterOption {
  label: string;
  value: string;
}

const RUN_STATUSES = [
  'pending',
  'running',
  'waiting_human',
  'succeeded',
  'failed',
  'cancelled',
] as const;

export function getRunStatusOptions(): FilterOption[] {
  return RUN_STATUSES.map((value) => ({
    value,
    label: getRunStatusText(value),
  }));
}

export function getRunStatusColor(status: null | string | undefined): string {
  switch (status) {
    case 'running': {
      return 'processing';
    }
    case 'waiting_human': {
      return 'orange';
    }
    case 'succeeded': {
      return 'success';
    }
    case 'failed': {
      return 'error';
    }
    case 'cancelled': {
      return 'default';
    }
    case 'pending':
    default: {
      return 'blue';
    }
  }
}

export function getRunStatusText(status: null | string | undefined): string {
  if (!status) {
    return $t(`${ADMIN_I18N_PREFIX}.common.unknown`);
  }
  const key = `${ADMIN_I18N_PREFIX}.status.run.${status}`;
  const translated = $t(key);
  return translated === key ? status : translated;
}

export function getNodeStatusColor(status: null | string | undefined): string {
  switch (status) {
    case 'running': {
      return 'processing';
    }
    case 'waiting_human':
    case 'waiting_approval':
    case 'waiting_input': {
      return 'orange';
    }
    case 'succeeded':
    case 'skipped':
    case 'compensated': {
      return 'success';
    }
    case 'failed_retryable':
    case 'failed_terminal': {
      return 'error';
    }
    case 'cancelled': {
      return 'default';
    }
    case 'pending':
    default: {
      return 'blue';
    }
  }
}

export function getNodeStatusText(status: null | string | undefined): string {
  if (!status) {
    return $t(`${ADMIN_I18N_PREFIX}.common.unknown`);
  }
  const key = `${ADMIN_I18N_PREFIX}.status.node.${status}`;
  const translated = $t(key);
  return translated === key ? status : translated;
}

export function getArtifactStatusColor(status: null | string | undefined): string {
  switch (status) {
    case 'ready': {
      return 'success';
    }
    case 'draft': {
      return 'processing';
    }
    case 'failed': {
      return 'error';
    }
    case 'archived':
    default: {
      return 'default';
    }
  }
}

export function getArtifactStatusText(status: null | string | undefined): string {
  if (!status) {
    return $t(`${ADMIN_I18N_PREFIX}.common.unknown`);
  }
  const key = `${ADMIN_I18N_PREFIX}.status.artifact.${status}`;
  const translated = $t(key);
  return translated === key ? status : translated;
}

export function getArtifactTypeText(type: null | string | undefined): string {
  if (!type) {
    return $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`);
  }
  const key = `${ADMIN_I18N_PREFIX}.runtime.artifactType.${type}`;
  const translated = $t(key);
  return translated === key ? type : translated;
}

export function hasRunAction(
  run: null | Pick<GlobalRunSummary, 'available_actions' | 'status'>,
  action: string,
): boolean {
  if (run?.available_actions?.length) {
    return run.available_actions.includes(action);
  }

  switch (action) {
    case 'replay': {
      return ['succeeded', 'failed', 'cancelled'].includes(run?.status || '');
    }
    case 'recover': {
      return run?.status === 'failed';
    }
    case 'terminate': {
      return ['pending', 'running', 'waiting_human'].includes(run?.status || '');
    }
    default: {
      return false;
    }
  }
}
