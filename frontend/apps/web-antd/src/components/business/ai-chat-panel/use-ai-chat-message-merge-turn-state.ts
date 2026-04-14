import type {
  ActionButton,
  PendingConfirmation,
  PendingConsent,
  RagSource,
  ToolCallEvent,
} from './types';

import type {
  TurnContextSourcePayload,
  TurnRecordPayload,
} from '#/api/shared/ai-chat';
import type { AppErrorInfo } from '#/utils/request';

export interface AssistantTurnMergeState {
  contentParts: string[];
  hasInterrupted: boolean;
  hasMemoryUpdated: boolean;
  hasPartial: boolean;
  startIndex: number;
  thinkingContentParts: string[];
  toolCalls: ToolCallEvent[];
  turnActionButtons?: ActionButton[];
  turnActionButtonsUsed: boolean;
  turnAgentAvatar: null | string;
  turnAgentDescription: null | string;
  turnAgentId: null | number;
  turnAgentName: null | string;
  turnCompletionReason?: string;
  turnContextDiagnosticsRaw: null | Record<string, unknown>;
  turnContextSources: TurnContextSourcePayload[];
  turnCreatedAt: null | string;
  turnLastRunSummaryRaw: null | Record<string, unknown>;
  turnModelName: null | string;
  turnOutcome?: string;
  turnPendingConfirmation?: PendingConfirmation;
  turnPendingConsent?: PendingConsent;
  turnPersistedError?: AppErrorInfo;
  turnPersistedErrorOnly: boolean;
  turnProtocolPath?: string;
  turnRagSources?: RagSource[];
  turnRecordPayload: null | TurnRecordPayload;
  turnRecordRaw: null | Record<string, unknown>;
  turnRouteSource: null | string;
  turnSelectedSkillNames: string[];
  turnSelectedToolNames: string[];
  turnTerminationReason?: string;
}

export function createInitialAssistantTurnState(
  startIndex: number,
): AssistantTurnMergeState {
  return {
    contentParts: [],
    hasInterrupted: false,
    hasMemoryUpdated: false,
    hasPartial: false,
    startIndex,
    thinkingContentParts: [],
    toolCalls: [],
    turnActionButtonsUsed: false,
    turnAgentAvatar: null,
    turnAgentDescription: null,
    turnAgentId: null,
    turnAgentName: null,
    turnContextDiagnosticsRaw: null,
    turnContextSources: [],
    turnCreatedAt: null,
    turnLastRunSummaryRaw: null,
    turnModelName: null,
    turnPersistedErrorOnly: false,
    turnRecordPayload: null,
    turnRecordRaw: null,
    turnRouteSource: null,
    turnSelectedSkillNames: [],
    turnSelectedToolNames: [],
  };
}
