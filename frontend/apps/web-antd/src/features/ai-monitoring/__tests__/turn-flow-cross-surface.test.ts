import type { MonitoringConversationMessage } from '../api';

// @vitest-environment happy-dom
import type { ChatMessage } from '#/types/ai-chat';

import { describe, expect, it } from 'vitest';

import { getTurnFlowForDisplay } from '#/components/business/ai-chat-panel/chat-message-turn-flow';

import { toTurnFlowFirstChatMessage } from '../../../views/user/ai-chat/modules/user-chat-message-normalizer';
import { toMonitoringChatMessage } from '../pages/monitoring-conversation/monitoring-chat-message-adapter';

const RAW_SUCCESS_TURN_FLOW = {
  answer_card: {
    summary: 'answer summary',
  },
  completion_reason: 'completed',
  evidence: [
    {
      id: 'ev-1',
      kind: 'web',
      title: 'source',
      url: 'https://example.com',
    },
  ],
  timeline: [
    {
      id: 'stage-thinking',
      status: 'completed',
      summary: 'thinking done',
      type: 'thinking',
    },
  ],
};

const RAW_FAILURE_TURN_FLOW = {
  completion_reason: 'provider_failure_after_partial_progress',
  failure_kind: 'provider_failure_after_partial_progress',
  final_stage_status: 'error',
  timeline: [
    {
      id: 'stage-thinking',
      status: 'completed',
      summary: 'thinking done',
      type: 'thinking',
    },
    {
      id: 'stage-tool-selection',
      metrics: { selected: 0, total: 3 },
      status: 'skipped',
      type: 'tool_selection',
    },
    {
      id: 'stage-tool-execution',
      metrics: { failed: 0, running: 0, success: 1, total: 1 },
      status: 'completed',
      type: 'tool_execution',
    },
    {
      id: 'stage-answer',
      status: 'completed',
      summary: 'partial answer assembled',
      type: 'answer_assembly',
    },
    {
      id: 'stage-terminal',
      status: 'completed',
      type: 'failed',
    },
  ],
  turn_flow_complete: true,
  turn_outcome: 'partial',
};

describe('turn flow cross-surface normalization', () => {
  it('keeps the same turn_flow payload for user workspace and monitoring surfaces', () => {
    const userMessage = {
      clientKey: 'user-surface-message',
      content: 'final answer',
      role: 'assistant',
      thinkingContent: 'legacy thinking',
      toolCalls: [{ name: 'legacy_tool', status: 'success' }],
      turn_flow: RAW_SUCCESS_TURN_FLOW,
    } as unknown as ChatMessage;

    const monitoringMessage = {
      content: 'final answer',
      created_at: '2026-04-16T10:00:00Z',
      id: 18,
      metadata: {
        turn_flow: RAW_SUCCESS_TURN_FLOW,
      },
      role: 'assistant',
      sequence: 3,
      token_count: 42,
    } as unknown as MonitoringConversationMessage;

    const normalizedUser = toTurnFlowFirstChatMessage(userMessage);
    const normalizedMonitoring = toMonitoringChatMessage(monitoringMessage);

    expect(normalizedUser.turnFlow).toEqual(RAW_SUCCESS_TURN_FLOW);
    expect(normalizedMonitoring.turnFlow).toEqual(RAW_SUCCESS_TURN_FLOW);
    expect(normalizedUser.thinkingContent).toBeUndefined();
    expect(normalizedUser.toolCalls).toBeUndefined();
    expect(normalizedMonitoring.thinkingContent).toBeUndefined();
    expect(normalizedMonitoring.toolCalls).toBeUndefined();
    expect(normalizedMonitoring.streaming).toBe(false);
  });

  it('keeps user workspace, shared timeline projection, and monitoring drawer aligned on failure terminal semantics', () => {
    const userMessage = {
      clientKey: 'user-failure-message',
      content: 'fallback answer',
      role: 'assistant',
      thinkingContent: 'legacy thinking',
      toolCalls: [{ name: 'legacy_tool', status: 'success' }],
      turn_flow: RAW_FAILURE_TURN_FLOW,
    } as unknown as ChatMessage;

    const monitoringMessage = {
      content: 'fallback answer',
      created_at: '2026-04-16T10:02:00Z',
      id: 19,
      metadata: {
        failure_kind: 'provider_failure_after_partial_progress',
        selected_tool_names: ['web_search'],
        termination_reason: 'provider_failure_after_partial_progress',
        turn_flow: RAW_FAILURE_TURN_FLOW,
        turn_outcome: 'partial',
      },
      role: 'assistant',
      sequence: 4,
      token_count: 21,
      tool_calls: [{ function: { name: 'legacy_tool' }, success: true }],
    } as unknown as MonitoringConversationMessage;

    const normalizedUser = toTurnFlowFirstChatMessage(userMessage);
    const normalizedMonitoring = toMonitoringChatMessage(monitoringMessage);

    const sharedUserFlow = getTurnFlowForDisplay(normalizedUser);
    const sharedMonitoringFlow = getTurnFlowForDisplay(normalizedMonitoring);

    const expectedStageOrder = [
      'thinking',
      'tool_selection',
      'tool_execution',
      'answer_assembly',
      'failed',
    ];

    expect(sharedUserFlow.timeline.map((stage) => stage.type)).toEqual(
      expectedStageOrder,
    );
    expect(sharedMonitoringFlow.timeline.map((stage) => stage.type)).toEqual(
      expectedStageOrder,
    );

    expect(sharedUserFlow.timeline).toHaveLength(expectedStageOrder.length);
    expect(sharedMonitoringFlow.timeline).toHaveLength(
      expectedStageOrder.length,
    );

    expect(
      sharedUserFlow.timeline[sharedUserFlow.timeline.length - 1],
    ).toMatchObject({
      status: 'error',
      type: 'failed',
    });
    expect(
      sharedMonitoringFlow.timeline[sharedMonitoringFlow.timeline.length - 1],
    ).toMatchObject({
      status: 'error',
      type: 'failed',
    });

    expect(
      sharedUserFlow.timeline.find((stage) => stage.type === 'answer_assembly')
        ?.status,
    ).toBe('error');
    expect(
      sharedMonitoringFlow.timeline.find(
        (stage) => stage.type === 'answer_assembly',
      )?.status,
    ).toBe('error');

    expect(normalizedMonitoring.turnOutcome).toBe('failed');
    expect(normalizedMonitoring.terminationReason).toBe(
      'provider_failure_after_partial_progress',
    );
    expect(normalizedMonitoring.selectedToolNames).toEqual(['web_search']);

    expect(normalizedUser.thinkingContent).toBeUndefined();
    expect(normalizedUser.toolCalls).toBeUndefined();
    expect(normalizedMonitoring.thinkingContent).toBeUndefined();
    expect(normalizedMonitoring.toolCalls).toBeUndefined();
    expect(normalizedMonitoring.streaming).toBe(false);
  });

  it('projects persisted error metadata into the shared ChatMessage error model', () => {
    const monitoringMessage = {
      content: '',
      created_at: '2026-04-16T10:04:00Z',
      id: 20,
      metadata: {
        error: true,
        error_debug_message: 'raw provider stack',
        error_message: 'Provider request failed',
        error_trace_id: 'trace-monitoring-20',
        error_type: 'provider_error',
      },
      role: 'assistant',
      sequence: 5,
      token_count: 0,
    } as unknown as MonitoringConversationMessage;

    const normalizedMonitoring = toMonitoringChatMessage(monitoringMessage);

    expect(normalizedMonitoring.error).toMatchObject({
      code: 'provider_error',
      message: 'Provider request failed',
      source: 'sse',
      traceId: 'trace-monitoring-20',
    });
    expect(normalizedMonitoring.error?.debugMessage).toBe('raw provider stack');
  });

  it('preserves non-user monitoring roles and keeps message identity stable across reordering indexes', () => {
    const monitoringMessage = {
      content: 'tool execution output',
      created_at: '2026-04-16T10:06:00Z',
      id: 21,
      role: 'tool',
      sequence: 6,
      token_count: 0,
    } as unknown as MonitoringConversationMessage;

    const normalizedFirst = toMonitoringChatMessage(monitoringMessage, 0);
    const normalizedAfterPrepend = toMonitoringChatMessage(
      monitoringMessage,
      8,
    );

    expect(normalizedFirst.role).toBe('tool');
    expect(normalizedAfterPrepend.role).toBe('tool');
    expect(normalizedFirst.clientKey).toBe('monitoring-message-21');
    expect(normalizedAfterPrepend.clientKey).toBe('monitoring-message-21');
    expect(normalizedFirst.streaming).toBe(false);
    expect(normalizedAfterPrepend.streaming).toBe(false);
  });
});
