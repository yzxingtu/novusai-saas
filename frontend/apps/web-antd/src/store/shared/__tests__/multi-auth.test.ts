// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: tenant user-info refresh only overwrites permission codes when /me explicitly returns permissions.
import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useMultiAuthStore } from '../multi-auth';
import { TokenStorage } from '../token-storage';

const routerPush = vi.hoisted(() => vi.fn());
const routerReplace = vi.hoisted(() => vi.fn());
const getTenantAdminInfoApi = vi.hoisted(() => vi.fn());
const tenantLoginApi = vi.hoisted(() => vi.fn());
const getUserInfoApi = vi.hoisted(() => vi.fn());
const setAccessCodes = vi.hoisted(() => vi.fn());
const setUserInfo = vi.hoisted(() => vi.fn());

const accessStore = vi.hoisted(() => ({
  accessToken: 'tenant-token',
  loginExpired: false,
  setAccessCodes,
  setAccessMenus: vi.fn(),
  setAccessRoutes: vi.fn(),
  setAccessToken: vi.fn(),
  setIsAccessChecked: vi.fn(),
  setLoginExpired: vi.fn(),
  setRefreshToken: vi.fn(),
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({
    path: '/tenant/dashboard',
    query: {},
  }),
  useRouter: () => ({
    currentRoute: {
      value: {
        fullPath: '/tenant/dashboard',
      },
    },
    push: routerPush,
    replace: routerReplace,
  }),
}));

vi.mock('@vben/stores', () => ({
  useAccessStore: () => accessStore,
  useTabbarStore: () => ({
    $patch: vi.fn(),
  }),
  useUserStore: () => ({
    setUserInfo,
  }),
}));

vi.mock('#/api/admin/auth', () => ({
  adminChangePasswordApi: vi.fn(),
  adminLoginApi: vi.fn(),
  adminLogoutApi: vi.fn(),
  adminRefreshTokenApi: vi.fn(),
  getAdminInfoApi: vi.fn(),
}));

vi.mock('#/api/tenant/auth', () => ({
  getTenantAdminInfoApi,
  tenantChangePasswordApi: vi.fn(),
  tenantLoginApi,
  tenantLogoutApi: vi.fn(),
  tenantRefreshTokenApi: vi.fn(),
}));

vi.mock('#/api/user/auth', () => ({
  getUserInfoApi,
  userChangePasswordApi: vi.fn(),
  userLoginApi: vi.fn(),
  userLoginByCodeApi: vi.fn(),
  userLogoutApi: vi.fn(),
  userRefreshTokenApi: vi.fn(),
  userSendLoginCodeApi: vi.fn(),
}));

vi.mock('ant-design-vue', () => ({
  notification: {
    success: vi.fn(),
    warning: vi.fn(),
  },
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils/image', () => ({
  toAvatarDisplayUrl: (value: string | undefined) => value,
}));

vi.mock('#/utils/tabbar-storage', () => ({
  clearPersistedTabbarStorage: vi.fn(),
}));

vi.mock('../user-preference', () => ({
  useUserPreferenceStore: () => ({
    clearPreferences: vi.fn(),
    loadPreferences: vi.fn().mockResolvedValue(undefined),
  }),
}));

describe('useMultiAuthStore permissions refresh', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    accessStore.accessToken = 'tenant-token';
    accessStore.loginExpired = false;
    localStorage.clear();
    sessionStorage.clear();
    TokenStorage.init('vitest_multi_auth');
  });

  it('does not overwrite access codes when tenant user info omits permissions', async () => {
    getTenantAdminInfoApi.mockResolvedValueOnce({
      hasPlan: true,
      id: 7,
      realName: 'Owner',
      roles: [],
      tenantId: 5,
      tenantName: 'Tenant',
      username: 'owner',
    });

    const store = useMultiAuthStore();
    await store.fetchUserInfo('tenant');

    expect(setAccessCodes).not.toHaveBeenCalled();
    expect(setUserInfo).toHaveBeenCalledWith(
      expect.objectContaining({
        token: 'tenant-token',
        userId: '7',
        username: 'owner',
      }),
    );
  });

  it('updates access codes when tenant user info explicitly returns permissions', async () => {
    getTenantAdminInfoApi.mockResolvedValueOnce({
      hasPlan: true,
      id: 7,
      permissions: ['menu:tenant.ai.chat', 'agent_chat:chat'],
      realName: 'Owner',
      roles: [],
      tenantId: 5,
      tenantName: 'Tenant',
      username: 'owner',
    });

    const store = useMultiAuthStore();
    await store.fetchUserInfo('tenant');

    expect(setAccessCodes).toHaveBeenCalledTimes(1);
    expect(setAccessCodes).toHaveBeenCalledWith([
      'menu:tenant.ai.chat',
      'agent_chat:chat',
    ]);
  });
});
