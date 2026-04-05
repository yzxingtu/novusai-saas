// @vitest-environment happy-dom

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { navigateToPathWithContext } from '../page-navigation';

const mocks = vi.hoisted(() => ({
  currentRouteValue: {
    meta: {},
    path: '/admin/dashboard',
  },
  pushMock: vi.fn(),
  resolvePageContextMock: vi.fn(),
}));

vi.mock('#/router', () => ({
  router: {
    currentRoute: {
      get value() {
        return mocks.currentRouteValue;
      },
      set value(value) {
        mocks.currentRouteValue = value;
      },
    },
    push: mocks.pushMock,
  },
}));

vi.mock('#/composables/use-page-session', () => ({
  getActivePageSessionId: () => 'page-session-2',
}));

vi.mock('#/components/business/ai-slide-panel/page-context-registry', () => ({
  resolvePageContext: mocks.resolvePageContextMock,
}));

describe('page-navigation', () => {
  beforeEach(() => {
    mocks.currentRouteValue = {
      meta: {},
      path: '/admin/dashboard',
    };
    mocks.pushMock.mockReset();
    mocks.resolvePageContextMock.mockReset();
    mocks.resolvePageContextMock.mockImplementation((pageKey: string) => ({
      page_key: pageKey,
      page_title: 'Resolved Page',
      page_data: {
        source: 'registered',
      },
    }));
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('returns already_on_page without pushing when the target matches current route', async () => {
    mocks.currentRouteValue = {
      meta: {
        ai: {
          pageContextKey: 'admin.ai.agents',
        },
      },
      path: '/admin/ai/agents',
    };

    const result = await navigateToPathWithContext({
      pageKey: 'admin.ai.agents',
      path: '/admin/ai/agents',
      title: 'Agents',
    });

    expect(result.success).toBe(true);
    expect(result.data?.already_on_page).toBe(true);
    expect(mocks.pushMock).not.toHaveBeenCalled();
  });

  it('returns page context and session data after a successful navigation', async () => {
    mocks.pushMock.mockImplementation(async (path: string) => {
      mocks.currentRouteValue = {
        meta: {
          ai: {
            pageContextKey: 'admin.ai.agents',
          },
          title: '智能体',
        },
        path,
      };
    });

    const result = await navigateToPathWithContext({
      pageKey: 'admin.ai.agents',
      path: '/admin/ai/agents',
      title: '智能体',
    });

    expect(result.success).toBe(true);
    expect(result.data?.page_session_id).toBe('page-session-2');
    expect(result.data?.page_context).toMatchObject({
      page_key: 'admin.ai.agents',
    });
    expect(result.data?.navigation_target).toMatchObject({
      page_key: 'admin.ai.agents',
      path: '/admin/ai/agents',
    });
    expect(result.data?.destination_ready).toBe(true);
    expect(result.data?.can_auto_continue).toBe(false);
  });

  it('returns a partial success when the route matches but destination readiness is not reached', async () => {
    mocks.pushMock.mockImplementation(async (path: string) => {
      mocks.currentRouteValue = {
        meta: {
          ai: {
            pageContextKey: 'admin.ai.agents',
          },
          title: '智能体',
        },
        path,
      };
    });
    mocks.resolvePageContextMock.mockReturnValue({
      page_key: 'admin.ai.agents',
      page_title: 'Resolved Page',
      page_data: {
        source: 'minimal_fallback',
      },
    });

    const result = await navigateToPathWithContext({
      pageKey: 'admin.ai.agents',
      path: '/admin/ai/agents',
      title: '智能体',
    });

    expect(result.success).toBe(true);
    expect(result.data?.destination_ready).toBe(false);
    expect(result.data?.can_auto_continue).toBe(false);
    expect(result.data?.destination_ready_reason).toBe('destination_not_ready');
  });

  it('returns permission_denied when navigation ends on a forbidden route', async () => {
    mocks.pushMock.mockImplementation(async () => {
      mocks.currentRouteValue = {
        meta: {},
        path: '/admin/403',
      };
    });

    const result = await navigateToPathWithContext({
      pageKey: 'admin.plugins',
      path: '/admin/plugins',
      title: '插件管理',
    });

    expect(result.success).toBe(false);
    expect(result.error_type).toBe('permission_denied');
  });
});
