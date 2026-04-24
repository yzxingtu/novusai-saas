// Test type: structural
// Verifies: tool call detail helpers build input/search/output view models from canonical tool evidence.
import { describe, expect, it, vi } from 'vitest';

import { buildToolDisplayItems } from '../chat-message-tool-call-display-helpers';
import { buildToolCallDetailsViewModel } from '../chat-message-tool-call-details-helpers';

vi.mock('#/locales', () => ({
  $t: (key: string, params?: Record<string, unknown>) => {
    if (!params || Object.keys(params).length === 0) {
      return key;
    }
    const suffix = Object.entries(params)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([name, value]) => `${name}=${String(value)}`)
      .join(',');
    return `${key}:${suffix}`;
  },
}));

describe('chat-message-tool-call-details helpers', () => {
  it('builds one coherent detail view from arguments, search summary, and returned payload', () => {
    const [toolItem] = buildToolDisplayItems(
      [
        {
          arguments: {
            filters: {
              owner: 'ops',
              status: 'active',
            },
            tenant_code: 'northwind',
          },
          name: 'web_search',
          output: JSON.stringify({
            records: [
              {
                name: 'Northwind',
                total: 12,
              },
            ],
            result: {
              trace_id: 'trace-123',
              updated: true,
            },
          }),
          status: 'success',
          summaryPayload: {
            fallback_reason:
              'native_not_attempted:default_verified_target_unavailable',
            items: [
              {
                snippet: '第一条摘要内容',
                title: '示例搜索结果一',
                url: 'https://example.com/result-1',
              },
            ],
            provider: 'baidu_public',
            selected_backend: 'public:baidu',
            status: 'success',
          },
        },
      ],
      {
        resolveExpanded: () => true,
      },
    );

    expect(toolItem).toBeDefined();
    if (!toolItem) {
      throw new Error('Tool display item was not built');
    }

    const detailView = buildToolCallDetailsViewModel(toolItem);

    expect(detailView.argumentFields.map((field) => field.key)).toEqual([
      'filters',
      'tenant_code',
    ]);
    expect(detailView.searchResults).toEqual([
      expect.objectContaining({
        domain: 'example.com',
        title: '示例搜索结果一',
        url: 'https://example.com/result-1',
      }),
    ]);
    expect(detailView.searchTechnicalDetails).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: 'provider',
          value: 'common.globalAiChat.toolSearchSourceBaidu',
        }),
        expect.objectContaining({
          key: 'selectedBackend',
          value: 'public:baidu',
        }),
      ]),
    );
    expect(detailView.outputFields.map((field) => field.key)).toEqual([
      'records',
      'result',
    ]);
    expect(detailView.rawOutput).toContain('"trace_id": "trace-123"');
    expect(detailView.searchFallbackNotice).toBe(
      'common.globalAiChat.toolSearchFallbackNeedVerifiedNativeTarget',
    );
  });
});
