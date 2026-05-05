import type { App } from 'vue';

import type {
  MountedEditor,
  MountOptions,
  RichTextEditorExposed,
  RichTextEditorSetContentOptions,
} from './types';

import { createApp, defineComponent, h } from 'vue';

import { i18n } from '@vben/locales';

import RichTextEditor from './RichTextEditor.vue';

export { RichTextEditor };
export type {
  AttachmentInfo,
  MountedEditor,
  MountOptions,
  RichTextEditorApplyContentOptions,
  RichTextEditorExposed,
  RichTextEditorProps,
  RichTextEditorSelectionSnapshot,
  RichTextEditorSetContentOptions,
} from './types';
export { useRichTextEditor } from './useRichTextEditor';

/**
 * Mount a RichTextEditor imperatively to any DOM element or CSS selector.
 * / 将 RichTextEditor 以命令式方式挂载到任意 DOM 元素或 CSS 选择器。
 */
export function mountRichTextEditor(
  target: HTMLElement | string,
  options: MountOptions = {},
): MountedEditor {
  const container =
    typeof target === 'string' ? document.querySelector(target) : target;
  if (!container) {
    throw new Error(`mountRichTextEditor: target "${target}" not found in DOM`);
  }
  let editorRef: null | RichTextEditorExposed = null;
  let app: App | null = null;

  const propsObj: Record<string, unknown> = {
    modelValue: options.content,
    mode: options.mode || 'compact',
    'onUpdate:modelValue': () => {
      if (options.onChange && editorRef) {
        const json = editorRef.getJSON?.();
        const html = editorRef.getHTML?.() as string;
        const text = editorRef.getText?.() as string;
        options.onChange(json as never, html, text);
      }
    },
  };

  if (options.defaultValue !== undefined)
    propsObj.defaultValue = options.defaultValue;
  if (options.toolbar !== undefined) propsObj.toolbar = options.toolbar;
  if (options.upload !== undefined) propsObj.upload = options.upload;
  if (options.editable !== undefined) propsObj.editable = options.editable;
  if (options.placeholder !== undefined)
    propsObj.placeholder = options.placeholder;
  if (options.minHeight !== undefined) propsObj.minHeight = options.minHeight;
  if (options.maxHeight !== undefined) propsObj.maxHeight = options.maxHeight;
  if (options.autofocus !== undefined) propsObj.autofocus = options.autofocus;
  if (options.extensions !== undefined)
    propsObj.extensions = options.extensions;
  if (options.aiWriting !== undefined) propsObj.aiWriting = options.aiWriting;
  const Wrapper = defineComponent({
    setup() {
      return () =>
        h(RichTextEditor, {
          ...propsObj,
          ref: (r: unknown) => {
            editorRef = r as null | RichTextEditorExposed;
            if (r && options.onReady) {
              const inst = r as Record<string, unknown>;
              if (inst.editor) {
                options.onReady(inst.editor as never);
              }
            }
          },
        });
    },
  });

  app = createApp(Wrapper);
  app.use(i18n);
  app.mount(container as Element);

  return {
    get editorInstanceId() {
      return editorRef?.editorInstanceId ?? '';
    },
    getRevision: () => editorRef?.getRevision() ?? 0,
    getJSON: () => (editorRef?.getJSON?.() as never) ?? null,
    getHTML: () => (editorRef?.getHTML?.() as string) ?? '',
    getText: () => (editorRef?.getText?.() as string) ?? '',
    getSelectionSnapshot: () =>
      editorRef?.getSelectionSnapshot?.() ?? {
        afterText: '',
        beforeText: '',
        empty: true,
        from: 0,
        revision: 0,
        selectedText: '',
        to: 0,
      },
    setContent: (
      content,
      setContentOptions?: RichTextEditorSetContentOptions,
    ) => editorRef?.setContent?.(content as never, setContentOptions),
    applyContent: (content, applyOptions) =>
      editorRef?.applyContent?.(content, applyOptions),
    focus: () => editorRef?.focus?.(),
    destroy: () => {
      if (app) {
        app.unmount();
        app = null;
        editorRef = null;
      }
    },
  };
}
