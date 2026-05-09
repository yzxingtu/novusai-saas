// Test type: behavioral
// Verifies: kernel turn-flow state filters runtime diagnostics out of evidence,
// answer source chips, and retrieval source counts.
// Mock strategy: i18n only; buildTurnFlowState runs real projection logic.
import type { ChatMessage } from '#/types/ai-chat';

import { describe, expect, it, vi } from 'vitest';

import { buildTurnFlowState } from '../TurnFlowState';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

describe('buildTurnFlowState', () => {
  it('does not select title-only runtime context evidence for provider-failed turns', () => {
    const state = buildTurnFlowState({
      clientKey: 'conversation-2340-provider-failure',
      completionReason: 'provider_unavailable',
      content: '我先把已完成部分整理给你：direct_reply。',
      role: 'assistant',
      turnFlow: {
        answerCard: {
          sourceChipIds: ['evidence_1', 'evidence_2', 'evidence_3'],
          summary: 'Connection error.',
        },
        completionReason: 'provider_unavailable',
        errorSurface: {
          errorType: 'untrusted_final_output_source',
          message: 'Connection error.',
        },
        evidence: [
          { id: 'evidence_1', kind: 'knowledge_base', title: 'skill_resolver' },
          { id: 'evidence_2', kind: 'memory', title: 'long_term_memory' },
          { id: 'evidence_3', kind: 'knowledge_base', title: 'gpt-5.5' },
        ],
        failureKind: 'provider_unavailable',
        finalStageStatus: 'error',
        timeline: [
          {
            id: 'retrieval',
            metrics: { source_count: 3 },
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
      turnOutcome: 'partial',
    } as ChatMessage);

    expect(state.evidence).toEqual([]);
    expect(state.selectedEvidence).toEqual([]);
    expect(state.hiddenEvidenceCount).toBe(0);
    expect(state.flow.answerCard?.sourceChipIds).toEqual([]);
    const retrievalStage = state.timeline.find(
      (stage) => stage.type === 'retrieval',
    );
    expect(retrievalStage?.status).toBe('skipped');
    expect(retrievalStage?.metrics?.source_count).toBe(0);
  });

  it('uses knowledge base name in selected evidence labels when RAG evidence is present', () => {
    const state = buildTurnFlowState({
      clientKey: 'conversation-kb-evidence',
      content: 'NovusAI 平台支持知识库 RAG。',
      role: 'assistant',
      turnFlow: {
        answerCard: {
          sourceChipIds: ['kb-chunk-301'],
          summary: 'NovusAI 平台支持知识库 RAG。',
        },
        evidence: [
          {
            chunkId: 301,
            docId: 21,
            docName: 'test_doc.txt',
            id: 'kb-chunk-301',
            kind: 'knowledge_base',
            knowledgeBaseId: 1,
            knowledgeBaseName: '测试知识库',
            score: 0.82,
            snippet: 'NovusAI 平台支持知识库 RAG。',
            sourceKind: 'formal_kb',
            title: 'test_doc.txt',
          },
        ],
        timeline: [
          {
            id: 'retrieval',
            sourceRefs: ['kb-chunk-301'],
            status: 'completed',
            type: 'retrieval',
          },
        ],
      },
    } as ChatMessage);

    expect(state.selectedEvidence).toHaveLength(1);
    expect(state.selectedEvidence[0]?.label).toBe('测试知识库 / test_doc.txt');
    expect(state.evidence[0]?.knowledgeBaseName).toBe('测试知识库');
  });
});
