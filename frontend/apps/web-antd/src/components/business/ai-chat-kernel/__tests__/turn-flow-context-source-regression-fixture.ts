import type { ChatMessage } from '#/types/ai-chat';

import { createApp, h, nextTick } from 'vue';

import ChatMessageKernel from '../ChatMessageKernel.vue';
import { buildTurnFlowState } from '../TurnFlowState';

interface TurnFlowRegressionWindowState {
  answerChipCount: number;
  evidenceCount: number;
  finalStageStatus: null | string;
  retrievalSourceCount: null | number;
  retrievalStatus: null | string;
  selectedEvidenceCount: number;
}

declare global {
  interface Window {
    __turnFlowRegressionReady?: boolean;
    __turnFlowRegressionState?: TurnFlowRegressionWindowState;
  }
}

export async function mountTurnFlowContextSourceRegressionFixture(
  target: Element,
) {
  const pollutedMessage = {
    clientKey: 'conversation-2340-provider-failure',
    completionReason: 'provider_unavailable',
    content: '',
    requestFailedRetry: true,
    role: 'assistant',
    streaming: false,
    turnOutcome: 'partial',
    turnFlow: {
      answerCard: {
        sections: [
          {
            content: 'Connection error.',
            title: 'Answer',
          },
        ],
        sourceChipIds: ['evidence_1', 'evidence_2', 'evidence_3'],
        summary: 'Connection error.',
      },
      completionReason: 'provider_unavailable',
      errorSurface: {
        errorType: 'untrusted_final_output_source',
        failureKind: 'provider_unavailable',
        message: 'Connection error.',
      },
      evidence: [
        {
          id: 'evidence_1',
          kind: 'knowledge_base',
          title: 'skill_resolver',
        },
        {
          id: 'evidence_2',
          kind: 'memory',
          title: 'long_term_memory',
        },
        {
          id: 'evidence_3',
          kind: 'knowledge_base',
          title: 'gpt-5.5',
        },
      ],
      failureKind: 'provider_unavailable',
      finalStageStatus: 'error',
      timeline: [
        {
          id: 'retrieval',
          metrics: {
            source_count: 3,
          },
          sourceRefs: ['evidence_1', 'evidence_2', 'evidence_3'],
          status: 'completed',
          summary: 'Retrieved 3 sources',
          type: 'retrieval',
        },
        {
          id: 'failed',
          status: 'error',
          summary: 'provider_unavailable',
          type: 'failed',
        },
      ],
      turnOutcome: 'partial',
    },
  } as ChatMessage;

  const state = buildTurnFlowState(pollutedMessage);
  const retrievalStage = state.timeline.find(
    (stage) => stage.type === 'retrieval',
  );
  const rawRetrievalSourceCount = retrievalStage?.metrics?.source_count;
  const retrievalSourceCount =
    typeof rawRetrievalSourceCount === 'number'
      ? rawRetrievalSourceCount
      : null;

  window.__turnFlowRegressionState = {
    answerChipCount: state.flow.answerCard?.sourceChipIds?.length ?? 0,
    evidenceCount: state.evidence.length,
    finalStageStatus: state.flow.finalStageStatus ?? null,
    retrievalSourceCount,
    retrievalStatus: retrievalStage?.status ?? null,
    selectedEvidenceCount: state.selectedEvidence.length,
  };

  createApp({
    render() {
      return h(ChatMessageKernel, {
        compact: false,
        msg: pollutedMessage,
        state,
      });
    },
  }).mount(target);

  await nextTick();
  window.__turnFlowRegressionReady = true;
}
