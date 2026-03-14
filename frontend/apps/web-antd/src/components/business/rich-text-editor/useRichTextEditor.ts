/**
 * Platform-level rich text editor composable
 * / 平台级富文本编辑器 composable
 */

import type { AnyExtension, JSONContent } from '@tiptap/core';

import { onBeforeUnmount, ref } from 'vue';

import { useEditor } from '@tiptap/vue-3';

import { buildExtensions } from './extensions';

export interface UseRichTextEditorOptions {
  content?: JSONContent | null;
  editable?: boolean;
  autofocus?: boolean;
  placeholder?: string;
  extensions?: AnyExtension[];
  handlePaste?: (view: unknown, event: ClipboardEvent, slice: unknown) => boolean;
  handleDrop?: (view: unknown, event: DragEvent, slice: unknown, moved: boolean) => boolean;
  onUpdate?: (json: JSONContent, text: string, wordCount: number) => void;
}

function countWords(text: string): number {
  let wc = 0;
  let inWord = false;
  for (const ch of text) {
    const code = ch.codePointAt(0) ?? 0;
    if (
      (code >= 0x4e00 && code <= 0x9fff) ||
      (code >= 0x3400 && code <= 0x4dbf)
    ) {
      wc++;
      inWord = false;
    } else if (/\w/.test(ch)) {
      if (!inWord) {
        wc++;
        inWord = true;
      }
    } else {
      inWord = false;
    }
  }
  return wc;
}

export function useRichTextEditor(options: UseRichTextEditorOptions = {}) {
  const wordCount = ref(0);
  const characterCount = ref(0);

  let _updateTimer: ReturnType<typeof setTimeout> | null = null;
  const UPDATE_DEBOUNCE_MS = 300;

  const baseExtensions = [
    ...buildExtensions({ placeholder: options.placeholder }),
    ...(options.extensions || []),
  ];
  const editor = useEditor({
    extensions: baseExtensions,
    content: options.content || {
      type: 'doc',
      content: [{ type: 'paragraph' }],
    },
    editable: options.editable !== false,
    autofocus: options.autofocus ? 'end' : false,
    editorProps: {
      ...(options.handlePaste ? { handlePaste: options.handlePaste as never } : {}),
      ...(options.handleDrop ? { handleDrop: options.handleDrop as never } : {}),
    },
    onUpdate: ({ editor: ed }) => {
      if (_updateTimer) clearTimeout(_updateTimer);
      _updateTimer = setTimeout(() => {
        const json = ed.getJSON();
        const text = ed.getText();

        wordCount.value = countWords(text);
        characterCount.value = text.replace(/\s/g, '').length;

        if (options.onUpdate) {
          options.onUpdate(json, text, wordCount.value);
        }
      }, UPDATE_DEBOUNCE_MS);
    },
  });

  onBeforeUnmount(() => {
    if (_updateTimer) clearTimeout(_updateTimer);
    editor.value?.destroy();
  });

  function setContent(content: JSONContent | string | null) {
    if (!editor.value || !content) return;
    editor.value.commands.setContent(content);
  }

  function getJSON(): JSONContent | null {
    return editor.value?.getJSON() ?? null;
  }

  function getText(): string {
    return editor.value?.getText() ?? '';
  }

  function getHTML(): string {
    return editor.value?.getHTML() ?? '';
  }

  function focus() {
    editor.value?.commands.focus();
  }

  return {
    editor,
    wordCount,
    characterCount,
    setContent,
    getJSON,
    getText,
    getHTML,
    focus,
  };
}
