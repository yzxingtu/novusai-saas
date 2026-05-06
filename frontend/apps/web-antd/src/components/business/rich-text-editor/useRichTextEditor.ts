/**
 * Platform-level rich text editor composable
 * / 平台级富文本编辑器 composable
 */

import type { AnyExtension, JSONContent } from '@tiptap/core';

import type {
  RichTextEditorApplyContentOptions,
  RichTextEditorSelectionSnapshot,
  RichTextEditorSetContentOptions,
} from './types';

import { onBeforeUnmount, ref } from 'vue';

import { useEditor } from '@tiptap/vue-3';

import { buildExtensions } from './extensions';
import { createEditorInstanceId } from './editorInstanceId';

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

const SELECTION_BEFORE_CHARS = 2000;
const SELECTION_AFTER_CHARS = 500;

type InlineMark = NonNullable<JSONContent['marks']>[number];

function textNode(text: string, marks: InlineMark[] = []): JSONContent {
  const node: JSONContent = { text, type: 'text' };
  if (marks.length > 0) {
    node.marks = marks;
  }
  return node;
}

function appendInlineText(
  nodes: JSONContent[],
  text: string,
  marks: InlineMark[],
) {
  if (!text) return;
  nodes.push(textNode(text, marks));
}

function closingInlineMarkerIndex(
  source: string,
  start: number,
  marker: string,
): number {
  const close = source.indexOf(marker, start);
  if (close <= start) return -1;
  const inner = source.slice(start, close);
  return inner.trim() ? close : -1;
}

function parseInlineContent(
  source: string,
  activeMarks: InlineMark[] = [],
): JSONContent[] {
  const nodes: JSONContent[] = [];
  let buffer = '';
  let index = 0;

  const flushBuffer = () => {
    appendInlineText(nodes, buffer, activeMarks);
    buffer = '';
  };

  while (index < source.length) {
    const ch = source[index] ?? '';
    const next = source[index + 1] ?? '';

    if (ch === '\\' && next) {
      buffer += next;
      index += 2;
      continue;
    }

    if (ch === '`') {
      const close = closingInlineMarkerIndex(source, index + 1, '`');
      if (close > -1 && !source.slice(index + 1, close).includes('\n')) {
        flushBuffer();
        appendInlineText(nodes, source.slice(index + 1, close), [
          { type: 'code' },
        ]);
        index = close + 1;
        continue;
      }
    }

    if (source.startsWith('**', index)) {
      const close = closingInlineMarkerIndex(source, index + 2, '**');
      if (close > -1) {
        flushBuffer();
        nodes.push(
          ...parseInlineContent(source.slice(index + 2, close), [
            ...activeMarks,
            { type: 'bold' },
          ]),
        );
        index = close + 2;
        continue;
      }
    }

    if (source.startsWith('~~', index)) {
      const close = closingInlineMarkerIndex(source, index + 2, '~~');
      if (close > -1) {
        flushBuffer();
        nodes.push(
          ...parseInlineContent(source.slice(index + 2, close), [
            ...activeMarks,
            { type: 'strike' },
          ]),
        );
        index = close + 2;
        continue;
      }
    }

    buffer += ch;
    index += 1;
  }

  flushBuffer();
  return nodes;
}

function paragraphNode(text: string): JSONContent {
  const parts = text.split('\n');
  const content: JSONContent[] = [];
  parts.forEach((part, index) => {
    if (part) {
      content.push(...parseInlineContent(part));
    }
    if (index < parts.length - 1) {
      content.push({ type: 'hardBreak' });
    }
  });
  return content.length > 0
    ? { content, type: 'paragraph' }
    : { type: 'paragraph' };
}

function headingNode(text: string, level: number): JSONContent {
  const content = parseInlineContent(text);
  return {
    attrs: { level },
    content: content.length > 0 ? content : undefined,
    type: 'heading',
  };
}

function listItemNode(text: string): JSONContent {
  return {
    content: [paragraphNode(text)],
    type: 'listItem',
  };
}

function flushListBuffer(
  nodes: JSONContent[],
  listType: 'bulletList' | 'orderedList' | null,
  items: string[],
) {
  if (!listType || items.length === 0) return;
  nodes.push({
    content: items.map((item) => listItemNode(item)),
    type: listType,
  });
  items.length = 0;
}

function flushBlockquoteBuffer(nodes: JSONContent[], lines: string[]) {
  if (lines.length === 0) return;
  nodes.push({
    content: lines.map((line) => paragraphNode(line)),
    type: 'blockquote',
  });
  lines.length = 0;
}

function isWhitespace(ch: string | undefined): boolean {
  return ch === undefined ? false : /\s/.test(ch);
}

function isAsciiAlphanumeric(ch: string | undefined): boolean {
  return ch === undefined ? false : /^[\dA-Za-z]$/.test(ch);
}

function isCjk(ch: string | undefined): boolean {
  return ch === undefined ? false : /^[\u3400-\u9FFF\uF900-\uFAFF]$/.test(ch);
}

function isQuoteBoundaryPrefix(ch: string | undefined): boolean {
  return ch === ':' || ch === '：' || isCjk(ch);
}

function nextNonSpaceIndex(source: string, start: number): number {
  let index = start;
  while (
    index < source.length &&
    source[index] !== '\n' &&
    source[index] === ' '
  ) {
    index += 1;
  }
  return index;
}

function shouldBreakBeforeListMarker(source: string, index: number): boolean {
  const prev = source[index - 1];
  const next = source[index + 1];
  if (!prev || prev === '\n' || isWhitespace(prev)) return false;
  if (prev === '/' || prev === '\\') return false;
  if (next !== ' ') return false;
  return nextNonSpaceIndex(source, index + 1) < source.length;
}

function shouldBreakBeforeBlockquote(source: string, index: number): boolean {
  const prev = source[index - 1];
  if (!prev || prev === '\n' || isWhitespace(prev)) return false;
  if (!isQuoteBoundaryPrefix(prev)) return false;

  const contentIndex = nextNonSpaceIndex(source, index + 1);
  const next = source[contentIndex];
  if (!next || next === '=' || next === '>') return false;
  if (isAsciiAlphanumeric(prev) && isAsciiAlphanumeric(next)) return false;
  if (isCjk(prev) && isAsciiAlphanumeric(next)) return false;
  return true;
}

function normalizeMarkdownBlockBoundaries(raw: string): string {
  const source = raw.replace(/\r\n?/g, '\n');
  let normalized = '';

  for (let index = 0; index < source.length; index += 1) {
    const ch = source[index];
    // 中文: AI 常把 Markdown 块边界黏在上一句后面，只在可识别块标记前补换行。
    // EN: AI often glues Markdown block boundaries to prior text; only insert breaks before recognizable block markers.
    if (
      (ch === '-' || ch === '*' || ch === '•') &&
      shouldBreakBeforeListMarker(source, index)
    ) {
      normalized += '\n';
    } else if (ch === '>' && shouldBreakBeforeBlockquote(source, index)) {
      normalized += '\n';
    }
    normalized += ch;
  }

  return normalized;
}

function looksLikeCompactListLead(line: string, nextLine: string | undefined) {
  if (!nextLine || !/^[-*•]\s+/.test(nextLine.trim())) return false;
  if (/[：:]\s*$/.test(line)) return false;
  return /^\*\*[^*\n]{1,40}\*\*\s*[：:]\s*\S/.test(line);
}

function buildSafeEditorContent(raw: string): JSONContent[] {
  const normalized = normalizeMarkdownBlockBoundaries(raw).trim();
  if (!normalized) return [];

  const nodes: JSONContent[] = [];
  const listItems: string[] = [];
  const blockquoteLines: string[] = [];
  const lines = normalized.split('\n');
  let listType: 'bulletList' | 'orderedList' | null = null;

  for (let index = 0; index < lines.length; index += 1) {
    const rawLine = lines[index] ?? '';
    const line = rawLine.trim();
    if (!line) {
      flushListBuffer(nodes, listType, listItems);
      flushBlockquoteBuffer(nodes, blockquoteLines);
      listType = null;
      continue;
    }

    const blockquoteMatch = /^>\s?(.*)$/.exec(line);
    if (blockquoteMatch) {
      flushListBuffer(nodes, listType, listItems);
      listType = null;
      blockquoteLines.push(blockquoteMatch[1] ?? '');
      continue;
    }

    const headingMatch = /^(#{1,3})\s+(.+)$/.exec(line);
    if (headingMatch) {
      const headingMarks = headingMatch[1] ?? '#';
      const headingText = headingMatch[2] ?? line;
      flushListBuffer(nodes, listType, listItems);
      flushBlockquoteBuffer(nodes, blockquoteLines);
      listType = null;
      nodes.push(headingNode(headingText, headingMarks.length));
      continue;
    }

    const bulletMatch = /^[-*•]\s+(.+)$/.exec(line);
    if (bulletMatch) {
      flushBlockquoteBuffer(nodes, blockquoteLines);
      if (listType !== 'bulletList') {
        flushListBuffer(nodes, listType, listItems);
        listType = 'bulletList';
      }
      listItems.push(bulletMatch[1] ?? line);
      continue;
    }

    const orderedMatch = /^\d+[.)]\s+(.+)$/.exec(line);
    if (orderedMatch) {
      flushBlockquoteBuffer(nodes, blockquoteLines);
      if (listType !== 'orderedList') {
        flushListBuffer(nodes, listType, listItems);
        listType = 'orderedList';
      }
      listItems.push(orderedMatch[1] ?? line);
      continue;
    }

    if (looksLikeCompactListLead(line, lines[index + 1])) {
      flushBlockquoteBuffer(nodes, blockquoteLines);
      if (listType !== 'bulletList') {
        flushListBuffer(nodes, listType, listItems);
        listType = 'bulletList';
      }
      listItems.push(line);
      continue;
    }

    flushListBuffer(nodes, listType, listItems);
    flushBlockquoteBuffer(nodes, blockquoteLines);
    listType = null;
    nodes.push(paragraphNode(line));
  }

  flushListBuffer(nodes, listType, listItems);
  flushBlockquoteBuffer(nodes, blockquoteLines);
  return nodes;
}

function clampSelectionPosition(pos: number, max: number): number {
  if (!Number.isFinite(pos)) return max;
  return Math.min(Math.max(Math.trunc(pos), 0), max);
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

  function getSelectionSnapshot(): RichTextEditorSelectionSnapshot {
    const ed = editor.value;
    if (!ed) {
      return {
        afterText: '',
        beforeText: '',
        empty: true,
        from: 0,
        revision: revision.value,
        selectedText: '',
        to: 0,
      };
    }

    const { from, to, empty } = ed.state.selection;
    const docSize = ed.state.doc.content.size;
    const safeFrom = clampSelectionPosition(from, docSize);
    const safeTo = clampSelectionPosition(to, docSize);
    const selectionStart = Math.min(safeFrom, safeTo);
    const selectionEnd = Math.max(safeFrom, safeTo);

    return {
      afterText: ed.state.doc.textBetween(
        selectionEnd,
        Math.min(docSize, selectionEnd + SELECTION_AFTER_CHARS),
        '\n',
        '\n',
      ),
      beforeText: ed.state.doc.textBetween(
        Math.max(0, selectionStart - SELECTION_BEFORE_CHARS),
        selectionStart,
        '\n',
        '\n',
      ),
      empty: empty || selectionStart === selectionEnd,
      from: selectionStart,
      revision: revision.value,
      selectedText:
        selectionStart === selectionEnd
          ? ''
          : ed.state.doc.textBetween(selectionStart, selectionEnd, '\n', '\n'),
      to: selectionEnd,
    };
  }

  function validateSelectionSnapshot(
    selection: RichTextEditorSelectionSnapshot | null | undefined,
  ): boolean {
    const ed = editor.value;
    if (!ed || !selection) return false;
    if (selection.revision !== revision.value) return false;

    const docSize = ed.state.doc.content.size;
    const from = clampSelectionPosition(selection.from, docSize);
    const to = clampSelectionPosition(selection.to, docSize);
    if (from !== selection.from || to !== selection.to) return false;

    const start = Math.min(from, to);
    const end = Math.max(from, to);
    if (selection.empty || start === end) {
      return selection.empty === true && start === end;
    }

    return (
      ed.state.doc.textBetween(start, end, '\n', '\n') ===
      selection.selectedText
    );
  }

  function applyContent(
    content: string,
    applyOptions: RichTextEditorApplyContentOptions = {},
  ) {
    const ed = editor.value;
    const safeContent = buildSafeEditorContent(content);
    if (!ed || safeContent.length === 0) return;

    if (_updateTimer) {
      clearTimeout(_updateTimer);
      _updateTimer = null;
    }

    const docSize = ed.state.doc.content.size;
    const selection = applyOptions.selection;
    const fallbackFrom = ed.state.selection.from;
    const fallbackTo = ed.state.selection.to;
    const from = clampSelectionPosition(
      selection?.from ?? fallbackFrom,
      docSize,
    );
    const to = clampSelectionPosition(selection?.to ?? fallbackTo, docSize);
    const replaceSelection = applyOptions.mode === 'replace';
    const range = replaceSelection
      ? { from: Math.min(from, to), to: Math.max(from, to) }
      : {
          from: selection && !selection.empty ? Math.max(from, to) : from,
          to: selection && !selection.empty ? Math.max(from, to) : from,
        };

    ed.chain().focus().insertContentAt(range, safeContent).run();

    if (applyOptions.emitUpdate === false) {
      revision.value += 1;
      emitEditorUpdate();
    }
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
    getSelectionSnapshot,
    validateSelectionSnapshot,
    applyContent,
    focus,
  };
}
