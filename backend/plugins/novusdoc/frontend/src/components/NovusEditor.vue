<script lang="ts" setup>
import { watch } from 'vue'
import { EditorContent } from '@tiptap/vue-3'
import { useDocEditor } from '../composables/useDocEditor'
import type { AnyExtension, JSONContent } from '@tiptap/core'

const props = defineProps<{
  content?: JSONContent | null
  editable?: boolean
  extraExtensions?: AnyExtension[]
}>()

const emit = defineEmits<{
  update: [json: JSONContent, text: string, wordCount: number]
}>()

const { editor, wordCount, characterCount, setContent, getJSON, getHTML, getText, focus } =
  useDocEditor({
    content: props.content,
    editable: props.editable,
    autofocus: true,
    extraExtensions: props.extraExtensions,
    onUpdate: (json, text, wc) => {
      emit('update', json, text, wc)
    },
  })

watch(() => props.editable, (val) => {
  if (editor.value) {
    editor.value.setEditable(val !== false)
  }
})

defineExpose({ editor, setContent, getJSON, getHTML, getText, focus, wordCount, characterCount })
</script>

<template>
  <div class="nd-editor-wrapper">
    <EditorContent v-if="editor" :editor="editor" class="nd-editor-content" />
  </div>
</template>
