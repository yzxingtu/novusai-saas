<script lang="ts" setup>
import type {
  TextSelectionAiAnchorRect,
  TextSelectionAiAssistExpose,
  TextSelectionAiAssistOpenOptions,
  TextSelectionAiAssistProps,
  TextSelectionAiSnapshot,
} from './types';

import type { AgentAssignmentResolveResult } from '#/api/shared/agent-assignments';
import type {
  RichTextAiOperationDoneEvent,
  RichTextAiOperationPayload,
} from '#/api/shared/rich-text-ai';
import type {
  RichTextAiActionTemplate,
  RichTextAiApplyMode,
} from '#/features/rich-text-ai';

import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';
import { $t } from '@vben/locales';
import { preferences } from '@vben/preferences';

import { resolveAgentAssignmentApi } from '#/api/shared/agent-assignments';
import { streamRichTextAiOperationApi } from '#/api/shared/rich-text-ai';
import {
  getRichTextAiActionTemplate,
  getRichTextAiContextMenuActions,
  RICH_TEXT_AI_FEATURE_CODE,
} from '#/features/rich-text-ai';

defineOptions({ name: 'TextSelectionAiAssist' });

const props = withDefaults(defineProps<TextSelectionAiAssistProps>(), {
  apiPrefix: '/admin',
  documentType: 'plain_text',
  editable: true,
  enabled: true,
  featureCode: RICH_TEXT_AI_FEATURE_CODE,
  i18nPrefix: 'common.textSelectionAi',
  requireSelectionToOpen: false,
  surface: 'text_selection_input',
});

type AiActionKey =
  | 'continue'
  | 'custom'
  | 'expand'
  | 'format'
  | 'insert'
  | 'more'
  | 'optimize'
  | 'proofread'
  | 'rewrite'
  | 'summarize'
  | 'translate';

interface AiActionDef extends RichTextAiActionTemplate {
  key: AiActionKey;
}

interface AiPreviewState {
  action: AiActionDef;
  applyMode: RichTextAiApplyMode | string;
  conversationId: null | number;
  customPrompt: string;
  draft: string;
  error: string;
  loading: boolean;
  outputContract: string;
  selection: TextSelectionAiSnapshot;
  targetLanguageLabel: string;
}

type AiInlineChatRole = 'assistant' | 'user';

interface AiInlineChatMessage {
  content: string;
  error: string;
  id: number;
  loading: boolean;
  role: AiInlineChatRole;
}

interface AiInlineChatState {
  action: AiActionDef;
  conversationId: null | number;
  error: string;
  input: string;
  loading: boolean;
  messages: AiInlineChatMessage[];
  selection: TextSelectionAiSnapshot;
  targetLanguageLabel: string;
}

interface RichTextLanguage {
  displayKey: string;
  key: 'english' | 'japanese' | 'korean' | 'simplifiedChinese';
  promptName: string;
}

const aiFallbackText: Record<string, string> = {
  agentInactive: '文档写作助手已停用，请到「功能分配」启用 system.ai_writing。',
  agentMissing:
    '尚未配置文档写作助手，请到「功能分配」为 system.ai_writing 绑定智能体。',
  agentUnavailable:
    '已绑定的文档写作助手不可用，请检查 system.ai_writing 对应智能体的发布状态。',
  close: '关闭',
  connecting: '正在连接文档写作助手…',
  copy: '复制',
  copied: '已复制 AI 结果。',
  copyFailed: '复制失败，请手动复制。',
  constraintFailed: '结果不符合当前输入框约束，请先编辑候选结果。',
  customPromptPlaceholder: '请输入自定义提示词。',
  discard: '丢弃',
  apply: '应用',
  'applyMode.insert': '将插入到光标处',
  'applyMode.insertAfterSelection': '将插入到选区后',
  'applyMode.replace': '将替换原选区',
  applied: '已应用 AI 结果。',
  applying: '正在应用…',
  emptyCustomPrompt: '请输入自定义提示词。',
  emptyResult: 'AI 未返回可应用内容，请重试。',
  'instructions.base': '请只基于以下显式文本选区与上下文处理内容。',
  'instructions.custom': '请按自定义提示词处理当前文本选区或光标上下文。',
  'instructions.format':
    '请将选中文本整理成更清晰的标题、列表、引用或结构化格式。',
  'instructions.insert': '请根据选区和上下文新增一段可插入到当前位置的内容。',
  'instructions.more':
    '请围绕选区提供摘要、扩写、缩短、校对、翻译、生成大纲或调整语气等更多写作建议。',
  languageInstruction:
    '请使用{language}输出，除非用户在指令中明确指定其他语言。',
  languageAuto: '语言跟随原文',
  languageOutput: '输出：{language}',
  'languages.english': '英文',
  'languages.japanese': '日文',
  'languages.korean': '韩文',
  'languages.simplifiedChinese': '中文',
  inlineChatComposerPlaceholder: '继续追问、让它改短、列大纲或给替代表达…',
  inlineChatContext: '基于当前选区',
  inlineChatDefaultPrompt: '请围绕当前选区给出可直接用于写作的建议。',
  inlineChatEmptyPrompt: '请输入要继续追问的内容。',
  inlineChatInsert: '插入正文',
  inlineChatSend: '发送',
  inlineChatTitle: 'AI 对话',
  menuHint: '选择文字或将光标放在插入点后可使用 AI 写作。',
  menuTitle: 'AI',
  notEditable: '当前内容只读，无法使用 AI 编辑。',
  noPermission: '当前账号无法使用 AI 写作。',
  previewHint: '检查结果后再应用到正文。',
  previewLoading: '正在生成 AI 预览…',
  previewPlaceholder: 'AI 结果会显示在这里，也可以在应用前编辑。',
  previewTitle: 'AI 预览',
  regenerate: '重新生成',
  requiresSelection: '请先选择要处理的文本。',
  retry: '重试',
  selectionDrifted: '正文或选区已变化，请重新选择后再应用。',
  sourceUnsupported: '源码模式下暂不支持 AI 写作，请切回所见即所得。',
  stop: '停止',
  stopped: '已停止生成，可应用或编辑当前结果。',
  chatStopped: '已停止回复。',
  streamError: 'AI 生成失败，请重试。',
};

const actionFallbackText: Record<AiActionKey, string> = {
  continue: '续写',
  custom: '自定义提示词…',
  expand: '扩写',
  format: '增加格式',
  insert: '新增内容',
  more: '更多 AI 内容',
  optimize: '优化',
  proofread: '校对',
  rewrite: '改写',
  summarize: '摘要',
  translate: '翻译',
};

const aiWritingEnabled = computed(() => props.enabled === true);
const aiApiPrefix = computed(() => props.apiPrefix || '/admin');
const aiI18nPrefix = computed(
  () => props.i18nPrefix || 'common.textSelectionAi',
);
const aiFeatureCode = computed(
  () => props.featureCode || RICH_TEXT_AI_FEATURE_CODE,
);
const aiActions = computed(() => {
  const enabled = props.enabledActions;
  const templates = getRichTextAiContextMenuActions({
    enabledActions: enabled,
  });
  const actions = templates.map((template) => toEditorAiAction(template));
  const allowMore =
    !enabled ||
    enabled.includes('chat') ||
    (enabled as string[]).includes('more');
  return allowMore ? [...actions, buildMoreAiAction()] : actions;
});
const aiActionRows = computed(() => {
  const actions = aiActions.value;
  const midpoint = Math.ceil(actions.length / 2);
  return [actions.slice(0, midpoint), actions.slice(midpoint)];
});
const compactActionMenu = computed(
  () => !aiInlineChat.value && !aiPreview.value && aiActions.value.length <= 6,
);
const aiPromptWidthPx = computed(() => {
  if (aiInlineChat.value) return 460;
  if (aiPreview.value) return 420;
  if (!compactActionMenu.value) return 640;
  const rowWidths = aiActionRows.value.map((row) => {
    const actionWidth = row.reduce(
      (total, action) => total + estimateActionButtonWidth(action),
      0,
    );
    const fixedSlotWidth = 64;
    const horizontalPadding = 8;
    const gapWidth = Math.max(0, row.length + 1) * 4;
    return actionWidth + fixedSlotWidth + horizontalPadding + gapWidth;
  });
  return Math.min(460, Math.max(320, Math.ceil(Math.max(...rowWidths, 0))));
});
const aiFloatingLayerStyle = computed(() => ({
  left: `${aiPromptX.value}px`,
  top: `${aiPromptY.value}px`,
  width: `${aiPromptWidthPx.value}px`,
}));

const aiSelection = ref<null | TextSelectionAiSnapshot>(null);
const aiSelectionPromptOpen = ref(false);
const aiPromptX = ref(0);
const aiPromptY = ref(0);
const aiNotice = ref<null | {
  text: string;
  type: 'error' | 'info' | 'success';
}>(null);
const aiAssignment = ref<AgentAssignmentResolveResult | null>(null);
const aiResolving = ref(false);
const aiCustomAction = ref<AiActionDef | null>(null);
const aiCustomPrompt = ref('');
const aiPreview = ref<AiPreviewState | null>(null);
const aiInlineChat = ref<AiInlineChatState | null>(null);
const aiStreamingAbortController = ref<AbortController | null>(null);
const aiLastAnchorEvent = ref<KeyboardEvent | MouseEvent | null>(null);
const aiInlineChatMessageSeq = ref(0);

const hasAiSelection = computed(
  () => (aiSelection.value?.selectedText.trim().length ?? 0) > 0,
);

const richTextLanguages: Record<RichTextLanguage['key'], RichTextLanguage> = {
  english: {
    displayKey: 'languages.english',
    key: 'english',
    promptName: 'English',
  },
  japanese: {
    displayKey: 'languages.japanese',
    key: 'japanese',
    promptName: 'Japanese',
  },
  korean: {
    displayKey: 'languages.korean',
    key: 'korean',
    promptName: 'Korean',
  },
  simplifiedChinese: {
    displayKey: 'languages.simplifiedChinese',
    key: 'simplifiedChinese',
    promptName: 'Simplified Chinese',
  },
};

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
  let result = raw;
  for (const [paramKey, paramValue] of Object.entries(params)) {
    result = result.replaceAll(
      new RegExp(String.raw`\{${paramKey}\}`, 'g'),
      String(paramValue ?? ''),
    );
  }
  return result;
}

function translateAiAction(action: AiActionDef): string {
  const fullKey = `${aiI18nPrefix.value}.actions.${action.key}`;
  const translate = $t as unknown as (k: string) => string;
  const translated = translate(fullKey);
  if (translated && translated !== fullKey) {
    return translated;
  }
  const templateLabel = translate(action.labelKey);
  if (templateLabel && templateLabel !== action.labelKey) {
    return templateLabel;
  }
  return actionFallbackText[action.key];
}

function estimateActionButtonWidth(action: AiActionDef): number {
  const label = translateAiAction(action);
  let textWidth = 0;
  for (const char of label) {
    textWidth += /[\u3400-\u9FFF\uF900-\uFAFF]/.test(char) ? 14 : 7;
  }
  return Math.min(136, Math.max(72, textWidth + 38));
}

function languageTextSample(selection: TextSelectionAiSnapshot): string {
  return [
    selection.selectedText,
    selection.beforeText,
    selection.afterText,
    props.documentTitle ?? '',
  ]
    .join('\n')
    .trim();
}

function countPattern(text: string, pattern: RegExp): number {
  return text.match(pattern)?.length ?? 0;
}

function inferLanguageFromText(sample: string): null | RichTextLanguage {
  const hanCount = countPattern(sample, /[\u3400-\u9FFF\uF900-\uFAFF]/g);
  const japaneseCount = countPattern(sample, /[\u3040-\u30FF]/g);
  const koreanCount = countPattern(sample, /[\uAC00-\uD7AF]/g);
  const latinCount = countPattern(sample, /[A-Z]/gi);

  if (japaneseCount >= 2 && japaneseCount >= hanCount) {
    return richTextLanguages.japanese;
  }
  if (koreanCount >= 2 && koreanCount >= hanCount) {
    return richTextLanguages.korean;
  }
  if (hanCount >= 2 && hanCount >= Math.ceil(latinCount / 2)) {
    return richTextLanguages.simplifiedChinese;
  }
  if (latinCount > 0) {
    return richTextLanguages.english;
  }
  return null;
}

function inferSourceLanguage(
  selection: TextSelectionAiSnapshot,
): RichTextLanguage {
  return (
    inferLanguageFromText(languageTextSample(selection)) ??
    richTextLanguages.simplifiedChinese
  );
}

function inferSurroundingLanguage(
  selection: TextSelectionAiSnapshot,
): null | RichTextLanguage {
  return inferLanguageFromText(
    [selection.beforeText, selection.afterText, props.documentTitle ?? '']
      .join('\n')
      .trim(),
  );
}

function resolveUiLanguage(): RichTextLanguage {
  const locale = String(preferences.app.locale || '').toLowerCase();
  if (locale.startsWith('en')) return richTextLanguages.english;
  if (locale.startsWith('ja')) return richTextLanguages.japanese;
  if (locale.startsWith('ko')) return richTextLanguages.korean;
  return richTextLanguages.simplifiedChinese;
}

function resolveOperationLanguage(
  action: AiActionDef,
  selection: TextSelectionAiSnapshot,
): RichTextLanguage {
  const sourceLanguage = inferSourceLanguage(selection);
  if (action.action !== 'translate') {
    return sourceLanguage;
  }
  const surroundingLanguage = inferSurroundingLanguage(selection);
  if (surroundingLanguage && surroundingLanguage.key !== sourceLanguage.key) {
    return surroundingLanguage;
  }
  const uiLanguage = resolveUiLanguage();
  if (uiLanguage.key !== sourceLanguage.key) {
    return uiLanguage;
  }
  return sourceLanguage.key === 'english'
    ? richTextLanguages.simplifiedChinese
    : richTextLanguages.english;
}

function languageDisplayName(language: RichTextLanguage): string {
  return translateAi(language.displayKey);
}

function operationTargetLang(
  action: AiActionDef,
  selection: TextSelectionAiSnapshot,
): string | undefined {
  if (action.action !== 'translate') return undefined;
  return resolveOperationLanguage(action, selection).promptName;
}

function showAiNotice(
  type: 'error' | 'info' | 'success',
  key: string,
  params?: Record<string, unknown>,
) {
  aiNotice.value = { text: translateAi(key, params), type };
}

function toEditorAiAction(template: RichTextAiActionTemplate): AiActionDef {
  return {
    ...template,
    key: template.action as AiActionKey,
  };
}

function buildMoreAiAction(): AiActionDef {
  const chat = getRichTextAiActionTemplate('chat');
  return {
    ...chat,
    icon: 'lucide:sparkles',
    key: 'more',
    visibleInContextMenu: true,
  };
}

function normalizeSelection(
  selection: TextSelectionAiSnapshot,
): TextSelectionAiSnapshot {
  return {
    ...selection,
    beforeText: selection.beforeText ?? '',
    afterText: selection.afterText ?? '',
    selectedText: selection.selectedText ?? '',
  };
}

function readCurrentSelection(): null | TextSelectionAiSnapshot {
  const selection = props.getSelection();
  if (!selection) {
    return null;
  }
  return normalizeSelection(selection);
}

function getCurrentSelection(): TextSelectionAiSnapshot {
  const selection = readCurrentSelection();
  if (selection) {
    aiSelection.value = selection;
    return selection;
  }
  return {
    afterText: '',
    beforeText: '',
    empty: true,
    from: 0,
    revision: 0,
    selectedText: '',
    to: 0,
  };
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

function getBrowserSelectionRect(): null | TextSelectionAiAnchorRect {
  try {
    const browserSelection = window.getSelection?.();
    if (!browserSelection || browserSelection.rangeCount === 0) return null;
    const range = browserSelection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    return buildAiAnchorRect(rect.left, rect.top, rect.right, rect.bottom);
  } catch {
    return null;
  }
}

function getAiAnchorRect(): null | TextSelectionAiAnchorRect {
  const selection =
    aiPreview.value?.selection ??
    aiInlineChat.value?.selection ??
    aiSelection.value;
  return props.getAnchorRect?.(selection ?? null) ?? getBrowserSelectionRect();
}

function placeAiPromptFromEvent(event?: KeyboardEvent | MouseEvent) {
  if (event) {
    aiLastAnchorEvent.value = event;
  }
  const promptWidth = aiPromptWidthPx.value;
  let promptHeight = 88;
  if (aiInlineChat.value) {
    promptHeight = 500;
  } else if (aiPreview.value) {
    promptHeight = 360;
  }
  const viewportWidth = window.innerWidth || 1024;
  const viewportHeight = window.innerHeight || 768;
  const rect = getAiAnchorRect();
  let x = Math.round(viewportWidth / 2 - promptWidth / 2);
  let y = 96;

  if (rect) {
    x = Math.round(rect.left + rect.width / 2 - promptWidth / 2);
    const aboveY = Math.round(rect.top - promptHeight - 10);
    const belowY = Math.round(rect.bottom + 10);
    y = aboveY >= 8 ? aboveY : belowY;
  } else if (event instanceof MouseEvent) {
    x = Math.round(event.clientX - promptWidth / 2);
    y = Math.round(event.clientY - promptHeight - 10);
  } else if (aiLastAnchorEvent.value instanceof MouseEvent) {
    x = Math.round(aiLastAnchorEvent.value.clientX - promptWidth / 2);
    y = Math.round(aiLastAnchorEvent.value.clientY - promptHeight - 10);
  }

  aiPromptX.value = Math.max(8, Math.min(x, viewportWidth - promptWidth - 8));
  aiPromptY.value = Math.max(8, Math.min(y, viewportHeight - promptHeight - 8));
}

function repositionAiFloatingLayer() {
  if (!aiSelectionPromptOpen.value && !aiPreview.value && !aiInlineChat.value) {
    return;
  }
  const rect = getAiAnchorRect();
  if (
    rect &&
    (rect.bottom < 0 || rect.top > (window.innerHeight || 768)) &&
    !aiPreview.value?.loading &&
    !aiInlineChat.value?.loading
  ) {
    closeAiSelectionPrompt();
    return;
  }
  placeAiPromptFromEvent();
}

function addAiFloatingAnchorListeners() {
  window.addEventListener('scroll', repositionAiFloatingLayer, true);
  window.addEventListener('resize', repositionAiFloatingLayer);
}

function removeAiFloatingAnchorListeners() {
  window.removeEventListener('scroll', repositionAiFloatingLayer, true);
  window.removeEventListener('resize', repositionAiFloatingLayer);
}

function closeAiSelectionPrompt() {
  if (aiPreview.value || aiInlineChat.value) return;
  aiSelectionPromptOpen.value = false;
  aiCustomAction.value = null;
}

function open(
  event?: KeyboardEvent | MouseEvent,
  options: TextSelectionAiAssistOpenOptions = {},
) {
  if (!aiWritingEnabled.value) return;
  if (props.editable === false) {
    closeAiSelectionPrompt();
    if (!options.silent) showAiNotice('error', 'notEditable');
    return;
  }
  if (options.unavailableReasonKey) {
    closeAiSelectionPrompt();
    if (!options.silent) showAiNotice('error', options.unavailableReasonKey);
    return;
  }

  aiSelection.value = readCurrentSelection();
  const selection = aiSelection.value;
  if (!selection) {
    closeAiSelectionPrompt();
    return;
  }
  if (
    !selection.selectedText.trim() &&
    (options.requireSelection ?? props.requireSelectionToOpen ?? options.silent)
  ) {
    closeAiSelectionPrompt();
    if (
      !options.silent &&
      (options.requireSelection ?? props.requireSelectionToOpen)
    ) {
      showAiNotice('error', 'requiresSelection');
    }
    return;
  }
  placeAiPromptFromEvent(event);
  aiSelectionPromptOpen.value = true;
  aiCustomAction.value = null;
  aiCustomPrompt.value = '';
}

function isActionDisabled(action: AiActionDef): boolean {
  if (aiResolving.value || props.editable === false) {
    return true;
  }
  return action.requiresSelection && !hasAiSelection.value;
}

function actionNeedsInlinePrompt(action: AiActionDef): boolean {
  return action.action === 'custom';
}

function resolveApplyMode(action: AiActionDef): RichTextAiApplyMode {
  if (action.action === 'custom') {
    return hasAiSelection.value ? 'replace_selection' : 'insert_at_cursor';
  }
  return action.defaultApplyMode;
}

function buildInstruction(action: AiActionDef, customPrompt?: string): string {
  if (typeof customPrompt === 'string' && customPrompt.trim()) {
    return customPrompt.trim();
  }
  if (action.action === 'insert') return translateAi('instructions.insert');
  if (action.action === 'format') return translateAi('instructions.format');
  if (action.action === 'custom') return translateAi('instructions.custom');
  if (action.action === 'chat') return translateAi('instructions.more');
  return translateAi('instructions.base');
}

function buildOperationInstruction(
  action: AiActionDef,
  selection: TextSelectionAiSnapshot,
  customPrompt?: string,
): string {
  const instruction = buildInstruction(action, customPrompt);
  const language = resolveOperationLanguage(action, selection);
  const languageInstruction = translateAi('languageInstruction', {
    language: languageDisplayName(language),
  });
  return [instruction, languageInstruction].filter(Boolean).join('\n');
}

function applyModeLabel(mode: RichTextAiApplyMode | string): string {
  if (mode === 'copy_only') return translateAi('applyMode.insert');
  if (mode === 'append_to_document') return translateAi('applyMode.insert');
  if (mode === 'insert_at_cursor') return translateAi('applyMode.insert');
  if (mode === 'insert_after_selection') {
    return translateAi('applyMode.insertAfterSelection');
  }
  return translateAi('applyMode.replace');
}

function buildOperationPayload(
  action: AiActionDef,
  selection: TextSelectionAiSnapshot,
  customPrompt?: string,
): RichTextAiOperationPayload {
  const instruction = buildOperationInstruction(
    action,
    selection,
    customPrompt,
  );
  const formatInstruction = buildInstruction(action, customPrompt);
  const targetLang = operationTargetLang(action, selection);
  const payload: RichTextAiOperationPayload = {
    selected_text: selection.selectedText,
    before_text: selection.beforeText,
    after_text: selection.afterText,
    document_title: props.documentTitle?.trim() || '',
    document_id: props.documentId ?? undefined,
    document_type: props.documentType || 'plain_text',
    surface: props.surface || 'text_selection_input',
    instruction,
    format_instruction: action.action === 'format' ? formatInstruction : '',
  };
  if (targetLang) {
    payload.target_lang = targetLang;
  }
  if (selection.plainInputPolicy) {
    payload.plain_input_policy = {
      allowed_actions: selection.plainInputPolicy.allowedActions,
      enabled: selection.plainInputPolicy.enabled,
      field_kind: selection.plainInputPolicy.fieldKind,
    };
  }
  return payload;
}

function normalizePreviewDone(
  done: RichTextAiOperationDoneEvent,
  action: AiActionDef,
) {
  if (!aiPreview.value || aiPreview.value.action.key !== action.key) return;
  aiPreview.value.conversationId =
    typeof done.conversation_id === 'number' ? done.conversation_id : null;
  aiPreview.value.applyMode =
    done.apply_strategy === 'replace_or_insert_by_context'
      ? resolveApplyMode(action)
      : done.apply_strategy || resolveApplyMode(action);
  aiPreview.value.outputContract = done.output_contract || '';
}

function handleAiStreamError(error?: unknown) {
  const message =
    typeof error === 'object' &&
    error !== null &&
    'message' in error &&
    typeof (error as { message?: unknown }).message === 'string'
      ? (error as { message: string }).message || translateAi('streamError')
      : translateAi('streamError');
  if (aiPreview.value) {
    aiPreview.value.loading = false;
    aiPreview.value.error = message;
    aiPreview.value.draft = '';
  }
  showAiNotice('error', 'streamError');
}

function abortAiStream() {
  aiStreamingAbortController.value?.abort();
  aiStreamingAbortController.value = null;
}

async function resolveAiAssignment(): Promise<AgentAssignmentResolveResult | null> {
  aiResolving.value = true;
  try {
    const assignment = await resolveAgentAssignmentApi(
      aiApiPrefix.value,
      aiFeatureCode.value,
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
    return assignment;
  } catch {
    aiAssignment.value = null;
    showAiNotice('error', 'noPermission');
    return null;
  } finally {
    aiResolving.value = false;
  }
}

async function runEditorAiOperation(
  action: AiActionDef,
  selection: TextSelectionAiSnapshot,
  customPrompt?: string,
) {
  abortAiStream();
  const controller = new AbortController();
  aiStreamingAbortController.value = controller;

  aiPreview.value = {
    action,
    applyMode: resolveApplyMode(action),
    conversationId: null,
    customPrompt: customPrompt?.trim() ?? '',
    draft: '',
    error: '',
    loading: true,
    outputContract: '',
    selection,
    targetLanguageLabel: languageDisplayName(
      resolveOperationLanguage(action, selection),
    ),
  };
  aiSelectionPromptOpen.value = true;
  aiCustomAction.value = null;
  aiCustomPrompt.value = '';
  await nextTick();
  repositionAiFloatingLayer();

  try {
    await streamRichTextAiOperationApi(
      aiApiPrefix.value,
      action.endpointFeature,
      buildOperationPayload(action, selection, customPrompt),
      {
        onMessage(delta) {
          if (!aiPreview.value || aiPreview.value.action.key !== action.key) {
            return;
          }
          aiPreview.value.draft += delta;
        },
        onDone(done) {
          normalizePreviewDone(done, action);
        },
        onError(error) {
          handleAiStreamError(error);
        },
        onEnd() {
          if (aiPreview.value && aiPreview.value.action.key === action.key) {
            aiPreview.value.loading = false;
          }
        },
      },
      { abortController: controller },
    );
  } catch (error) {
    if (!controller.signal.aborted) {
      handleAiStreamError(error);
    }
  } finally {
    if (aiStreamingAbortController.value === controller) {
      aiStreamingAbortController.value = null;
    }
    if (aiPreview.value && aiPreview.value.action.key === action.key) {
      aiPreview.value.loading = false;
    }
  }
}

function toInlineChatHistory(
  messages: readonly AiInlineChatMessage[],
): Array<{ content: string; role: AiInlineChatRole }> {
  return messages
    .filter((message) => message.content.trim() && !message.loading)
    .slice(-10)
    .map((message) => ({
      content: message.content.trim(),
      role: message.role,
    }));
}

function nextInlineChatMessageId(): number {
  aiInlineChatMessageSeq.value += 1;
  return aiInlineChatMessageSeq.value;
}

function buildInlineChatPayload(
  action: AiActionDef,
  selection: TextSelectionAiSnapshot,
  prompt: string,
  history: Array<{ content: string; role: AiInlineChatRole }>,
): RichTextAiOperationPayload {
  return {
    ...buildOperationPayload(action, selection, prompt),
    history,
  };
}

function ensureInlineChatState(
  action: AiActionDef,
  selection: TextSelectionAiSnapshot,
): AiInlineChatState {
  if (!aiInlineChat.value || aiInlineChat.value.action.key !== action.key) {
    aiInlineChat.value = {
      action,
      conversationId: null,
      error: '',
      input: '',
      loading: false,
      messages: [],
      selection,
      targetLanguageLabel: languageDisplayName(
        resolveOperationLanguage(action, selection),
      ),
    };
  }
  return aiInlineChat.value;
}

function handleInlineChatStreamError(
  assistantMessage: AiInlineChatMessage,
  error?: unknown,
) {
  const message =
    typeof error === 'object' &&
    error !== null &&
    'message' in error &&
    typeof (error as { message?: unknown }).message === 'string'
      ? (error as { message: string }).message || translateAi('streamError')
      : translateAi('streamError');
  assistantMessage.loading = false;
  assistantMessage.error = message;
  if (aiInlineChat.value) {
    aiInlineChat.value.loading = false;
    aiInlineChat.value.error = message;
  }
  showAiNotice('error', 'streamError');
}

async function runInlineAiChat(
  action: AiActionDef,
  selection: TextSelectionAiSnapshot,
  prompt?: string,
) {
  abortAiStream();
  aiPreview.value = null;
  const controller = new AbortController();
  aiStreamingAbortController.value = controller;
  const state = ensureInlineChatState(action, selection);
  const promptText =
    prompt?.trim() ||
    buildInstruction(action).trim() ||
    translateAi('inlineChatDefaultPrompt');
  const history = toInlineChatHistory(state.messages);
  const userMessage: AiInlineChatMessage = {
    content: promptText,
    error: '',
    id: nextInlineChatMessageId(),
    loading: false,
    role: 'user',
  };
  const assistantMessage: AiInlineChatMessage = {
    content: '',
    error: '',
    id: nextInlineChatMessageId(),
    loading: true,
    role: 'assistant',
  };
  state.messages.push(userMessage, assistantMessage);
  state.input = '';
  state.error = '';
  state.loading = true;
  aiSelectionPromptOpen.value = true;
  aiCustomAction.value = null;
  aiCustomPrompt.value = '';
  await nextTick();
  repositionAiFloatingLayer();

  try {
    await streamRichTextAiOperationApi(
      aiApiPrefix.value,
      action.endpointFeature,
      buildInlineChatPayload(action, selection, promptText, history),
      {
        onMessage(delta) {
          assistantMessage.content += delta;
        },
        onDone(done) {
          state.conversationId =
            typeof done.conversation_id === 'number'
              ? done.conversation_id
              : state.conversationId;
        },
        onError(error) {
          handleInlineChatStreamError(assistantMessage, error);
        },
        onEnd() {
          assistantMessage.loading = false;
          state.loading = false;
        },
      },
      { abortController: controller },
    );
  } catch (error) {
    if (!controller.signal.aborted) {
      handleInlineChatStreamError(assistantMessage, error);
    }
  } finally {
    if (aiStreamingAbortController.value === controller) {
      aiStreamingAbortController.value = null;
    }
    assistantMessage.loading = false;
    state.loading = false;
  }
}

async function runAiAction(action: AiActionDef, customPrompt?: string) {
  const selection = aiSelection.value ?? getCurrentSelection();
  if (action.requiresSelection && selection.empty) {
    showAiNotice('error', 'requiresSelection');
    return;
  }
  if (actionNeedsInlinePrompt(action) && !customPrompt?.trim()) {
    aiCustomAction.value = action;
    return;
  }

  if (!(await resolveAiAssignment())) return;

  if (action.action === 'chat') {
    void runInlineAiChat(action, selection, customPrompt);
    return;
  }

  void runEditorAiOperation(action, selection, customPrompt);
}

function submitCustomPrompt() {
  if (!aiCustomAction.value) return;
  if (!aiCustomPrompt.value.trim()) {
    showAiNotice('error', 'emptyCustomPrompt');
    return;
  }
  void runAiAction(aiCustomAction.value, aiCustomPrompt.value);
}

function discardAiPreview() {
  abortAiStream();
  aiPreview.value = null;
  aiSelectionPromptOpen.value = false;
  aiCustomAction.value = null;
  aiCustomPrompt.value = '';
}

function discardInlineChat() {
  abortAiStream();
  aiInlineChat.value = null;
  aiSelectionPromptOpen.value = false;
  aiCustomAction.value = null;
  aiCustomPrompt.value = '';
}

function stopInlineChat() {
  if (!aiInlineChat.value) return;
  abortAiStream();
  for (const message of aiInlineChat.value.messages) {
    message.loading = false;
  }
  aiInlineChat.value.loading = false;
  showAiNotice('info', 'chatStopped');
}

async function submitInlineChatPrompt() {
  const state = aiInlineChat.value;
  const prompt = state?.input.trim() ?? '';
  if (!state || !prompt) {
    showAiNotice('error', 'inlineChatEmptyPrompt');
    return;
  }
  if (!(await resolveAiAssignment())) return;
  void runInlineAiChat(state.action, state.selection, prompt);
}

function retryAiPreview() {
  const preview = aiPreview.value;
  if (!preview) return;
  void runEditorAiOperation(
    preview.action,
    preview.selection,
    preview.customPrompt,
  );
}

function stopAiPreview() {
  if (!aiPreview.value) return;
  abortAiStream();
  aiPreview.value.loading = false;
  showAiNotice('info', 'stopped');
}

async function copyAiPreview() {
  const content = aiPreview.value?.draft.trim() ?? '';
  if (!content) {
    showAiNotice('error', 'emptyResult');
    return;
  }
  try {
    if (!navigator.clipboard?.writeText) {
      throw new Error('Clipboard API unavailable');
    }
    await navigator.clipboard.writeText(content);
    showAiNotice('success', 'copied');
  } catch {
    showAiNotice('error', 'copyFailed');
  }
}

async function copyInlineChatMessage(message: AiInlineChatMessage) {
  const content = message.content.trim();
  if (!content) {
    showAiNotice('error', 'emptyResult');
    return;
  }
  try {
    if (!navigator.clipboard?.writeText) {
      throw new Error('Clipboard API unavailable');
    }
    await navigator.clipboard.writeText(content);
    showAiNotice('success', 'copied');
  } catch {
    showAiNotice('error', 'copyFailed');
  }
}

function insertInlineChatMessage(message: AiInlineChatMessage) {
  const state = aiInlineChat.value;
  const content = message.content.trim();
  if (!state || !content) {
    showAiNotice('error', 'emptyResult');
    return;
  }
  if (!props.validateSelection(state.selection)) {
    state.error = translateAi('selectionDrifted');
    showAiNotice('error', 'selectionDrifted');
    return;
  }
  const applied = props.applyResult({
    applyMode: 'insert_after_selection',
    content,
    mode: 'insert',
    selection: state.selection,
  });
  if (applied === false) return;
  showAiNotice('success', 'applied');
}

function applyAiPreview() {
  const preview = aiPreview.value;
  if (!preview) return;
  const content = preview.draft.trim();
  if (!content) {
    showAiNotice('error', 'emptyResult');
    return;
  }
  if (!props.validateSelection(preview.selection)) {
    preview.error = translateAi('selectionDrifted');
    showAiNotice('error', 'selectionDrifted');
    return;
  }
  const mode = preview.applyMode === 'replace_selection' ? 'replace' : 'insert';
  const applied = props.applyResult({
    applyMode: preview.applyMode,
    content,
    mode,
    selection: preview.selection,
  });
  if (applied === false) return;
  discardAiPreview();
  showAiNotice('success', 'applied');
}

function close() {
  if (aiPreview.value) {
    discardAiPreview();
    return;
  }
  if (aiInlineChat.value) {
    discardInlineChat();
    return;
  }
  aiSelectionPromptOpen.value = false;
  aiCustomAction.value = null;
}

function isWorkflowActive() {
  return !!aiPreview.value || !!aiInlineChat.value || aiResolving.value;
}

function isPromptOpen() {
  return aiSelectionPromptOpen.value;
}

watch(aiSelectionPromptOpen, (open) => {
  if (open) {
    addAiFloatingAnchorListeners();
    nextTick(() => {
      setTimeout(
        () => document.addEventListener('click', onDocumentAiPromptClick),
        0,
      );
    });
  } else {
    removeAiFloatingAnchorListeners();
    document.removeEventListener('click', onDocumentAiPromptClick);
  }
});

function onDocumentAiPromptClick(event: MouseEvent) {
  const target = event.target as Element | null;
  if (
    !target?.closest?.('[data-text-selection-ai-assist]') &&
    !aiPreview.value &&
    !aiInlineChat.value
  )
    closeAiSelectionPrompt();
}

function onPromptKeydown(event: KeyboardEvent) {
  if (event.key !== 'Escape') return;
  event.stopPropagation();
  if (aiPreview.value) discardAiPreview();
  else if (aiInlineChat.value) discardInlineChat();
  else closeAiSelectionPrompt();
}

onBeforeUnmount(() => {
  abortAiStream();
  document.removeEventListener('click', onDocumentAiPromptClick);
  removeAiFloatingAnchorListeners();
});

defineExpose<TextSelectionAiAssistExpose>({
  close,
  discard: close,
  isPromptOpen,
  isWorkflowActive,
  notify: showAiNotice,
  open,
  reposition: repositionAiFloatingLayer,
});
</script>

<template>
  <div
    v-if="aiNotice"
    class="fixed bottom-5 left-1/2 z-[1100] -translate-x-1/2 rounded-lg border px-4 py-2 text-sm shadow-lg"
    :class="{
      'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900/50 dark:bg-blue-950/40 dark:text-blue-300':
        aiNotice.type === 'info',
      'border-green-200 bg-green-50 text-green-700 dark:border-green-900/50 dark:bg-green-950/40 dark:text-green-300':
        aiNotice.type === 'success',
      'border-red-200 bg-red-50 text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300':
        aiNotice.type === 'error',
    }"
    aria-live="polite"
    data-testid="rte-ai-notice"
  >
    {{ aiNotice.text }}
  </div>

  <div
    v-if="aiSelectionPromptOpen"
    data-rte-ai-selection-prompt
    data-text-selection-ai-assist
    data-testid="rte-ai-selection-prompt"
    :role="aiPreview || aiInlineChat ? 'dialog' : 'menu'"
    class="fixed z-[1050] max-w-[calc(100vw-16px)] rounded-xl border border-border bg-popover p-1 text-popover-foreground shadow-lg"
    :style="aiFloatingLayerStyle"
    @click.stop
    @keydown="onPromptKeydown"
  >
    <div v-if="!aiPreview && !aiInlineChat" class="space-y-1">
      <div
        v-for="(row, rowIndex) in aiActionRows"
        :key="rowIndex"
        class="flex items-center gap-1"
        :data-testid="`rte-ai-action-row-${rowIndex + 1}`"
      >
        <span
          v-if="rowIndex === 0"
          class="inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
          :aria-label="translateAi('menuTitle')"
          data-testid="rte-ai-trigger-icon"
        >
          <IconifyIcon icon="lucide:sparkles" class="size-4" />
        </span>
        <span v-else class="size-8 shrink-0" aria-hidden="true"></span>
        <button
          v-for="action in row"
          :key="action.key"
          type="button"
          role="menuitem"
          class="inline-flex min-h-8 items-center justify-center gap-1.5 rounded-lg text-sm hover:bg-accent disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:bg-transparent"
          :class="
            compactActionMenu
              ? 'max-w-[136px] flex-none px-2.5'
              : 'min-w-0 flex-1 px-2'
          "
          :aria-label="translateAiAction(action)"
          :data-testid="`rte-ai-action-${action.key}`"
          :disabled="isActionDisabled(action)"
          @click="
            actionNeedsInlinePrompt(action)
              ? (aiCustomAction = action)
              : runAiAction(action)
          "
        >
          <IconifyIcon
            :icon="action.icon"
            class="size-3.5 shrink-0"
            :data-testid="`rte-ai-action-${action.key}-icon`"
          />
          <span class="truncate">{{ translateAiAction(action) }}</span>
        </button>
        <button
          v-if="rowIndex === aiActionRows.length - 1"
          type="button"
          class="inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent"
          :class="{ 'ml-auto': compactActionMenu }"
          :aria-label="translateAi('close')"
          data-testid="rte-ai-selection-prompt-close"
          @click="close()"
        >
          <IconifyIcon icon="lucide:x" class="size-3.5" />
        </button>
        <span v-else class="size-8 shrink-0" aria-hidden="true"></span>
      </div>
    </div>

    <div
      v-if="aiResolving"
      class="px-2 pb-1 text-xs text-muted-foreground"
      aria-live="polite"
      data-testid="rte-ai-resolving"
    >
      {{ translateAi('connecting') }}
    </div>

    <div
      v-if="!aiPreview && !aiInlineChat && aiCustomAction"
      class="mt-1 border-t border-border p-2"
    >
      <textarea
        v-model="aiCustomPrompt"
        class="min-h-[72px] w-full resize-none rounded-lg border border-border bg-background p-2 text-sm outline-none focus:border-primary"
        :placeholder="translateAi('customPromptPlaceholder')"
        data-testid="rte-ai-custom-prompt"
      ></textarea>
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

    <div v-if="aiInlineChat" class="p-3" data-testid="rte-ai-inline-chat">
      <div class="mb-2 flex items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="flex items-center gap-2 text-sm font-medium">
            <IconifyIcon
              :icon="aiInlineChat.action.icon"
              class="size-4 text-primary"
            />
            <span
              >{{ translateAi('inlineChatTitle') }} ·
              {{ translateAiAction(aiInlineChat.action) }}</span
            >
          </div>
          <div class="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
            <span class="rounded-full bg-primary/10 px-2 py-0.5 text-primary">
              {{ translateAi('inlineChatContext') }}
            </span>
            <span
              class="rounded-full bg-muted px-2 py-0.5 text-muted-foreground"
            >
              {{
                translateAi('languageOutput', {
                  language: aiInlineChat.targetLanguageLabel,
                })
              }}
            </span>
          </div>
        </div>
        <button
          type="button"
          class="inline-flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-accent"
          :aria-label="translateAi('close')"
          data-testid="rte-ai-inline-chat-close"
          @click="discardInlineChat"
        >
          <IconifyIcon icon="lucide:x" class="size-4" />
        </button>
      </div>

      <div
        class="max-h-[280px] space-y-2 overflow-y-auto rounded-lg border border-border bg-background/60 p-2"
        data-testid="rte-ai-inline-chat-messages"
      >
        <div
          v-for="message in aiInlineChat.messages"
          :key="message.id"
          class="flex"
          :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
          :data-testid="`rte-ai-inline-chat-message-${message.role}`"
        >
          <div
            class="max-w-[88%] rounded-lg px-3 py-2 text-sm leading-6"
            :class="
              message.role === 'user'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-foreground'
            "
          >
            <div class="whitespace-pre-wrap break-words">
              {{
                message.content ||
                (message.loading ? translateAi('previewLoading') : '')
              }}
            </div>
            <div
              v-if="message.error"
              class="mt-1 text-xs text-red-600 dark:text-red-300"
              data-testid="rte-ai-inline-chat-message-error"
            >
              {{ message.error }}
            </div>
            <div
              v-if="
                message.role === 'assistant' &&
                message.content.trim() &&
                !message.loading &&
                !message.error
              "
              class="mt-2 flex flex-wrap gap-1"
            >
              <button
                type="button"
                class="inline-flex min-h-7 items-center gap-1 rounded-md px-2 text-xs hover:bg-background"
                data-testid="rte-ai-inline-chat-copy"
                @click="copyInlineChatMessage(message)"
              >
                <IconifyIcon icon="lucide:copy" class="size-3" />
                {{ translateAi('copy') }}
              </button>
              <button
                type="button"
                class="inline-flex min-h-7 items-center gap-1 rounded-md px-2 text-xs hover:bg-background"
                data-testid="rte-ai-inline-chat-insert"
                @click="insertInlineChatMessage(message)"
              >
                <IconifyIcon icon="lucide:file-plus-2" class="size-3" />
                {{ translateAi('inlineChatInsert') }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="aiInlineChat.error"
        class="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300"
        data-testid="rte-ai-inline-chat-error"
      >
        {{ aiInlineChat.error }}
      </div>

      <div class="mt-3">
        <textarea
          v-model="aiInlineChat.input"
          class="min-h-[72px] w-full resize-none rounded-lg border border-border bg-background p-2 text-sm outline-none focus:border-primary"
          :placeholder="translateAi('inlineChatComposerPlaceholder')"
          data-testid="rte-ai-inline-chat-input"
          @keydown.enter.exact.prevent="submitInlineChatPrompt"
        ></textarea>
        <div class="mt-2 flex items-center justify-between gap-2">
          <button
            type="button"
            class="inline-flex min-h-9 items-center gap-1.5 rounded-md px-3 text-sm hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="!aiInlineChat.loading"
            data-testid="rte-ai-inline-chat-stop"
            @click="stopInlineChat"
          >
            <IconifyIcon icon="lucide:square" class="size-3.5" />
            {{ translateAi('stop') }}
          </button>
          <button
            type="button"
            class="inline-flex min-h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="aiInlineChat.loading || !aiInlineChat.input.trim()"
            data-testid="rte-ai-inline-chat-send"
            @click="submitInlineChatPrompt"
          >
            <IconifyIcon icon="lucide:send" class="size-3.5" />
            {{ translateAi('inlineChatSend') }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="aiPreview" class="p-3" data-testid="rte-ai-preview-card">
      <div class="mb-2 flex items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="flex items-center gap-2 text-sm font-medium">
            <IconifyIcon
              :icon="aiPreview.action.icon"
              class="size-4 text-primary"
            />
            <span
              >{{ translateAi('previewTitle') }} ·
              {{ translateAiAction(aiPreview.action) }}</span
            >
          </div>
          <div class="mt-0.5 text-xs text-muted-foreground">
            {{
              aiPreview.loading
                ? translateAi('previewLoading')
                : translateAi('previewHint')
            }}
          </div>
          <div class="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
            <span class="rounded-full bg-primary/10 px-2 py-0.5 text-primary">
              {{ applyModeLabel(aiPreview.applyMode) }}
            </span>
            <span
              class="rounded-full bg-muted px-2 py-0.5 text-muted-foreground"
            >
              {{
                translateAi('languageOutput', {
                  language: aiPreview.targetLanguageLabel,
                })
              }}
            </span>
          </div>
        </div>
        <button
          type="button"
          class="inline-flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-accent"
          :aria-label="translateAi('close')"
          data-testid="rte-ai-preview-close"
          @click="discardAiPreview"
        >
          <IconifyIcon icon="lucide:x" class="size-4" />
        </button>
      </div>

      <textarea
        v-model="aiPreview.draft"
        class="min-h-[180px] w-full resize-y rounded-lg border border-border bg-background p-3 text-sm leading-6 outline-none focus:border-primary"
        :placeholder="translateAi('previewPlaceholder')"
        data-testid="rte-ai-preview-editor"
      ></textarea>

      <div
        v-if="aiPreview.error"
        class="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300"
        data-testid="rte-ai-preview-error"
      >
        {{ aiPreview.error }}
      </div>

      <div class="mt-3 flex items-center justify-between gap-2">
        <button
          type="button"
          class="inline-flex min-h-9 items-center gap-1.5 rounded-md px-3 text-sm hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="
            !aiPreview.loading && !aiPreview.draft.trim() && !aiPreview.error
          "
          data-testid="rte-ai-preview-retry"
          @click="aiPreview.loading ? stopAiPreview() : retryAiPreview()"
        >
          <IconifyIcon
            :icon="aiPreview.loading ? 'lucide:square' : 'lucide:refresh-cw'"
            class="size-3.5"
          />
          {{
            aiPreview.loading
              ? translateAi('stop')
              : aiPreview.error
                ? translateAi('retry')
                : translateAi('regenerate')
          }}
        </button>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="inline-flex min-h-9 items-center gap-1.5 rounded-md px-3 text-sm hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="!aiPreview.draft.trim()"
            data-testid="rte-ai-preview-copy"
            @click="copyAiPreview"
          >
            <IconifyIcon icon="lucide:copy" class="size-3.5" />
            {{ translateAi('copy') }}
          </button>
          <button
            type="button"
            class="min-h-9 rounded-md px-3 text-sm hover:bg-accent"
            data-testid="rte-ai-preview-discard"
            @click="discardAiPreview"
          >
            {{ translateAi('discard') }}
          </button>
          <button
            type="button"
            class="inline-flex min-h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-sm text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="
              aiPreview.loading || !!aiPreview.error || !aiPreview.draft.trim()
            "
            data-testid="rte-ai-preview-apply"
            @click="applyAiPreview"
          >
            <IconifyIcon icon="lucide:check" class="size-3.5" />
            {{ translateAi('apply') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
