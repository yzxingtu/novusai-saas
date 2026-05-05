<script lang="ts" setup>
import type { JSONContent } from '@tiptap/core';
import type { AgentAssignmentResolveResult } from '#/api/shared/agent-assignments';
import type {
  RichTextAiApplyMode,
  RichTextAiWritingAction,
} from '#/features/rich-text-ai';

import type {
  RichTextEditorProps,
  RichTextEditorSelectionSnapshot,
} from './types';

import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';
import { $t } from '@vben/locales';

import { EditorContent } from '@tiptap/vue-3';

import { resolveAgentAssignmentApi } from '#/api/shared/agent-assignments';
import { RICH_TEXT_AI_FEATURE_CODE } from '#/features/rich-text-ai';
import { useAIPanelStore } from '#/store';

import EditorToolbar from './toolbar/EditorToolbar.vue';
import MiniToolbar from './toolbar/MiniToolbar.vue';
import { handleImageDrop, handleImagePaste } from './useEditorUpload';
import { useRichTextEditor } from './useRichTextEditor';

import './rich-text-editor.css';

type AiActionKey =
  | 'continue'
  | 'custom'
  | 'format'
  | 'insert'
  | 'more'
  | 'rewrite';

interface AiActionDef {
  applyMode: RichTextAiApplyMode;
  endpointFeature: RichTextAiWritingAction;
  icon: string;
  instructionKey?: string;
  key: AiActionKey;
  promptRequired?: boolean;
  requiresSelection: boolean;
}

type ResolvedAiAssignment = AgentAssignmentResolveResult & {
  agent_id: number;
  agent_name: string;
};

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

const aiPanelStore = useAIPanelStore();
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

function toggleSourceMode() {
  if (!editor.value) return;
  closeAiSelectionPrompt();
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

const DEFAULT_AI_ACTIONS: AiActionDef[] = [
  {
    applyMode: 'insert_after_selection',
    endpointFeature: 'continue',
    icon: 'lucide:pen-line',
    key: 'continue',
    requiresSelection: false,
  },
  {
    applyMode: 'replace_selection',
    endpointFeature: 'rewrite',
    icon: 'lucide:refresh-ccw-dot',
    key: 'rewrite',
    requiresSelection: true,
  },
  {
    applyMode: 'insert_after_selection',
    endpointFeature: 'insert',
    icon: 'lucide:file-plus-2',
    instructionKey: 'instructions.insert',
    key: 'insert',
    requiresSelection: false,
  },
  {
    applyMode: 'replace_selection',
    endpointFeature: 'format',
    icon: 'lucide:paintbrush-vertical',
    instructionKey: 'instructions.format',
    key: 'format',
    requiresSelection: true,
  },
  {
    applyMode: 'insert_after_selection',
    endpointFeature: 'chat',
    icon: 'lucide:sparkles',
    instructionKey: 'instructions.more',
    key: 'more',
    requiresSelection: false,
  },
  {
    applyMode: 'replace_selection',
    endpointFeature: 'custom',
    icon: 'lucide:wand-sparkles',
    key: 'custom',
    promptRequired: true,
    requiresSelection: false,
  },
];

const aiFallbackText: Record<string, string> = {
  agentInactive:
    '文档写作助手已停用，请到「功能分配」启用 system.ai_writing。',
  agentMissing:
    '尚未配置文档写作助手，请到「功能分配」为 system.ai_writing 绑定智能体。',
  agentUnavailable:
    '已绑定的文档写作助手不可用，请检查 system.ai_writing 对应智能体的发布状态。',
  close: '关闭',
  connecting: '正在连接文档写作助手…',
  customPromptPlaceholder: '请输入自定义提示词。',
  discard: '丢弃',
  emptyCustomPrompt: '请输入自定义提示词。',
  instructions: '请只基于以下显式富文本选区与上下文处理内容。',
  'instructions.format': '请将选区整理成更清晰的标题、列表、引用或结构化格式。',
  'instructions.insert': '请根据选区和上下文新增一段可插入到选区后的内容。',
  'instructions.more': '请围绕选区提供摘要、扩写、缩短、校对、翻译、生成大纲或调整语气等更多写作建议。',
  menuHint: '选择文字后可打开右侧 AI 对话处理该选区。',
  menuTitle: 'AI',
  notEditable: '当前文档只读，无法使用 AI 编辑。',
  noPermission: '当前账号无法使用 AI 写作。',
  openedPanel: '已打开右侧 AI 对话：{agentName}',
  panelUnavailable: '当前账号无法使用 AI 写作。',
  requiresSelection: '请先选择要处理的文本。',
  sourceUnsupported: '源码模式下暂不支持 AI 写作，请切回所见即所得。',
};

const actionFallbackText: Record<AiActionKey, string> = {
  continue: '续写',
  custom: '自定义提示词…',
  format: '增加格式',
  insert: '新增内容',
  more: '更多 AI 内容',
  rewrite: '改写',
};

const aiWritingEnabled = computed(() => props.aiWriting?.enabled === true);
const aiApiPrefix = computed(() => props.aiWriting?.apiPrefix || '/admin');
const aiI18nPrefix = computed(
  () => props.aiWriting?.i18nPrefix || 'plugin.novusdoc.ai',
);
const aiActions = computed(() => {
  const enabled = props.aiWriting?.enabledActions;
  if (!enabled || enabled.length === 0) return DEFAULT_AI_ACTIONS;
  const allowed = new Set<string>(enabled);
  return DEFAULT_AI_ACTIONS.filter(
    (item) => allowed.has(item.endpointFeature) || allowed.has(item.key),
  );
});

const aiSelection = ref<RichTextEditorSelectionSnapshot | null>(null);
const aiSelectionPromptOpen = ref(false);
const aiPromptX = ref(0);
const aiPromptY = ref(0);
const aiNotice = ref<null | { text: string; type: 'error' | 'info' | 'success' }>(
  null,
);
const aiAssignment = ref<AgentAssignmentResolveResult | null>(null);
const aiResolving = ref(false);
const aiCustomAction = ref<AiActionDef | null>(null);
const aiCustomPrompt = ref('');

const hasAiSelection = computed(
  () => (aiSelection.value?.selectedText.trim().length ?? 0) > 0,
);

function translateAi(key: string, params?: Record<string, unknown>): string {
  const fullKey = `${aiI18nPrefix.value}.${key}`;
  const translate = $t as unknown as (
    k: string,
    p?: Record<string, unknown>,
  ) => string;
  const translated = translate(fullKey, params);
  const fallback = aiFallbackText[key] ?? fullKey;
  const raw = translated && translated !== fullKey ? translated : fallback;
  if (!params) return raw;
  return Object.entries(params).reduce(
    (value, [paramKey, paramValue]) =>
      value.replace(new RegExp(`\\{${paramKey}\\}`, 'g'), String(paramValue ?? '')),
    raw,
  );
}

function translateAiAction(action: AiActionDef): string {
  const fullKey = `${aiI18nPrefix.value}.actions.${action.key}`;
  const translate = $t as unknown as (k: string) => string;
  const translated = translate(fullKey);
  return translated && translated !== fullKey
    ? translated
    : actionFallbackText[action.key];
}

function showAiNotice(
  type: 'error' | 'info' | 'success',
  key: string,
  params?: Record<string, unknown>,
) {
  aiNotice.value = { text: translateAi(key, params), type };
}

function refreshAiSelection() {
  if (!editor.value) return;
  aiSelection.value = getSelectionSnapshot();
  if (!hasAiSelection.value) {
    closeAiSelectionPrompt();
  }
}

function getCurrentSelection(): RichTextEditorSelectionSnapshot {
  refreshAiSelection();
  return aiSelection.value ?? getSelectionSnapshot();
}

function getBrowserSelectionRect(): DOMRect | null {
  try {
    const browserSelection = window.getSelection?.();
    if (!browserSelection || browserSelection.rangeCount === 0) return null;
    const range = browserSelection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    if (rect.width > 0 || rect.height > 0) return rect;
  } catch {
    // Some test/browser environments do not expose selection geometry.
  }
  return null;
}

function placeAiPromptFromEvent(event?: MouseEvent | KeyboardEvent) {
  const promptWidth = 336;
  const promptHeight = 48;
  const viewportWidth = window.innerWidth || 1024;
  const viewportHeight = window.innerHeight || 768;
  const rect = getBrowserSelectionRect();
  let x = Math.round(viewportWidth / 2 - promptWidth / 2);
  let y = 96;

  if (rect) {
    x = Math.round(rect.left + rect.width / 2 - promptWidth / 2);
    y = Math.round(rect.top - promptHeight - 10);
  } else if (event instanceof MouseEvent) {
    x = Math.round(event.clientX - promptWidth / 2);
    y = Math.round(event.clientY - promptHeight - 10);
  }

  aiPromptX.value = Math.max(8, Math.min(x, viewportWidth - promptWidth - 8));
  aiPromptY.value = Math.max(8, Math.min(y, viewportHeight - promptHeight - 8));
}

function openAiSelectionPrompt(
  event?: MouseEvent | KeyboardEvent,
  options: { silent?: boolean } = {},
) {
  if (!aiWritingEnabled.value) return;
  if (props.editable === false) {
    closeAiSelectionPrompt();
    if (!options.silent) showAiNotice('error', 'notEditable');
    return;
  }
  if (sourceMode.value) {
    closeAiSelectionPrompt();
    if (!options.silent) showAiNotice('error', 'sourceUnsupported');
    return;
  }
  refreshAiSelection();
  if (!hasAiSelection.value) {
    closeAiSelectionPrompt();
    if (!options.silent) showAiNotice('error', 'requiresSelection');
    return;
  }
  placeAiPromptFromEvent(event);
  aiSelectionPromptOpen.value = true;
  aiCustomAction.value = null;
  aiCustomPrompt.value = '';
}

function closeAiSelectionPrompt() {
  aiSelectionPromptOpen.value = false;
  aiCustomAction.value = null;
}

function onEditorContextMenu(event: MouseEvent) {
  if (!aiWritingEnabled.value) return;
  refreshAiSelection();
  if (!hasAiSelection.value && !sourceMode.value) return;
  event.preventDefault();
  openAiSelectionPrompt(event);
}

function onEditorSelectionMouseup(event: MouseEvent) {
  openAiSelectionPrompt(event, { silent: true });
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

function onDocumentAiPromptClick(event: MouseEvent) {
  const target = event.target as Element | null;
  if (!target?.closest?.('[data-rte-ai-selection-prompt]')) {
    closeAiSelectionPrompt();
  }
}

watch(aiSelectionPromptOpen, (open) => {
  if (open) {
    nextTick(() => {
      setTimeout(
        () => document.addEventListener('click', onDocumentAiPromptClick),
        0,
      );
    });
  } else {
    document.removeEventListener('click', onDocumentAiPromptClick);
  }
});

function isActionDisabled(action: AiActionDef): boolean {
  if (aiResolving.value || props.editable === false || sourceMode.value) {
    return true;
  }
  return action.requiresSelection && !hasAiSelection.value;
}

function buildInstruction(action: AiActionDef, customPrompt?: string): string {
  if (typeof customPrompt === 'string' && customPrompt.trim()) {
    return customPrompt.trim();
  }
  return action.instructionKey ? translateAi(action.instructionKey) : translateAi('instructions');
}

function clipContext(text: string, maxLength = 720): string {
  const normalized = text.trim();
  if (!normalized) return '（无）';
  return normalized.length > maxLength
    ? `${normalized.slice(0, maxLength)}…`
    : normalized;
}

function buildPanelMessage(
  action: AiActionDef,
  selection: RichTextEditorSelectionSnapshot,
  customPrompt?: string,
): string {
  const operationName = translateAiAction(action);
  const documentTitle = props.aiWriting?.documentTitle?.trim() || '未命名文档';
  const applyHint =
    action.applyMode === 'replace_selection' ? '替换原选区' : '插入到选区后';
  const instruction = buildInstruction(action, customPrompt);

  return [
    `文档写作助手：${operationName}（${applyHint}）`,
    `标题：${documentTitle}`,
    `选区：${clipContext(selection.selectedText, 1200)}`,
    selection.beforeText.trim()
      ? `前文：${clipContext(selection.beforeText, 240)}`
      : '',
    selection.afterText.trim()
      ? `后文：${clipContext(selection.afterText, 240)}`
      : '',
    `要求：${instruction}`,
    `范围：editor=${editorInstanceId}; revision=${selection.revision}; range=${selection.from}-${selection.to}`,
    '仅根据以上显式内容回复正文建议，不读取页面或 DOM。',
  ]
    .filter(Boolean)
    .join('\n');
}

async function resolveAiAssignment(): Promise<ResolvedAiAssignment | null> {
  aiResolving.value = true;

  try {
    const assignment = await resolveAgentAssignmentApi(
      aiApiPrefix.value,
      RICH_TEXT_AI_FEATURE_CODE,
    );
    aiAssignment.value = assignment;

    if (!assignment.is_active) {
      showAiNotice('error', 'agentInactive');
      return null;
    }
    if (typeof assignment.agent_id !== 'number' || assignment.agent_id <= 0) {
      showAiNotice('error', 'agentMissing');
      return null;
    }
    if (!assignment.agent_name) {
      showAiNotice('error', 'agentUnavailable');
      return null;
    }

    return assignment as ResolvedAiAssignment;
  } catch {
    aiAssignment.value = null;
    showAiNotice('error', 'noPermission');
    return null;
  } finally {
    aiResolving.value = false;
  }
}

async function runAiAction(action: AiActionDef, customPrompt?: string) {
  const selection = getCurrentSelection();
  if (action.requiresSelection && selection.empty) {
    showAiNotice('error', 'requiresSelection');
    return;
  }
  if (action.promptRequired && !customPrompt?.trim()) {
    aiCustomAction.value = action;
    return;
  }

  const assignment = await resolveAiAssignment();
  if (!assignment) return;

  const opened = aiPanelStore.openWithContext({
    agentId: assignment.agent_id,
    message: buildPanelMessage(action, selection, customPrompt),
  });

  if (!opened) {
    showAiNotice('error', 'panelUnavailable');
    return;
  }

  closeAiSelectionPrompt();
  showAiNotice('success', 'openedPanel', { agentName: assignment.agent_name });
}

function submitCustomPrompt() {
  if (!aiCustomAction.value) return;
  if (!aiCustomPrompt.value.trim()) {
    showAiNotice('error', 'emptyCustomPrompt');
    return;
  }
  void runAiAction(aiCustomAction.value, aiCustomPrompt.value);
}

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentAiPromptClick);
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
      class="overflow-y-auto px-3 py-2"
      :style="{ minHeight: minH, maxHeight: maxH }"
      @contextmenu="onEditorContextMenu"
      @keyup="onEditorSelectionKeyup"
      @mouseup="onEditorSelectionMouseup"
    >
      <EditorContent v-if="editor" :editor="editor" />
    </div>
  </div>

  <div
    v-if="aiNotice"
    class="fixed bottom-5 left-1/2 z-[1100] -translate-x-1/2 rounded-lg border px-4 py-2 text-sm shadow-lg"
    :class="{
      'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900/50 dark:bg-blue-950/40 dark:text-blue-300': aiNotice.type === 'info',
      'border-green-200 bg-green-50 text-green-700 dark:border-green-900/50 dark:bg-green-950/40 dark:text-green-300': aiNotice.type === 'success',
      'border-red-200 bg-red-50 text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300': aiNotice.type === 'error',
    }"
    aria-live="polite"
    data-testid="rte-ai-notice"
  >
    {{ aiNotice.text }}
  </div>

  <div
    v-if="aiSelectionPromptOpen"
    data-rte-ai-selection-prompt
    data-testid="rte-ai-selection-prompt"
    role="menu"
    class="fixed z-[1050] max-w-[calc(100vw-16px)] rounded-xl border border-border bg-popover p-1 text-popover-foreground shadow-lg"
    :style="{ left: `${aiPromptX}px`, top: `${aiPromptY}px` }"
    @click.stop
    @keydown.esc.stop.prevent="closeAiSelectionPrompt"
  >
    <div class="flex flex-wrap items-center gap-1">
      <span
        class="inline-flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary"
        :aria-label="translateAi('menuTitle')"
        data-testid="rte-ai-trigger-icon"
      >
        <IconifyIcon icon="lucide:sparkles" class="size-4" />
      </span>
      <button
        v-for="action in aiActions"
        :key="action.key"
        type="button"
        role="menuitem"
        class="inline-flex min-h-8 items-center gap-1.5 rounded-lg px-2 text-sm hover:bg-accent disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:bg-transparent"
        :aria-label="translateAiAction(action)"
        :data-testid="`rte-ai-action-${action.key}`"
        :disabled="isActionDisabled(action)"
        @click="action.promptRequired ? (aiCustomAction = action) : runAiAction(action)"
      >
        <IconifyIcon
          :icon="action.icon"
          class="size-3.5"
          :data-testid="`rte-ai-action-${action.key}-icon`"
        />
        {{ translateAiAction(action) }}
      </button>
      <button
        type="button"
        class="inline-flex min-h-8 items-center rounded-lg px-2 text-muted-foreground hover:bg-accent"
        :aria-label="translateAi('close')"
        data-testid="rte-ai-selection-prompt-close"
        @click="closeAiSelectionPrompt"
      >
        <IconifyIcon icon="lucide:x" class="size-3.5" />
      </button>
    </div>

    <div v-if="aiResolving" class="px-2 pb-1 text-xs text-muted-foreground" aria-live="polite" data-testid="rte-ai-resolving">
      {{ translateAi('connecting') }}
    </div>

    <div v-if="aiCustomAction" class="mt-1 border-t border-border p-2">
      <textarea
        v-model="aiCustomPrompt"
        class="min-h-[72px] w-full resize-none rounded-lg border border-border bg-background p-2 text-sm outline-none focus:border-primary"
        :placeholder="translateAi('customPromptPlaceholder')"
        data-testid="rte-ai-custom-prompt"
      />
      <div class="mt-2 flex justify-end gap-2">
        <button
          type="button"
          class="min-h-9 rounded-md px-3 text-sm hover:bg-accent"
          @click="aiCustomAction = null"
        >
          {{ translateAi('discard') }}
        </button>
        <button
          type="button"
          class="min-h-9 rounded-md bg-primary px-3 text-sm text-primary-foreground"
          data-testid="rte-ai-custom-submit"
          @click="submitCustomPrompt"
        >
          {{ translateAiAction(aiCustomAction) }}
        </button>
      </div>
    </div>
  </div>
</template>
