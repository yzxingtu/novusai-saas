import type { ChatMessage } from './types';

import { normalizeTurnFlowViewModel } from './chat-message-turn-flow-ingestion';

type TurnFlowRecord = Record<string, unknown>;

function asRecord(value: unknown): null | Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function hasTurnFlowShape(value: unknown): value is TurnFlowRecord {
  const record = asRecord(value);
  if (!record) {
    return false;
  }
  return Array.isArray(record.timeline) || Array.isArray(record.evidence);
}

export function extractMessageTurnFlow(
  message: ChatMessage,
): TurnFlowRecord | undefined {
  if (hasTurnFlowShape(message.turnFlow)) {
    return message.turnFlow as unknown as TurnFlowRecord;
  }

  const messageRecord = message as unknown as Record<string, unknown>;
  if (hasTurnFlowShape(messageRecord.turn_flow)) {
    return messageRecord.turn_flow as TurnFlowRecord;
  }
  const metadata = asRecord(messageRecord.metadata);
  if (!metadata) {
    return undefined;
  }
  if (hasTurnFlowShape(metadata.turn_flow)) {
    return metadata.turn_flow as TurnFlowRecord;
  }
  if (hasTurnFlowShape(metadata.turnFlow)) {
    return metadata.turnFlow as TurnFlowRecord;
  }
  return undefined;
}

export function toTurnFlowFirstChatMessage(message: ChatMessage): ChatMessage {
  const nextMessage = { ...message } as ChatMessage;
  const nextRecord = nextMessage as unknown as Record<string, unknown>;
  delete nextRecord.thinkingContent;
  delete nextRecord.optimizingTools;
  delete nextRecord.ragSources;
  delete nextRecord.toolCalls;

  const turnFlow = normalizeTurnFlowViewModel(extractMessageTurnFlow(message));
  if (!turnFlow) {
    return nextMessage;
  }
  return {
    ...nextMessage,
    turnFlow: turnFlow as unknown as ChatMessage['turnFlow'],
  };
}
