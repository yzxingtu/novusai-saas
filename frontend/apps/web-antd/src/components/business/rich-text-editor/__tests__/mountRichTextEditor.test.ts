// @vitest-environment happy-dom
import { describe, expect, it, vi } from 'vitest';

import { mountRichTextEditor } from '../index';

vi.mock('@vben/locales', () => ({
  i18n: {
    install: () => {},
  },
}));

vi.mock('../RichTextEditor.vue', () => ({
  default: {
    name: 'RichTextEditorStub',
    template: '<div class="rich-text-editor-stub"></div>',
  },
}));

vi.mock('../document-page-ai', () => ({
  registerRichTextDocumentPageAI: vi.fn(),
  waitForRichTextEditorOperations: vi.fn(),
}));

vi.mock('../sourceEditorRegistry', () => ({
  registerSourceEditor: vi.fn(),
  resolveSourceEditor: vi.fn(),
  unregisterSourceEditor: vi.fn(),
}));

describe('mountRichTextEditor', () => {
  it('throws when ai is explicitly enabled without a pageKey', () => {
    const container = document.createElement('div');
    document.body.append(container);

    expect(() =>
      mountRichTextEditor(container, {
        ai: true,
      }),
    ).toThrowError(
      'mountRichTextEditor: pageKey is required when ai=true for RichTextEditor',
    );
  });
});
