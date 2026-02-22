/**
 * useRichEditor composable
 *
 * 封装 TipTap editor 实例与常用方法，方便业务页面集成。
 * 提供 getHTML/getJSON/setContent/focus/isEmpty 等 API。
 */
import { computed, type Ref } from 'vue';

import type { Editor } from '@tiptap/vue-3';

export interface UseRichEditorOptions {
  editor: Ref<Editor | undefined>;
}

export function useRichEditor({ editor }: UseRichEditorOptions) {
  const isEmpty = computed(() => {
    if (!editor.value) return true;
    return editor.value.isEmpty;
  });

  const wordCount = computed(() => {
    if (!editor.value) return 0;
    const text = editor.value.getText();
    return text.trim().split(/\s+/).filter(Boolean).length;
  });

  const characterCount = computed(() => {
    if (!editor.value) return 0;
    return editor.value.getText().length;
  });

  const isFocused = computed(() => {
    return editor.value?.isFocused ?? false;
  });

  function getHTML(): string {
    return editor.value?.getHTML() ?? '';
  }

  function getJSON(): Record<string, unknown> | null {
    return (editor.value?.getJSON() as Record<string, unknown>) ?? null;
  }

  function getText(): string {
    return editor.value?.getText() ?? '';
  }

  function setContent(content: string, emitUpdate = false) {
    editor.value?.commands.setContent(content, emitUpdate);
  }

  function clearContent(emitUpdate = false) {
    editor.value?.commands.clearContent(emitUpdate);
  }

  function focus(position: 'start' | 'end' | 'all' = 'end') {
    editor.value?.commands.focus(position);
  }

  function blur() {
    editor.value?.commands.blur();
  }

  function setEditable(editable: boolean) {
    editor.value?.setEditable(editable);
  }

  return {
    isEmpty,
    wordCount,
    characterCount,
    isFocused,
    getHTML,
    getJSON,
    getText,
    setContent,
    clearContent,
    focus,
    blur,
    setEditable,
  };
}
