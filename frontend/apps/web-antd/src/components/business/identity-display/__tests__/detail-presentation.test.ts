// Test type: structural
// Verifies: identity detail presentation rows preserve account AI status.
import type { IdentityDetail } from '../identity-detail';

import { describe, expect, it, vi } from 'vitest';

import {
  buildIdentityActivityRows,
  buildIdentitySummaryRows,
  formatIdentityDateTime,
  resolveIdentityPrimaryContextLabel,
  resolveIdentityPrimaryContextValue,
  shouldShowRoleRow,
  shouldShowSecondaryOrganization,
} from '../detail-presentation';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils/common', () => ({
  formatDate: (value?: null | string) =>
    value === '2026-02-08T20:28:24.941275+00:00'
      ? '2026-02-09 04:28:24'
      : value || 'shared.identity.field.empty',
  formatRelativeTime: (value?: null | string) =>
    value ? `relative:${value}` : '',
}));

describe('detail presentation', () => {
  it('uses role as the primary context for tenant users', () => {
    const detail: Pick<
      IdentityDetail,
      'orgNodeName' | 'roleName' | 'userType'
    > = {
      orgNodeName: '华东一区',
      roleName: '采购专员',
      userType: 'tenant_user',
    };

    expect(resolveIdentityPrimaryContextLabel(detail)).toBe(
      'shared.identity.field.role',
    );
    expect(resolveIdentityPrimaryContextValue(detail)).toBe('采购专员');
  });

  it('uses organization as the primary context for non tenant users', () => {
    const detail: Pick<
      IdentityDetail,
      'orgNodeName' | 'roleName' | 'userType'
    > = {
      orgNodeName: '平台管理组',
      roleName: '供应商审核角色',
      userType: 'admin',
    };

    expect(resolveIdentityPrimaryContextLabel(detail)).toBe(
      'shared.identity.field.organization',
    );
    expect(resolveIdentityPrimaryContextValue(detail)).toBe('平台管理组');
  });

  it('hides role row when it duplicates organization name', () => {
    const detail: Pick<
      IdentityDetail,
      'orgNodeName' | 'roleName' | 'userType'
    > = {
      orgNodeName: '平台管理组',
      roleName: '平台管理组',
      userType: 'admin',
    };

    expect(shouldShowRoleRow(detail)).toBe(false);
  });

  it('keeps secondary organization for tenant users whose role is primary', () => {
    const detail: Pick<
      IdentityDetail,
      'orgNodeName' | 'roleName' | 'userType'
    > = {
      orgNodeName: '华东一区',
      roleName: '采购专员',
      userType: 'tenant_user',
    };

    expect(shouldShowSecondaryOrganization(detail)).toBe(true);
  });

  it('builds overview rows without duplicating the role for non tenant users', () => {
    const detail = {
      orgNodeName: '平台管理组',
      roleName: '平台管理组',
      tenantName: 'Novus',
      userType: 'admin',
      username: 'platform.admin',
    } as IdentityDetail;

    expect(
      buildIdentitySummaryRows(detail, 'detail-overview').map((row) => row.key),
    ).toEqual(['username', 'tenant', 'primary-context']);
  });

  it('formats activity time with the project date-time format', () => {
    expect(formatIdentityDateTime('2026-02-08T20:28:24.941275+00:00')).toBe(
      '2026-02-09 04:28:24',
    );
  });

  it('shows account-level AI chat status in account rows', () => {
    const detail = {
      aiEnabled: false,
      isActive: true,
      username: 'platform.admin',
    } as IdentityDetail;

    expect(buildIdentitySummaryRows(detail, 'detail-account')).toContainEqual({
      key: 'ai-chat',
      label: 'shared.identity.field.aiChat',
      value: 'shared.common.statusDisabled',
    });
  });

  it('masks recent activity rows when the viewer cannot access activity data', () => {
    const rows = buildIdentityActivityRows({
      canViewActivity: false,
      createdAt: null,
      lastLoginAt: null,
      lastLoginIp: null,
      updatedAt: null,
    });

    expect(rows.map((row) => row.value)).toEqual([
      '*****',
      '*****',
      '*****',
      '*****',
    ]);
  });
});
