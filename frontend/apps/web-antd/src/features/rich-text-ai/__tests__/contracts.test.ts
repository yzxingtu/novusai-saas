// Test type: structural
// Scope: Rich Text AI frontend contract constants and editor-domain operation payload shape.
// Mock strategy: No mocks; pure shared contract helpers are imported directly.
import type { RichTextAiOperationPayload } from '#/api/shared/rich-text-ai';

import { describe, expect, it } from 'vitest';

import * as richTextAiExports from '../index';
import {
  isRichTextAiWritingAction,
  RICH_TEXT_AI_FEATURE_CODE,
  RICH_TEXT_AI_FEATURE_CODE_RESOLUTION_ORDER,
  RICH_TEXT_AI_MANIFEST_FEATURE_CODE,
  RICH_TEXT_AI_WRITING_ACTIONS,
} from '../index';

describe('rich text ai structural contract', () => {
  it('keeps feature codes aligned with the single system writing assignment', () => {
    expect(RICH_TEXT_AI_MANIFEST_FEATURE_CODE).toBe('rich_text_ai');
    expect(RICH_TEXT_AI_FEATURE_CODE).toBe('system.ai_writing');
    expect([...RICH_TEXT_AI_FEATURE_CODE_RESOLUTION_ORDER]).toEqual([
      'system.ai_writing',
    ]);
  });

  it('keeps the frontend action union aligned with global writing actions', () => {
    expect([...RICH_TEXT_AI_WRITING_ACTIONS]).toEqual([
      'continue',
      'insert',
      'rewrite',
      'optimize',
      'proofread',
      'translate',
      'summarize',
      'expand',
      'format',
      'custom',
      'chat',
    ]);

    expect(isRichTextAiWritingAction('insert')).toBe(true);
    expect(isRichTextAiWritingAction('format')).toBe(true);
    expect(isRichTextAiWritingAction('editor_replace_section')).toBe(false);
  });

  it('does not expose a local rich-text writing transport helper from the frontend contract', () => {
    const retiredTransportExport = `buildRichTextAi${'Writing'}Endpoint`;
    expect(retiredTransportExport in richTextAiExports).toBe(false);
  });

  it('does not expose retired editor-tool denylist helpers from the frontend contract', () => {
    expect('RETIRED_EDITOR_TOOL_PREFIXES' in richTextAiExports).toBe(false);
    expect('isRetiredEditorToolName' in richTextAiExports).toBe(false);
  });

  it('types editor-domain operation payloads without global panel or page-runtime fields', () => {
    const payload = {
      after_text: 'Next paragraph',
      before_text: 'Previous paragraph',
      document_id: 9,
      document_title: 'Launch Plan',
      document_type: 'novusdoc',
      history: [
        { content: 'Please review this selection.', role: 'user' },
        { content: 'I can suggest a tighter wording.', role: 'assistant' },
      ],
      instruction: 'Make the selected paragraph tighter.',
      selected_text: 'Selected paragraph',
      surface: 'rich_text_editor',
    } satisfies RichTextAiOperationPayload;

    expect(Object.keys(payload).toSorted()).toEqual([
      'after_text',
      'before_text',
      'document_id',
      'document_title',
      'document_type',
      'history',
      'instruction',
      'selected_text',
      'surface',
    ]);
    expect(payload.selected_text).toBe('Selected paragraph');
    expect(payload.history?.[1]).toEqual({
      content: 'I can suggest a tighter wording.',
      role: 'assistant',
    });

    const serialized = JSON.stringify(payload);
    const forbiddenFragments = [
      'agentId',
      'message',
      'openWithContext',
      `page${'_'}context`,
      `page${'_'}session`,
      `page${'_'}data`,
      `page${'_'}session${'_'}id`,
      `ui${'_'}action`,
      `pageop${'_'}action`,
      `/ai/${'writing'}`,
    ];
    for (const fragment of forbiddenFragments) {
      expect(serialized).not.toContain(fragment);
    }
  });
});
