// Test type: behavioral
// Verifies: default rich text context-menu behavior and apply modes.
// Mock strategy: No mocks; behavior is pure template selection and filtering.
import { describe, expect, it } from 'vitest';

import {
  DEFAULT_RICH_TEXT_AI_ACTION_TEMPLATES,
  DEFAULT_RICH_TEXT_AI_FORMAT_TEMPLATES,
  getRichTextAiActionTemplate,
  getRichTextAiContextMenuActions,
  groupRichTextAiActionsByKind,
} from '../index';

describe('rich text ai action template behavior', () => {
  it('exposes right-click actions for editing text while keeping chat out of the default context menu', () => {
    const actions = getRichTextAiContextMenuActions();

    expect(actions.map((action) => action.action)).toEqual([
      'continue',
      'rewrite',
      'insert',
      'format',
      'optimize',
      'proofread',
      'translate',
      'summarize',
      'expand',
      'custom',
    ]);
    expect(actions.every((action) => action.visibleInContextMenu)).toBe(true);
    expect(actions.some((action) => action.action === 'chat')).toBe(false);

    const continueAction = getRichTextAiActionTemplate('continue');
    expect(continueAction.defaultApplyMode).toBe('insert_after_selection');
    expect(continueAction.requiresSelection).toBe(false);

    const insertAction = getRichTextAiActionTemplate('insert');
    expect(insertAction.defaultApplyMode).toBe('insert_at_cursor');
    expect(insertAction.supportsCustomInstruction).toBe(true);

    const formatAction = getRichTextAiActionTemplate('format');
    expect(formatAction.operationKind).toBe('format');
    expect(formatAction.requiresSelection).toBe(true);
    expect(formatAction.supportsFormatInstruction).toBe(true);

    const rewriteAction = getRichTextAiActionTemplate('rewrite');
    expect(rewriteAction.defaultApplyMode).toBe('replace_selection');
    expect(rewriteAction.requiresSelection).toBe(true);
    expect(rewriteAction.supportsFormatInstruction).toBe(true);
  });

  it('filters enabled actions through the canonical action list', () => {
    const visible = getRichTextAiContextMenuActions({
      enabledActions: ['chat', 'rewrite', 'continue', 'insert', 'format'],
    });
    const visibleWithAssist = getRichTextAiContextMenuActions({
      enabledActions: ['chat', 'rewrite', 'continue', 'insert', 'format'],
      includeAssistActions: true,
    });

    expect(visible.map((action) => action.action)).toEqual([
      'continue',
      'rewrite',
      'insert',
      'format',
    ]);
    expect(visibleWithAssist.map((action) => action.action)).toEqual([
      'continue',
      'rewrite',
      'insert',
      'format',
      'chat',
    ]);
  });

  it('keeps default action groups and format presets concrete enough for configuration UI', () => {
    const groups = groupRichTextAiActionsByKind(
      DEFAULT_RICH_TEXT_AI_ACTION_TEMPLATES,
    );

    expect(groups.map((group) => group.kind)).toEqual([
      'insert',
      'transform',
      'format',
      'translate',
      'summarize',
      'assist',
    ]);
    expect(
      groups
        .find((group) => group.kind === 'transform')
        ?.actions.map((action) => action.action),
    ).toEqual(['rewrite', 'optimize', 'proofread', 'expand', 'custom']);
    expect(
      groups
        .find((group) => group.kind === 'insert')
        ?.actions.map((action) => action.action),
    ).toEqual(['continue', 'insert']);
    expect(
      DEFAULT_RICH_TEXT_AI_FORMAT_TEMPLATES.map((item) => item.preset),
    ).toEqual([
      'preserve_structure',
      'plain_text',
      'bullet_list',
      'structured_sections',
    ]);
  });
});
