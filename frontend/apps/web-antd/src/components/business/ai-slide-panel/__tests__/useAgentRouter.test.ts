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

  it('reuses route cache without page-context fingerprints', async () => {
    const scope = effectScope();

    await scope.run(async () => {
      const { routeMessage } = useAgentRouter({
        activeConversationId: ref(null),
        agents: ref([]),
        apiPrefix: ref('/tenant'),
        pinnedAgentId: ref(null),
        pinnedAgentName: ref(null),
      });

      await routeMessage('请分析当前页面');
      await routeMessage('请分析当前页面');

      expect(routeMessageApiMock).toHaveBeenCalledTimes(1);
    });

    scope.stop();
  });

  it('does not send retired page_context to the route API', async () => {
    const scope = effectScope();

    await scope.run(async () => {
      const { routeMessage } = useAgentRouter({
        activeConversationId: ref(null),
        agents: ref([]),
        apiPrefix: ref('/tenant'),
        pinnedAgentId: ref(null),
        pinnedAgentName: ref(null),
      });

      await routeMessage('帮我切到智能体页面');

      const requestBody = routeMessageApiMock.mock.calls[0]?.[1];
      expect(requestBody).not.toHaveProperty('page_context');
      expect(requestBody).not.toHaveProperty('page_session_id');
    });

    scope.stop();
  });

  it('uses the pinned agent without calling the route API', async () => {
    const scope = effectScope();

    await scope.run(async () => {
      const { routeMessage } = useAgentRouter({
        activeConversationId: ref(null),
        agents: ref([]),
        apiPrefix: ref('/tenant'),
        pinnedAgentId: ref(13),
        pinnedAgentName: ref('Pinned Agent'),
      });

      const result = await routeMessage('anything');

      expect(routeMessageApiMock).not.toHaveBeenCalled();
      expect(result).toMatchObject({
        agentId: 13,
        agentName: 'Pinned Agent',
        routedBy: 'pinned',
      });
    });

    scope.stop();
  });
});
