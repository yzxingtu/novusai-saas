// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: mobile history rows keep the delete affordance visible without relying on hover-only styles.
import { mount } from '@vue/test-utils';
import { defineComponent, ref } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import UserAIChatConversationList from '../UserAIChatConversationList.vue';

const groupedConversations = ref([
  {
    items: [{ agent_name: 'Agent', id: 11, title: 'Mobile history item' }],
    label: '今天',
  },
]);
const editingConversationId = ref<null | number>(null);
const editingTitle = ref('');
const activeConversationId = ref<null | number>(11);
const conversationsLoading = ref(false);

const actions = {
  cancelEditTitle: vi.fn(),
  commitEditTitle: vi.fn(),
  onDeleteConversation: vi.fn(),
  onSelectConversation: vi.fn(),
  startEditTitle: vi.fn(),
};

vi.mock('../ai-chat-context', () => ({
  useUserAIChatContext: () => ({
    cancelEditTitle: actions.cancelEditTitle,
    chat: {
      activeConversationId,
      conversationsLoading,
    },
    commitEditTitle: actions.commitEditTitle,
    editingConversationId,
    editingTitle,
    groupedConversations,
    onDeleteConversation: actions.onDeleteConversation,
    onSelectConversation: actions.onSelectConversation,
    startEditTitle: actions.startEditTitle,
  }),
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
  Input: defineComponent({
    name: 'InputStub',
    template: '<input />',
  }),
  Spin: defineComponent({
    name: 'SpinStub',
    props: {
      spinning: {
        default: false,
        type: Boolean,
      },
    },
    template: '<div data-testid="spin-stub"><slot /></div>',
  }),
}));

describe('userAIChatConversationList', () => {
  beforeEach(() => {
    editingConversationId.value = null;
    editingTitle.value = '';
    activeConversationId.value = 11;
    actions.onDeleteConversation.mockClear();
  });

  it('shows the delete button by default for mobile rows', () => {
    const wrapper = mount(UserAIChatConversationList, {
      props: {
        variant: 'mobile',
      },
    });

    const deleteButton = wrapper.get(
      'button[aria-label="common.globalAiChat.deleteConversation"]',
    );
    expect(deleteButton.classes()).toContain('opacity-100');
  });

  it('keeps the desktop delete button hover-gated', () => {
    const wrapper = mount(UserAIChatConversationList, {
      props: {
        variant: 'desktop',
      },
    });

    const deleteButton = wrapper.get(
      'button[aria-label="common.globalAiChat.deleteConversation"]',
    );
    expect(deleteButton.classes()).toContain('opacity-0');
  });
});
