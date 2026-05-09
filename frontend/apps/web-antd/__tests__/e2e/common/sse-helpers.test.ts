// 中文: Test type: smoke. SSE smoke 指标只能统计 canonical turn-flow 工具证据。
// EN: Test type: smoke. SSE smoke metrics must only count canonical turn-flow tool evidence.
// 中文: Mock strategy: 不 mock LLM 或工具执行器，断言使用已捕获事件形状的载荷。
// EN: Mock strategy: no LLM/tool mocks; assertions use captured-event shaped payloads.
import { describe, expect, it } from 'vitest';

import { collectCanonicalToolCallsFromEvents } from './sse-helpers';

function event(data: Record<string, unknown>) {
  return { data: JSON.stringify(data) };
}

describe('sse smoke tool evidence extraction', () => {
  it('does not synthesize toolCalls from legacy tool events or selection diagnostics', () => {
    const toolCalls = collectCanonicalToolCallsFromEvents([
      event({
        event: 'optimizing_tools',
        selected: 1,
        total: 2,
      }),
      event({
        arguments: { city: 'Shanghai' },
        event: 'tool_start',
        name: 'legacy_weather',
      }),
      event({
        event: 'tool_call',
        name: 'legacy_weather',
        output: 'sunny',
        success: true,
      }),
      event({
        event: 'turn_stage',
        kind: 'tool',
        status: 'completed',
        summary: 'legacy_weather completed',
        tool_name: 'legacy_weather',
        type: 'tool_execution',
      }),
      event({
        conversation_id: 42,
        event: 'done',
        selected_tool_names: ['legacy_weather'],
        turn_record: {
          selected_tool_names: ['legacy_from_turn_record'],
        },
      }),
    ]);

    expect(toolCalls).toEqual([]);
  });

  it('extracts toolCalls from canonical turn_evidence and done turn_flow only', () => {
    const toolCalls = collectCanonicalToolCallsFromEvents([
      event({
        event: 'turn_evidence',
        evidence: {
          arguments: { timezone: 'Asia/Shanghai' },
          duration_ms: 12,
          id: 'evidence-time-1',
          kind: 'tool',
          output: '2026-05-09 18:00',
          status: 'success',
          tool_call_id: 'call-time-1',
          tool_name: 'current_time',
        },
      }),
      event({
        conversation_id: 42,
        event: 'done',
        selected_tool_names: ['legacy_selected_is_not_enough'],
        turn_record: {
          turn_flow: {
            evidence: [
              {
                error: 'timeout',
                error_type: 'provider_timeout',
                id: 'evidence-weather-1',
                kind: 'tool',
                status: 'error',
                tool_name: 'weather_lookup',
              },
            ],
            timeline: [
              {
                status: 'completed',
                tool_name: 'timeline_name_is_not_evidence',
                type: 'tool_execution',
              },
            ],
          },
        },
      }),
    ]);

    expect(toolCalls).toEqual([
      expect.objectContaining({
        arguments: { timezone: 'Asia/Shanghai' },
        duration_ms: 12,
        name: 'current_time',
        output: '2026-05-09 18:00',
        success: true,
      }),
      expect.objectContaining({
        error: 'timeout',
        error_type: 'provider_timeout',
        name: 'weather_lookup',
        success: false,
      }),
    ]);
  });
});
