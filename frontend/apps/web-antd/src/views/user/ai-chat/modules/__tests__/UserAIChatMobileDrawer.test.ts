// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file */
// Test type: behavioral
// Verifies: the mobile AI chat drawer keeps history search discoverable and
// resolves agent avatars through the shared image helper instead of raw URLs.
import { mount } from '@vue/test-utils';
import { defineComponent, ref } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import UserAIChatMobileDrawer from '../UserAIChatMobileDrawer.vue';

const conversationSearch = ref('');
const mobileSidebarOpen = ref(true);
const agents = ref([
  {
    avatar: '/avatars/navigator.png',
    id: 7,
    name: 'Navigator',
  },
]);
const conversations = ref([
  { id: 1, title: 'One' },
  { id: 2, title: 'Two' },
  { id: 3, title: 'Three' },
  { id: 4, title: 'Four' },
]);
const selectedAgentId = ref(7);

const actions = {
  onSelectAgent: vi.fn(),
  onStartNewChat: vi.fn(),
};

vi.mock('../ai-chat-context', () => ({
  useUserAIChatContext: () => ({
    chat: {
      agents,
      conversations,
      selectedAgentId,
    },
    conversationSearch,
    mobileSidebarOpen,
    onSelectAgent: actions.onSelectAgent,
    onStartNewChat: actions.onStartNewChat,
  }),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils/image', () => ({
  toAvatarDisplayUrl: (value: string) => `resolved:${value}`,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-stub"></span>',
  }),
}));

vi.mock('ant-design-vue', () => ({
  Drawer: defineComponent({
    name: 'DrawerStub',
    props: {
      open: {
        default: false,
        type: Boolean,
      },
    },
    template:
      '<div data-testid="drawer-stub" :data-open="String(open)"><slot name="title" /><slot /></div>',
  }),
  Input: defineComponent({
    name: 'InputStub',
    props: {
      value: {
        default: '',
        type: String,
      },
    },
    emits: ['update:value'],
    template:
      '<label data-testid="mobile-history-search"><input :value="value" @input="$emit(\'update:value\', $event.target && $event.target.value ? $event.target.value : \'\')" /><slot name="prefix" /></label>',
  }),
}));

vi.mock('../UserAIChatConversationList.vue', () => ({
  default: defineComponent({
    name: 'UserAIChatConversationListStub',
    template: '<div data-testid="conversation-list-stub"></div>',
  }),
}));

describe('userAIChatMobileDrawer', () => {
  beforeEach(() => {
    conversationSearch.value = '';
    mobileSidebarOpen.value = true;
    selectedAgentId.value = 7;
    actions.onSelectAgent.mockClear();
    actions.onStartNewChat.mockClear();
  });

  it('shows the same history search affordance as desktop when enough conversations exist', async () => {
    const wrapper = mount(UserAIChatMobileDrawer);

    const searchInput = wrapper.get('[data-testid="mobile-history-search"] input');
    expect((searchInput.element as HTMLInputElement).value).toBe('');

    await searchInput.setValue('trip');

    expect(conversationSearch.value).toBe('trip');
  });

  it('renders agent avatars through the shared resolver', () => {
    const wrapper = mount(UserAIChatMobileDrawer);

    const avatar = wrapper.get('img');
    expect(avatar.attributes('src')).toBe('resolved:/avatars/navigator.png');
  });
});
