import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { usePresenceStore } from '../presence';

const requestGet = vi.hoisted(() => vi.fn());
const registerHandler = vi.hoisted(() => vi.fn());
const unregisterHandler = vi.hoisted(() => vi.fn());
const replace = vi.hoisted(() => vi.fn());
const clearToken = vi.hoisted(() => vi.fn());
const clearPreferences = vi.hoisted(() => vi.fn());

vi.mock('#/utils/request', () => ({
  requestClient: {
    get: requestGet,
  },
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({
    path: '/admin/dashboard',
  }),
  useRouter: () => ({
    currentRoute: {
      value: {
        fullPath: '/admin/dashboard',
      },
    },
    replace,
  }),
}));

vi.mock('@vben/stores', () => ({
  useAccessStore: () => ({
    setAccessCodes: vi.fn(),
    setAccessMenus: vi.fn(),
    setAccessRoutes: vi.fn(),
    setAccessToken: vi.fn(),
    setIsAccessChecked: vi.fn(),
    setLoginExpired: vi.fn(),
    setRefreshToken: vi.fn(),
  }),
  useTabbarStore: () => ({
    $patch: vi.fn(),
  }),
  useUserStore: () => ({
    setUserInfo: vi.fn(),
  }),
}));

vi.mock('ant-design-vue', () => ({
  Modal: {
    warning: vi.fn(),
  },
}));

vi.mock('../notification', () => ({
  useNotificationStore: () => ({
    $reset: vi.fn(),
  }),
}));

vi.mock('../socketio', () => ({
  useSocketIOStore: () => ({
    $reset: vi.fn(),
    currentEndpoint: 'admin',
    registerHandler,
    unregisterHandler,
  }),
}));

vi.mock('../token-storage', () => ({
  TokenStorage: {
    clearToken,
  },
}));

vi.mock('../user-preference', () => ({
  useUserPreferenceStore: () => ({
    clearPreferences,
  }),
}));

vi.mock('#/utils/tabbar-storage', () => ({
  clearPersistedTabbarStorage: vi.fn(),
}));

describe('usePresenceStore ensurePresenceLoaded', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    vi.spyOn(console, 'error').mockImplementation(() => {});
    requestGet.mockResolvedValue({
      details: {},
      online_ids: [],
      total_online: 0,
    });
  });

  it('routes supported targets to the correct presence endpoints', async () => {
    const store = usePresenceStore();

    await store.ensurePresenceLoaded('admin', 'admin');
    expect(requestGet).toHaveBeenLastCalledWith('/admin/ws/presence');

    store.$reset();
    requestGet.mockClear();

    await store.ensurePresenceLoaded('tenant_admin', 'admin', 42);
    expect(requestGet).toHaveBeenLastCalledWith('/admin/ws/presence/tenant/42');

    store.$reset();
    requestGet.mockClear();

    await store.ensurePresenceLoaded('tenant_user', 'admin', 42);
    expect(requestGet).toHaveBeenLastCalledWith(
      '/admin/ws/presence/tenant/42/users',
    );

    store.$reset();
    requestGet.mockClear();

    await store.ensurePresenceLoaded('tenant_admin', 'tenant');
    expect(requestGet).toHaveBeenLastCalledWith('/tenant/ws/presence');

    store.$reset();
    requestGet.mockClear();

    await store.ensurePresenceLoaded('tenant_user', 'tenant');
    expect(requestGet).toHaveBeenLastCalledWith('/tenant/ws/presence/users');
  });

  it('deduplicates concurrent requests for the same supported target', async () => {
    const store = usePresenceStore();
    let resolveRequest!: (value: {
      details: Record<string, never>;
      online_ids: number[];
      total_online: number;
    }) => void;

    requestGet.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveRequest = resolve;
      }),
    );

    const first = store.ensurePresenceLoaded('tenant_user', 'tenant');
    const second = store.ensurePresenceLoaded('tenant_user', 'tenant');

    expect(requestGet).toHaveBeenCalledTimes(1);

    resolveRequest({
      details: {},
      online_ids: [8],
      total_online: 1,
    });

    await Promise.all([first, second]);
    await store.ensurePresenceLoaded('tenant_user', 'tenant');

    expect(requestGet).toHaveBeenCalledTimes(1);
  });

  it('stores admin tenant-user presence per tenant without polluting other tenants', async () => {
    const store = usePresenceStore();

    requestGet.mockResolvedValueOnce({
      details: {},
      online_ids: [8, 9],
      total_online: 2,
    });
    await store.ensurePresenceLoaded('tenant_user', 'admin', 42);

    requestGet.mockResolvedValueOnce({
      details: {},
      online_ids: [15],
      total_online: 1,
    });
    await store.ensurePresenceLoaded('tenant_user', 'admin', 99);

    expect(store.isOnline('tenant_user', 8, 42)).toBe(true);
    expect(store.isOnline('tenant_user', 15, 42)).toBe(false);
    expect(store.isOnline('tenant_user', 15, 99)).toBe(true);
  });

  it('skips unsupported targets without issuing a request', async () => {
    const store = usePresenceStore();

    await expect(
      store.ensurePresenceLoaded('tenant_user', 'admin'),
    ).resolves.toBe(false);
    expect(requestGet).not.toHaveBeenCalled();
  });
});
