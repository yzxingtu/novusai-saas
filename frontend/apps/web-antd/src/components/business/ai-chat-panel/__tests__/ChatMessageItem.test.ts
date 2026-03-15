/**
 * ChatMessageItem component tests: waiting_confirm, executing, 8s hint, error_type mapping.
 * ChatMessageItem 组件测试：待确认、执行中、8s 提示、error_type 映射。
 */
import { mount } from '@vue/test-utils';
import { ref } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ChatMessageItem from '../ChatMessageItem.vue';
import type { ChatMessage } from '../types';

const pendingPageOpsValue = ref<{ resolved: boolean; toolCallId?: string }[]>([]);
const resolvePageOp = vi.fn();

vi.mock('#/store', () => ({
  useAIPanelStore: () => ({
    get pendingPageOps() {
      return pendingPageOpsValue.value;
    },
    resolvePageOp,
  }),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

function createAssistantMsg(toolCalls: ChatMessage['toolCalls']): ChatMessage {
  return {
    id: 'msg-1',
    role: 'assistant',
    content: '',
    toolCalls,
  };
}

describe('ChatMessageItem', () => {
  beforeEach(() => {
    pendingPageOpsValue.value = [];
    vi.useRealTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows toolWaitingConfirm when invoke_page_operation + pending op (legacy: no toolCallId)', async () => {
    pendingPageOpsValue.value = [{ resolved: false }];
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([
          { name: 'invoke_page_operation', status: 'running' },
        ]),
        pendingOps: [{ resolved: false, invokeId: 'i1', operationLabel: 'Op', operationDescription: '', params: {}, startedAt: Date.now() }],
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          AgentProfilePopover: true,
          MarkdownRender: true,
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain('common.globalAiChat.toolWaitingConfirm');
  });

  it('shows toolExecuting when running tool without pending op', async () => {
    pendingPageOpsValue.value = [];
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([
          {
            name: 'invoke_page_operation',
            status: 'running',
          },
        ]),
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          AgentProfilePopover: true,
          MarkdownRender: true,
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain('common.globalAiChat.toolExecuting');
  });

  it('shows toolExecuting for non-page-op running tool', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([
          {
            name: 'search_database',
            status: 'running',
          },
        ]),
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          AgentProfilePopover: true,
          MarkdownRender: true,
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain('common.globalAiChat.toolExecuting');
  });

  it('shows toolStillRunningHint when running 8s+', async () => {
    vi.useFakeTimers();
    const baseTime = 1000000000000;
    vi.setSystemTime(baseTime);

    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([
          {
            name: 'invoke_page_operation',
            status: 'running',
            startedAt: baseTime - 9000,
          },
        ]),
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          AgentProfilePopover: true,
          MarkdownRender: true,
          IconifyIcon: true,
        },
      },
    });

    await vi.advanceTimersByTimeAsync(1500);
    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain('common.globalAiChat.toolStillRunningHint');
  });

  it('shows pageOpPendingConfirmationHint for errorType=pending_confirmation', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([
          {
            name: 'invoke_page_operation',
            status: 'error',
            error: 'Awaiting confirmation',
            errorType: 'pending_confirmation',
          },
        ]),
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          AgentProfilePopover: true,
          MarkdownRender: true,
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain('common.globalAiChat.pageOpPendingConfirmationHint');
  });

  it('shows waiting_confirm when pendingOps has matching toolCallId', async () => {
    pendingPageOpsValue.value = [
      { resolved: false, toolCallId: 'tc_123', invokeId: 'inv_1', operationLabel: 'Replace content', operationDescription: '...', params: {}, startedAt: Date.now() },
    ];
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([
          { id: 'tc_123', name: 'pageop_replace_content', status: 'running' },
        ]),
        pendingOps: pendingPageOpsValue.value,
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          AgentProfilePopover: true,
          MarkdownRender: true,
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain('common.globalAiChat.toolWaitingConfirm');
    expect(wrapper.text()).toContain('Replace content');
  });

  it('shows toolStatusOk (not error) when tool completes successfully after name-mismatch fallback', async () => {
    // Simulates: tool_start had name pageop_xxx, tool_call had name invoke_page_operation;
    // fallback matched and updated the running tool to success, so we show success not error.
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([
          {
            name: 'pageop_get_editor_html',
            status: 'success',
            durationMs: 200,
          },
        ]),
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          AgentProfilePopover: true,
          MarkdownRender: true,
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain('common.globalAiChat.toolStatusOk');
    expect(wrapper.text()).not.toContain('common.globalAiChat.toolStatusErr');
  });

  it('shows toolExecuting when pendingOps has non-matching toolCallId', async () => {
    pendingPageOpsValue.value = [
      { resolved: false, toolCallId: 'tc_other', invokeId: 'inv_1', operationLabel: 'Replace', operationDescription: '', params: {}, startedAt: Date.now() },
    ];
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([
          { id: 'tc_123', name: 'pageop_replace_content', status: 'running' },
        ]),
        pendingOps: pendingPageOpsValue.value,
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          AgentProfilePopover: true,
          MarkdownRender: true,
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain('common.globalAiChat.toolExecuting');
  });

  it('shows pageOpExecFailedHint for unknown error_type fallback', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([
          {
            name: 'invoke_page_operation',
            status: 'error',
            error: 'Unknown failure',
            errorType: 'unknown_type',
          },
        ]),
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          AgentProfilePopover: true,
          MarkdownRender: true,
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain('common.globalAiChat.pageOpExecFailedHint');
  });
});
