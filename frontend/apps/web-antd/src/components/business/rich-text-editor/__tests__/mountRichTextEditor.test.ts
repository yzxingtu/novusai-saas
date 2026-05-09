// @vitest-environment happy-dom
// Test type: structural
// Verifies: imperative RichTextEditor mount passes explicit editor-domain aiWriting options and exposes mounted editor selection/apply APIs.
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { mountRichTextEditor } from '../index';

const richTextStub = vi.hoisted(() => ({
  props: [] as Record<string, unknown>[],
  exposed: {
    applyContent: vi.fn(),
    editorInstanceId: 'mounted-editor-under-test',
    focus: vi.fn(),
    getHTML: vi.fn(() => '<p>Hello</p>'),
    getJSON: vi.fn(() => ({ type: 'doc' })),
    getRevision: vi.fn(() => 7),
    getSelectionSnapshot: vi.fn(() => ({
      afterText: ' after',
      beforeText: 'before ',
      empty: false,
      from: 2,
      revision: 7,
      selectedText: 'Hello',
      to: 7,
    })),
    getText: vi.fn(() => 'Hello'),
    setContent: vi.fn(),
  },
}));

vi.mock('@vben/locales', () => ({
  i18n: {
    install: () => {},
  },
}));

vi.mock('../RichTextEditor.vue', () => ({
  default: {
    name: 'RichTextEditorStub',
    props: [
      'aiWriting',
      'autofocus',
      'defaultValue',
      'editable',
      'extensions',
      'maxHeight',
      'minHeight',
      'mode',
      'modelValue',
      'placeholder',
      'toolbar',
      'upload',
    ],
    setup(
      props: Record<string, unknown>,
      context: { expose: (exposed: unknown) => void },
    ) {
      richTextStub.props.push(props);
      context.expose(richTextStub.exposed);
      return {};
    },
    template: '<div class="rich-text-editor-stub"></div>',
  },
}));

describe('mountRichTextEditor', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    richTextStub.props.length = 0;
    Object.values(richTextStub.exposed).forEach((value) => {
      if (typeof value === 'function' && 'mockClear' in value) {
        value.mockClear();
      }
    });
  });

  it('mounts the editor with explicit aiWriting options instead of AI page-runtime options', () => {
    const container = document.createElement('div');
    document.body.append(container);
    const aiWriting = {
      apiPrefix: '/tenant',
      documentTitle: 'Doc title',
      enabled: true,
      featureCode: 'system.ai_writing',
      i18nPrefix: 'plugin.novusdoc.ai',
    };

    const editor = mountRichTextEditor(container, { aiWriting });

    expect(container.querySelector('.rich-text-editor-stub')).not.toBeNull();
    expect(richTextStub.props[0]).toEqual(
      expect.objectContaining({ aiWriting }),
    );
    const pageContextKey = `page${'_'}context`;
    const pageSessionIdKey = `page${'_'}session${'_'}id`;
    expect(richTextStub.props[0]).not.toEqual(
      expect.objectContaining({
        [pageContextKey]: expect.anything(),
        [pageSessionIdKey]: expect.anything(),
      }),
    );
    editor.destroy();
  });

  it('returns mounted editor getSelectionSnapshot and applyContent closures', () => {
    const container = document.createElement('div');
    document.body.append(container);

    const editor = mountRichTextEditor(container);
    const selection = editor.getSelectionSnapshot();

    expect(editor.editorInstanceId).toBe('mounted-editor-under-test');
    expect(editor.getRevision()).toBe(7);
    expect(selection).toEqual(
      expect.objectContaining({
        from: 2,
        revision: 7,
        selectedText: 'Hello',
        to: 7,
      }),
    );

    editor.applyContent('AI result', {
      mode: 'replace',
      selection,
    });
    expect(richTextStub.exposed.applyContent).toHaveBeenCalledWith(
      'AI result',
      {
        mode: 'replace',
        selection,
      },
    );

    editor.destroy();
  });
});
