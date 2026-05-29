<script lang="ts" setup>
import type { JSONContent } from '@tiptap/core';

import type {
  RichTextEditorProps,
  RichTextEditorSelectionSnapshot,
} from './types';

import type {
  TextSelectionAiAnchorRect,
  TextSelectionAiApplyRequest,
  TextSelectionAiAssistExpose,
  TextSelectionAiSnapshot,
} from '#/components/business/text-selection-ai-assist';

import { computed, onBeforeUnmount, ref, watch } from 'vue';

import { $t } from '@vben/locales';

import { EditorContent } from '@tiptap/vue-3';

import { TextSelectionAiAssist } from '#/components/business/text-selection-ai-assist';

import EditorToolbar from './toolbar/EditorToolbar.vue';
import MiniToolbar from './toolbar/MiniToolbar.vue';
import { handleImageDrop, handleImagePaste } from './useEditorUpload';
import { useRichTextEditor } from './useRichTextEditor';

import './rich-text-editor.css';

const props = withDefaults(defineProps<RichTextEditorProps>(), {
  mode: 'compact',
  toolbar: true,
  upload: true,
  editable: true,
  autofocus: false,
});

const emit = defineEmits<{
  change: [json: JSONContent, html: string, text: string];
  'update:modelValue': [value: JSONContent | null];
}>();

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
  setContent,
  getJSON,
  getHTML,
  getText,
  getSelectionSnapshot,
  validateSelectionSnapshot,
  applyContent,
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

const sourceMode = ref(false);
const sourceCode = ref('');

watch(sourceMode, (enabled) => {
  if (!enabled) return;
  sourceCode.value = getHTML();
});

const textSelectionAiAssistRef = ref<null | TextSelectionAiAssistExpose>(null);
const aiWritingEnabled = computed(() => props.aiWriting?.enabled === true);
const aiApiPrefix = computed(() => props.aiWriting?.apiPrefix || '/admin');
const aiI18nPrefix = computed(
  () => props.aiWriting?.i18nPrefix || 'plugin.novusdoc.ai',
);
let pendingSelectionMouseupTimer: null | number = null;

function clearPendingSelectionMouseup() {
  if (pendingSelectionMouseupTimer === null) return;
  window.clearTimeout(pendingSelectionMouseupTimer);
  pendingSelectionMouseupTimer = null;
}

function closeTextSelectionAiAssist() {
  textSelectionAiAssistRef.value?.close();
}

function toggleSourceMode() {
  if (!editor.value) return;
  closeTextSelectionAiAssist();
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

function focusEditorEnd() {
  if (editor.value) {
    editor.value.commands.focus('end');
  }
}

function getRichTextAiSelection(): TextSelectionAiSnapshot {
  return getSelectionSnapshot();
}

function validateRichTextAiSelection(
  selection: TextSelectionAiSnapshot,
): boolean {
  return validateSelectionSnapshot(
    selection as RichTextEditorSelectionSnapshot,
  );
}

function applyRichTextAiResult(
  request: TextSelectionAiApplyRequest,
): boolean | undefined {
  applyContent(request.content, {
    mode: request.mode,
    selection: request.selection as RichTextEditorSelectionSnapshot,
  });
  return true;
}

function buildAiAnchorRect(
  left: number,
  top: number,
  right: number,
  bottom: number,
): null | TextSelectionAiAnchorRect {
  const normalizedLeft = Math.min(left, right);
  const normalizedRight = Math.max(left, right);
  const normalizedTop = Math.min(top, bottom);
  const normalizedBottom = Math.max(top, bottom);
  const width = normalizedRight - normalizedLeft;
  const height = normalizedBottom - normalizedTop;
  if (width <= 0 && height <= 0) return null;
  return {
    bottom: normalizedBottom,
    height: Math.max(1, height),
    left: normalizedLeft,
    right: normalizedRight,
    top: normalizedTop,
    width: Math.max(1, width),
  };
}

function getRichTextAiAnchorRect(
  selection: null | TextSelectionAiSnapshot,
): null | TextSelectionAiAnchorRect {
  const view = (
    editor.value as
      | undefined
      | {
          view?: {
            coordsAtPos?: (position: number) => {
              bottom: number;
              left: number;
              right: number;
              top: number;
            };
          };
        }
  )?.view;
  if (!selection || !view?.coordsAtPos) return null;

  try {
    const fromCoords = view.coordsAtPos(selection.from);
    const toCoords = view.coordsAtPos(
      selection.empty ? selection.from : selection.to,
    );
    return buildAiAnchorRect(
      Math.min(fromCoords.left, toCoords.left),
      Math.min(fromCoords.top, toCoords.top),
      Math.max(fromCoords.right, toCoords.right),
      Math.max(fromCoords.bottom, toCoords.bottom),
    );
  } catch {
    return null;
  }
}

function openAiSelectionPrompt(
  event?: KeyboardEvent | MouseEvent,
  options: { requireSelection?: boolean; silent?: boolean } = {},
) {
  if (!aiWritingEnabled.value) return;
  textSelectionAiAssistRef.value?.open(event, {
    ...options,
    unavailableReasonKey: sourceMode.value ? 'sourceUnsupported' : undefined,
  });
}

function closeAiSelectionPrompt() {
  textSelectionAiAssistRef.value?.close();
}

function onEditorContextMenu(event: MouseEvent) {
  if (!aiWritingEnabled.value) return;
  event.preventDefault();
  openAiSelectionPrompt(event);
}

function onEditorSelectionMouseup(event: MouseEvent) {
  clearPendingSelectionMouseup();
  pendingSelectionMouseupTimer = window.setTimeout(() => {
    pendingSelectionMouseupTimer = null;
    openAiSelectionPrompt(event, { silent: true });
  }, 0);
}

function onEditorSelectionKeyup(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    closeAiSelectionPrompt();
    return;
  }
  openAiSelectionPrompt(event, { silent: true });
}

function onEditorKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    closeAiSelectionPrompt();
    return;
  }
  if ((event.shiftKey && event.key === 'F10') || event.key === 'ContextMenu') {
    event.preventDefault();
    openAiSelectionPrompt(event);
  }
}

onBeforeUnmount(() => {
  clearPendingSelectionMouseup();
});

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
  getSelectionSnapshot,
  validateSelectionSnapshot,
  applyContent,
  focus,
});
</script>

<template>
  <!-- Full mode -->
  <div
    v-if="isFull"
    class="rte-editor relative flex h-full flex-col"
    tabindex="0"
    @keydown="onEditorKeydown"
  >
    <EditorToolbar
      v-if="toolbar !== false"
      :editor="editor!"
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
        @contextmenu="onEditorContextMenu"
        @keyup="onEditorSelectionKeyup"
        @mouseup="onEditorSelectionMouseup"
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
        @contextmenu.prevent="openAiSelectionPrompt"
      ></textarea>
    </div>

    <div
      class="flex items-center justify-between border-t border-border px-4 py-1.5 text-xs text-muted-foreground"
    >
      <span>{{ $t('common.wordCount') }}: {{ wordCount }}</span>
    </div>
  </div>

  <!-- Compact mode -->
  <div
    v-else
    class="rte-editor rte-compact relative"
    tabindex="0"
    @keydown="onEditorKeydown"
  >
    <MiniToolbar v-if="toolbar !== false" :editor="editor" :upload="upload" />

    <div
      class="rte-editor-body flex flex-col overflow-y-auto px-3 py-2"
      :style="{ minHeight: minH, maxHeight: maxH }"
      @click.self="focusEditorEnd"
      @contextmenu="onEditorContextMenu"
      @keyup="onEditorSelectionKeyup"
      @mouseup="onEditorSelectionMouseup"
    >
      <EditorContent
        v-if="editor"
        :editor="editor"
        class="rte-editor-content flex flex-1 flex-col"
        @click.self="focusEditorEnd"
      />
    </div>
  </div>

  <TextSelectionAiAssist
    ref="textSelectionAiAssistRef"
    :enabled="aiWritingEnabled"
    :editable="editable !== false"
    :api-prefix="aiApiPrefix"
    :i18n-prefix="aiI18nPrefix"
    :document-title="aiWriting?.documentTitle"
    document-type="novusdoc"
    surface="rich_text_editor"
    :enabled-actions="aiWriting?.enabledActions"
    :feature-code="aiWriting?.featureCode"
    :get-selection="getRichTextAiSelection"
    :validate-selection="validateRichTextAiSelection"
    :apply-result="applyRichTextAiResult"
    :get-anchor-rect="getRichTextAiAnchorRect"
  />
</template>
