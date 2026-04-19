import { describe, expect, it } from 'vitest';

import {
  buildCompactNavigationPageData,
  buildMenuNavigationEntries,
  resolveMenuNavigationTarget,
  searchMenuNavigationEntries,
} from '../menu-navigation';

describe('menu-navigation', () => {
  it('matches semantic navigation from backend-provided ai metadata', () => {
    const entries = buildMenuNavigationEntries({
      currentEndpoint: 'admin',
      menus: [
        {
          name: '智能体管理',
          path: '/admin/ai/agents',
          meta: {
            ai: {
              category: 'ai',
              description: '创建、编辑和管理 AI 智能体',
              keywords: ['智能体', 'AI助手', 'assistant'],
              capabilities: ['create_agent', 'edit_agent'],
            },
          },
        },
      ] as any,
    });

    const matches = searchMenuNavigationEntries(entries, '帮我新增 AI 助手');

    expect(matches).toHaveLength(1);
    expect(matches[0]?.pageKey).toBe('admin.ai.agents');
    expect(matches[0]?.score).toBeGreaterThanOrEqual(900);
  });

  it('resolves by exact title without local preset knowledge', () => {
    const entries = buildMenuNavigationEntries({
      currentEndpoint: 'admin',
      menus: [
        {
          name: '插件管理',
          path: '/admin/plugins',
        },
      ] as any,
    });

    const resolution = resolveMenuNavigationTarget({
      currentPageKey: 'admin.dashboard',
      currentPath: '/admin/dashboard',
      entries,
      target: '打开插件管理',
    });

    expect(resolution.kind).toBe('success');
    if (resolution.kind === 'success') {
      expect(resolution.entry.path).toBe('/admin/plugins');
    }
  });

  it('builds compact navigation page data from query-bearing current paths', () => {
    const entries = buildMenuNavigationEntries({
      currentEndpoint: 'admin',
      menus: [
        {
          name: '智能体管理',
          path: '/admin/ai/agents',
          meta: {
            ai: {
              pageContextKey: 'admin.ai.agents',
            },
          },
        },
      ] as any,
    });

    const pageData = buildCompactNavigationPageData({
      currentPageKey: 'admin.ai.agents',
      currentPath: '/admin/ai/agents?tab=create#modal',
      entries,
    });

    expect(pageData).toMatchObject({
      navigation_catalog: [
        expect.objectContaining({
          page_key: 'admin.ai.agents',
          path: '/admin/ai/agents',
        }),
      ],
      navigation_context: {
        breadcrumb: ['智能体管理'],
        endpoint: 'admin',
        page_key: 'admin.ai.agents',
        path: '/admin/ai/agents',
      },
    });
  });
});
