import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, reactive } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import CommandBar from '../CommandBar.vue';

const mocks = vi.hoisted(() => ({
  getChatAgentsApi: vi.fn(),
  getGlobalConversationsApi: vi.fn(),
  routerPush: vi.fn(),
  updateChatConversationTitleApi: vi.fn(),
}));

let aiPanelStore: {
  open: ReturnType<typeof vi.fn>;
  pinnedAgentId: null | number;
  pinnedAgentName: null | string;
  unpinAgent: ReturnType<typeof vi.fn>;
  visible: boolean;
};

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mocks.routerPush,
  }),
}));

vi.mock('#/store', () => ({
  useAIPanelStore: () => aiPanelStore,
}));

vi.mock('#/api/shared/ai-chat', () => ({
  getChatAgentsApi: mocks.getChatAgentsApi,
  getGlobalConversationsApi: mocks.getGlobalConversationsApi,
  updateChatConversationTitleApi: mocks.updateChatConversationTitleApi,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIcon',
    template: '<span class="iconify-stub"></span>',
  }),
}));

vi.mock('#/utils/common', () => ({
  formatDate: (value: string) => value,
  formatRelativeTime: (value: string) => value,
}));

vi.mock('#/utils/image', () => ({
  toAvatarDisplayUrl: (value: string) => value,
}));

vi.mock('ant-design-vue', () => {
  const TextArea = defineComponent({
    name: 'TextAreaStub',
    props: {
      value: {
        default: '',
        type: String,
      },
    },
    emits: ['keydown', 'update:value'],
    template: `
      <textarea
        data-testid="cmd-input"
        :value="value"
        @input="$emit('update:value', $event.target.value)"
        @keydown="$emit('keydown', $event)"
      />
    `,
  });

  const Input = defineComponent({
    name: 'InputStub',
    props: {
      value: {
        default: '',
        type: String,
      },
    },
    emits: ['blur', 'click', 'keydown.enter', 'keydown.esc', 'update:value'],
    template: `
      <input
        :value="value"
        @input="$emit('update:value', $event.target.value)"
        @blur="$emit('blur')"
        @click="$emit('click', $event)"
      />
    `,
  }) as any;

  Input.TextArea = TextArea;

  const Spin = defineComponent({
    name: 'SpinStub',
    template: '<div><slot /></div>',
  });

  const Tooltip = defineComponent({
    name: 'TooltipStub',
    template: '<div><slot /></div>',
  });

  const SkeletonBlock = defineComponent({
    name: 'SkeletonBlock',
    template: '<div class="skeleton-stub"></div>',
  });

  return {
    Input,
    Skeleton: {
      Avatar: SkeletonBlock,
      Input: SkeletonBlock,
    },
    Spin,
    Tooltip,
  };
});

function createPinnedAgentStore() {
  const store = reactive<{
    open: ReturnType<typeof vi.fn>;
    pinnedAgentId: null | number;
    pinnedAgentName: null | string;
    unpinAgent: ReturnType<typeof vi.fn>;
    visible: boolean;
  }>({
    visible: false,
    pinnedAgentId: 1,
    pinnedAgentName: 'Cat Agent',
    open: vi.fn(),
    unpinAgent: vi.fn(),
  });
  store.open = vi.fn(() => {
    store.visible = true;
  });
  store.unpinAgent = vi.fn(() => {
    store.pinnedAgentId = null;
    store.pinnedAgentName = null;
  });
  return store;
}

async function openCommandBar() {
  const wrapper = mount(CommandBar, {
    attachTo: document.body,
    props: {
      apiPrefix: '/tenant',
      canChat: true,
      menus: [],
    },
  });

  await (wrapper.vm as typeof wrapper.vm & { show: () => Promise<void> }).show();
  await flushPromises();

  return wrapper;
}

function findButtonByText(text: string) {
  return Array.from(document.body.querySelectorAll('button')).find((button) =>
    button.textContent?.includes(text),
  );
}

describe('CommandBar', () => {
  beforeEach(() => {
    aiPanelStore = createPinnedAgentStore();
    mocks.routerPush.mockReset();
    mocks.getChatAgentsApi.mockReset();
    mocks.getGlobalConversationsApi.mockReset();
    mocks.updateChatConversationTitleApi.mockReset();

    mocks.getChatAgentsApi.mockResolvedValue({
      items: [
        {
          id: 1,
          tenant_id: 1,
          name: 'Cat Agent',
          description: 'A cat assistant',
          avatar: null,
          status: 'active',
          welcome_message: '你好呀，主人喵~',
          suggested_questions: ['帮我总结今天工作', '帮我写一段欢迎语'],
        },
      ],
    });

    mocks.getGlobalConversationsApi.mockResolvedValue({ items: [] });
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('shows pinned agent welcome and starter questions in the command bar', async () => {
    const wrapper = await openCommandBar();

    expect(mocks.getChatAgentsApi).toHaveBeenCalledWith('/tenant');
    expect(document.body.textContent).toContain('Cat Agent');
    expect(document.body.textContent).toContain('你好呀，主人喵~');
    expect(document.body.textContent).toContain('帮我总结今天工作');
    expect(document.body.textContent).toContain('帮我写一段欢迎语');

    wrapper.unmount();
  });

  it('keeps starter content visible after typing a custom message', async () => {
    const wrapper = await openCommandBar();
    const textarea = document.body.querySelector(
      '[data-testid="cmd-input"]',
    ) as HTMLTextAreaElement | null;

    expect(textarea).toBeTruthy();
    textarea!.value = '帮我分析今天的客户反馈';
    textarea!.dispatchEvent(new Event('input'));
    await flushPromises();

    expect(document.body.textContent).toContain('你好呀，主人喵~');
    expect(document.body.textContent).toContain('帮我总结今天工作');

    wrapper.unmount();
  });

  it('sends starter questions directly when clicked', async () => {
    const wrapper = await openCommandBar();
    const starterButton = findButtonByText('帮我总结今天工作');

    expect(starterButton).toBeTruthy();
    starterButton!.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flushPromises();

    expect(wrapper.emitted('submit')).toEqual([['帮我总结今天工作']]);
    expect(aiPanelStore.open).toHaveBeenCalledTimes(1);

    wrapper.unmount();
  });

  it('renders the recent conversations section only once in starter mode', async () => {
    mocks.getGlobalConversationsApi.mockResolvedValue({
      items: [
        {
          agent_avatar: null,
          agent_id: 1,
          agent_name: 'Cat Agent',
          created_at: '2026-03-23T10:00:00Z',
          id: 101,
          status: 'active',
          title: '最近的对话',
        },
      ],
    });

    const wrapper = await openCommandBar();
    const recentChatsCount =
      document.body.textContent?.match(/common\.commandBar\.recentChats/g)
        ?.length ?? 0;

    expect(document.body.textContent).toContain('最近的对话');
    expect(recentChatsCount).toBe(1);

    wrapper.unmount();
  });
});
