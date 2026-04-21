// @vitest-environment happy-dom
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
import { defineComponent, ref } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { buildTurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';

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

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-stub"></span>',
  }),
}));

vi.mock('#/utils/request', () => ({
  isDevErrorMode: () => false,
}));

function createAssistantMsg(toolCalls: ChatMessage['toolCalls']): ChatMessage {
  return {
    clientKey: 'assistant-tool-message',
    role: 'assistant',
    content: '',
    toolCalls,
  };
}

function createTurnFlow(
  value: Record<string, unknown>,
): NonNullable<ChatMessage['turnFlow']> {
  return {
    evidence: [],
    ...(value as NonNullable<ChatMessage['turnFlow']>),
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

  it('shows toolWaitingConfirm when ui runtime tool is pending confirmation', async () => {
    pendingPageOpsValue.value = [createPendingOp()];
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([
          { name: 'ui_submit_form', status: 'running' },
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
            name: 'ui_submit_form',
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
            name: 'ui_submit_form',
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
            name: 'ui_submit_form',
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
          { id: 'tc_123', name: 'ui_set_field', status: 'running' },
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

  it('shows toolStatusOk (not error) when ui runtime tool completes successfully', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([
          {
            name: 'ui_get_snapshot',
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
          { id: 'tc_123', name: 'ui_fill_form', status: 'running' },
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
            name: 'ui_submit_form',
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

  it('delays thinking auto-collapse briefly so the close animation is visible', async () => {
    vi.useFakeTimers();
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-thinking-auto-collapse',
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
    await wrapper.setProps({
      msg: {
        clientKey: 'assistant-thinking-auto-collapse',
        role: 'assistant',
        content: '最终答复',
        thinkingContent: '先检查上下文，再决定下一步。',
        streaming: false,
      },
    });
    await wrapper.vm.$nextTick();

    expect(
      wrapper.get('[data-testid="thinking-body"]').attributes('style'),
    ).toContain('grid-template-rows: 1fr');

    vi.advanceTimersByTime(220);
    await wrapper.vm.$nextTick();

    expect(
      wrapper.get('[data-testid="thinking-body"]').attributes('style'),
    ).toContain('grid-template-rows: 0fr');
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
              selected_backend: 'public:baidu',
              provider_chain: ['native:provider_1:gpt-5.4', 'public:baidu'],
              fallback_reason:
                'native_not_attempted:default_verified_target_unavailable:untrusted_openai_compatible_runtime_target:api.asxs.top',
              native_failure_kind: 'unsupported',
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
    expect(wrapper.text()).toContain('common.globalAiChat.toolSearchBackend');
    expect(wrapper.text()).toContain('public:baidu');
    expect(wrapper.text()).toContain(
      'common.globalAiChat.toolSearchProviderChain',
    );
    expect(wrapper.text()).toContain(
      'native:provider_1:gpt-5.4 -> public:baidu',
    );
    expect(wrapper.text()).toContain(
      'common.globalAiChat.toolSearchFallbackReason',
    );
    expect(wrapper.text()).toContain(
      'common.globalAiChat.toolSearchFallbackNeedVerifiedNativeTarget',
    );
    expect(wrapper.text()).toContain(
      'native_not_attempted:default_verified_target_unavailable:untrusted_openai_compatible_runtime_target:api.asxs.top',
    );
    expect(wrapper.text()).toContain(
      'common.globalAiChat.toolSearchNativeFailure',
    );
    expect(wrapper.text()).toContain('unsupported');
    expect(wrapper.text()).toContain('示例搜索结果一');
    expect(wrapper.text()).not.toContain('https://example.com/result-1');
    expect(wrapper.text()).toContain('第一条摘要内容');

    const resultLink = wrapper.get(
      '[data-testid="tool-search-result-link-0-0"]',
    );
    expect(resultLink.attributes('href')).toBe('https://example.com/result-1');
    expect(resultLink.attributes('target')).toBe('_blank');
    expect(resultLink.attributes('rel')).toBe('noopener noreferrer');
    expect(resultLink.text()).toContain('示例搜索结果一');
    expect(resultLink.text()).not.toContain('https://example.com/result-1');
  });

  it('does not display a fake zero result count for native search summaries without counts', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: createAssistantMsg([
          {
            name: 'native_web_search',
            status: 'success',
            summaryPayload: {
              provider: 'native_hosted',
              status: 'success',
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
    await wrapper.get('[data-testid="tool-call-toggle-0"]').trigger('click');
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain(
      'common.globalAiChat.toolSearchSourceNative',
    );
    expect(wrapper.text()).toContain(
      'common.globalAiChat.toolSearchStatusSuccess',
    );
    expect(
      wrapper.find('[data-testid="tool-search-result-count"]').exists(),
    ).toBe(false);
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

  it('renders turn timeline and answer evidence card from turnFlow payload', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-turn-flow-payload',
          role: 'assistant',
          content: '最终答案',
          turnFlow: createTurnFlow({
            timeline: [
              {
                id: 'stage-tool-selection',
                type: 'tool_selection',
                status: 'skipped',
                summary: '15 个工具中筛选了 0 个',
              },
              {
                id: 'stage-answer',
                type: 'answer_assembly',
                status: 'completed',
                summary: '已完成答案整理',
              },
            ],
            evidence: [
              {
                id: 'evidence-web-1',
                kind: 'web',
                title: '示例来源',
                url: 'https://example.com/ref',
              },
            ],
            answerCard: {
              summary: '已按可验证来源整理结论',
              sections: [
                {
                  title: '核心结论',
                  body: '这是结构化结论摘要',
                },
              ],
              sourceChipIds: ['evidence-web-1'],
            },
          }),
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

    expect(
      wrapper.find('[data-testid="chat-message-kernel-timeline"]').exists(),
    ).toBe(true);
    expect(
      wrapper.find('[data-testid="chat-message-kernel-evidence"]').exists(),
    ).toBe(true);
    expect(wrapper.text()).toContain('15 个工具中筛选了 0 个');
    expect(wrapper.text()).toContain('已按可验证来源整理结论');
    expect(wrapper.text()).not.toContain('https://example.com/ref');

    const evidenceLink = wrapper.get(
      '[data-testid="chat-message-kernel-evidence"] a',
    );
    expect(evidenceLink.attributes('href')).toBe('https://example.com/ref');
    expect(evidenceLink.text()).toContain('示例来源');
    expect(evidenceLink.text()).not.toContain('https://example.com/ref');
  });

  it('extracts and deduplicates answer evidence chips by source ids in shared message ui', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-turn-flow-evidence-dedupe',
          role: 'assistant',
          content: '最终答案',
          turnFlow: createTurnFlow({
            timeline: [
              {
                id: 'stage-answer',
                type: 'answer_assembly',
                status: 'completed',
                summary: '已完成答案整理',
              },
            ],
            evidence: [
              {
                id: 'evidence-web-1',
                kind: 'web',
                title: '来源一',
                url: 'https://example.com/ref-1',
              },
              {
                id: 'evidence-web-2',
                kind: 'web',
                title: '来源二',
                url: 'https://example.com/ref-2',
              },
            ],
            answerCard: {
              summary: '按证据卡片输出',
              sourceChipIds: [
                'evidence-web-2',
                'evidence-web-2',
                'missing-id',
                'evidence-web-1',
              ],
            },
          }),
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

    const evidenceLinks = wrapper
      .get('[data-testid="chat-message-kernel-evidence"]')
      .findAll('a');
    expect(evidenceLinks.length).toBeGreaterThanOrEqual(2);
    expect(
      evidenceLinks.map((link) => link.get('.min-w-0.truncate').text()),
    ).toEqual(expect.arrayContaining(['来源一', '来源二']));
  });

  it('uses compact evidence pill fallback labels when evidence title is a raw URL', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-turn-flow-evidence-url-fallback',
          role: 'assistant',
          content: '最终答案',
          turnFlow: createTurnFlow({
            timeline: [
              {
                id: 'stage-answer',
                type: 'answer_assembly',
                status: 'completed',
                summary: '已完成答案整理',
              },
            ],
            evidence: [
              {
                id: 'evidence-web-url-only',
                kind: 'web',
                title: 'https://news.example.com/path/to/source',
                url: 'https://news.example.com/path/to/source',
              },
            ],
            answerCard: {
              sourceChipIds: ['evidence-web-url-only'],
              summary: '按证据来源输出',
            },
          }),
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

    const evidenceLink = wrapper.get(
      '[data-testid="chat-message-kernel-evidence"] a',
    );
    expect(evidenceLink.attributes('href')).toBe(
      'https://news.example.com/path/to/source',
    );
    const labelText = evidenceLink.get('.min-w-0.truncate').text();
    expect(labelText).toContain('news.example.com');
    expect(labelText).not.toContain('https://news.example.com/path/to/source');
  });

  it('extracts trailing source blocks from content into evidence pills without repeating raw urls in the message body', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-turn-flow-content-tail-references',
          role: 'assistant',
          content: `这是整理后的结论。

来源：
- 官方公告：https://example.com/path/to/policy`,
          turnFlow: createTurnFlow({
            timeline: [
              {
                id: 'stage-answer',
                type: 'answer_assembly',
                status: 'completed',
                summary: '已完成答案整理',
              },
            ],
          }),
        },
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          AgentProfilePopover: true,
          MarkdownRender: {
            props: ['content'],
            template: '<div data-testid="markdown-body">{{ content }}</div>',
          },
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();

    expect(wrapper.get('[data-testid="markdown-body"]').text()).toContain(
      '这是整理后的结论。',
    );
    expect(wrapper.get('[data-testid="markdown-body"]').text()).not.toContain(
      'https://example.com/path/to/policy',
    );

    const evidenceLink = wrapper.get(
      '[data-testid="chat-message-kernel-evidence"] a',
    );
    expect(evidenceLink.attributes('href')).toBe(
      'https://example.com/path/to/policy',
    );
    expect(evidenceLink.text()).toContain('官方公告');
    expect(evidenceLink.text()).not.toContain(
      'https://example.com/path/to/policy',
    );
  });

  it('prefers canonical thinking summaries and suppresses raw thinking detail dumps', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-turn-flow-thinking-summary',
          role: 'assistant',
          content: '',
          turnFlow: createTurnFlow({
            timeline: [
              {
                id: 'stage-thinking',
                type: 'thinking',
                status: 'completed',
                summary: '已完成思考摘要',
                detailLines: [
                  'Raw private reasoning should not render as primary UX.',
                ],
              },
            ],
          }),
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

    expect(wrapper.text()).toContain('已完成思考摘要');
    expect(wrapper.text()).not.toContain(
      'Raw private reasoning should not render as primary UX.',
    );
  });

  it('accepts answer card sections using content field from backend turn_flow', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-turn-flow-answer-content',
          role: 'assistant',
          content: '最终答案',
          turnFlow: createTurnFlow({
            timeline: [
              {
                id: 'stage-answer',
                type: 'answer_assembly',
                status: 'completed',
              },
            ],
            answerCard: {
              summary: '结构化结论',
              sections: [
                {
                  title: '政策要点',
                  content: '后端返回的是 content 字段',
                },
              ],
            },
          }),
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

    expect(
      wrapper.find('[data-testid="chat-message-kernel-evidence"]').exists(),
    ).toBe(true);
    expect(wrapper.text()).toContain('政策要点');
    expect(wrapper.text()).toContain('后端返回的是 content 字段');
  });

  it('shows a provisional answer evidence card while answer_assembly is still streaming', async () => {
    const liveMessage: ChatMessage = {
      clientKey: 'assistant-turn-flow-provisional-answer-card',
      role: 'assistant',
      content: '',
      streaming: true,
      turnFlow: createTurnFlow({
        timeline: [
          {
            id: 'stage-answer',
            type: 'answer_assembly',
            status: 'running',
            summary: '正在整理本轮结果',
            detailLines: ['提炼核心结论', '补充执行建议'],
          },
        ],
      }),
    };
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: liveMessage,
        kernelState: buildTurnFlowState(liveMessage),
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

    expect(
      wrapper.find('[data-testid="chat-message-kernel-evidence"]').exists(),
    ).toBe(true);
    expect(
      wrapper
        .find('[data-testid="chat-message-kernel-evidence-live-state"]')
        .exists(),
    ).toBe(true);
    expect(wrapper.text()).toContain('正在整理本轮结果');
    expect(wrapper.text()).toContain('提炼核心结论');
    expect(wrapper.text()).toContain('补充执行建议');

    const settledMessage: ChatMessage = {
      clientKey: 'assistant-turn-flow-provisional-answer-card',
      role: 'assistant',
      content: '最终答案',
      streaming: false,
      turnFlow: createTurnFlow({
        timeline: [
          {
            id: 'stage-answer',
            type: 'answer_assembly',
            status: 'completed',
            summary: '已完成答案整理',
            detailLines: ['提炼核心结论', '补充执行建议'],
          },
        ],
      }),
    };
    await wrapper.setProps({
      msg: settledMessage,
      kernelState: buildTurnFlowState(settledMessage),
    });
    await wrapper.vm.$nextTick();

    expect(
      wrapper.find('[data-testid="chat-message-kernel-evidence"]').exists(),
    ).toBe(true);
    expect(wrapper.text()).toContain('已完成答案整理');

    const canonicalMessage: ChatMessage = {
      clientKey: 'assistant-turn-flow-provisional-answer-card',
      role: 'assistant',
      content: '最终答案',
      streaming: false,
      turnFlow: createTurnFlow({
        timeline: [
          {
            id: 'stage-answer',
            type: 'answer_assembly',
            status: 'completed',
            summary: '已完成答案整理',
          },
        ],
        answerCard: {
          summary: '这是正式 answerCard 摘要',
          sections: [
            {
              title: '结果整理',
              body: '这是正式结构化整理内容',
            },
          ],
        },
      }),
    };
    await wrapper.setProps({
      msg: canonicalMessage,
      kernelState: buildTurnFlowState(canonicalMessage),
    });
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain('这是正式 answerCard 摘要');
    expect(wrapper.text()).toContain('这是正式结构化整理内容');
    expect(
      wrapper
        .find('[data-testid="chat-message-kernel-evidence-live-state"]')
        .exists(),
    ).toBe(false);
  });

  it('normalizes partial-failed terminal turnFlow stages into failed + error semantics', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-turn-flow-partial-failed',
          role: 'assistant',
          content: '',
          turnFlow: createTurnFlow({
            completionReason: 'provider_failure_after_partial_progress',
            error_surface: {
              message: 'Provider failed after partial progress.',
            },
            failure_kind: 'provider_failure_after_partial_progress',
            timeline: [
              {
                id: 'stage-answer',
                type: 'answer_assembly',
                status: 'completed',
                summary: '已完成答案整理',
              },
              {
                id: 'stage-terminal',
                type: 'completed',
                status: 'completed',
                summary: '本轮流程已完成',
              },
            ],
            turn_outcome: 'partial',
          }),
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

    expect(wrapper.text()).toContain(
      'common.globalAiChat.turnStageType.failed',
    );
    expect(wrapper.text()).toContain(
      'common.globalAiChat.turnStageStatus.error',
    );
    expect(wrapper.text()).not.toContain(
      'common.globalAiChat.turnStageStatus.completed',
    );
    expect(wrapper.text()).toContain('Provider failed after partial progress.');
  });

  it('does not backfill a skipped tool-selection record from legacy optimizingTools when turnFlow exists', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-turn-flow-skipped-selection-supplement',
          role: 'assistant',
          content: '',
          optimizingTools: {
            selected: 0,
            total: 12,
          },
          turnFlow: createTurnFlow({
            timeline: [
              {
                id: 'stage-thinking',
                type: 'thinking',
                status: 'completed',
                summary: '已完成思考摘要',
              },
              {
                id: 'stage-answer',
                type: 'answer_assembly',
                status: 'completed',
                summary: '正在组织回复',
              },
            ],
          }),
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

    expect(wrapper.text()).not.toContain('common.globalAiChat.optimizingTools');
    expect(wrapper.text()).not.toContain(
      'common.globalAiChat.turnStageStatus.skipped',
    );
  });

  it('forwards skipped stage transitions into the kernel timeline when stage has body content', async () => {
    vi.useFakeTimers();
    const initialMessage: ChatMessage = {
      clientKey: 'assistant-turn-flow-skipped',
      role: 'assistant',
      content: '',
      streaming: true,
      turnFlow: createTurnFlow({
        timeline: [
          {
            id: 'stage-tool-selection',
            type: 'tool_selection',
            status: 'running',
            summary: '正在筛选工具',
            detailLines: ['正在筛选候选工具'],
          },
        ],
      }),
    };
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: initialMessage,
        kernelState: buildTurnFlowState(initialMessage),
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

    expect(
      wrapper.get('[data-testid="turn-stage-body-0"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 1fr');

    const nextMessage: ChatMessage = {
      clientKey: 'assistant-turn-flow-skipped',
      role: 'assistant',
      content: '',
      streaming: false,
      turnFlow: createTurnFlow({
        timeline: [
          {
            id: 'stage-tool-selection',
            type: 'tool_selection',
            status: 'skipped',
            summary: '15 个工具中筛选了 0 个',
            detailLines: ['本轮无需调用工具，直接进入答案整理'],
          },
        ],
      }),
    };
    await wrapper.setProps({
      msg: nextMessage,
      kernelState: buildTurnFlowState(nextMessage),
    });
    await wrapper.vm.$nextTick();

    expect(
      wrapper.get('[data-testid="turn-stage-body-0"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 1fr');

    expect(wrapper.text()).toContain('15 个工具中筛选了 0 个');
  });

  it('forwards answer_assembly transitions into the kernel timeline when stage has body content', async () => {
    vi.useFakeTimers();
    const initialMessage: ChatMessage = {
      clientKey: 'assistant-turn-flow-answer-assembly-collapse-delay',
      role: 'assistant',
      content: '',
      streaming: true,
      turnFlow: createTurnFlow({
        timeline: [
          {
            id: 'stage-answer',
            type: 'answer_assembly',
            status: 'running',
            summary: '正在组织答案',
            detailLines: ['正在根据检索结果整理答案结构'],
          },
        ],
      }),
    };
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: initialMessage,
        kernelState: buildTurnFlowState(initialMessage),
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

    expect(
      wrapper.get('[data-testid="turn-stage-body-0"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 1fr');

    const nextMessage: ChatMessage = {
      clientKey: 'assistant-turn-flow-answer-assembly-collapse-delay',
      role: 'assistant',
      content: '最终答案',
      streaming: false,
      turnFlow: createTurnFlow({
        timeline: [
          {
            id: 'stage-answer',
            type: 'answer_assembly',
            status: 'completed',
            summary: '已完成答案整理',
            detailLines: ['已完成段落组织与措辞润色'],
          },
          {
            id: 'stage-terminal',
            type: 'completed',
            status: 'completed',
            summary: '本轮完成',
          },
        ],
      }),
    };
    await wrapper.setProps({
      msg: nextMessage,
      kernelState: buildTurnFlowState(nextMessage),
    });
    await wrapper.vm.$nextTick();

    expect(
      wrapper.get('[data-testid="turn-stage-body-0"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 1fr');

    expect(wrapper.text()).toContain('已完成答案整理');

    vi.advanceTimersByTime(220);
    await wrapper.vm.$nextTick();

    expect(
      wrapper.get('[data-testid="turn-stage-body-0"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 0fr');
  });

  it('keeps interrupted terminal stages compact when the kernel timeline rerenders through ChatMessageItem', async () => {
    vi.useFakeTimers();
    const initialMessage: ChatMessage = {
      clientKey: 'assistant-turn-flow-interrupted-terminal-expanded',
      role: 'assistant',
      content: '',
      streaming: true,
      turnFlow: createTurnFlow({
        timeline: [
          {
            id: 'stage-answer',
            type: 'answer_assembly',
            status: 'running',
            summary: '正在组织答案',
            detailLines: ['正在生成最终答复草稿'],
          },
        ],
      }),
    };
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: initialMessage,
        kernelState: buildTurnFlowState(initialMessage),
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

    const nextMessage: ChatMessage = {
      clientKey: 'assistant-turn-flow-interrupted-terminal-expanded',
      role: 'assistant',
      content: '部分答案',
      streaming: false,
      turnFlow: createTurnFlow({
        timeline: [
          {
            id: 'stage-answer',
            type: 'answer_assembly',
            status: 'interrupted',
            summary: '答复生成中断',
            detailLines: ['模型输出在中途被中断'],
          },
          {
            id: 'stage-terminal',
            type: 'failed',
            status: 'interrupted',
            summary: 'interrupted',
            detailLines: ['用户主动停止了本轮生成'],
          },
        ],
      }),
    };
    await wrapper.setProps({
      msg: nextMessage,
      kernelState: buildTurnFlowState(nextMessage),
    });
    await wrapper.vm.$nextTick();

    expect(
      wrapper.get('[data-testid="turn-stage-body-0"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 1fr');

    expect(
      wrapper.get('[data-testid="turn-stage-body-1"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 0fr');

    expect(wrapper.text()).toContain('答复生成中断');
  });

  it('eliminates stale running badges when non-streaming turnFlow already has terminal hints', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-turn-flow-non-streaming-terminal-hints',
          role: 'assistant',
          content: '最终答案',
          streaming: false,
          turnFlow: createTurnFlow({
            timeline: [
              {
                id: 'stage-tool-execution',
                type: 'tool_execution',
                status: 'running',
                summary: '工具还在运行',
                detailLines: ['旧状态残留：running'],
              },
              {
                id: 'stage-answer',
                type: 'answer_assembly',
                status: 'completed',
                summary: '已完成答案整理',
              },
            ],
          }),
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

    const firstStageToggle = wrapper.get('[data-testid="turn-stage-toggle-0"]');
    expect(firstStageToggle.text()).toContain(
      'common.globalAiChat.turnStageStatus.completed',
    );
    expect(firstStageToggle.text()).not.toContain(
      'common.globalAiChat.turnStageStatus.running',
    );
  });

  it('shows meaningful live progress copy for canonical running stages without raw detail lines', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-turn-flow-live-progress-1216',
          role: 'assistant',
          content: '',
          streaming: true,
          turnFlow: createTurnFlow({
            timeline: [
              {
                id: 'stage-tool-execution',
                type: 'tool_execution',
                status: 'running',
                metrics: {
                  provider: 'native:provider_1:gpt-5.4',
                },
              },
              {
                id: 'stage-retrieval',
                type: 'retrieval',
                status: 'running',
                metrics: {
                  source_count: 2,
                },
              },
            ],
          }),
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

    expect(wrapper.text()).toContain('common.globalAiChat.toolSearchProvider');
    expect(wrapper.text()).toContain('native:provider_1:gpt-5.4');
    expect(wrapper.text()).toContain(
      'common.globalAiChat.turnRetrievalSummary',
    );
    expect(
      wrapper.get('[data-testid="turn-stage-body-0"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 1fr');
  });

  it('keeps single-stage completed answer_assembly collapsed in completed history', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-turn-flow-answer-only-history',
          role: 'assistant',
          content: '最终答案',
          turnFlow: createTurnFlow({
            timeline: [
              {
                id: 'stage-answer',
                type: 'answer_assembly',
                status: 'completed',
                summary: '已完成答案整理',
              },
            ],
          }),
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

    expect(
      wrapper.get('[data-testid="turn-stage-body-0"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 0fr');
  });

  it('keeps historical answer_assembly stages compact by default after completion', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-turn-flow-answer-assembly-history-collapsed',
          role: 'assistant',
          content: '最终答案',
          turnFlow: createTurnFlow({
            timeline: [
              {
                id: 'stage-thinking',
                type: 'thinking',
                status: 'completed',
                summary: '已完成思考',
              },
              {
                id: 'stage-answer',
                type: 'answer_assembly',
                status: 'completed',
                summary: '已完成答案整理',
              },
              {
                id: 'stage-terminal',
                type: 'completed',
                status: 'completed',
                summary: '本轮完成',
              },
            ],
          }),
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

    expect(
      wrapper.get('[data-testid="turn-stage-body-1"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 0fr');
  });

  it('keeps skipped-only tool-selection stages compact when loading completed history', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-turn-flow-skipped-history',
          role: 'assistant',
          content: '',
          turnFlow: createTurnFlow({
            timeline: [
              {
                id: 'stage-tool-selection',
                type: 'tool_selection',
                status: 'skipped',
                summary: '15 个工具中筛选了 0 个',
              },
            ],
          }),
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

    expect(
      wrapper.get('[data-testid="turn-stage-body-0"]').attributes('style') ??
        '',
    ).toContain('grid-template-rows: 0fr');
  });

  it('does not synthesize a turn timeline from legacy thinking/tool/rag fields when turnFlow is missing', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-legacy-fallback',
          role: 'assistant',
          content: '最终答复',
          thinkingContent: '先做分析，再给答案。',
          optimizingTools: { selected: 0, total: 15 },
          toolCalls: [{ name: 'web_search', status: 'success' }],
          ragSources: [
            {
              doc_name: '来源文档',
              doc_id: 1,
              score: 0.92,
              snippet: '来源摘要',
            },
          ],
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

    expect(
      wrapper.find('[data-testid="chat-message-kernel-timeline"]').exists(),
    ).toBe(false);
    expect(wrapper.text()).toContain('common.globalAiChat.optimizingTools');
    expect(wrapper.text()).toContain('common.globalAiChat.ragSources');
  });

  it('prefers prepared content body over raw content in the shared content block', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-prepared-content-body',
          role: 'assistant' as const,
          content: 'raw content from persistence',
          metadata: {
            prepared_content_body: 'prepared display content',
          },
          preparedContentBody: 'prepared display content',
          prepared_content_body: 'prepared display content',
        } as ChatMessage & {
          metadata: { prepared_content_body: string };
          prepared_content_body: string;
          preparedContentBody: string;
        },
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          AgentProfilePopover: true,
          MarkdownRender: {
            props: ['content'],
            template:
              '<div data-testid="markdown-render-content">{{ content }}</div>',
          },
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();

    const renderedMarkdownBlocks = wrapper.findAll(
      '[data-testid="markdown-render-content"]',
    );
    expect(
      renderedMarkdownBlocks.some((block) =>
        block.text().includes('prepared display content'),
      ),
    ).toBe(true);
  });

  it('hides persisted body text when the turn failed with untrusted final output', async () => {
    const leakedSnippet = 'Fetched reddit.json leaked snippet';
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-untrusted-final-output-history',
          role: 'assistant' as const,
          content: leakedSnippet,
          turnFlow: createTurnFlow({
            completion_reason: 'completed',
            error_surface: {
              error_type: 'untrusted_final_output_source',
              message: '这些来源被系统中断了，请稍后再试。',
            },
            final_stage_status: 'error',
            timeline: [
              {
                id: 'stage-answer',
                type: 'answer_assembly',
                status: 'error',
                summary: '答复生成失败',
              },
              {
                id: 'stage-terminal',
                type: 'failed',
                status: 'error',
                summary: 'completed',
              },
            ],
          }),
        },
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          AgentProfilePopover: true,
          MarkdownRender: {
            props: ['content'],
            template:
              '<div data-testid="markdown-render-content">{{ content }}</div>',
          },
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();

    const renderedMarkdownBlocks = wrapper.findAll(
      '[data-testid="markdown-render-content"]',
    );
    expect(
      renderedMarkdownBlocks.some((block) =>
        block.text().includes(leakedSnippet),
      ),
    ).toBe(false);
    expect(wrapper.text()).not.toContain(leakedSnippet);
  });

  it('shows a folded-message hint for very long replies', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-long-message',
          role: 'assistant' as const,
          content: '很长的内容'.repeat(500),
          streaming: false,
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

    expect(wrapper.get('[data-testid="collapsed-message-hint"]').text()).toBe(
      'common.globalAiChat.collapsedMessageHint',
    );
  });
});
