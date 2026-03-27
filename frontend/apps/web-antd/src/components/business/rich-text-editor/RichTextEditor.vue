<script lang="ts" setup>
import type { JSONContent } from '@tiptap/core';

import type { RichTextEditorProps } from './types';

import { computed, getCurrentInstance, onBeforeUnmount, ref, watch } from 'vue';

import { $t } from '@vben/locales';

import { EditorContent } from '@tiptap/vue-3';

import AIBubbleMenu from './ai/AIBubbleMenu.vue';
import { launchRichTextTask } from './ai/launchRichTextTask';
import {
  registerSourceEditor,
  updateSourceEditorRevision,
} from './sourceEditorRegistry';
import EditorToolbar from './toolbar/EditorToolbar.vue';
import MiniToolbar from './toolbar/MiniToolbar.vue';
import { useEditorPageOps } from './useEditorPageOps';
import { handleImageDrop, handleImagePaste } from './useEditorUpload';
import { useRichTextEditor } from './useRichTextEditor';

import './rich-text-editor.css';

const props = withDefaults(defineProps<RichTextEditorProps>(), {
  mode: 'compact',
  toolbar: true,
  ai: true,
  upload: true,
  editable: true,
  autofocus: false,
});

const emit = defineEmits<{
  change: [json: JSONContent, html: string, text: string];
  'update:modelValue': [value: JSONContent | null];
}>();

const explicitProps = getCurrentInstance()?.vnode.props;
const aiExplicitlyEnabled =
  props.ai === true &&
  !!explicitProps &&
  Object.prototype.hasOwnProperty.call(explicitProps, 'ai');

if (aiExplicitlyEnabled && !props.pageKey) {
  throw new Error('RichTextEditor: pageKey is required when ai=true');
}

const isFull = computed(() => props.mode === 'full');

const minH = computed(() => {
  if (props.minHeight)
    return typeof props.minHeight === 'number'
      ? `${props.minHeight}px`
      : props.minHeight;
  return isFull.value ? '400px' : '150px';
});

const maxH = computed(() => {
  if (props.maxHeight)
    return typeof props.maxHeight === 'number'
      ? `${props.maxHeight}px`
      : props.maxHeight;
  return undefined;
});

const {
  editor,
  wordCount,
  characterCount,
  revision,
  setContent,
  getJSON,
  getHTML,
  getText,
  focus,
  editorInstanceId,
  getRevision,
} = useRichTextEditor({
  content: props.modelValue || props.defaultValue || undefined,
  editable: props.editable,
  autofocus: props.autofocus,
  placeholder: props.placeholder || $t('common.editorPlaceholder'),
  extensions: props.extensions,
  handlePaste: (_view: unknown, event: ClipboardEvent) => {
    if (props.upload) {
      const ed = editor.value;
      if (ed) return handleImagePaste(ed, event);
    }
    return false;
  },
  handleDrop: (
    view: unknown,
    event: DragEvent,
    _slice: unknown,
    moved: boolean,
  ) => {
    if (props.upload && !moved) {
      const ed = editor.value;
      if (ed) {
        const coords = { left: event.clientX, top: event.clientY };
        const pos =
          (
            view as {
              posAtCoords: (c: {
                left: number;
                top: number;
              }) => null | { pos: number };
            }
          ).posAtCoords(coords)?.pos ?? 0;
        return handleImageDrop(ed, event, pos);
      }
    }
    return false;
  },
  onUpdate: (json, text) => {
    emit('update:modelValue', json);
    emit('change', json, getHTML(), text);
  },
});

const aiEntryEnabled = computed(
  () => props.ai !== false && !!props.pageKey && !!editor.value,
);

watch(
  () => props.modelValue,
  (val) => {
    if (!editor.value) return;
    const currentJson = JSON.stringify(editor.value.getJSON());
    const newJson = JSON.stringify(val);
    if (currentJson !== newJson && val) {
      setContent(val);
      if (sourceMode.value) {
        sourceCode.value = getHTML();
      }
    }
  },
);

watch(
  () => props.editable,
  (val) => {
    if (editor.value) editor.value.setEditable(val !== false);
  },
);

useEditorPageOps(editor, {
  editable: computed(() => props.editable !== false),
  enabled: computed(() => props.ai !== false && !!editor.value),
  pageKey: computed(() => props.pageKey),
});

const sourceMode = ref(false);
const sourceCode = ref('');
let unregisterSourceEditorEntry: (() => void) | null = null;

function cleanupSourceEditorRegistration() {
  if (!unregisterSourceEditorEntry) return;
  unregisterSourceEditorEntry();
  unregisterSourceEditorEntry = null;
}

watch(
  [editor, () => props.pageKey],
  ([editorInstance, pageKey]) => {
    cleanupSourceEditorRegistration();
    if (!editorInstance || !pageKey) return;

    unregisterSourceEditorEntry = registerSourceEditor({
      pageKey,
      editorInstanceId,
      revision: getRevision(),
      getRevision,
      isMounted: () => !!editor.value,
      getText,
      getHTML,
      focus,
      replaceRange: (from, to, content) => {
        if (!editor.value) return false;
        editor.value
          .chain()
          .focus()
          .deleteRange({ from, to })
          .insertContent(content, {
            parseOptions: { preserveWhitespace: false },
          })
          .run();
        return true;
      },
      insertAfterRange: (_from, to, content) => {
        if (!editor.value) return false;
        editor.value.commands.insertContentAt(to, content, {
          parseOptions: { preserveWhitespace: false },
        });
        return true;
      },
      appendToEnd: (content) => {
        if (!editor.value) return false;
        const end = editor.value.state.doc.content.size;
        editor.value.commands.insertContentAt(end, content, {
          parseOptions: { preserveWhitespace: false },
        });
        return true;
      },
      undo: () => {
        if (!editor.value) return false;
        return editor.value.chain().focus().undo().run();
      },
    });
  },
  { immediate: true },
);

watch(revision, (nextRevision) => {
  if (!props.pageKey) return;
  updateSourceEditorRevision(props.pageKey, editorInstanceId, nextRevision);
});

watch(sourceMode, (enabled) => {
  if (!enabled) return;
  sourceCode.value = getHTML();
});

onBeforeUnmount(() => {
  cleanupSourceEditorRegistration();
});

function toggleSourceMode() {
  if (!editor.value) return;
  if (sourceMode.value) {
    if (sourceCode.value !== getHTML()) {
      setContent(sourceCode.value, { emitUpdate: false });
    }
    sourceMode.value = false;
  } else {
    sourceCode.value = editor.value.getHTML();
    sourceMode.value = true;
  }
}

async function handleAiAction(feature: string) {
  if (!editor.value || !props.pageKey) return;
  await launchRichTextTask({
    editor: editor.value,
    editorInstanceId,
    feature,
    getRevision,
    pageKey: props.pageKey,
    contextTitle: props.contextTitle,
  });
}

function focusEditorEnd() {
  if (editor.value) {
    editor.value.commands.focus('end');
  }
}

defineExpose({
  editor,
  wordCount,
  characterCount,
  editorInstanceId,
  setContent,
  getRevision,
  getJSON,
  getHTML,
  getText,
  focus,
});
</script>

<template>
  <!-- Full mode -->
  <div v-if="isFull" class="rte-editor flex h-full flex-col">
    <EditorToolbar
      v-if="toolbar !== false"
      :editor="editor"
      :upload="upload"
      :source-mode="sourceMode"
      @toggle-source="toggleSourceMode"
    />

    <div class="flex min-h-0 flex-1">
      <!-- WYSIWYG view -->
      <div
        v-if="!sourceMode"
        class="flex flex-1 flex-col overflow-y-auto"
        :style="{ minHeight: minH }"
        @click.self="focusEditorEnd"
      >
        <div
          class="rte-content-area mx-auto flex w-full max-w-[760px] flex-1 flex-col p-4 md:px-8 md:py-6"
          @click.self="focusEditorEnd"
        >
          <EditorContent
            v-if="editor"
            :editor="editor"
            class="rte-editor-content flex flex-1 flex-col"
          />
        </div>
      </div>

      <!-- Source code view -->
      <textarea
        v-else
        v-model="sourceCode"
        class="rte-source-code flex-1 resize-none bg-background p-4 font-mono text-sm text-foreground outline-none"
        :style="{ minHeight: minH }"
        spellcheck="false"
      ></textarea>
    </div>

    <AIBubbleMenu
      v-if="aiEntryEnabled"
      :editor="editor"
      :loading="false"
      @action="handleAiAction"
    />

    <div
      class="flex items-center justify-between border-t border-border px-4 py-1.5 text-xs text-muted-foreground"
    >
      <span>{{ $t('common.wordCount') }}: {{ wordCount }}</span>
    </div>
  </div>

  <!-- Compact mode -->
  <div v-else class="rte-editor rte-compact">
    <MiniToolbar v-if="toolbar !== false" :editor="editor" :upload="upload" />

    <div
      class="overflow-y-auto px-3 py-2"
      :style="{ minHeight: minH, maxHeight: maxH }"
    >
      <EditorContent v-if="editor" :editor="editor" />
    </div>

    <AIBubbleMenu
      v-if="aiEntryEnabled"
      :editor="editor"
      :loading="false"
      @action="handleAiAction"
    />
  </div>
</template>
