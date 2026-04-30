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

describe('mountRichTextEditor', () => {
  it('mounts without requiring page-level AI context keys', () => {
    const container = document.createElement('div');
    document.body.append(container);

    const editor = mountRichTextEditor(container, { ai: true });

    expect(container.querySelector('.rich-text-editor-stub')).not.toBeNull();
    editor.destroy();
  });
});
