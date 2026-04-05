import type {
  ChatMessage,
  RichTextAISelectionSnapshot,
  RichTextAITask,
  RichTextDraftRuntimeState,
} from '../types';

/**
 * ChatMessageItem component tests: waiting_confirm, executing, 8s hint, error_type mapping.
 * ChatMessageItem 组件测试：待确认、执行中、8s 提示、error_type 映射。
 */
import { mount } from '@vue/test-utils';
import { ref } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ChatMessageItem from '../ChatMessageItem.vue';

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
    clientKey: 'assistant-tool-message',
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

function createRichTextTask(
  overrides: Partial<RichTextAITask> & {
    selectionSnapshot?: Partial<RichTextAISelectionSnapshot>;
  } = {},
): RichTextAITask {
  const pageKey = overrides.pageKey ?? 'tenant.docs.detail';
  const editorInstanceId = overrides.editorInstanceId ?? 'editor-1';
  return {
    agentId: 7,
    availableModes: ['plain', 'formatted'],
    conversationId: 88,
    contextTitle: '富文档',
    createdAt: 1000,
    draft: {
      html: '<p>Draft</p>',
      markdown: 'Draft',
      plainText: 'Draft',
    },
    editorInstanceId,
    feature: 'rewrite',
    message: '[Rich Text Task] Rewrite',
    pageKey,
    preferredApplyMode: 'formatted',
    selectionLabel: '待改写段落',
    selectionSnapshot: {
      afterTextExcerpt: 'after',
      beforeTextExcerpt: 'before',
      editorInstanceId,
      editorRevision: 2,
      from: 4,
      pageKey,
      selectedText: '待改写段落',
      to: 12,
      ...overrides.selectionSnapshot,
    },
    state: 'ready',
    summary: '已生成一版草稿',
    taskId: 'rich-text-task-1',
    title: 'AI Rewrite',
    updatedAt: 1000,
    ...overrides,
  };
}

function createRichTextState(
  overrides: Partial<RichTextDraftRuntimeState> = {},
): RichTextDraftRuntimeState {
  return {
    canAppendToEnd: true,
    canCopy: true,
    canInsertAfterSelection: true,
    canReplaceSelection: true,
    canUndo: true,
    helperText: '可以直接应用到原文',
    ...overrides,
  };
}

function createRichTextMessage(
  overrides: Partial<ChatMessage> = {},
): ChatMessage {
  const { clientKey = 'assistant-rich-text-message', ...rest } = overrides;
  return {
    clientKey,
    role: 'assistant',
    content: '这是一段 AI 草稿正文',
    source: 'rich_text_ai',
    richTextAI: createRichTextTask(),
    ...rest,
  };
}

describe('chatMessageItem', () => {
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
    const baseTime = 1_000_000_000_000;
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
    expect(wrapper.text()).toContain(
      'common.globalAiChat.toolStillRunningHint',
    );
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
    expect(wrapper.text()).toContain(
      'common.globalAiChat.pageOpPendingConfirmationHint',
    );
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
    expect(wrapper.text()).toContain(
      'common.globalAiChat.pageOpExecFailedHint',
    );
  });

  it('renders streamed thinking content separately', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-thinking-message',
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
    expect(
      wrapper.get('[data-testid="thinking-body"]').attributes('style'),
    ).toContain('grid-template-rows: 1fr');
  });

  it('renders a compact thinking trigger after streaming completes and expands on demand', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-thinking-finished',
          role: 'assistant',
          content: '最终答复',
          thinkingContent:
            '先检查上下文，再确认用户意图，然后组织更合适的回答结构。',
          streaming: false,
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

    expect(wrapper.text()).toContain('common.globalAiChat.thinkingCollapsed');
    expect(wrapper.text()).toContain(
      '先检查上下文，再确认用户意图，然后组织更合适的回答结构。',
    );
    expect(
      wrapper.get('[data-testid="thinking-body"]').attributes('style'),
    ).toContain('grid-template-rows: 0fr');

    await wrapper.get('[data-testid="thinking-toggle"]').trigger('click');
    await wrapper.vm.$nextTick();

    expect(
      wrapper.get('[data-testid="thinking-body"]').attributes('style'),
    ).toContain('grid-template-rows: 1fr');
  });

  it('renders @ route badge for one-time mention messages', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-mention-message',
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

  it('renders the rich text draft card and re-emits rich text draft actions', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createRichTextMessage({
          richTextAI: createRichTextTask({
            draft: {
              html: '<p>Formatted draft</p>',
              markdown: '**Formatted draft**',
              plainText: 'Plain draft',
            },
          }),
        }),
        index: 4,
        compact: true,
        richTextState: createRichTextState(),
      },
      global: {
        stubs: {
          AgentProfilePopover: true,
          MarkdownRender: true,
          IconifyIcon: true,
          RichTextDraftCard: {
            props: ['compact', 'state', 'task'],
            template: `
              <div data-testid="rich-text-draft-card">
                <span>{{ task.title }}</span>
                <span>{{ state ? state.helperText : '' }}</span>
                <button
                  data-testid="rich-text-apply"
                  @click="$emit('apply', 'replace_selection', 'formatted')"
                />
                <button
                  data-testid="rich-text-copy-plain"
                  @click="$emit('copy', 'plain')"
                />
                <button
                  data-testid="rich-text-copy-formatted"
                  @click="$emit('copy', 'formatted')"
                />
                <button
                  data-testid="rich-text-discard"
                  @click="$emit('discard')"
                />
                <button data-testid="rich-text-undo" @click="$emit('undo')" />
              </div>
            `,
          },
        },
      },
    });

    await wrapper.vm.$nextTick();

    const card = wrapper.get('[data-testid="rich-text-draft-card"]');
    expect(card.text()).toContain('AI Rewrite');
    expect(card.text()).toContain('可以直接应用到原文');

    await wrapper.get('[data-testid="rich-text-apply"]').trigger('click');
    await wrapper.get('[data-testid="rich-text-copy-plain"]').trigger('click');
    await wrapper
      .get('[data-testid="rich-text-copy-formatted"]')
      .trigger('click');
    await wrapper.get('[data-testid="rich-text-discard"]').trigger('click');
    await wrapper.get('[data-testid="rich-text-undo"]').trigger('click');

    expect(wrapper.emitted('richTextApply')?.[0]).toEqual([
      4,
      'replace_selection',
      'formatted',
    ]);
    expect(wrapper.emitted('copy')?.[0]).toEqual(['Plain draft']);
    expect(wrapper.emitted('copy')?.[1]).toEqual(['**Formatted draft**']);
    expect(wrapper.emitted('richTextDiscard')?.[0]).toEqual([4]);
    expect(wrapper.emitted('richTextUndo')?.[0]).toEqual([4]);
  });

  it('hides the rich text draft card once the draft state is discarded', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createRichTextMessage(),
        index: 2,
        compact: true,
        richTextState: createRichTextState({ discarded: true }),
      },
      global: {
        stubs: {
          AgentProfilePopover: true,
          MarkdownRender: true,
          IconifyIcon: true,
          RichTextDraftCard: {
            template: '<div data-testid="rich-text-draft-card" />',
          },
        },
      },
    });

    await wrapper.vm.$nextTick();
    expect(wrapper.find('[data-testid="rich-text-draft-card"]').exists()).toBe(
      false,
    );
  });

  it('renders tool target badges and toggles tool details with animated state', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([
          {
            name: 'query_records',
            status: 'success',
            arguments: {
              question: '统计今天调用情况',
            },
            output: JSON.stringify({
              explanation: '按今天范围统计 AI 调用，并按租户分组。',
              sql: 'SELECT t.name, COUNT(acl.id) AS total_calls FROM ai_call_logs acl JOIN tenants t ON t.id = acl.tenant_id WHERE acl.created_at >= CURRENT_DATE GROUP BY t.name',
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
    expect(details.attributes('style') ?? '').toContain(
      'grid-template-rows: 0fr',
    );

    await wrapper.get('[data-testid="tool-call-toggle-0"]').trigger('click');
    await wrapper.vm.$nextTick();

    expect(details.attributes('style') ?? '').toContain(
      'grid-template-rows: 1fr',
    );
    expect(wrapper.text()).toContain('common.globalAiChat.toolExplanation');
    expect(wrapper.text()).toContain('按今天范围统计 AI 调用，并按租户分组。');
    expect(wrapper.text()).toContain('common.globalAiChat.toolSql');

    const sqlCopyButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('common.globalAiChat.copySql'));
    expect(sqlCopyButton).toBeTruthy();
    if (!sqlCopyButton) {
      throw new Error('SQL copy button not found');
    }
    await sqlCopyButton.trigger('click');
    expect(wrapper.emitted('copy')?.[0]).toEqual([
      'SELECT t.name, COUNT(acl.id) AS total_calls FROM ai_call_logs acl JOIN tenants t ON t.id = acl.tenant_id WHERE acl.created_at >= CURRENT_DATE GROUP BY t.name',
    ]);

    expect(wrapper.text()).toContain('common.globalAiChat.rawResult');
  });

  it('renders structured web search results directly from summary payload', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([
          {
            name: 'web_search',
            status: 'success',
            summaryPayload: {
              provider: 'baidu_public',
              status: 'success',
              result_count: 2,
              items: [
                {
                  title: '示例搜索结果一',
                  url: 'https://example.com/result-1',
                  snippet: '第一条摘要内容',
                },
                {
                  title: '示例搜索结果二',
                  url: 'https://example.com/result-2',
                  snippet: '第二条摘要内容',
                },
              ],
            },
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

    const details = wrapper.get('[data-testid="tool-call-details-0"]');
    expect(details.attributes('style') ?? '').toContain(
      'grid-template-rows: 0fr',
    );

    await wrapper.get('[data-testid="tool-call-toggle-0"]').trigger('click');
    await wrapper.vm.$nextTick();

    expect(details.attributes('style') ?? '').toContain(
      'grid-template-rows: 1fr',
    );
    expect(wrapper.text()).toContain('common.globalAiChat.toolSearchResults');
    expect(wrapper.text()).toContain(
      'common.globalAiChat.toolSearchSourceBaidu',
    );
    expect(wrapper.text()).toContain(
      'common.globalAiChat.toolSearchStatusSuccess',
    );
    expect(wrapper.text()).toContain('示例搜索结果一');
    expect(wrapper.text()).toContain('https://example.com/result-1');
    expect(wrapper.text()).toContain('第一条摘要内容');

    const resultButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('示例搜索结果一'));
    expect(resultButton).toBeTruthy();
    if (!resultButton) {
      throw new Error('Search result button not found');
    }
    await resultButton.trigger('click');
    expect(wrapper.emitted('openUrl')?.[0]).toEqual([
      'https://example.com/result-1',
    ]);
  });

  it('tool group card collapses when all tools are completed', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([
          { name: 'web_search', status: 'success' },
          { name: 'fetch_url', status: 'success' },
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
    const body = wrapper.get('[data-testid="tool-group-body"]');
    expect(body.attributes('style') ?? '').toContain('grid-template-rows: 0fr');
  });

  it('tool group card toggles on click', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([{ name: 'web_search', status: 'success' }]),
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

    const body = wrapper.get('[data-testid="tool-group-body"]');
    expect(body.attributes('style') ?? '').toContain('grid-template-rows: 0fr');

    await wrapper.get('[data-testid="tool-group-toggle"]').trigger('click');
    await wrapper.vm.$nextTick();

    expect(body.attributes('style') ?? '').toContain('grid-template-rows: 1fr');

    await wrapper.get('[data-testid="tool-group-toggle"]').trigger('click');
    await wrapper.vm.$nextTick();

    expect(body.attributes('style') ?? '').toContain('grid-template-rows: 0fr');
  });

  it('tool group auto-collapses when streaming ends', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-streaming-tools',
          role: 'assistant' as const,
          content: '',
          streaming: true,
          toolCalls: [{ name: 'web_search', status: 'running' as const }],
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

    const body = wrapper.get('[data-testid="tool-group-body"]');
    expect(body.attributes('style') ?? '').toContain('grid-template-rows: 1fr');

    await wrapper.setProps({
      msg: {
        clientKey: 'assistant-streaming-tools',
        role: 'assistant' as const,
        content: 'Final reply',
        streaming: false,
        toolCalls: [{ name: 'web_search', status: 'success' as const }],
      },
    });
    await wrapper.vm.$nextTick();

    expect(body.attributes('style') ?? '').toContain('grid-template-rows: 0fr');
  });
});
