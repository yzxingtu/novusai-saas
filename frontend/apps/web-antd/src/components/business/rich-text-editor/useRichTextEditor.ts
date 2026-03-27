/**
 * Platform-level rich text editor composable
 * / 平台级富文本编辑器 composable
 */

import type { AnyExtension, JSONContent } from '@tiptap/core';

import type { RichTextEditorSetContentOptions } from './types';

import { onBeforeUnmount, ref } from 'vue';

import { useEditor } from '@tiptap/vue-3';

import { buildExtensions } from './extensions';
import { createEditorInstanceId } from './sourceEditorRegistry';

export interface UseRichTextEditorOptions {
  content?: JSONContent | null;
  editable?: boolean;
  autofocus?: boolean;
  placeholder?: string;
  extensions?: AnyExtension[];
  handlePaste?: (
    view: unknown,
    event: ClipboardEvent,
    slice: unknown,
  ) => boolean;
  handleDrop?: (
    view: unknown,
    event: DragEvent,
    slice: unknown,
    moved: boolean,
  ) => boolean;
  onUpdate?: (json: JSONContent, text: string, wordCount: number) => void;
}

function countWords(text: string): number {
  let wc = 0;
  let inWord = false;
  for (const ch of text) {
    const code = ch.codePointAt(0) ?? 0;
    if (
      (code >= 19_968 && code <= 40_959) ||
      (code >= 13_312 && code <= 19_903)
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
  const revision = ref(0);
  const editorInstanceId = createEditorInstanceId();

  let _updateTimer: null | ReturnType<typeof setTimeout> = null;
  const UPDATE_DEBOUNCE_MS = 300;

  function syncMetrics(text: string) {
    wordCount.value = countWords(text);
    characterCount.value = text.replaceAll(/\s/g, '').length;
  }

  function getRevision() {
    return revision.value;
  }

  function emitEditorUpdate() {
    const ed = editor.value;
    if (!ed) return;

    const json = ed.getJSON();
    const text = ed.getText();
    syncMetrics(text);

    if (options.onUpdate) {
      options.onUpdate(json, text, wordCount.value);
    }
  }

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
      ...(options.handlePaste
        ? { handlePaste: options.handlePaste as never }
        : {}),
      ...(options.handleDrop
        ? { handleDrop: options.handleDrop as never }
        : {}),
    },
    onCreate: ({ editor: ed }) => {
      syncMetrics(ed.getText());
    },
    onTransaction: ({ editor: ed, transaction }) => {
      if (!transaction.docChanged) {
        return;
      }
      revision.value += 1;
      syncMetrics(ed.getText());
    },
    onUpdate: () => {
      if (_updateTimer) clearTimeout(_updateTimer);
      _updateTimer = setTimeout(() => {
        emitEditorUpdate();
      }, UPDATE_DEBOUNCE_MS);
    },
  });

  onBeforeUnmount(() => {
    if (_updateTimer) clearTimeout(_updateTimer);
    editor.value?.destroy();
  });

  function setContent(
    content: JSONContent | null | string,
    setContentOptions: RichTextEditorSetContentOptions = {},
  ) {
    if (!editor.value || content === null || content === undefined) return;

    const emitUpdate = setContentOptions.emitUpdate !== false;
    if (_updateTimer) {
      clearTimeout(_updateTimer);
      _updateTimer = null;
    }

    editor.value.commands.setContent(
      content,
      emitUpdate ? undefined : { emitUpdate: false },
    );

    if (!emitUpdate) {
      revision.value += 1;
      emitEditorUpdate();
    }
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
    revision,
    editorInstanceId,
    setContent,
    getRevision,
    getJSON,
    getText,
    getHTML,
    focus,
  };
}
