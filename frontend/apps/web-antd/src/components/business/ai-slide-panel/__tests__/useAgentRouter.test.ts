// @vitest-environment happy-dom

import type { PageContextSuggestedTool } from '#/api/shared/ai-chat';

import { effectScope, ref } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useAgentRouter } from '../use-agent-router';

const { routeMessageApiMock } = vi.hoisted(() => ({
  routeMessageApiMock: vi.fn(),
}));

vi.mock('#/api/shared/ai-chat', () => ({
  routeMessageApi: routeMessageApiMock,
}));

vi.mock('#/components/business/ai-runtime/runtime-bridge', () => ({
  getRuntimeThinPageContext: vi.fn(() => null),
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

  it('reuses route cache when non-fingerprint thin fields change', async () => {
    const scope = effectScope();

    await scope.run(async () => {
      const { routeMessage } = useAgentRouter({
        activeConversationId: ref(null),
        agents: ref([]),
        apiPrefix: ref('/tenant'),
        pinnedAgentId: ref(null),
        pinnedAgentName: ref(null),
      });

      const primaryTools: PageContextSuggestedTool[] = [
        'ui_get_snapshot',
        'ui_list_interactables',
      ];
      const secondaryTools: PageContextSuggestedTool[] = ['ui_read_region'];
      const baseContext = {
        active_surface_id: 'surface:page',
        page_key: 'tenant.demo.fallback',
        page_title: 'Fallback Demo',
        suggested_tools: {
          primary: primaryTools,
          secondary: secondaryTools,
        },
        surface_stack: [
          {
            kind: 'page' as const,
            surface_id: 'surface:page',
            title: 'Fallback Demo',
          },
        ],
        ui_epoch: 3,
      };

      await routeMessage('请分析当前页面', undefined, baseContext);
      await routeMessage('请分析当前页面', undefined, {
        ...baseContext,
        page_title: 'Fallback Demo (debug title only)',
        suggested_tools: {
          ...baseContext.suggested_tools,
          reason: 'title changed only',
        },
      });

      expect(routeMessageApiMock).toHaveBeenCalledTimes(1);
    });

    scope.stop();
  });

  it('busts route cache when meaningful thin context fields change', async () => {
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
        active_surface_id: 'surface:page',
        page_key: 'tenant.demo.fallback',
        page_title: 'Fallback Demo',
        surface_stack: [
          {
            kind: 'page' as const,
            surface_id: 'surface:page',
            title: 'Fallback Demo',
          },
        ],
        ui_epoch: 3,
      });

      await routeMessage('请分析当前页面', undefined, {
        active_form_summary: {
          can_submit: false,
          entity_name: 'supplier',
          form_session_id: 'form:1',
          mode: 'edit' as const,
          remaining_required_fields: ['supplier_name'],
          stage: 'ready' as const,
          submit_policy: 'confirm' as const,
        },
        active_surface_id: 'surface:drawer',
        page_key: 'tenant.demo.fallback',
        page_title: 'Fallback Demo',
        surface_stack: [
          {
            kind: 'page' as const,
            surface_id: 'surface:page',
            title: 'Fallback Demo',
          },
          {
            kind: 'drawer' as const,
            surface_id: 'surface:drawer',
            title: 'Supplier Config',
          },
        ],
        ui_epoch: 4,
      });

      expect(routeMessageApiMock).toHaveBeenCalledTimes(2);
    });

    scope.stop();
  });
});
