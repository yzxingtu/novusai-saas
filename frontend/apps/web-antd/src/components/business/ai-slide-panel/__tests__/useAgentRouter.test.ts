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

      const baseContext = {
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
      };

      await routeMessage('请分析当前页面', undefined, baseContext);
      await routeMessage('请分析当前页面', undefined, {
        ...baseContext,
        page_title: 'Fallback Demo (debug title only)',
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

  it('busts route cache when compact navigation page data changes', async () => {
    const scope = effectScope();

    await scope.run(async () => {
      const { routeMessage } = useAgentRouter({
        activeConversationId: ref(null),
        agents: ref([]),
        apiPrefix: ref('/tenant'),
        pinnedAgentId: ref(null),
        pinnedAgentName: ref(null),
      });

      await routeMessage('帮我切到智能体页面', undefined, {
        page_data: {
          navigation_catalog: [
            {
              breadcrumb: ['Dashboard'],
              endpoint: 'tenant',
              page_key: 'tenant.dashboard',
              path: '/tenant/dashboard',
              title: 'Dashboard',
            },
          ],
          navigation_context: {
            breadcrumb: ['Dashboard'],
            endpoint: 'tenant',
            page_key: 'tenant.dashboard',
            path: '/tenant/dashboard',
          },
        },
        page_key: 'tenant.dashboard',
        page_title: 'Dashboard',
      });

      await routeMessage('帮我切到智能体页面', undefined, {
        page_data: {
          navigation_catalog: [
            {
              breadcrumb: ['Dashboard'],
              endpoint: 'tenant',
              page_key: 'tenant.dashboard',
              path: '/tenant/dashboard',
              title: 'Dashboard',
            },
            {
              breadcrumb: ['AI', 'Agents'],
              endpoint: 'tenant',
              page_key: 'tenant.ai.agents',
              path: '/tenant/ai/agents',
              title: 'Agents',
            },
          ],
          navigation_context: {
            breadcrumb: ['Dashboard'],
            endpoint: 'tenant',
            page_key: 'tenant.dashboard',
            path: '/tenant/dashboard',
          },
        },
        page_key: 'tenant.dashboard',
        page_title: 'Dashboard',
      });

      expect(routeMessageApiMock).toHaveBeenCalledTimes(2);
    });

    scope.stop();
  });

  it('sends a slim route page_context payload', async () => {
    const scope = effectScope();

    await scope.run(async () => {
      const { routeMessage } = useAgentRouter({
        activeConversationId: ref(null),
        agents: ref([]),
        apiPrefix: ref('/tenant'),
        pinnedAgentId: ref(null),
        pinnedAgentName: ref(null),
      });

      await routeMessage('帮我切到智能体页面', undefined, {
        active_form_session_id: 'form:1',
        active_form_summary: {
          can_submit: true,
          entity_name: '智能体',
          form_session_id: 'form:1',
          mode: 'edit',
          remaining_required_fields: ['名称', '模型', '提示词', '图标', '头像'],
          stage: 'ready',
          submit_policy: 'confirm',
        },
        active_surface_id: 'surface:drawer',
        page_data: {
          entity_description:
            '这个字段不需要给路由器携带完整描述，只保留路由判断需要的上下文。',
          navigation_catalog: Array.from({ length: 10 }, (_value, index) => ({
            breadcrumb: ['AI', `Page ${index + 1}`],
            page_key: `tenant.ai.page_${index + 1}`,
            path: `/tenant/ai/page-${index + 1}`,
            title: index === 8 ? '智能体管理' : `Page ${index + 1}`,
          })),
          navigation_context: {
            breadcrumb: ['AI', 'Dashboard'],
            endpoint: 'tenant',
            page_key: 'tenant.ai.dashboard',
            path: '/tenant/ai/dashboard',
          },
          search_inputs: [
            {
              label: '搜索词',
              locator: 'input[name="keyword"]',
            },
          ],
          visible_tables: [
            {
              label: '列表',
              locator: '[data-testid="table"]',
            },
          ],
        },
        page_key: 'tenant.ai.dashboard',
        page_session_id: 'page-session-1',
        page_title: 'AI Dashboard',
        surface_stack: [
          {
            kind: 'page',
            surface_id: 'surface:page',
            title: 'AI Dashboard',
          },
          {
            kind: 'drawer',
            surface_id: 'surface:drawer',
            title: '智能体配置',
          },
          {
            kind: 'modal',
            surface_id: 'surface:modal',
            title: '高级设置',
          },
          {
            kind: 'popover',
            surface_id: 'surface:popover',
            title: '更多操作',
          },
          {
            kind: 'dropdown',
            surface_id: 'surface:dropdown',
            title: '额外菜单',
          },
        ],
        ui_epoch: 11,
      });

      const requestBody = routeMessageApiMock.mock.calls[0]?.[1];
      expect(requestBody?.page_context).toMatchObject({
        active_form_session_id: 'form:1',
        active_form_summary: {
          can_submit: true,
          entity_name: '智能体',
          form_session_id: 'form:1',
          remaining_required_fields: ['名称', '模型', '提示词', '图标'],
          stage: 'ready',
          submit_policy: 'confirm',
        },
        active_surface_id: 'surface:drawer',
        page_data: {
          navigation_context: {
            breadcrumb: ['AI', 'Dashboard'],
            endpoint: 'tenant',
            page_key: 'tenant.ai.dashboard',
            path: '/tenant/ai/dashboard',
          },
        },
        page_key: 'tenant.ai.dashboard',
        page_session_id: 'page-session-1',
        page_title: 'AI Dashboard',
        ui_epoch: 11,
      });
      expect(requestBody?.page_context?.surface_stack).toHaveLength(4);
      expect(requestBody?.page_context?.page_data?.navigation_catalog).toHaveLength(6);
      expect(requestBody?.page_context?.page_data?.search_inputs).toBeUndefined();
      expect(requestBody?.page_context?.page_data?.visible_tables).toBeUndefined();
      expect(requestBody?.page_context?.page_data?.entity_description).toBeUndefined();
    });

    scope.stop();
  });
});
