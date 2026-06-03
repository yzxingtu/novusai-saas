// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: route cache keys include endpoint scope and route API payloads stay runtime-safe.

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

  it('reuses route cache by message and attachment flags', async () => {
    const scope = effectScope();

    await scope.run(async () => {
      const { routeMessage } = useAgentRouter({
        activeConversationId: ref(null),
        agents: ref([]),
        apiPrefix: ref('/tenant'),
        pinnedAgentId: ref(null),
        pinnedAgentName: ref(null),
      });

      await routeMessage('请分析这批记录');
      await routeMessage('请分析这批记录');

      expect(routeMessageApiMock).toHaveBeenCalledTimes(1);
    });

    scope.stop();
  });

  it('does not reuse a cached route after apiPrefix changes', async () => {
    const scope = effectScope();

    await scope.run(async () => {
      const apiPrefix = ref('/tenant');
      const { routeMessage } = useAgentRouter({
        activeConversationId: ref(null),
        agents: ref([]),
        apiPrefix,
        pinnedAgentId: ref(null),
        pinnedAgentName: ref(null),
      });

      await routeMessage('请分析这批记录');
      apiPrefix.value = '/admin';
      await routeMessage('请分析这批记录');

      expect(routeMessageApiMock).toHaveBeenCalledTimes(2);
      expect(routeMessageApiMock.mock.calls.map((call) => call[0])).toEqual([
        '/tenant',
        '/admin',
      ]);
    });

    scope.stop();
  });

  it('does not send invalid runtime fields to the route API', async () => {
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
      expect(Object.keys(requestBody ?? {}).toSorted()).toEqual([
        'conversation_id',
        'force_reroute',
        'has_audio_attachments',
        'has_file_attachments',
        'has_image_attachments',
        'has_video_attachments',
        'message',
        'pinned_agent_id',
      ]);
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
