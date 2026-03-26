/**
 * ChatMessageItem component tests: waiting_confirm, executing, 8s hint, error_type mapping.
 * ChatMessageItem 组件测试：待确认、执行中、8s 提示、error_type 映射。
 */
import { mount } from '@vue/test-utils';
import { ref } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ChatMessageItem from '../ChatMessageItem.vue';
import type { ChatMessage } from '../types';

interface PendingPageOpTest {
  invokeId: string;
  operationLabel: string;
  operationDescription: string;
  params: Record<string, unknown>;
  resolved: boolean;
  allowed?: boolean;
  startedAt: number;
  toolCallId?: string;
}

const pendingPageOpsValue = ref<PendingPageOpTest[]>([]);
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
    role: 'assistant',
    content: '',
    toolCalls,
  };
}

function createPendingOp(
  overrides: Partial<PendingPageOpTest> = {},
): PendingPageOpTest {
  return {
    invokeId: 'inv-1',
    operationLabel: 'Op',
    operationDescription: '',
    params: {},
    resolved: false,
    startedAt: Date.now(),
    ...overrides,
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
    pendingPageOpsValue.value = [createPendingOp()];
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([
          { name: 'invoke_page_operation', status: 'running' },
        ]),
        pendingOps: [createPendingOp({ invokeId: 'i1' })],
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
      createPendingOp({
        invokeId: 'inv_1',
        operationLabel: 'Replace content',
        operationDescription: '...',
        toolCallId: 'tc_123',
      }),
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
    // Simulates: tool_start had name pageop_xxx, tool_call had name invoke_page_operation; / 模拟名称不一致
    // fallback matched and updated the running tool to success, so we show success not error. / 回退匹配后应显示成功
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
      createPendingOp({
        invokeId: 'inv_1',
        operationLabel: 'Replace',
        toolCallId: 'tc_other',
      }),
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

  it('renders streamed thinking content separately', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          role: 'assistant',
          content: '',
          thinkingContent: '先检查上下文，再决定下一步。',
          streaming: true,
        },
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          AgentProfilePopover: true,
          MarkdownRender: {
            props: ['content'],
            template: '<div>{{ content }}</div>',
          },
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain('common.globalAiChat.thinking');
    expect(wrapper.text()).toContain('先检查上下文，再决定下一步。');
  });

  it('renders @ route badge for one-time mention messages', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          role: 'assistant',
          content: '喵~收到',
          agent_id: 2,
          agent_name: '猫娘智能体',
          routeSource: 'mention',
        },
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
    expect(wrapper.text()).toContain('@ 猫娘智能体');
  });

  it('renders tool target badges and toggles tool details with animated state', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([
          {
            name: 'data_query',
            status: 'success',
            arguments: {
              question: '统计今天调用情况',
            },
            output: JSON.stringify({
              explanation: '按今天范围统计 AI 调用，并按租户分组。',
              sql: "SELECT t.name, COUNT(acl.id) AS total_calls FROM ai_call_logs acl JOIN tenants t ON t.id = acl.tenant_id WHERE acl.created_at >= CURRENT_DATE GROUP BY t.name",
              success: true,
            }),
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

    expect(wrapper.text()).toContain('common.globalAiChat.toolTouched');
    expect(wrapper.text()).toContain('统计今天调用情况');
    expect(wrapper.text()).toContain('ai_call_logs, tenants');
    expect(wrapper.text()).toContain('common.globalAiChat.toolTargetMetrics');
    expect(wrapper.text()).toContain('COUNT(acl.id)');
    expect(wrapper.text()).toContain('common.globalAiChat.toolTargetGrouping');
    expect(wrapper.text()).toContain('t.name');
    expect(wrapper.text()).toContain('common.globalAiChat.toolTargetFilter');
    expect(wrapper.text()).toContain('common.globalAiChat.toolFilterToday');

    const details = wrapper.get('[data-testid="tool-call-details-0"]');
    expect(details.attributes('style') ?? '').toContain('grid-template-rows: 0fr');

    await wrapper.get('[data-testid="tool-call-toggle-0"]').trigger('click');
    await wrapper.vm.$nextTick();

    expect(details.attributes('style') ?? '').toContain('grid-template-rows: 1fr');
    expect(wrapper.text()).toContain('common.globalAiChat.toolExplanation');
    expect(wrapper.text()).toContain('按今天范围统计 AI 调用，并按租户分组。');
    expect(wrapper.text()).toContain('common.globalAiChat.toolSql');

    const sqlCopyButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('common.globalAiChat.copySql'));
    expect(sqlCopyButton).toBeTruthy();
    await sqlCopyButton!.trigger('click');
    expect(wrapper.emitted('copy')?.[0]).toEqual([
      "SELECT t.name, COUNT(acl.id) AS total_calls FROM ai_call_logs acl JOIN tenants t ON t.id = acl.tenant_id WHERE acl.created_at >= CURRENT_DATE GROUP BY t.name",
    ]);

    expect(wrapper.text()).toContain('common.globalAiChat.rawResult');
  });
});
