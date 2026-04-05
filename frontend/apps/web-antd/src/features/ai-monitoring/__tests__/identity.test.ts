import type { MonitoringActorInfo, MonitoringCallLogInfo } from '../api';

import { describe, expect, it, vi } from 'vitest';

vi.mock('#/components/business/identity-display', () => ({
  createIdentityDisplayModel: (model: Record<string, unknown>) => {
    const displayName =
      (typeof model.nickname === 'string' && model.nickname.trim()) ||
      (typeof model.displayName === 'string' && model.displayName.trim()) ||
      (typeof model.username === 'string' && model.username.trim()) ||
      `#${String(model.id ?? '-')}`;

    const secondaryText =
      typeof model.username === 'string' && model.username.trim() !== displayName
        ? model.username.trim()
        : '';

    return {
      ...model,
      displayName,
      secondaryText,
    };
  },
  getIdentityDetailTypeLabel: (type?: null | string) => {
    switch (type) {
      case 'admin':
      case 'platform_admin': {
        return 'shared.identity.userTypes.admin';
      }
      case 'tenant_admin': {
        return 'shared.identity.userTypes.tenantAdmin';
      }
      case 'tenant_user': {
        return 'shared.identity.userTypes.tenantUser';
      }
      default: {
        return 'shared.identity.userTypes.unknown';
      }
    }
  },
}));

import {
  createMonitoringActorDetailMeta,
  createMonitoringActorIdentityModel,
  createMonitoringCallerDetailMeta,
  createMonitoringCallerIdentityModel,
} from '../identity';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

describe('ai monitoring identity helpers', () => {
  it('uses shared user type labels and backend display role names for actors', () => {
    const model = createMonitoringActorIdentityModel({
      display_role_name: '安全审核员',
      id: 1,
      nickname: 'Root',
      org_node_name: '平台管理组',
      role_name: '平台管理组',
      type: 'platform_admin',
      username: 'root',
    } satisfies MonitoringActorInfo);

    expect(model?.badges?.[0]?.label).toBe('shared.identity.userTypes.admin');
    expect(model?.roleName).toBe('安全审核员');
  });

  it('respects explicit null actor display_role_name without falling back to raw role', () => {
    const model = createMonitoringActorIdentityModel({
      display_role_name: null,
      id: 2,
      nickname: 'Alice',
      org_node_name: '华东一区',
      role_name: '华东一区',
      type: 'tenant_admin',
      username: 'alice',
    } satisfies MonitoringActorInfo);

    expect(model?.roleName).toBeUndefined();
  });

  it('respects explicit null caller display role name and keeps compact username fallback', () => {
    const model = createMonitoringCallerIdentityModel({
      caller_display_name: '企业管理员A',
      caller_display_role_name: null,
      caller_id: 9,
      caller_name: '企业管理员A',
      caller_nickname: '企业管理员A',
      caller_org_node_name: '华东一区',
      caller_role_name: '华东一区',
      caller_type: 'tenant_admin',
      caller_username: 'tenant_admin_9',
    } satisfies Partial<MonitoringCallLogInfo> as MonitoringCallLogInfo);

    expect(model.roleName).toBeUndefined();
    expect(model.secondaryText).toBe('tenant_admin_9');
  });

  it('builds detail meta from display role names instead of duplicated raw roles', () => {
    const actorMeta = createMonitoringActorDetailMeta(
      {
        display_name: 'Bob',
        display_role_name: '供应商审核角色',
        org_node_name: '供应商中心',
        role_name: '供应商中心',
        type: 'tenant_user',
        username: 'bob',
      } satisfies MonitoringActorInfo,
      {
        scope: 'tenant',
        tenantId: 11,
        tenantName: 'Tenant A',
      },
    );

    const callerMeta = createMonitoringCallerDetailMeta(
      {
        caller_display_name: 'Bob',
        caller_display_role_name: null,
        caller_id: 7,
        caller_name: 'Bob',
        caller_org_node_name: '供应商中心',
        caller_role_name: '供应商中心',
        caller_type: 'tenant_user',
        caller_username: 'bob',
      } satisfies Partial<MonitoringCallLogInfo> as MonitoringCallLogInfo,
      {
        createdAt: '2026-04-05T11:16:26.926870+00:00',
        scope: 'tenant',
        tenantId: 11,
        tenantName: 'Tenant A',
      },
    );

    expect(actorMeta.roleName).toBe('供应商审核角色');
    expect(actorMeta.tenantName).toBe('Tenant A');
    expect(callerMeta.roleName).toBeUndefined();
    expect(callerMeta.username).toBe('bob');
  });
});
