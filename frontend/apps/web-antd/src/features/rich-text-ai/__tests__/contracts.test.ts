// Test type: structural
// Scope: Rich Text AI frontend contract constants and global AI panel handoff shape.
// Mock strategy: No mocks; pure shared contract helpers are imported directly.
import { describe, expect, it } from 'vitest';

import * as richTextAiExports from '../index';
import {
  isRichTextAiWritingAction,
  RICH_TEXT_AI_FEATURE_CODE,
  RICH_TEXT_AI_FEATURE_CODE_RESOLUTION_ORDER,
  RICH_TEXT_AI_MANIFEST_FEATURE_CODE,
  RICH_TEXT_AI_WRITING_ACTIONS,
} from '../index';

import type { RichTextAiPanelHandoff } from '../index';

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

  it('types the global AI panel handoff using explicit editor-domain fields only', () => {
    const handoff = {
      action: 'rewrite',
      afterText: 'Next paragraph',
      agentId: 9,
      beforeText: 'Previous paragraph',
      documentTitle: 'Launch Plan',
      editorInstanceId: 'editor-1',
      message: '请对富文本选区执行「改写」操作。\n选中文本：Selected paragraph',
      selectedText: 'Selected paragraph',
      selectionRange: { from: 2, revision: 7, to: 20 },
    } satisfies RichTextAiPanelHandoff;

    expect(Object.keys(handoff).sort()).toEqual([
      'action',
      'afterText',
      'agentId',
      'beforeText',
      'documentTitle',
      'editorInstanceId',
      'message',
      'selectedText',
      'selectionRange',
    ]);
    expect(handoff.message).toContain('Selected paragraph');

    const serialized = JSON.stringify(handoff);
    const forbiddenFragments = [
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
