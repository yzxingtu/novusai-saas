<script lang="ts" setup>
import type {
  TextSelectionAiAnchorRect,
  TextSelectionAiApplyRequest,
  TextSelectionAiAssistExpose,
  TextSelectionAiSnapshot,
} from './types';

import type { RichTextAiActionType } from '#/features/rich-text-ai';

import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { isRichTextAiWritingAction } from '#/features/rich-text-ai';

import TextSelectionAiAssist from './TextSelectionAiAssist.vue';

defineOptions({ name: 'GlobalPlainTextInputAiAssist' });

const props = withDefaults(
  defineProps<{
    apiPrefix: string;
    enabled?: boolean;
  }>(),
  {
    enabled: true,
  },
);

type TextControlElement = HTMLInputElement | HTMLTextAreaElement;
type PlainTextInputAiFieldKind =
  | 'code'
  | 'description'
  | 'markdown'
  | 'plain'
  | 'secret'
  | 'structured'
  | 'title';

interface PlainTextInputAiFieldPolicy {
  actions: RichTextAiActionType[];
  kind: PlainTextInputAiFieldKind;
  multiline: boolean;
}

interface PlainTextInputAiSession {
  afterText: string;
  beforeText: string;
  fieldPolicy: PlainTextInputAiFieldPolicy;
  from: number;
  selectedText: string;
  selectionDirection: HTMLInputElement['selectionDirection'];
  sessionId: string;
  target: TextControlElement;
  to: number;
  valueHash: string;
}

const INPUT_CONTEXT_BEFORE_CHARS = 2000;
const INPUT_CONTEXT_AFTER_CHARS = 500;
const ASSIST_ATTRIBUTE = 'data-input-ai-assist';
const ASSIST_ACTIONS_ATTRIBUTE = 'data-input-ai-assist-actions';
const ASSIST_KIND_ATTRIBUTE = 'data-input-ai-assist-kind';
const assistRef = ref<null | TextSelectionAiAssistExpose>(null);
const activeSession = ref<null | PlainTextInputAiSession>(null);
let snapshotRevision = 0;
let listenerAttached = false;
let pendingMouseupOpenTimer: null | number = null;

const ignoredInputTypes = new Set([
  'button',
  'checkbox',
  'color',
  'date',
  'datetime-local',
  'email',
  'file',
  'hidden',
  'image',
  'month',
  'number',
  'password',
  'radio',
  'range',
  'reset',
  'submit',
  'tel',
  'time',
  'url',
  'week',
]);

const disabledKinds = new Set<PlainTextInputAiFieldKind>([
  'code',
  'secret',
  'structured',
]);

const singleLineDefaultActions: RichTextAiActionType[] = [
  'optimize',
  'rewrite',
  'proofread',
  'translate',
  'custom',
];

const multilineDefaultActions: RichTextAiActionType[] = [
  'continue',
  'rewrite',
  'insert',
  'optimize',
  'proofread',
  'translate',
  'summarize',
  'expand',
  'custom',
  'chat',
];

function isTextControlElement(
  target: EventTarget | null,
): target is TextControlElement {
  if (
    !(
      target instanceof HTMLInputElement ||
      target instanceof HTMLTextAreaElement
    )
  ) {
    return false;
  }
  if (target instanceof HTMLInputElement) {
    const type = target.type?.toLowerCase() || 'text';
    if (ignoredInputTypes.has(type)) return false;
  }
  return true;
}

function readPolicyAttribute(
  target: TextControlElement,
  name: string,
): null | string {
  const source = target.closest(`[${name}]`);
  return source?.getAttribute(name) ?? null;
}

function normalizeFieldKind(value: null | string): PlainTextInputAiFieldKind {
  const normalized = String(value || '')
    .trim()
    .toLowerCase();
  if (
    normalized === 'code' ||
    normalized === 'description' ||
    normalized === 'markdown' ||
    normalized === 'plain' ||
    normalized === 'secret' ||
    normalized === 'structured' ||
    normalized === 'title'
  ) {
    return normalized;
  }
  return 'plain';
}

function fieldIdentityText(target: TextControlElement): string {
  return [
    target.getAttribute('name'),
    target.getAttribute('id'),
    target.getAttribute('autocomplete'),
    target.getAttribute('aria-label'),
    target.getAttribute('placeholder'),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
}

function looksSensitiveOrStructured(target: TextControlElement): boolean {
  const text = fieldIdentityText(target);
  if (!text) return false;
  return /(?:^|[\s_.:-])(?:api[_-]?key|access[_-]?key|client[_-]?secret|captcha|code|email|e-mail|json|otp|password|passwd|phone|prompt[_-]?template|regexp?|secret|slug|sql|tel|token|uri|url|verification|verify|yaml|验证码|密钥|令牌|邮箱|链接|手机号|编号)(?:$|[\s_.:-])/i.test(
    text,
  );
}

function shouldSkipTarget(target: TextControlElement): boolean {
  const assistFlag = readPolicyAttribute(target, ASSIST_ATTRIBUTE);
  const kind = normalizeFieldKind(
    readPolicyAttribute(target, ASSIST_KIND_ATTRIBUTE),
  );
  return (
    target.disabled ||
    target.readOnly ||
    assistFlag === 'off' ||
    disabledKinds.has(kind) ||
    looksSensitiveOrStructured(target) ||
    target.closest('[data-text-selection-ai-assist]') !== null ||
    target.closest('.rte-editor') !== null ||
    target.closest('.ProseMirror') !== null
  );
}

function getSelectionRange(target: TextControlElement) {
  const start = target.selectionStart ?? 0;
  const end = target.selectionEnd ?? start;
  return {
    end: Math.max(start, end),
    start: Math.min(start, end),
  };
}

function hashText(value: string): string {
  let hash = 2_166_136_261;
  for (const char of value) {
    hash ^= char.codePointAt(0) ?? 0;
    hash = Math.imul(hash, 16_777_619);
  }
  return `${value.length}:${hash >>> 0}`;
}

function parseActionAllowlist(
  raw: null | string,
): null | RichTextAiActionType[] {
  if (!raw?.trim()) return null;
  const actions = raw
    .split(',')
    .map((item) => item.trim())
    .filter((item): item is RichTextAiActionType =>
      isRichTextAiWritingAction(item),
    );
  return [...new Set(actions)];
}

function resolveFieldPolicy(
  target: TextControlElement,
): null | PlainTextInputAiFieldPolicy {
  const explicitKind = normalizeFieldKind(
    readPolicyAttribute(target, ASSIST_KIND_ATTRIBUTE),
  );
  if (disabledKinds.has(explicitKind)) return null;

  const multiline = target instanceof HTMLTextAreaElement;
  const baseActions = multiline
    ? [...multilineDefaultActions]
    : [...singleLineDefaultActions];
  if (explicitKind === 'markdown' || explicitKind === 'description') {
    baseActions.push('format');
  }

  const allowlist = parseActionAllowlist(
    readPolicyAttribute(target, ASSIST_ACTIONS_ATTRIBUTE),
  );
  const actions =
    allowlist === null
      ? baseActions
      : baseActions.filter((action) => allowlist.includes(action));
  if (actions.length === 0) return null;
  return {
    actions: [...new Set(actions)],
    kind: explicitKind,
    multiline,
  };
}

function buildSession(
  target: TextControlElement,
): null | PlainTextInputAiSession {
  const fieldPolicy = resolveFieldPolicy(target);
  if (!fieldPolicy) return null;

  const { start, end } = getSelectionRange(target);
  const value = target.value ?? '';
  const selectedText = value.slice(start, end);
  if (start === end || !selectedText.trim()) return null;

  snapshotRevision += 1;
  return {
    afterText: value.slice(end, end + INPUT_CONTEXT_AFTER_CHARS),
    beforeText: value.slice(
      Math.max(0, start - INPUT_CONTEXT_BEFORE_CHARS),
      start,
    ),
    fieldPolicy,
    from: start,
    selectedText,
    selectionDirection: target.selectionDirection ?? 'none',
    sessionId: `plain-input-ai-${Date.now()}-${snapshotRevision}`,
    target,
    to: end,
    valueHash: hashText(value),
  };
}

function snapshotFromSession(
  session: PlainTextInputAiSession,
): TextSelectionAiSnapshot {
  return {
    afterText: session.afterText,
    beforeText: session.beforeText,
    empty: session.from === session.to,
    from: session.from,
    plainInputPolicy: {
      allowedActions: session.fieldPolicy.actions,
      enabled: true,
      fieldKind: session.fieldPolicy.kind,
    },
    revision: snapshotRevision,
    selectedText: session.selectedText,
    sessionId: session.sessionId,
    to: session.to,
  };
}

function getSelection(): null | TextSelectionAiSnapshot {
  const session = activeSession.value;
  if (
    !session ||
    !session.target.isConnected ||
    shouldSkipTarget(session.target)
  ) {
    return null;
  }
  return snapshotFromSession(session);
}

function isSameSession(selection: TextSelectionAiSnapshot): boolean {
  return (
    !!activeSession.value &&
    selection.sessionId === activeSession.value.sessionId
  );
}

function validateSelection(selection: TextSelectionAiSnapshot): boolean {
  const session = activeSession.value;
  if (!session || !isSameSession(selection)) return false;
  const target = session.target;
  if (!target.isConnected || shouldSkipTarget(target)) return false;
  const value = target.value ?? '';
  if (hashText(value) !== session.valueHash) return false;
  if (session.from < 0 || session.to > value.length) return false;
  return value.slice(session.from, session.to) === session.selectedText;
}

function normalizeInsertContent(
  target: TextControlElement,
  content: string,
): string {
  if (target instanceof HTMLTextAreaElement) return content;
  return content.replaceAll(/\s*\n\s*/g, ' ').trim();
}

function canApplyValue(target: TextControlElement, value: string): boolean {
  const maxLength = target.maxLength;
  if (
    Number.isFinite(maxLength) &&
    maxLength > -1 &&
    value.length > maxLength
  ) {
    return false;
  }

  if (target instanceof HTMLInputElement && target.pattern) {
    try {
      const pattern = new RegExp(`^(?:${target.pattern})$`);
      if (!pattern.test(value)) return false;
    } catch {
      return false;
    }
  }
  return true;
}

function applyResult(request: TextSelectionAiApplyRequest): boolean {
  const session = activeSession.value;
  if (!session || !validateSelection(request.selection)) return false;

  const target = session.target;
  const value = target.value ?? '';
  let start = session.to;
  if (request.mode === 'replace' || request.applyMode === 'insert_at_cursor') {
    start = session.from;
  }
  const end = request.mode === 'replace' ? session.to : start;
  const content = normalizeInsertContent(target, request.content);
  const nextValue = `${value.slice(0, start)}${content}${value.slice(end)}`;

  if (!canApplyValue(target, nextValue)) {
    assistRef.value?.notify('error', 'constraintFailed');
    return false;
  }

  target.focus();
  target.setRangeText(content, start, end, 'end');
  target.dispatchEvent(new Event('input', { bubbles: true }));
  target.dispatchEvent(new Event('change', { bubbles: true }));
  activeSession.value = null;
  return true;
}

function readNumberStyle(style: CSSStyleDeclaration, name: string): number {
  const value = Number.parseFloat(style.getPropertyValue(name));
  return Number.isFinite(value) ? value : 0;
}

function buildInputAnchorRect(
  target: TextControlElement,
  position = getSelectionRange(target).end,
): TextSelectionAiAnchorRect {
  const elementRect = target.getBoundingClientRect();
  const style = window.getComputedStyle(target);
  const mirror = document.createElement('div');
  const span = document.createElement('span');
  const copiedStyleNames = [
    'border-bottom-width',
    'border-left-width',
    'border-right-width',
    'border-top-width',
    'box-sizing',
    'font-family',
    'font-size',
    'font-style',
    'font-weight',
    'letter-spacing',
    'line-height',
    'padding-bottom',
    'padding-left',
    'padding-right',
    'padding-top',
    'text-transform',
    'white-space',
    'word-break',
    'word-spacing',
    'word-wrap',
  ];

  for (const name of copiedStyleNames) {
    mirror.style.setProperty(name, style.getPropertyValue(name));
  }

  mirror.style.position = 'fixed';
  mirror.style.left = `${elementRect.left}px`;
  mirror.style.top = `${elementRect.top}px`;
  mirror.style.width = `${elementRect.width}px`;
  mirror.style.height = 'auto';
  mirror.style.visibility = 'hidden';
  mirror.style.overflow = 'hidden';
  mirror.style.whiteSpace =
    target instanceof HTMLTextAreaElement ? 'pre-wrap' : 'pre';
  mirror.style.overflowWrap = 'break-word';
  mirror.textContent = (target.value ?? '').slice(0, position) || ' ';
  span.textContent = '\u200B';
  mirror.append(span);
  document.body.append(mirror);

  const spanRect = span.getBoundingClientRect();
  mirror.remove();

  const borderLeft = readNumberStyle(style, 'border-left-width');
  const borderTop = readNumberStyle(style, 'border-top-width');
  const left = Math.max(
    elementRect.left,
    Math.min(spanRect.left - target.scrollLeft + borderLeft, elementRect.right),
  );
  const top = Math.max(
    elementRect.top,
    Math.min(spanRect.top - target.scrollTop + borderTop, elementRect.bottom),
  );
  const height =
    Number.parseFloat(style.lineHeight) ||
    Number.parseFloat(style.fontSize) ||
    Math.max(1, elementRect.height);

  return {
    bottom: top + height,
    height,
    left,
    right: left + 1,
    top,
    width: 1,
  };
}

function getAnchorRect(): null | TextSelectionAiAnchorRect {
  const session = activeSession.value;
  if (
    !session ||
    !session.target.isConnected ||
    shouldSkipTarget(session.target)
  ) {
    return null;
  }
  return buildInputAnchorRect(session.target, session.to);
}

function resolveTextControl(
  target: EventTarget | null,
): null | TextControlElement {
  if (isTextControlElement(target)) return target;
  if (!(target instanceof Element)) return resolveActiveTextControl();
  const candidate = target.closest('input,textarea');
  if (isTextControlElement(candidate)) return candidate;
  return resolveActiveTextControl();
}

function resolveActiveTextControl(): null | TextControlElement {
  const active = document.activeElement;
  return isTextControlElement(active) ? active : null;
}

function hasUsableSelection(target: TextControlElement): boolean {
  const { start, end } = getSelectionRange(target);
  const selectedText = (target.value ?? '').slice(start, end);
  return start !== end && selectedText.trim().length > 0;
}

function closePromptForCollapsedSelection(target: TextControlElement): boolean {
  if (hasUsableSelection(target)) return false;
  if (
    activeSession.value?.target === target &&
    !assistRef.value?.isWorkflowActive()
  ) {
    activeSession.value = null;
    assistRef.value?.close();
  }
  return true;
}

function activateSession(
  target: TextControlElement,
  event?: KeyboardEvent | MouseEvent,
  options: { silent?: boolean } = {},
) {
  if (assistRef.value?.isWorkflowActive()) return;
  if (assistRef.value?.isPromptOpen()) return;
  const session = buildSession(target);
  if (!session) return;
  activeSession.value = session;
  assistRef.value?.open(event, {
    requireSelection: true,
    silent: options.silent,
  });
}

function openForEvent(event: KeyboardEvent | MouseEvent) {
  if (!props.enabled) return;
  const target = resolveTextControl(event.target);
  if (!target || shouldSkipTarget(target)) return;
  if (closePromptForCollapsedSelection(target)) return;
  activateSession(target, event, { silent: true });
}

function onDocumentMouseup(event: MouseEvent) {
  if (
    (event.target as Element | null)?.closest?.(
      '[data-text-selection-ai-assist]',
    )
  ) {
    return;
  }
  if (pendingMouseupOpenTimer !== null) {
    window.clearTimeout(pendingMouseupOpenTimer);
  }
  pendingMouseupOpenTimer = window.setTimeout(() => {
    pendingMouseupOpenTimer = null;
    void nextTick(() => openForEvent(event));
  }, 0);
}

function onDocumentKeyup(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    assistRef.value?.close();
    activeSession.value = null;
    return;
  }
  void nextTick(() => openForEvent(event));
}

function onDocumentContextMenu(event: MouseEvent) {
  const target = resolveTextControl(event.target);
  if (!target || shouldSkipTarget(target)) return;
  const { start, end } = getSelectionRange(target);
  if (start === end) return;
  event.preventDefault();
  activateSession(target, event);
}

function onDocumentSelectionChange() {
  const target = resolveActiveTextControl();
  if (!target || shouldSkipTarget(target)) return;
  closePromptForCollapsedSelection(target);
}

function attachListeners() {
  if (listenerAttached) return;
  document.addEventListener('mouseup', onDocumentMouseup, true);
  document.addEventListener('keyup', onDocumentKeyup, true);
  document.addEventListener('contextmenu', onDocumentContextMenu, true);
  document.addEventListener('selectionchange', onDocumentSelectionChange, true);
  listenerAttached = true;
}

function detachListeners() {
  if (!listenerAttached) return;
  if (pendingMouseupOpenTimer !== null) {
    window.clearTimeout(pendingMouseupOpenTimer);
    pendingMouseupOpenTimer = null;
  }
  document.removeEventListener('mouseup', onDocumentMouseup, true);
  document.removeEventListener('keyup', onDocumentKeyup, true);
  document.removeEventListener('contextmenu', onDocumentContextMenu, true);
  document.removeEventListener(
    'selectionchange',
    onDocumentSelectionChange,
    true,
  );
  listenerAttached = false;
}

function syncListenerState(enabled: boolean) {
  if (enabled) {
    attachListeners();
    return;
  }
  detachListeners();
  activeSession.value = null;
  assistRef.value?.close();
}

onMounted(() => {
  syncListenerState(props.enabled);
});

watch(
  () => props.enabled,
  (enabled) => {
    syncListenerState(enabled);
  },
);

onBeforeUnmount(() => {
  detachListeners();
});
</script>

<template>
  <TextSelectionAiAssist
    ref="assistRef"
    :enabled="enabled"
    :api-prefix="apiPrefix"
    :enabled-actions="activeSession?.fieldPolicy.actions"
    i18n-prefix="common.textSelectionAi"
    document-type="plain_text_input"
    surface="plain_text_input"
    :require-selection-to-open="true"
    :get-selection="getSelection"
    :validate-selection="validateSelection"
    :apply-result="applyResult"
    :get-anchor-rect="getAnchorRect"
  />
</template>
