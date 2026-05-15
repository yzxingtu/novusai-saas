// Test type: structural
// Verifies: backend identity detail payload fields are preserved in the UI model.
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { shouldShowIdentityRole } from '../detail-presentation';

const apiMocks = vi.hoisted(() => ({
  getAdminIdentityDetailApi: vi.fn(),
  getAdminTenantAdminDetailApi: vi.fn(),
  getAdminTenantUserIdentityDetailApi: vi.fn(),
  getTenantAdminIdentityDetailApi: vi.fn(),
  getTenantUserDetailApi: vi.fn(),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/api/admin/users', () => ({
  getAdminIdentityDetailApi: apiMocks.getAdminIdentityDetailApi,
}));

vi.mock('#/api/admin/tenant', () => ({
  getAdminTenantAdminDetailApi: apiMocks.getAdminTenantAdminDetailApi,
}));

vi.mock('#/api/admin/tenant-users', () => ({
  getAdminTenantUserIdentityDetailApi:
    apiMocks.getAdminTenantUserIdentityDetailApi,
}));

vi.mock('#/api/tenant/admins', () => ({
  getTenantAdminIdentityDetailApi: apiMocks.getTenantAdminIdentityDetailApi,
}));

vi.mock('#/api/tenant/tenant-users', () => ({
  getTenantUserDetailApi: apiMocks.getTenantUserDetailApi,
}));

describe('identity detail contract mapping', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('prefers backend display_role_name when present', async () => {
    apiMocks.getAdminIdentityDetailApi.mockResolvedValueOnce({
      avatar: null,
      created_at: null,
      display_name: '平台管理员',
      display_role_name: '平台审核角色',
      email: null,
      id: 1,
      is_active: true,
      is_leader: false,
      is_owner: false,
      is_super: false,
      last_login_at: null,
      last_login_ip: null,
      nickname: '平台管理员',
      org_node_id: 10,
      org_node_name: '平台管理组',
      phone: null,
      role_id: 5,
      role_name: '平台审核角色',
      updated_at: null,
      user_type: 'admin',
      username: 'platform_admin',
    });

    const { loadIdentityDetail } = await import('../identity-detail');
    const detail = await loadIdentityDetail({
      id: 1,
      scope: 'admin',
      subjectType: 'admin',
    });

    expect(detail.roleName).toBe('平台审核角色');
    expect(shouldShowIdentityRole(detail)).toBe(true);
  });

  it('keeps role hidden when backend suppresses redundant display_role_name', async () => {
    apiMocks.getAdminIdentityDetailApi.mockResolvedValueOnce({
      avatar: null,
      created_at: null,
      display_name: '平台管理员',
      display_role_name: null,
      email: null,
      id: 2,
      is_active: true,
      is_leader: true,
      is_owner: false,
      is_super: false,
      last_login_at: null,
      last_login_ip: null,
      nickname: '平台管理员',
      org_node_id: 11,
      org_node_name: '平台管理组',
      phone: null,
      role_id: 6,
      role_name: '平台管理组',
      updated_at: null,
      user_type: 'admin',
      username: 'platform_admin_2',
    });

    const { loadIdentityDetail } = await import('../identity-detail');
    const detail = await loadIdentityDetail({
      id: 2,
      scope: 'admin',
      subjectType: 'admin',
    });

    expect(detail.roleName).toBeUndefined();
    expect(shouldShowIdentityRole(detail)).toBe(false);
  });

  it('preserves account-level AI disabled state from admin identity detail', async () => {
    apiMocks.getAdminIdentityDetailApi.mockResolvedValueOnce({
      ai_enabled: false,
      avatar: null,
      can_view_activity: false,
      created_at: null,
      display_name: '平台管理员',
      display_role_name: null,
      email: null,
      id: 3,
      is_active: true,
      is_leader: false,
      is_owner: false,
      is_super: true,
      last_login_at: null,
      last_login_ip: null,
      nickname: '平台管理员',
      org_node_id: 12,
      org_node_name: '平台管理组',
      phone: null,
      role_id: 7,
      role_name: null,
      updated_at: null,
      user_type: 'admin',
      username: 'platform_admin_3',
    });

    const { loadIdentityDetail } = await import('../identity-detail');
    const detail = await loadIdentityDetail({
      id: 3,
      scope: 'admin',
      subjectType: 'admin',
    });

    expect(detail.aiEnabled).toBe(false);
    expect(detail.canViewActivity).toBe(false);
  });
});
