// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file */
// Test type: behavioral
// Verifies: the user AI workspace header keeps a generic title while exposing
// agent details through the shared profile trigger and preserving action affordances.
import { mount } from '@vue/test-utils';
import { defineComponent, ref } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import UserAIChatWorkspaceHeader from '../UserAIChatWorkspaceHeader.vue';

const selectedAgent = ref<null | Record<string, unknown>>(null);
const activeConversationId = ref<null | number>(null);
const streaming = ref(false);
const memoryLoading = ref(false);
const clearingMemory = ref(false);
const lastMemoryUpdated = ref<null | string>(null);
const chatHeaderSubtitle = ref('');
const selectedAgentHasVariables = ref(false);
const selectedAgentVarsConfigured = ref(false);
const showMemoryPanel = ref(false);

const workspaceActions = {
  onStartNewChat: vi.fn(),
  onToggleMemory: vi.fn().mockResolvedValue(undefined),
  openMobileSidebar: vi.fn(),
  openSelectedAgentVarsModal: vi.fn(),
};

const workspaceContext = {
  openMobileSidebar: workspaceActions.openMobileSidebar,
  page: {
    apiPrefix: '/api/user',
    chat: {
      activeConversationId,
      clearingMemory,
      lastMemoryUpdated,
      memoryLoading,
      selectedAgent,
      streaming,
    },
    chatHeaderSubtitle,
    onStartNewChat: workspaceActions.onStartNewChat,
    onToggleMemory: workspaceActions.onToggleMemory,
    openSelectedAgentVarsModal: workspaceActions.openSelectedAgentVarsModal,
    selectedAgentHasVariables,
    selectedAgentVarsConfigured,
    showMemoryPanel,
  },
};

function resetWorkspaceState() {
  selectedAgent.value = {
    avatar: '/avatars/navigator.png',
    description: 'A routing specialist for travel planning',
    id: 17,
    model_name: 'gpt-5.4-mini',
    name: 'Navigator',
  };
  activeConversationId.value = 42;
  streaming.value = false;
  memoryLoading.value = false;
  clearingMemory.value = false;
  lastMemoryUpdated.value = null;
  chatHeaderSubtitle.value = 'Conversation checkpoint';
  selectedAgentHasVariables.value = false;
  selectedAgentVarsConfigured.value = false;
  showMemoryPanel.value = false;
  workspaceActions.onStartNewChat.mockClear();
  workspaceActions.onToggleMemory.mockClear();
  workspaceActions.openMobileSidebar.mockClear();
  workspaceActions.openSelectedAgentVarsModal.mockClear();
}

vi.mock('../user-ai-chat-workspace-context', () => ({
  useUserAIChatWorkspaceContext: () => workspaceContext,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-stub"></span>',
  }),
}));

vi.mock('ant-design-vue', () => ({
  Spin: defineComponent({
    name: 'SpinStub',
    template: '<span data-testid="spin-stub"></span>',
  }),
  Tooltip: defineComponent({
    name: 'TooltipStub',
    props: {
      title: {
        default: '',
        type: [Object, String],
      },
    },
    template:
      '<div class="tooltip-stub" :data-tooltip-title="String(title)"><slot /></div>',
  }),
}));

vi.mock('#/components/business/agent-profile-popover', () => ({
  AgentProfilePopover: defineComponent({
    name: 'AgentProfilePopoverStub',
    props: {
      agentAvatar: { default: null, type: String },
      agentDescription: { default: null, type: String },
      agentId: { default: null, type: Number },
      agentName: { default: null, type: String },
      apiPrefix: { default: '', type: String },
      modelName: { default: null, type: String },
      size: { default: 'md', type: String },
    },
    template:
      '<div data-testid="agent-profile-popover-stub" :data-agent-avatar="agentAvatar || \'\'" :data-agent-description="agentDescription || \'\'" :data-agent-id="String(agentId ?? \'\')" :data-agent-name="agentName || \'\'" :data-api-prefix="apiPrefix" :data-model-name="modelName || \'\'" :data-size="size"></div>',
  }),
}));

describe('userAIChatWorkspaceHeader', () => {
  beforeEach(() => {
    resetWorkspaceState();
  });

  it('keeps the workspace title generic while delegating agent details to the shared profile trigger', () => {
    const wrapper = mount(UserAIChatWorkspaceHeader);

    expect(
      wrapper.get('[data-testid="user-ai-chat-workspace-title"]').text(),
    ).toBe('user.aiChat.title');
    expect(
      wrapper.get('[data-testid="user-ai-chat-workspace-subtitle"]').text(),
    ).toBe('Conversation checkpoint');
    expect(wrapper.text()).not.toContain('Navigator');
    expect(wrapper.text()).not.toContain('gpt-5.4-mini');

    const profileTrigger = wrapper.get('[data-testid="agent-profile-popover-stub"]');
    expect(profileTrigger.attributes('data-agent-name')).toBe('Navigator');
    expect(profileTrigger.attributes('data-model-name')).toBe('gpt-5.4-mini');
    expect(profileTrigger.attributes('data-api-prefix')).toBe('/api/user');
    expect(profileTrigger.attributes('data-size')).toBe('md');
  });

  it('keeps vars, new chat, and memory actions discoverable and clickable', async () => {
    selectedAgentHasVariables.value = true;
    selectedAgentVarsConfigured.value = true;
    lastMemoryUpdated.value = '2026-04-25T09:00:00Z';

    const wrapper = mount(UserAIChatWorkspaceHeader);

    expect(
      wrapper.find(
        '[data-tooltip-title="user.aiChat.varsModal.editVars"] [data-testid="user-ai-chat-vars-button"]',
      ).exists(),
    ).toBe(true);
    expect(
      wrapper.find(
        '[data-tooltip-title="common.aiPanel.newChat"] [data-testid="user-ai-chat-new-chat-button"]',
      ).exists(),
    ).toBe(true);
    expect(
      wrapper.find(
        '[data-tooltip-title="common.aiPanel.memory"] [data-testid="user-ai-chat-memory-button"]',
      ).exists(),
    ).toBe(true);

    await wrapper.get('[data-testid="user-ai-chat-vars-button"]').trigger('click');
    await wrapper
      .get('[data-testid="user-ai-chat-new-chat-button"]')
      .trigger('click');
    await wrapper.get('[data-testid="user-ai-chat-memory-button"]').trigger('click');

    expect(workspaceActions.openSelectedAgentVarsModal).toHaveBeenCalledTimes(1);
    expect(workspaceActions.onStartNewChat).toHaveBeenCalledTimes(1);
    expect(workspaceActions.onToggleMemory).toHaveBeenCalledTimes(1);
  });
});
