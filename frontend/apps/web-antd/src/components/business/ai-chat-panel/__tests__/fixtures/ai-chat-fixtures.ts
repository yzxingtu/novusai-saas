export const baseChatOptions = {
  apiPrefix: '/tenant',
  uploadUrl: '/tenant/attachments',
};

export const buildAgent = (overrides: Record<string, unknown> = {}) => ({
  avatar: null,
  description: 'Test agent',
  id: 1,
  input_variables: [],
  model_capabilities: {
    max_image_count: 4,
    max_image_size_mb: 10,
    supports_vision: false,
  },
  model_name: 'gpt-test',
  name: 'Agent One',
  status: 'published',
  tenant_id: 1,
  ...overrides,
});

export const buildAgentList = (
  items: Array<Record<string, unknown>> = [buildAgent()],
  overrides: Record<string, unknown> = {},
) => ({
  items,
  total: items.length,
  ...overrides,
});

export const buildConversation = (overrides: Record<string, unknown> = {}) => ({
  agent_id: 1,
  agent_name: 'Agent One',
  created_at: '2024-01-01T00:00:00Z',
  id: 42,
  message_count: 2,
  status: 'active',
  title: 'Recovered',
  ...overrides,
});

export const buildConversationList = (
  items: Array<Record<string, unknown>>,
  overrides: Record<string, unknown> = {},
) => ({
  items,
  total: items.length,
  ...overrides,
});

export const buildConversationDetail = (
  message_list: Array<Record<string, unknown>>,
  overrides: Record<string, unknown> = {},
) => ({
  agent_id: 1,
  message_list,
  ...overrides,
});

export const buildUserMessage = (
  content: string,
  overrides: Record<string, unknown> = {},
) => ({
  content,
  created_at: '2024-01-01T00:00:00Z',
  role: 'user',
  ...overrides,
});

export const buildAssistantMessage = (
  content: string,
  overrides: Record<string, unknown> = {},
) => ({
  agent_id: 1,
  agent_name: 'Agent One',
  content,
  created_at: '2024-01-01T00:00:01Z',
  model_name: 'gpt-test',
  role: 'assistant',
  ...overrides,
});

export const buildToolMessage = (
  content: string,
  overrides: Record<string, unknown> = {},
) => ({
  content,
  created_at: '2024-01-01T00:00:02Z',
  role: 'tool',
  ...overrides,
});

export const buildNativeSearchProgressHistoryMessages = () => [
  buildUserMessage('搜索一下'),
  buildAssistantMessage('', {
    metadata: {
      turn_record: {
        auto_fetch_gate_reason: 'native_search_completed',
        metadata: {
          stream_progress_kinds: ['web_search_in_progress'],
        },
      },
    },
  }),
];

export const buildRichToolHistoryMessages = () => [
  buildUserMessage('统计今天调用情况'),
  buildAssistantMessage('', {
    metadata: {
      action_buttons: [
        {
          label: '查看明细',
          style: 'primary',
          value: '查看今天调用明细',
        },
      ],
      pending_consent: {
        arguments: { question: '统计今天调用情况' },
        skill_name: '数据查询',
        tool_name: 'query_records',
      },
    },
    tool_calls: [
      {
        display_name: '数据查询',
        duration_ms: 120,
        function: {
          arguments: '{"question":"统计今天调用情况"}',
          name: 'query_records',
        },
        id: 'tc_history_1',
        pending_confirmation: {
          action: 'query',
          preview: { sql: 'SELECT 1' },
          table: 'ai_call_logs',
          tool_name: 'query_records',
        },
        result_link: '/admin/ai/chat',
        skill_name: '数据查询',
        success: true,
        summary: '按今天范围统计调用',
        summary_payload: {
          filters: ['today'],
          tables: ['ai_call_logs'],
          tool_kind: 'query_records',
        },
      },
    ],
  }),
  buildToolMessage('{"success": true}', {
    metadata: {
      tool_display_name: '数据查询',
      tool_success: true,
      tool_summary: '按今天范围统计调用',
      tool_summary_payload: {
        filters: ['today'],
        tables: ['ai_call_logs'],
        tool_kind: 'query_records',
      },
    },
    tool_call_id: 'tc_history_1',
    tool_name: 'query_records',
  }),
];

export const buildNativeSearchDiagnosticsMessages = () => [
  buildUserMessage('搜索一下 长沙市小学生什么时候放暑假'),
  buildAssistantMessage('查到了。', {
    metadata: {
      context_diagnostics: {
        intent_plan: [
          {
            completed_by_tool_names: ['native_web_search'],
          },
        ],
      },
      selected_tool_names: ['web_search', 'fetch_url'],
    },
  }),
];

export const buildNativeSearchInterruptedMessages = () => [
  buildUserMessage('搜索一下 长沙市小学生什么时候放暑假'),
  buildAssistantMessage('先帮你查找了一部分信息。', {
    metadata: {
      turn_record: {
        metadata: {
          stream_progress_kinds: ['web_search_in_progress'],
        },
        termination_reason: 'interrupted',
        turn_outcome: 'partial',
      },
    },
  }),
];

export const buildThinkingDedupHistoryMessages = () => [
  buildUserMessage('那广州今天的天气呢？'),
  buildAssistantMessage('', {
    metadata: {
      thinking_content:
        '**Considering tool responses** I have the weather details now.',
    },
    tool_calls: [
      {
        function: {
          arguments: '{"city":"广州"}',
          name: 'get_current_weather',
        },
        id: 'tc_weather_1',
      },
    ],
  }),
  buildToolMessage('{"city":"广州","condition":"多云"}', {
    metadata: {
      tool_success: true,
    },
    tool_call_id: 'tc_weather_1',
    tool_name: 'get_current_weather',
  }),
  buildAssistantMessage('广州今天多云，气温 24 到 29 摄氏度。', {
    metadata: {
      thinking_content:
        '**Considering tool responses** I have the weather details now.',
    },
  }),
];

export const sseEvent = (payload: Record<string, unknown>) =>
  `data: ${JSON.stringify(payload)}\n`;
