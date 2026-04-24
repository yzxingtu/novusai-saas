// Test type: behavioral
// Verifies: user-page vars editing follows the shared slide-panel rules by
// preferring a conversation-wide editor when multiple agents in the transcript
// expose variables, while still falling back to selected-agent editing.
import { ref } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { AgentItem } from '#/types/ai-chat';

import { useUserAIChatVarsModal } from '../use-user-ai-chat-vars-modal';

vi.mock('ant-design-vue', () => ({
  message: {
    warning: vi.fn(),
  },
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

describe('useUserAIChatVarsModal', () => {
  const applyVariables = vi.fn();
  const ensureAgentVarsLoaded = vi.fn();
  const sendMessage = vi.fn();

  beforeEach(() => {
    applyVariables.mockClear();
    ensureAgentVarsLoaded.mockClear();
    sendMessage.mockClear();
  });

  it('opens the multi-agent editor when conversation agents already expose variables', () => {
    const selectedAgent = ref<AgentItem | null>({
      avatar: null,
      description: null,
      id: 1,
      input_variables: [{ label: 'Topic', name: 'topic', type: 'string' }],
      name: 'Selected',
      status: 'active',
      tenant_id: 0,
    });
    const agentsWithVarsInConversation = ref<AgentItem[]>([
      {
        avatar: null,
        description: null,
        id: 2,
        input_variables: [{ label: 'Project', name: 'project', type: 'string' }],
        name: 'Analyst',
        status: 'active',
        tenant_id: 0,
      },
    ]);
    const allAgentsVariables = ref({
      2: { project: 'novus' },
    });

    const modal = useUserAIChatVarsModal({
      agentsWithVarsInConversation,
      allAgentsVariables,
      applyVariables,
      ensureAgentVarsLoaded,
      selectedAgent,
      sendMessage,
    });

    expect(modal.showHeaderVarsButton.value).toBe(true);
    expect(modal.headerVariablesConfigured.value).toBe(true);

    modal.openHeaderVarsModal();

    expect(modal.multiVarsModalVisible.value).toBe(true);
    expect(modal.varsModalVisible.value).toBe(false);
    expect(ensureAgentVarsLoaded).toHaveBeenCalledWith(2);
  });

  it('falls back to the selected-agent editor when no transcript agent needs the shared vars modal', () => {
    const selectedAgent = ref<AgentItem | null>({
      avatar: null,
      description: null,
      id: 9,
      input_variables: [{ label: 'Region', name: 'region', type: 'string' }],
      name: 'Planner',
      status: 'active',
      tenant_id: 0,
    });
    const agentsWithVarsInConversation = ref<AgentItem[]>([]);
    const allAgentsVariables = ref({
      9: { region: 'apac' },
    });

    const modal = useUserAIChatVarsModal({
      agentsWithVarsInConversation,
      allAgentsVariables,
      applyVariables,
      ensureAgentVarsLoaded,
      selectedAgent,
      sendMessage,
    });

    modal.openHeaderVarsModal();

    expect(modal.multiVarsModalVisible.value).toBe(false);
    expect(modal.varsModalVisible.value).toBe(true);
    expect(modal.varsModalAgent.value?.id).toBe(9);
    expect(modal.varsFormValues.region).toBe('apac');
  });
});
