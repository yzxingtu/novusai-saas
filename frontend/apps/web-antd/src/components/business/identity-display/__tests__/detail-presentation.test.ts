import type { IdentityDetail } from '../identity-detail';

import { describe, expect, it, vi } from 'vitest';

import {
  formatIdentityDateTime,
  shouldShowIdentityRole,
} from '../detail-presentation';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

describe('detail presentation', () => {
  it('hides role when it duplicates organization name', () => {
    const detail: Pick<IdentityDetail, 'orgNodeName' | 'roleName'> = {
      orgNodeName: '平台管理组',
      roleName: '平台管理组',
    };

    expect(
      shouldShowIdentityRole(detail),
    ).toBe(false);
  });

  it('shows role when it is distinct from organization name', () => {
    const detail: Pick<IdentityDetail, 'orgNodeName' | 'roleName'> = {
      orgNodeName: '平台管理组',
      roleName: '供应商审核角色',
    };

    expect(
      shouldShowIdentityRole(detail),
    ).toBe(true);
  });

  it('formats activity time with project date-time format', () => {
    expect(formatIdentityDateTime('2026-02-08T20:28:24.941275+00:00')).toBe(
      '2026-02-09 04:28:24',
    );
  });
});
