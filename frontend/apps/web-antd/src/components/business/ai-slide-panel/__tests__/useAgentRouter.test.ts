// @vitest-environment happy-dom

import { effectScope, ref } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useAgentRouter } from '../use-agent-router';

const { routeMessageApiMock } = vi.hoisted(() => ({
  routeMessageApiMock: vi.fn(),
}));

vi.mock('#/api/shared/ai-chat', () => ({
  routeMessageApi: routeMessageApiMock,
}));

vi.mock('../page-context-registry', () => ({
  resolvePageContext: vi.fn(),
}));

describe('useAgentRouter', () => {
  beforeEach(() => {
    routeMessageApiMock.mockReset();
    routeMessageApiMock.mockResolvedValue({
      agent_id: 7,
      agent_name: 'Router Agent',
      confidence: 0.91,
      routed_by: 'router',
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('reuses route cache when only visual_state changes', async () => {
    const scope = effectScope();

    await scope.run(async () => {
      const { routeMessage } = useAgentRouter({
        activeConversationId: ref(null),
        agents: ref([]),
        apiPrefix: ref('/tenant'),
        pinnedAgentId: ref(null),
        pinnedAgentName: ref(null),
      });

      const baseContext = {
        page_key: 'tenant.demo.fallback',
        page_title: 'Fallback Demo',
        page_data: {
          available_operations: [{ name: 'read_current_view', readonly: true }],
          entity_description: 'Inspect current page fallback context',
          source: 'dom_snapshot',
          tables: [{ columns: ['名称', '状态'], row_count: 12 }],
          visual_state: {
            scroll_y: 0,
            url: '/tenant/demo/fallback',
          },
        },
      };

      await routeMessage('请分析当前页面', undefined, baseContext);
      await routeMessage('请分析当前页面', undefined, {
        ...baseContext,
        page_data: {
          ...baseContext.page_data,
          visual_state: {
            has_modal: true,
            open_overlays: [{ title: '调试面板', type: 'drawer' }],
            scroll_y: 480,
            url: '/tenant/demo/fallback',
          },
        },
      });

      expect(routeMessageApiMock).toHaveBeenCalledTimes(1);
    });

    scope.stop();
  });

  it('busts route cache when meaningful structural page data changes', async () => {
    const scope = effectScope();

    await scope.run(async () => {
      const { routeMessage } = useAgentRouter({
        activeConversationId: ref(null),
        agents: ref([]),
        apiPrefix: ref('/tenant'),
        pinnedAgentId: ref(null),
        pinnedAgentName: ref(null),
      });

      await routeMessage('请分析当前页面', undefined, {
        page_key: 'tenant.demo.fallback',
        page_title: 'Fallback Demo',
        page_data: {
          available_operations: [{ name: 'read_current_view', readonly: true }],
          entity_description: 'Inspect current page fallback context',
          source: 'dom_snapshot',
        },
      });

      await routeMessage('请分析当前页面', undefined, {
        page_key: 'tenant.demo.fallback',
        page_title: 'Fallback Demo',
        page_data: {
          available_operations: [{ name: 'read_current_view', readonly: true }],
          entity_description: 'Inspect supplier configuration fallback context',
          source: 'dom_snapshot',
        },
      });

      expect(routeMessageApiMock).toHaveBeenCalledTimes(2);
    });

    scope.stop();
  });
});
