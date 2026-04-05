import type { IdentityDetail } from './identity-detail';

import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

function normalizeText(value?: null | string): string {
  return typeof value === 'string' ? value.trim() : '';
}

export function formatIdentityDateTime(value?: null | string): string {
  return formatDate(value, {
    fallback: $t('shared.identity.field.empty'),
    format: 'YYYY-MM-DD HH:mm:ss',
  });
}

export function shouldShowIdentityRole(
  detail: Pick<IdentityDetail, 'orgNodeName' | 'roleName'>,
): boolean {
  const roleName = normalizeText(detail.roleName);
  if (!roleName) {
    return false;
  }

  const orgNodeName = normalizeText(detail.orgNodeName);
  return roleName !== orgNodeName;
}
