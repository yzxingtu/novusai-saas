// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: assistant chat messages render canonical turnFlow process UX,
// inline thinking/tool content, and final-answer transitions without stale process artifacts.
import type {
  AgentItem,
  ChatMessage,
  RichTextAISelectionSnapshot,
  RichTextAITask,
  RichTextDraftRuntimeState,
  ToolCallEvent,
} from '../types';

/**
 * ChatMessageItem component tests: waiting_confirm, executing, 8s hint, error_type mapping.
 * ChatMessageItem 组件测试：待确认、执行中、8s 提示、error_type 映射。
 */
import { mount } from '@vue/test-utils';
import { defineComponent, ref } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { buildTurnFlowState } from '#/components/business/ai-chat-kernel/TurnFlowState';

import ChatMessageFooter from '../ChatMessageFooter.vue';
import ChatMessageItem from '../ChatMessageItem.vue';
import ChatMessageThinkingBlock from '../ChatMessageThinkingBlock.vue';
import ChatMessageToolCalls from '../ChatMessageToolCalls.vue';

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

const PopoverContentStub = defineComponent({
  name: 'PopoverContentStub',
  template:
    '<div><div data-testid="agent-profile-popover-content"><slot name="content" /></div><slot /></div>',
});

function createAssistantMsg(toolCalls: ToolCallEvent[] = []): ChatMessage {
  const completedCount = toolCalls.filter(
    (toolCall) => toolCall.status === 'success',
  ).length;
  const failedCount = toolCalls.filter(
    (toolCall) => toolCall.status === 'error',
  ).length;
  const runningCount = toolCalls.filter(
    (toolCall) => toolCall.status === 'running',
  ).length;
  let stageStatus: 'completed' | 'error' | 'running' = 'completed';
  if (runningCount > 0) {
    stageStatus = 'running';
  } else if (failedCount > 0) {
    stageStatus = 'error';
  }
  const turnFlow =
    toolCalls.length > 0
      ? createTurnFlow({
          evidence: toolCalls.map((toolCall, index) => ({
            id: toolCall.id ?? `tool-${index + 1}`,
            kind: 'tool',
            ...(toolCall.arguments ? { arguments: toolCall.arguments } : {}),
            ...(toolCall.displayName
              ? { displayName: toolCall.displayName }
              : {}),
            ...(toolCall.durationMs === undefined
              ? {}
              : { durationMs: toolCall.durationMs }),
            ...(toolCall.error ? { error: toolCall.error } : {}),
            ...(toolCall.errorType ? { errorType: toolCall.errorType } : {}),
            ...(toolCall.output ? { output: toolCall.output } : {}),
            ...(toolCall.resultLink ? { resultLink: toolCall.resultLink } : {}),
            ...(toolCall.skillName ? { skillName: toolCall.skillName } : {}),
            ...(toolCall.skillType ? { skillType: toolCall.skillType } : {}),
            ...(toolCall.startedAt === undefined
              ? {}
              : { startedAt: toolCall.startedAt }),
            status: toolCall.status,
            ...(toolCall.summary ? { snippet: toolCall.summary } : {}),
            ...(toolCall.summaryPayload
              ? { summaryPayload: toolCall.summaryPayload }
              : {}),
            ...(toolCall.id ? { toolCallId: toolCall.id } : {}),
            sourceRef: toolCall.name,
            toolName: toolCall.name,
            ...(toolCall.displayName ? { title: toolCall.displayName } : {}),
          })),
          timeline: [
            {
              detailLines: [`执行了 ${toolCalls.length} 个工具调用`],
              id: 'turn-tool-execution',
              metrics: {
                completed: completedCount,
                failed: failedCount,
                running: runningCount,
                tool_call_count: toolCalls.length,
                total: toolCalls.length,
              },
              status: stageStatus,
              summary: `执行了 ${toolCalls.length} 个工具调用`,
              toolCallIds: toolCalls.map(
                (toolCall, index) => toolCall.id ?? `tool-${index + 1}`,
              ),
              type: 'tool_execution',
            },
          ],
        })
      : undefined;
  return {
    clientKey: 'assistant-tool-message',
    role: 'assistant',
    content: '',
    ...(turnFlow ? { turnFlow } : {}),
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

async function expandKernelOverviewIfCollapsed(wrapper: {
  find: (selector: string) => {
    attributes: (name?: string) => Record<string, string> | string | undefined;
    exists: () => boolean;
    trigger: (event: string) => Promise<unknown>;
  };
  vm: { $nextTick: () => Promise<unknown> };
}) {
  const toggle = wrapper.find(
    '[data-testid="chat-message-kernel-overview-toggle"]',
  );
  if (!toggle.exists()) {
    return;
  }
  const expanded = toggle.attributes('aria-expanded');
  if (expanded === 'true') {
    return;
  }
  await toggle.trigger('click');
  await wrapper.vm.$nextTick();
}

async function expandDigestIfCollapsed(wrapper: {
  find: (selector: string) => {
    attributes: (name?: string) => Record<string, string> | string | undefined;
    exists: () => boolean;
    trigger: (event: string) => Promise<unknown>;
  };
  vm: { $nextTick: () => Promise<unknown> };
}) {
  await expandKernelOverviewIfCollapsed(wrapper);
  const toggle = wrapper.find('[data-testid="turn-digest-toggle"]');
  if (!toggle.exists()) {
    return;
  }
  await toggle.trigger('click');
  await wrapper.vm.$nextTick();
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
    await expandKernelOverviewIfCollapsed(wrapper);
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
    await expandKernelOverviewIfCollapsed(wrapper);
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
    await expandKernelOverviewIfCollapsed(wrapper);
    expect(wrapper.text()).toContain(
      'common.globalAiChat.pageOpExecFailedHint',
    );
  });

  it('renders streamed thinking content inline inside the turn transcript', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-thinking-message',
          role: 'assistant',
          content: '',
          turnFlow: createTurnFlow({
            timeline: [
              {
                detailLines: ['先检查上下文，再决定下一步。'],
                id: 'stage-thinking',
                status: 'running',
                type: 'thinking',
              },
            ],
          }),
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
    expect(wrapper.find('[data-testid="thinking-toggle"]').exists()).toBe(
      false,
    );
    expect(wrapper.text()).toContain('先检查上下文，再决定下一步。');
  });

  it('renders a compact thinking trigger after streaming completes and expands on demand in default mode', async () => {
    const wrapper = mount(ChatMessageThinkingBlock, {
      props: {
        msg: {
          clientKey: 'assistant-thinking-finished',
          role: 'assistant',
          content: '最终答复',
          turnFlow: createTurnFlow({
            timeline: [
              {
                detailLines: [
                  '先检查上下文，再确认用户意图，然后组织更合适的回答结构。',
                ],
                id: 'stage-thinking',
                status: 'completed',
                type: 'thinking',
              },
            ],
          }),
          streaming: false,
        },
        index: 0,
        compact: true,
        embedded: false,
      },
      global: {
        stubs: {
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

  it('delays thinking auto-collapse briefly so the close animation is visible in default mode', async () => {
    vi.useFakeTimers();
    const wrapper = mount(ChatMessageThinkingBlock, {
      props: {
        msg: {
          clientKey: 'assistant-thinking-auto-collapse',
          role: 'assistant',
          content: '',
          turnFlow: createTurnFlow({
            timeline: [
              {
                detailLines: ['先检查上下文，再决定下一步。'],
                id: 'stage-thinking',
                status: 'running',
                type: 'thinking',
              },
            ],
          }),
          streaming: true,
        },
        index: 0,
        compact: true,
        embedded: false,
      },
      global: {
        stubs: {
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
        turnFlow: createTurnFlow({
          timeline: [
            {
              detailLines: ['先检查上下文，再决定下一步。'],
              id: 'stage-thinking',
              status: 'completed',
              type: 'thinking',
            },
          ],
        }),
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

  it('renders embedded thinking content inline without nested toggle chrome', async () => {
    const wrapper = mount(ChatMessageThinkingBlock, {
      props: {
        msg: {
          clientKey: 'assistant-thinking-embedded',
          role: 'assistant',
          content: '',
          turnFlow: createTurnFlow({
            timeline: [
              {
                detailLines: ['先检查上下文，再决定下一步。'],
                id: 'stage-thinking-embedded',
                status: 'completed',
                type: 'thinking',
              },
            ],
          }),
        },
        index: 0,
        compact: true,
        embedded: true,
      },
      global: {
        stubs: {
          MarkdownRender: {
            props: ['content'],
            template: '<div>{{ content }}</div>',
          },
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();

    expect(wrapper.find('[data-testid="thinking-toggle"]').exists()).toBe(
      false,
    );
    expect(wrapper.find('[data-testid="thinking-body"]').exists()).toBe(false);
    expect(
      wrapper.get('[data-testid="thinking-embedded-body"]').classes(),
    ).toContain('thinking-inline-body');
    expect(
      wrapper.get('[data-testid="thinking-embedded-body"]').text(),
    ).toContain('先检查上下文，再决定下一步。');
  });

  it('keeps one-time mention messages transcript-first without a prominent agent badge', async () => {
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
    expect(wrapper.find('.assistant-message-surface').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('@ 猫娘智能体');
  });

  it('renders the assistant avatar rail with a profile trigger resolved from message agent fields', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-avatar-profile',
          role: 'assistant',
          content: '已经整理好了答案。',
          agent_id: 2,
          agent_avatar: '/uploads/avatars/cat-agent.png',
          agent_name: '猫娘智能体',
          agent_description: '负责轻量问答与页面操作。',
          model_name: 'gpt-5.4-mini',
        },
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          MarkdownRender: true,
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();

    const avatar = wrapper.get('[data-testid="assistant-agent-avatar"]');
    expect(wrapper.find('.assistant-avatar-rail').exists()).toBe(true);
    expect(avatar.find('img').exists()).toBe(true);
    expect(avatar.attributes('aria-label')).toContain(
      'common.globalAiChat.agentProfileAria',
    );
  });

  it('renders bound skill packages, skill entries, and knowledge-base chips in the assistant avatar profile popover', async () => {
    const agents: AgentItem[] = [
      {
        id: 2,
        tenant_id: 1,
        name: '猫娘智能体',
        description: '负责轻量问答与页面操作。',
        avatar: null,
        status: 'published',
        model_name: 'gpt-5.4-mini',
        skills: [
          {
            id: 10,
            name: '页面点击',
            package_id: 100,
            package_name: '页面工具包',
          },
          {
            id: 11,
            name: '表单填写',
            package_id: 100,
            package_name: '页面工具包',
          },
          {
            id: 12,
            name: '知识检索',
            package_name: '检索工具包',
          },
        ],
        knowledge_bases: [
          {
            id: 30,
            knowledge_base_id: 30,
            kb_name: '产品知识库',
          },
        ],
      },
    ];

    const wrapper = mount(ChatMessageItem, {
      props: {
        agents,
        msg: {
          clientKey: 'assistant-avatar-profile-bindings',
          role: 'assistant',
          content: '已经整理好了答案。',
          agent_id: 2,
        },
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          IconifyIcon: true,
          MarkdownRender: true,
          APopover: PopoverContentStub,
          Popover: PopoverContentStub,
        },
      },
    });

    await wrapper.vm.$nextTick();

    expect(
      wrapper.get('[data-testid="agent-profile-model-chip"]').text(),
    ).toContain('gpt-5.4-mini');
    expect(
      wrapper.get('[data-testid="agent-profile-popover-content"]').text(),
    ).toContain('猫娘智能体');
    expect(
      wrapper.get('[data-testid="agent-profile-description"]').text(),
    ).toContain('负责轻量问答与页面操作。');
    expect(
      wrapper
        .findAll('[data-testid="agent-profile-skill-package-chip"]')
        .map((chip) => chip.text()),
    ).toEqual(['页面工具包', '检索工具包']);
    expect(
      wrapper
        .findAll('[data-testid="agent-profile-skill-entry-chip"]')
        .map((chip) => chip.text()),
    ).toEqual(['页面点击', '表单填写', '知识检索']);
    expect(
      wrapper
        .findAll('[data-testid="agent-profile-kb-chip"]')
        .map((chip) => chip.text()),
    ).toEqual(['产品知识库']);
    expect(wrapper.get('.assistant-message-surface').text()).not.toContain(
      '猫娘智能体',
    );
  });

  it('renders i18n empty states when the assistant avatar profile has no bound skills or knowledge bases', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        selectedAgent: {
          id: 7,
          tenant_id: 1,
          name: '空配置智能体',
          description: null,
          avatar: null,
          status: 'published',
          skills: [],
          knowledge_bases: [],
          knowledge_base_ids: [],
        },
        msg: {
          clientKey: 'assistant-avatar-profile-empty-bindings',
          role: 'assistant',
          content: '暂无绑定。',
          agent_id: 7,
        },
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          IconifyIcon: true,
          MarkdownRender: true,
          APopover: PopoverContentStub,
          Popover: PopoverContentStub,
        },
      },
    });

    await wrapper.vm.$nextTick();

    expect(
      wrapper.get('[data-testid="agent-profile-skill-empty"]').text(),
    ).toBe('common.globalAiChat.noSkillPackages');
    expect(
      wrapper.get('[data-testid="agent-profile-skill-entry-empty"]').text(),
    ).toBe('common.globalAiChat.noSkillsInPackage');
    expect(wrapper.get('[data-testid="agent-profile-kb-empty"]').text()).toBe(
      'common.globalAiChat.noKnowledgeBases',
    );
  });

  it('renders message-agent knowledge bindings from the shared knowledge-base map even when the selected agent is different', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        selectedAgent: {
          id: 8,
          tenant_id: 1,
          name: '当前选中智能体',
          description: null,
          avatar: null,
          status: 'published',
          skills: [
            {
              id: 10,
              name: '当前技能',
            },
          ],
        },
        agentKnowledgeBases: [
          {
            id: 401,
            knowledge_base_id: 401,
            kb_name: '当前选中知识库',
            enabled: true,
          },
        ],
        agentKnowledgeBaseMap: {
          7: [
            {
              id: 301,
              knowledge_base_id: 301,
              kb_name: '企业制度库',
              enabled: true,
            },
          ],
        },
        msg: {
          clientKey: 'assistant-avatar-profile-current-kb-bindings',
          role: 'assistant',
          content: '已读取知识库。',
          agent_id: 7,
          agent_name: '知识智能体',
        },
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          IconifyIcon: true,
          MarkdownRender: true,
          APopover: PopoverContentStub,
          Popover: PopoverContentStub,
        },
      },
    });

    await wrapper.vm.$nextTick();

    expect(
      wrapper
        .findAll('[data-testid="agent-profile-kb-chip"]')
        .map((chip) => chip.text()),
    ).toEqual(['企业制度库']);
  });

  it('renders message-agent skill bindings from the shared skill map even when the selected agent is different', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        selectedAgent: {
          id: 8,
          tenant_id: 1,
          name: '当前选中智能体',
          description: null,
          avatar: null,
          status: 'published',
          skills: [
            {
              id: 10,
              package_name: '当前技能包',
              skill_id: 110,
              skill_name: '当前技能',
            },
          ],
        },
        agentSkillMap: {
          7: [
            {
              enabled: true,
              id: 301,
              package_name: '历史技能包',
              skill_id: 1301,
              skill_name: '历史技能',
            },
          ],
        },
        msg: {
          clientKey: 'assistant-avatar-profile-current-skill-bindings',
          role: 'assistant',
          content: '已读取技能详情。',
          agent_id: 7,
          agent_name: '技能智能体',
        },
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          IconifyIcon: true,
          MarkdownRender: true,
          APopover: PopoverContentStub,
          Popover: PopoverContentStub,
        },
      },
    });

    await wrapper.vm.$nextTick();

    expect(
      wrapper
        .findAll('[data-testid="agent-profile-skill-package-chip"]')
        .map((chip) => chip.text()),
    ).toEqual(['历史技能包']);
    expect(
      wrapper
        .findAll('[data-testid="agent-profile-skill-entry-chip"]')
        .map((chip) => chip.text()),
    ).toEqual(['历史技能']);
  });

  it('resolves avatar knowledge bases from the message agent map instead of the current selected agent', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        agents: [
          {
            id: 3,
            tenant_id: 1,
            name: '路由智能体',
            description: '历史消息所属智能体',
            avatar: null,
            status: 'published',
            skills: [],
          },
        ],
        selectedAgent: {
          id: 7,
          tenant_id: 1,
          name: '当前选中智能体',
          description: null,
          avatar: null,
          status: 'published',
          skills: [],
        },
        agentKnowledgeBases: [
          {
            id: 701,
            knowledge_base_id: 701,
            kb_name: '当前智能体知识库',
            enabled: true,
          },
        ],
        agentKnowledgeBaseMap: {
          3: [
            {
              id: 301,
              knowledge_base_id: 301,
              kb_name: '历史消息知识库',
              enabled: true,
            },
          ],
        },
        msg: {
          clientKey: 'assistant-avatar-profile-routed-kb-bindings',
          role: 'assistant',
          content: '已按历史消息所属智能体读取知识库。',
          agent_id: 3,
        },
        index: 0,
        compact: true,
      },
      global: {
        stubs: {
          IconifyIcon: true,
          MarkdownRender: true,
          APopover: PopoverContentStub,
          Popover: PopoverContentStub,
        },
      },
    });

    await wrapper.vm.$nextTick();

    expect(
      wrapper
        .findAll('[data-testid="agent-profile-kb-chip"]')
        .map((chip) => chip.text()),
    ).toEqual(['历史消息知识库']);
  });

  it('keeps assistant identity details inside the avatar trigger instead of rendering a visible meta row', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-no-agent-title-row',
          role: 'assistant',
          content: '已经整理好了答案。',
          agent_id: 2,
          agent_name: '猫娘智能体',
          turnFlow: createTurnFlow({
            timeline: [
              {
                id: 'stage-thinking',
                status: 'completed',
                summary: '已完成思考',
                type: 'thinking',
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

    expect(wrapper.text()).toContain('已完成思考');
    expect(wrapper.find('.assistant-message-meta').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('猫娘智能体');
    expect(wrapper.text()).not.toContain('gpt-5.4-xhigh');
  });

  it('keeps the compact assistant footer minimal by hiding usage stats', async () => {
    const wrapper = mount(ChatMessageFooter, {
      props: {
        compact: true,
        index: 0,
        msg: {
          clientKey: 'assistant-compact-footer',
          role: 'assistant',
          content: '最终答复',
          created_at: '2026-04-24T10:00:00Z',
          durationMs: 5230,
          tokenUsage: 128,
        } as ChatMessage,
      },
      global: {
        stubs: {
          ATooltip: defineComponent({
            name: 'ATooltipStub',
            template: '<div><slot /></div>',
          }),
          IconifyIcon: true,
          Tooltip: defineComponent({
            name: 'TooltipStub',
            template: '<div><slot /></div>',
          }),
        },
      },
    });

    await wrapper.vm.$nextTick();

    expect(wrapper.text()).not.toContain('common.globalAiChat.tokens');
    expect(wrapper.text()).not.toContain('5.2s');
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

  it('renders tool target badges and toggles tool details with animated state in default mode', async () => {
    const wrapper = mount(ChatMessageToolCalls, {
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
        embedded: false,
      },
      global: {
        stubs: {
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();

    const toggleText = wrapper.get('[data-testid="tool-call-toggle-0"]').text();
    expect(toggleText).toContain('common.globalAiChat.toolTouched');
    expect(toggleText).toContain('统计今天调用情况');
    expect(toggleText).toContain('ai_call_logs, tenants');
    expect(toggleText).toContain('common.globalAiChat.toolTargetQuery');
    expect(toggleText).toContain('common.globalAiChat.toolTargetTables');
    expect(toggleText).toContain('+3');
    expect(toggleText).not.toContain('common.globalAiChat.toolTargetMetrics');
    expect(toggleText).not.toContain('COUNT(acl.id)');
    expect(toggleText).not.toContain('common.globalAiChat.toolTargetGrouping');
    expect(toggleText).not.toContain('common.globalAiChat.toolTargetFilter');

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
    expect(wrapper.text()).toContain('COUNT(acl.id)');
    expect(wrapper.text()).toContain('t.name');

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

  it('renders structured args and returned payload details before the raw result toggle in default mode', async () => {
    const wrapper = mount(ChatMessageToolCalls, {
      props: {
        msg: createAssistantMsg([
          {
            name: 'sync_contacts',
            status: 'success',
            arguments: {
              tenant_code: 'northwind',
              filters: {
                owner: 'ops',
                status: 'active',
              },
              record_ids: [101, 202, 303],
            },
            output: JSON.stringify({
              result: {
                skipped: 1,
                trace_id: 'trace-123',
                updated: true,
              },
              records: [
                {
                  name: 'Northwind',
                  status: 'ok',
                  total: 12,
                },
                {
                  name: 'Contoso',
                  status: 'ok',
                  total: 9,
                },
              ],
            }),
          },
        ]),
        index: 0,
        compact: true,
        embedded: false,
      },
      global: {
        stubs: {
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();
    await wrapper.get('[data-testid="tool-call-toggle-0"]').trigger('click');
    await wrapper.vm.$nextTick();

    const argumentFields = wrapper.findAll('[data-testid^="tool-arg-field-"]');
    expect(argumentFields).toHaveLength(3);
    expect(argumentFields[0]?.text()).toContain('tenant_code');
    expect(argumentFields[0]?.text()).toContain('northwind');
    expect(argumentFields[1]?.text()).toContain('filters');
    expect(argumentFields[1]?.text()).toContain('owner');
    expect(argumentFields[1]?.text()).toContain('ops');
    expect(argumentFields[1]?.text()).toContain('status');
    expect(argumentFields[1]?.text()).toContain('active');
    expect(argumentFields[2]?.text()).toContain('record_ids');
    expect(argumentFields[2]?.text()).toContain('101');
    expect(argumentFields[2]?.text()).toContain('202');
    expect(argumentFields[2]?.text()).toContain('303');

    const outputFields = wrapper.findAll('[data-testid^="tool-output-field-"]');
    expect(outputFields).toHaveLength(2);
    expect(outputFields[0]?.text()).toContain('result');
    expect(outputFields[0]?.text()).toContain('updated');
    expect(outputFields[0]?.text()).toContain('true');
    expect(outputFields[0]?.text()).toContain('trace-123');
    expect(outputFields[1]?.text()).toContain('records');
    expect(outputFields[1]?.text()).toContain('Northwind');
    expect(outputFields[1]?.text()).toContain('total: 12');
    expect(outputFields[1]?.text()).toContain('Contoso');
    expect(outputFields[1]?.text()).toContain('total: 9');
    expect(wrapper.text()).toContain('common.globalAiChat.rawResult');
  });

  it('renders structured web search results directly from summary payload in default mode', async () => {
    const wrapper = mount(ChatMessageToolCalls, {
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
        embedded: false,
      },
      global: {
        stubs: {
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

  it('does not display a fake zero result count for native search summaries without counts in default mode', async () => {
    const wrapper = mount(ChatMessageToolCalls, {
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
        embedded: false,
      },
      global: {
        stubs: {
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

  it('tool group card collapses when all tools are completed in default mode', async () => {
    const wrapper = mount(ChatMessageToolCalls, {
      props: {
        msg: createAssistantMsg([
          { name: 'web_search', status: 'success' },
          { name: 'fetch_url', status: 'success' },
        ]),
        index: 0,
        compact: true,
        embedded: false,
      },
      global: {
        stubs: {
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();
    const body = wrapper.get('[data-testid="tool-group-body"]');
    expect(body.attributes('style') ?? '').toContain('grid-template-rows: 0fr');
  });

  it('tool group card toggles on click in default mode', async () => {
    const wrapper = mount(ChatMessageToolCalls, {
      props: {
        msg: createAssistantMsg([{ name: 'web_search', status: 'success' }]),
        index: 0,
        compact: true,
        embedded: false,
      },
      global: {
        stubs: {
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

  it('renders embedded tool calls as inline transcript rows with inline expandable details', async () => {
    const wrapper = mount(ChatMessageToolCalls, {
      props: {
        msg: createAssistantMsg([
          {
            name: 'web_search',
            status: 'success',
            resultLink: 'https://example.com/result-1',
            summaryPayload: {
              result_count: 2,
              items: [
                {
                  title: '示例搜索结果一',
                  url: 'https://example.com/result-1',
                },
              ],
            },
          },
        ]),
        index: 0,
        compact: true,
        embedded: true,
      },
      global: {
        stubs: {
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();

    expect(wrapper.find('[data-testid="tool-group-toggle"]').exists()).toBe(
      false,
    );
    expect(wrapper.find('[data-testid="tool-call-toggle-0"]').exists()).toBe(
      true,
    );
    expect(
      wrapper.get('[data-testid="tool-group-body"]').attributes('style'),
    ).toContain('grid-template-rows: 1fr');
    expect(
      wrapper.get('[data-testid="tool-call-details-0"]').attributes('style'),
    ).toContain('grid-template-rows: 0fr');
    expect(
      wrapper.get('[data-testid="tool-call-embedded-0"]').text(),
    ).toContain('common.globalAiChat.toolStatusOk');
    expect(
      wrapper.get('[data-testid="tool-call-embedded-0"]').text(),
    ).toContain('common.globalAiChat.toolSearchResults: 2');
    expect(
      wrapper.get('[data-testid="tool-call-embedded-0"]').text(),
    ).toContain('common.globalAiChat.viewResult');

    await wrapper.get('[data-testid="tool-call-toggle-0"]').trigger('click');
    await wrapper.vm.$nextTick();

    expect(
      wrapper.get('[data-testid="tool-call-details-0"]').attributes('style'),
    ).toContain('grid-template-rows: 1fr');
  });

  it('tool group auto-collapses when streaming ends in default mode', async () => {
    const wrapper = mount(ChatMessageToolCalls, {
      props: {
        msg: {
          ...createAssistantMsg([{ name: 'web_search', status: 'running' }]),
          clientKey: 'assistant-streaming-tools',
          streaming: true,
        },
        index: 0,
        compact: true,
        embedded: false,
      },
      global: {
        stubs: {
          IconifyIcon: true,
        },
      },
    });

    await wrapper.vm.$nextTick();

    const body = wrapper.get('[data-testid="tool-group-body"]');
    expect(body.attributes('style') ?? '').toContain('grid-template-rows: 1fr');

    await wrapper.setProps({
      msg: {
        ...createAssistantMsg([{ name: 'web_search', status: 'success' }]),
        clientKey: 'assistant-streaming-tools',
        content: 'Final reply',
        streaming: false,
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
    ).toBe(false);
    expect(
      wrapper
        .get('[data-testid="chat-message-kernel-overview-toggle"]')
        .attributes(),
    ).toMatchObject({
      'aria-expanded': 'false',
    });
    expect(
      wrapper.find('[data-testid="chat-message-kernel-evidence"]').exists(),
    ).toBe(false);
    expect(wrapper.text()).toContain('已按可验证来源整理结论');
    expect(wrapper.text()).not.toContain('https://example.com/ref');

    await expandDigestIfCollapsed(wrapper);

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

    await expandDigestIfCollapsed(wrapper);

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

    await expandDigestIfCollapsed(wrapper);

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

    await expandDigestIfCollapsed(wrapper);

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

  it('accepts answer card sections using content field from backend turn_flow when no summary is present', async () => {
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
      wrapper
        .get('[data-testid="chat-message-kernel-overview-toggle"]')
        .attributes(),
    ).toMatchObject({
      'aria-expanded': 'false',
    });
    expect(
      wrapper.find('[data-testid="chat-message-kernel-evidence"]').exists(),
    ).toBe(false);
    expect(wrapper.find('[data-testid="turn-digest-toggle"]').exists()).toBe(
      false,
    );
    expect(wrapper.find('[data-testid="turn-digest-body"]').exists()).toBe(
      false,
    );
    expect(wrapper.text()).toContain('政策要点');
    expect(wrapper.text()).not.toContain('后端返回的是 content 字段');

    await expandDigestIfCollapsed(wrapper);

    expect(wrapper.text()).toContain('政策要点');
    expect(wrapper.text()).toContain('后端返回的是 content 字段');
  });

  it('keeps completed answer digests collapsed by default and expands on demand', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-turn-flow-collapsed-answer-digest',
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
            answerCard: {
              sections: [
                {
                  title: '结果整理',
                  body: '这是正式结构化整理内容',
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
      wrapper
        .get('[data-testid="chat-message-kernel-overview-toggle"]')
        .attributes(),
    ).toMatchObject({
      'aria-expanded': 'false',
    });
    expect(wrapper.find('[data-testid="turn-digest-toggle"]').exists()).toBe(
      false,
    );
    expect(wrapper.find('[data-testid="turn-digest-body"]').exists()).toBe(
      false,
    );
    expect(wrapper.text()).toContain('结果整理');
    expect(wrapper.text()).not.toContain('这是正式结构化整理内容');

    await expandDigestIfCollapsed(wrapper);

    expect(
      wrapper.get('[data-testid="turn-digest-toggle"]').attributes(),
    ).toMatchObject({
      'aria-expanded': 'true',
    });
    expect(wrapper.find('[data-testid="turn-digest-body"]').exists()).toBe(
      true,
    );
    expect(wrapper.text()).toContain('这是正式结构化整理内容');
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
    ).toBe(false);
    expect(wrapper.text()).not.toContain('提炼核心结论');
    expect(wrapper.text()).not.toContain('补充执行建议');

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
    expect(wrapper.text()).not.toContain('这是正式结构化整理内容');
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
    await expandKernelOverviewIfCollapsed(wrapper);

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
        } as unknown as ChatMessage,
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
    await expandKernelOverviewIfCollapsed(wrapper);

    expect(
      wrapper.get('[data-testid="turn-process-body"]').attributes('style') ??
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
      wrapper.find('[data-testid="chat-message-kernel-timeline"]').exists(),
    ).toBe(false);
    expect(wrapper.text()).not.toContain('15 个工具中筛选了 0 个');
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
    await expandKernelOverviewIfCollapsed(wrapper);

    expect(
      wrapper.get('[data-testid="turn-process-body"]').attributes('style') ??
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
      wrapper.find('[data-testid="chat-message-kernel-evidence"]').exists(),
    ).toBe(false);
    expect(
      wrapper.find('[data-testid="chat-message-kernel-timeline"]').exists(),
    ).toBe(false);
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
    await expandKernelOverviewIfCollapsed(wrapper);

    expect(
      wrapper.get('[data-testid="turn-process-body"]').attributes('style') ??
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

    expect(wrapper.text()).not.toContain(
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
    await expandKernelOverviewIfCollapsed(wrapper);

    expect(wrapper.text()).toContain('common.globalAiChat.toolSearchProvider');
    expect(wrapper.text()).toContain('native:provider_1:gpt-5.4');
    expect(wrapper.text()).toContain(
      'common.globalAiChat.turnRetrievalSummary',
    );
    expect(
      wrapper.get('[data-testid="turn-process-body"]').attributes('style') ??
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
      wrapper.find('[data-testid="chat-message-kernel-timeline"]').exists(),
    ).toBe(false);
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
      wrapper
        .get('[data-testid="chat-message-kernel-overview-toggle"]')
        .attributes(),
    ).toMatchObject({
      'aria-expanded': 'false',
    });
    expect(wrapper.find('[data-testid="turn-process-body"]').exists()).toBe(
      false,
    );
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
      wrapper.find('[data-testid="chat-message-kernel-timeline"]').exists(),
    ).toBe(false);
  });

  it('does not render legacy fallback sections when turnFlow is missing', async () => {
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
        } as unknown as ChatMessage,
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
    expect(wrapper.text()).not.toContain('common.globalAiChat.optimizingTools');
    expect(wrapper.text()).not.toContain('common.globalAiChat.ragSources');
    expect(wrapper.text()).not.toContain('先做分析，再给答案。');
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

  it('strips DSML tool-call protocol text from the assistant transcript body', async () => {
    const assistantMessage = createAssistantMsg([
      {
        displayName: '读取表格',
        id: 'tc_read_table',
        name: 'ui_read_table',
        output: '{"explanation":"读取了 1 个表格"}',
        status: 'success',
        summary: '读取了 1 个表格',
      },
    ]);

    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          ...assistantMessage,
          content:
            '我看到页面上有一个表格，但表格内容只显示了部分数据。为了获取更完整的表格数据，让我读取一下表格区域。<｜DSML｜tool_calls><｜DSML｜invoke name="ui_read_table"><｜DSML｜parameter name="locator">div.table</｜DSML｜parameter></｜DSML｜invoke></｜DSML｜tool_calls>现在把整理结果告诉你。',
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
      renderedMarkdownBlocks.some((block) => block.text().includes('DSML')),
    ).toBe(false);
    expect(wrapper.text()).not.toContain('<｜DSML｜tool_calls>');
    expect(wrapper.text()).toContain('现在把整理结果告诉你。');
    expect(
      wrapper.find('[data-testid="chat-message-kernel-header"]').exists(),
    ).toBe(true);
  });

  it('renders transcript content before the kernel header for assistant messages', async () => {
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-transcript-first-order',
          role: 'assistant' as const,
          content: '最终答复正文',
          turnFlow: createTurnFlow({
            timeline: [
              {
                id: 'stage-thinking',
                type: 'thinking',
                status: 'completed',
                summary: '已完成思考',
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

    const html = wrapper.html();
    expect(html.indexOf('data-testid="markdown-render-content"')).toBeLessThan(
      html.indexOf('data-testid="chat-message-kernel-header"'),
    );
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

  it('hides raw provider html bodies when the turn ended in provider failure', async () => {
    const leakedHtml = `<!DOCTYPE html>
<html lang="en-US">
<head><title>asxs.top | 502: Bad gateway</title></head>
<body>
<div>Bad gateway</div>
<div>Cloudflare Ray ID: 9f0605e63a38f548</div>
</body>
</html>`;
    const wrapper = mount(ChatMessageItem, {
      props: {
        msg: {
          clientKey: 'assistant-provider-html-history',
          role: 'assistant' as const,
          content: leakedHtml,
          turnFlow: createTurnFlow({
            completion_reason: 'provider_error',
            error_surface: {
              error_type: 'provider_error',
              message: 'AI 供应商服务端错误',
              trace_id: 'trace-provider-html',
            },
            failure_kind: 'provider_error',
            final_stage_status: 'error',
            turn_outcome: 'failed',
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
                summary: 'provider_error',
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
        block.text().includes('Bad gateway'),
      ),
    ).toBe(false);
    expect(wrapper.text()).not.toContain('Bad gateway');
    expect(wrapper.text()).not.toContain('Cloudflare Ray ID');
  });

  it('uses a compact collapsed body for very long replies', async () => {
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

    const contentBody = wrapper.get('[data-testid="assistant-content-body"]');
    expect(contentBody.classes()).toContain('max-h-[176px]');
    expect(
      wrapper.get('[data-testid="assistant-content-collapse-toggle"]').text(),
    ).toBe('common.globalAiChat.expandMore');
    expect(
      wrapper.find('[data-testid="collapsed-message-hint"]').exists(),
    ).toBe(false);
  });
});
