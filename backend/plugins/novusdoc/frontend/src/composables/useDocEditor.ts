/**
 * NovusDoc 编辑器 composable
 *
 * 初始化 Tiptap editor 实例，管理生命周期和事件
 */

import { ref, onBeforeUnmount, watch } from 'vue'
import { useEditor } from '@tiptap/vue-3'
import type { AnyExtension, Editor, JSONContent } from '@tiptap/core'
import { getAllExtensions } from '../extensions'

export interface UseDocEditorOptions {
  content?: JSONContent | null
  editable?: boolean
  autofocus?: boolean
  extraExtensions?: AnyExtension[]
  onUpdate?: (json: JSONContent, text: string, wordCount: number) => void
}

export function useDocEditor(options: UseDocEditorOptions = {}) {
  const wordCount = ref(0)
  const characterCount = ref(0)

  // F16: 性能优化 — onUpdate 中避免同步调用 getJSON()/getText()
  // 使用 requestIdleCallback 延迟字数统计，减少长文档输入卡顿
  let _updateTimer: ReturnType<typeof setTimeout> | null = null
  const UPDATE_DEBOUNCE_MS = 300

  const editor = useEditor({
    extensions: [...getAllExtensions(), ...(options.extraExtensions || [])],
    content: options.content || { type: 'doc', content: [{ type: 'paragraph' }] },
    editable: options.editable !== false,
    autofocus: options.autofocus ? 'end' : false,
    onUpdate: ({ editor: ed }) => {
      // 节流：高频输入时只在最后一次变更后执行
      if (_updateTimer) clearTimeout(_updateTimer)
      _updateTimer = setTimeout(() => {
        const json = ed.getJSON()
        const text = ed.getText()

        // 字数统计：中文按字符数，英文按空格分词，取较大值
        const storage = ed.storage.characterCount
        const engWords = storage?.words?.() ?? 0
        const chars = storage?.characters?.() ?? text.replace(/\s/g, '').length
        wordCount.value = Math.max(engWords, chars > engWords * 3 ? chars : engWords)
        characterCount.value = chars

        if (options.onUpdate) {
          options.onUpdate(json, text, wordCount.value)
        }
      }, UPDATE_DEBOUNCE_MS)
    },
  })

  onBeforeUnmount(() => {
    editor.value?.destroy()
  })

  function setContent(json: JSONContent | null) {
    if (editor.value && json) {
      editor.value.commands.setContent(json)
    }
  }

  function getJSON(): JSONContent | null {
    return editor.value?.getJSON() ?? null
  }

  function getText(): string {
    return editor.value?.getText() ?? ''
  }

  function getHTML(): string {
    return editor.value?.getHTML() ?? ''
  }

  function focus() {
    editor.value?.commands.focus()
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
  }
}
