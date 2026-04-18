/**
 * Rich text editor page-AI exposure registration.
 * 富文本编辑器 page-AI 暴露能力注册。
 *
 * This module no longer participates in legacy page-operation registries.
 * Instead, it exposes editor context and callable operations through the
 * shared page-AI exposure seam.
 */

import type { Editor } from '@tiptap/core';

import type { MaybeRefOrGetter, ShallowRef } from 'vue';

import { toValue, watchEffect } from 'vue';

import { $t } from '@vben/locales';

import MarkdownIt from 'markdown-it';

import {
  buildEditorEnumParam,
  buildEditorNumberParam,
  createEditorEnumCommandOperation,
  resolveEditorEnumParam,
  resolveEditorIntParam,
} from './ai/editor-command-helpers';
import {
  buildEditorContentParams,
  createEditorContentMutationOperation,
  getEditorContentFormat,
  isEditorContentInputError,
  resolveEditorContentInput,
} from './ai/editor-content-helpers';
import {
  createParameterizedPageAIOperation,
  createSimplePageAIOperation,
} from './ai/editor-page-ai-operations';
import { registerRichTextPageAIExposure } from './ai/editor-page-ai-exposure';
import { normalizeRuntimePageKey } from './ai/page-key';
import { validateReplaceContentParams } from './replaceContentValidator';

const md = new MarkdownIt({ html: true, breaks: true });
const runtimeEditorIds = new WeakMap<Editor, string>();
let runtimeEditorIdSeed = 0;

/**
 * Normalize HTML for reliable string matching (e.g. replace_section old_html from LLM may have different escaping).
 * 规范化 HTML 以便可靠字符串匹配（如 replace_section 的 old_html 来自 LLM 时转义可能不同）。
 */
function normalizeHtmlForMatch(html: string): string {
  let s = html.trim();
  // Decode common entities / 解码常见 HTML 实体
  s = s
    .replaceAll(/&quot;/gi, '"')
    .replaceAll('&#39;', "'")
    .replaceAll(/&amp;/gi, '&')
    .replaceAll(/&lt;/gi, '<')
    .replaceAll(/&gt;/gi, '>');
  // Normalize JSON/backslash escaping that LLM may produce / 规范化 LLM 可能输出的 JSON 反斜杠转义
  s = s
    .replaceAll(String.raw`\"`, '"')
    .replaceAll(String.raw`\&quot;`, '"')
    .replaceAll(String.raw`\\&quot;`, '"');
  return s;
}

/**
 * Fix broken table style that TipTap or AI may output (width: 0px → 100%).
 * 修复 TipTap 或 AI 可能输出的错误表格样式（width: 0px → 100%）。
 */
function fixTableWidthZero(html: string): string {
  return html.replaceAll(/style="width:\s*0px;?"/gi, 'style="width: 100%;"');
}

/**
 * Sanitize table attributes so TipTap TableMap does not throw "No cell with offset X found".
 * Ensures colspan/rowspan are simple numeric attributes (e.g. colspan="1").
 * 清理表格属性，避免 TipTap TableMap 抛出 "No cell with offset X found"；确保 colspan/rowspan 为简单数字属性。
 */
function sanitizeTableAttributesForSetContent(html: string): string {
  if (typeof document === 'undefined') {
    return html;
  }
  const container = document.createElement('div');
  container.innerHTML = html;

  for (const cell of container.querySelectorAll('td, th')) {
    for (const attr of ['colspan', 'rowspan']) {
      const rawValue = cell.getAttribute(attr);
      if (!rawValue) {
        continue;
      }
      const normalized = rawValue
        .replaceAll('\\', '')
        .replaceAll('"', '')
        .trim();
      if (/^\d+$/.test(normalized)) {
        cell.setAttribute(attr, normalized);
      }
    }
  }

  return container.innerHTML;
}

/** Convert content to HTML. content_format="markdown" → render; else use as HTML (no auto-conversion). / 将内容转为 HTML。content_format=markdown 时渲染，否则按 HTML 使用（不自动转换） */
function toHtml(content: string, contentFormat?: string): string {
  return contentFormat === 'markdown' ? md.render(content) : content;
}

/** Used by validateReplaceContentParams; accepts format for content_format param. / 供 replace_content 校验使用 */
function ensureHtml(content: string, format?: string): string {
  return format === 'markdown' ? md.render(content) : content;
}

function sanitizeEditorHtml(html: string): string {
  return sanitizeTableAttributesForSetContent(fixTableWidthZero(html));
}

function resolveRuntimeEditorId(editor: Editor): string {
  const existing = runtimeEditorIds.get(editor);
  if (existing) {
    return existing;
  }
  runtimeEditorIdSeed += 1;
  const next = `rte-runtime-${runtimeEditorIdSeed}`;
  runtimeEditorIds.set(editor, next);
  return next;
}

const TEXT_FORMAT_COMMANDS = [
  'bold',
  'italic',
  'underline',
  'strike',
  'code',
  'highlight',
] as const;

const LIST_TYPES = ['bullet', 'ordered'] as const;
const TEXT_ALIGN_OPTIONS = ['left', 'center', 'right', 'justify'] as const;
const LINK_ACTIONS = ['set', 'unset'] as const;

function getTextFormatLabel(
  cmd: (typeof TEXT_FORMAT_COMMANDS)[number],
): string {
  const keyMap: Record<(typeof TEXT_FORMAT_COMMANDS)[number], string> = {
    bold: 'common.bold',
    italic: 'common.italic',
    underline: 'common.underline',
    strike: 'common.strike',
    code: 'common.code',
    highlight: 'common.highlight',
  };
  return $t(keyMap[cmd]);
}

function getListTypeLabel(type: (typeof LIST_TYPES)[number]): string {
  const keyMap: Record<(typeof LIST_TYPES)[number], string> = {
    bullet: 'common.unorderedList',
    ordered: 'common.orderedList',
  };
  return $t(keyMap[type]);
}

function getTextAlignLabel(align: (typeof TEXT_ALIGN_OPTIONS)[number]): string {
  const keyMap: Record<(typeof TEXT_ALIGN_OPTIONS)[number], string> = {
    left: 'common.alignLeft',
    center: 'common.alignCenter',
    right: 'common.alignRight',
    justify: 'common.alignJustify',
  };
  return $t(keyMap[align]);
}

export interface EditorPageOpsOptions {
  editable?: MaybeRefOrGetter<boolean>;
  enabled?: MaybeRefOrGetter<boolean>;
  pageKey?: MaybeRefOrGetter<string | undefined>;
}

export function useEditorPageOps(
  editorRef: ShallowRef<Editor | undefined>,
  pageKeyOrOptions?: EditorPageOpsOptions | string,
) {
  const options =
    typeof pageKeyOrOptions === 'string'
      ? { pageKey: pageKeyOrOptions }
      : (pageKeyOrOptions ?? {});

  /** Conservative excerpt size (~2.4KB UTF-8, ≈800 CJK chars). */
  const DOCUMENT_BODY_EXCERPT_LEN = 800;

  const effectiveKey = () => {
    const explicit = toValue(options.pageKey);
    return normalizeRuntimePageKey(explicit || window.location.pathname);
  };

  watchEffect((onCleanup) => {
    const editor = editorRef.value;
    const pageKey = effectiveKey();
    const enabled = toValue(options.enabled) ?? true;
    if (!editor || !enabled || !pageKey) {
      return;
    }

    const editorInstanceId = resolveRuntimeEditorId(editor);
    const providerId = `rich-text-editor:${pageKey}:${editorInstanceId}`;
    const unregister = registerRichTextPageAIExposure({
      providerId,
      pageKey,
      editorInstanceId,
      priority: 100,
      getContextData: () => {
        const fullText = editor.getText?.() ?? '';
        return {
          title: $t('common.richTextEditor'),
          entity_name: $t('common.richTextEditor'),
          entity_description_append: $t('common.editorRuntimeDescription'),
          document_body_length: fullText.length,
          document_body_text: fullText.slice(0, DOCUMENT_BODY_EXCERPT_LEN),
          editor_editable: toValue(options.editable) !== false,
          has_editor: true,
          word_count: editor.storage.characterCount?.words?.() ?? 0,
        };
      },
      getOperations: () => {
        const allowMutations = toValue(options.editable) !== false;
        const editorOps = [
          createSimplePageAIOperation({
            name: 'get_editor_text',
            label: $t('common.getEditorText'),
            description: $t('common.editorToolDesc.getEditorText'),
            readonly: true,
            action: async () => {
              const text = editor.getText();
              const words = text.trim() ? text.trim().split(/\s+/).length : 0;
              return {
                success: true,
                message: $t('common.editorOp.editorWordCount', {
                  count: words,
                }),
                data: { text: text.slice(0, 6000), word_count: words },
              };
            },
          }),
          createSimplePageAIOperation({
            name: 'get_editor_html',
            label: $t('common.getEditorHTML'),
            description: $t('common.editorToolDesc.getEditorHtml'),
            readonly: true,
            action: async () => {
              const raw = editor.getHTML();
              const html = fixTableWidthZero(raw);
              const maxLen = 8000;
              const cut = html.length <= maxLen ? html : html.slice(0, maxLen);
              const lastClose = cut.lastIndexOf('>');
              const safe = lastClose === -1 ? cut : cut.slice(0, lastClose + 1);
              const hint = $t('common.editorToolDesc.replaceSectionHint');
              return {
                success: true,
                message: $t('common.editorOp.htmlRetrieved', {
                  count: html.length,
                }),
                data: { html: safe, _hint: hint },
              };
            },
          }),
          createSimplePageAIOperation({
            name: 'get_selection',
            label: $t('common.getSelection'),
            description: $t('common.editorToolDesc.getSelection'),
            readonly: true,
            action: async () => {
              const { from, to } = editor.state.selection;
              const text = editor.state.doc.textBetween(from, to, '');
              return {
                success: true,
                message: $t('common.editorOp.selectionChars', {
                  count: text.length,
                }),
                data: { text, from, to },
              };
            },
          }),
        ];

        const mutationOps = [
          createEditorContentMutationOperation({
            name: 'insert_content',
            label: $t('common.insertContent'),
            description: $t('common.editorToolDesc.insertContent'),
            contentDescription: $t('common.editorToolDesc.insertContentHtml'),
            emptyMessage: $t('common.editorOp.noContentProvided'),
            ensureHtml: toHtml,
            postprocessHtml: sanitizeEditorHtml,
            execute: async ({ html, raw }) => {
              editor.chain().focus().insertContent(html).run();
              return $t('common.editorOp.insertedChars', { count: raw.length });
            },
          }),
          createParameterizedPageAIOperation({
            name: 'replace_content',
            label: $t('common.replaceContent'),
            description: $t('common.editorToolDesc.replaceContent'),
            readonly: false,
            params: buildEditorContentParams({
              fieldDescription: $t('common.editorToolDesc.replaceContentHtml'),
            }),
            action: async (params) => {
              const inputSize = String(params.content ?? '').trim().length;
              const fmt = getEditorContentFormat(params);
              const validation = validateReplaceContentParams(params, {
                ensureHtml: (s: string) => ensureHtml(s, fmt),
                fixTableWidthZero,
                sanitizeTableAttributesForSetContent,
              });
              if (!validation.valid) {
                console.warn(
                  '[replace_content audit] page_key=%s operation_name=replace_content input_size=%d success=false error_type=%s',
                  pageKey,
                  inputSize,
                  validation.error_type,
                );
                return {
                  success: false,
                  message:
                    inputSize === 0
                      ? $t('common.replaceContentEmptyError')
                      : $t('common.invalidInputEmptyContent'),
                  error_type: validation.error_type,
                };
              }
              editor.commands.setContent(validation.html);
              return {
                success: true,
                message: $t('common.editorOp.fullContentReplaced', {
                  count: validation.inputLength,
                }),
              };
            },
          }),
          createParameterizedPageAIOperation({
            name: 'replace_section',
            label: $t('common.replaceSection'),
            description: $t('common.editorToolDesc.replaceSection'),
            readonly: false,
            params: {
              old_html: {
                type: 'string',
                description: $t('common.editorToolDesc.replaceSectionOldHtml'),
              },
              ...buildEditorContentParams({
                fieldName: 'new_html',
                fieldDescription: $t(
                  'common.editorToolDesc.replaceSectionNewHtml',
                ),
                formatDescription: $t(
                  'common.editorToolDesc.replaceSectionFormat',
                ),
              }),
            },
            action: async (params) => {
              const oldSnippet = String(params.old_html || '').trim();
              if (!oldSnippet) {
                return {
                  success: false,
                  message: $t('common.editorOp.oldHtmlRequired'),
                  error_type: 'invalid_input',
                };
              }

              const currentHtml = editor.getHTML();
              const normCurrent = normalizeHtmlForMatch(currentHtml);
              const normOld = normalizeHtmlForMatch(oldSnippet);

              if (normOld.length < 3) {
                return {
                  success: false,
                  message: $t('common.editorOp.oldHtmlTooShort'),
                  error_type: 'invalid_input',
                };
              }
              const matchCount = normCurrent.split(normOld).length - 1;
              if (matchCount > 1) {
                return {
                  success: false,
                  message: `${$t(
                    'common.editorOp.oldHtmlNotFound',
                  )} ${$t('common.editorOp.snippetMatchesMultiple')}`,
                  error_type: 'non_unique_match',
                };
              }
              if (!normCurrent.includes(normOld)) {
                const snippetLen = 450;
                const excerpt = currentHtml.slice(0, snippetLen);
                return {
                  success: false,
                  message: `${$t('common.editorOp.oldHtmlNotFound')} ${$t(
                    'common.editorToolDesc.currentDocumentExcerpt',
                    {
                      count: snippetLen,
                      excerpt,
                      suffix: currentHtml.length > snippetLen ? '...' : '',
                    },
                  )}`,
                  error_type: 'target_not_found',
                };
              }

              const resolvedNewHtml = resolveEditorContentInput(params, {
                fieldName: 'new_html',
                trim: true,
                preprocessRaw: normalizeHtmlForMatch,
                ensureHtml: toHtml,
                postprocessHtml: sanitizeEditorHtml,
                emptyMessage: $t('common.editorOp.newHtmlRequired'),
                errorType: 'invalid_input',
              });
              if (isEditorContentInputError(resolvedNewHtml)) {
                return resolvedNewHtml;
              }

              const updatedNorm = normCurrent.replace(
                normOld,
                resolvedNewHtml.html,
              );
              const updatedHtml = sanitizeEditorHtml(updatedNorm);

              try {
                editor.commands.setContent(updatedHtml);
              } catch (error) {
                const errMsg =
                  error instanceof Error ? error.message : String(error);
                return {
                  success: false,
                  message: $t('common.editorOp.replacementInvalidStructure', {
                    error: errMsg,
                  }),
                  error_type: 'invalid_html',
                };
              }
              return {
                success: true,
                message: $t('common.editorOp.sectionReplaced', {
                  old: oldSnippet.length,
                  new: resolvedNewHtml.raw.length,
                }),
              };
            },
          }),
          createEditorContentMutationOperation({
            name: 'append_content',
            label: $t('common.appendContent'),
            description: $t('common.editorToolDesc.appendContent'),
            contentDescription: $t('common.editorToolDesc.appendContentHtml'),
            emptyMessage: $t('common.editorOp.noContentProvided'),
            ensureHtml: toHtml,
            postprocessHtml: sanitizeEditorHtml,
            execute: async ({ html, raw }) => {
              const endPos = editor.state.doc.content.size;
              editor.chain().focus().insertContentAt(endPos, html).run();
              return $t('common.editorOp.appendedChars', { count: raw.length });
            },
          }),
          createSimplePageAIOperation({
            name: 'select_all',
            label: $t('common.selectAll'),
            description: $t('common.editorToolDesc.selectAll'),
            readonly: false,
            action: async () => {
              editor.commands.selectAll();
              return {
                success: true,
                message: $t('common.editorOp.selectedAll'),
              };
            },
          }),
          createSimplePageAIOperation({
            name: 'undo',
            label: $t('common.undo'),
            description: $t('common.editorToolDesc.undo'),
            readonly: false,
            action: async () => {
              const ok = editor.chain().focus().undo().run();
              return {
                success: ok,
                message: ok
                  ? $t('common.editorOp.undone')
                  : $t('common.editorOp.nothingToUndo'),
              };
            },
          }),
          createSimplePageAIOperation({
            name: 'redo',
            label: $t('common.redo'),
            description: $t('common.editorToolDesc.redo'),
            readonly: false,
            action: async () => {
              const ok = editor.chain().focus().redo().run();
              return {
                success: ok,
                message: ok
                  ? $t('common.editorOp.redone')
                  : $t('common.editorOp.nothingToRedo'),
              };
            },
          }),
          createEditorEnumCommandOperation({
            name: 'format_text',
            label: $t('common.formatText'),
            description: $t('common.editorToolDesc.formatText'),
            paramName: 'command',
            paramDescription: $t('common.editorParam.formatCommand'),
            values: TEXT_FORMAT_COMMANDS,
            defaultValue: 'bold',
            execute: async (cmd) => {
              const chain = editor.chain().focus();
              const map: Record<
                (typeof TEXT_FORMAT_COMMANDS)[number],
                () => boolean
              > = {
                bold: () => chain.toggleBold().run(),
                italic: () => chain.toggleItalic().run(),
                underline: () => chain.toggleUnderline().run(),
                strike: () => chain.toggleStrike().run(),
                code: () => chain.toggleCode().run(),
                highlight: () => chain.toggleHighlight().run(),
              };
              return map[cmd]();
            },
            successMessage: (cmd) =>
              $t('common.editorOp.toggledFormat', {
                cmd: getTextFormatLabel(cmd),
              }),
            failureMessage: $t('common.editorOp.formatFailed'),
          }),
          createSimplePageAIOperation({
            name: 'clear_formatting',
            label: $t('common.clearFormatting'),
            description: $t('common.editorToolDesc.clearFormatting'),
            readonly: false,
            action: async () => {
              editor.chain().focus().unsetAllMarks().run();
              return {
                success: true,
                message: $t('common.editorOp.formattingCleared'),
              };
            },
          }),
          createParameterizedPageAIOperation({
            name: 'set_heading',
            label: $t('common.setHeading'),
            description: $t('common.editorToolDesc.setHeading'),
            readonly: false,
            params: {
              level: buildEditorNumberParam(
                $t('common.editorParam.headingLevel'),
              ),
            },
            action: async (params) => {
              const level = resolveEditorIntParam(params.level, {
                min: 1,
                max: 3,
                defaultValue: 1,
              }) as 1 | 2 | 3;
              editor.chain().focus().toggleHeading({ level }).run();
              return {
                success: true,
                message: $t('common.editorOp.headingApplied', { level }),
              };
            },
          }),
          createEditorEnumCommandOperation({
            name: 'toggle_list',
            label: $t('common.toggleList'),
            description: $t('common.editorToolDesc.toggleList'),
            paramName: 'type',
            paramDescription: $t('common.editorParam.listType'),
            values: LIST_TYPES,
            defaultValue: 'bullet',
            fallbackOnInvalid: true,
            execute: async (type) => {
              return type === 'ordered'
                ? editor.chain().focus().toggleOrderedList().run()
                : editor.chain().focus().toggleBulletList().run();
            },
            successMessage: (type) =>
              $t('common.editorOp.listToggled', {
                type: getListTypeLabel(type),
              }),
            failureMessage: $t('common.editorOp.formatFailed'),
          }),
          createSimplePageAIOperation({
            name: 'toggle_blockquote',
            label: $t('common.toggleBlockquote'),
            description: $t('common.editorToolDesc.toggleBlockquote'),
            readonly: false,
            action: async () => {
              editor.chain().focus().toggleBlockquote().run();
              return {
                success: true,
                message: $t('common.editorOp.blockquoteToggled'),
              };
            },
          }),
          createSimplePageAIOperation({
            name: 'toggle_code_block',
            label: $t('common.toggleCodeBlock'),
            description: $t('common.editorToolDesc.toggleCodeBlock'),
            readonly: false,
            action: async () => {
              editor.chain().focus().toggleCodeBlock().run();
              return {
                success: true,
                message: $t('common.editorOp.codeBlockToggled'),
              };
            },
          }),
          createSimplePageAIOperation({
            name: 'insert_horizontal_rule',
            label: $t('common.insertHorizontalRule'),
            description: $t('common.editorToolDesc.insertHorizontalRule'),
            readonly: false,
            action: async () => {
              editor.chain().focus().setHorizontalRule().run();
              return {
                success: true,
                message: $t('common.editorOp.horizontalRuleInserted'),
              };
            },
          }),
          createEditorEnumCommandOperation({
            name: 'set_text_align',
            label: $t('common.setTextAlign'),
            description: $t('common.editorToolDesc.setTextAlign'),
            paramName: 'align',
            paramDescription: $t('common.editorParam.textAlign'),
            values: TEXT_ALIGN_OPTIONS,
            defaultValue: 'left',
            invalidMessage: $t('common.editorOp.invalidAlign'),
            execute: async (align) => {
              return editor.chain().focus().setTextAlign(align).run();
            },
            successMessage: (align) =>
              $t('common.editorOp.alignApplied', {
                align: getTextAlignLabel(align),
              }),
            failureMessage: $t('common.editorOp.formatFailed'),
          }),
          createParameterizedPageAIOperation({
            name: 'manage_link',
            label: $t('common.manageLink'),
            description: $t('common.editorToolDesc.manageLink'),
            readonly: false,
            params: {
              action: buildEditorEnumParam({
                values: LINK_ACTIONS,
                description: $t('common.editorParam.linkAction'),
              }),
              href: {
                type: 'string',
                description: $t('common.editorParam.linkHref'),
              },
            },
            action: async (params) => {
              const action = resolveEditorEnumParam(params.action, {
                values: LINK_ACTIONS,
                defaultValue: 'set',
                normalize: (raw) => raw.trim().toLowerCase(),
              });
              if (!action) {
                return {
                  success: false,
                  message: $t('common.editorOp.formatFailed'),
                  error_type: 'invalid_input',
                };
              }
              if (action === 'unset') {
                editor
                  .chain()
                  .focus()
                  .extendMarkRange('link')
                  .unsetLink()
                  .run();
                return {
                  success: true,
                  message: $t('common.editorOp.linkRemoved'),
                };
              }
              const href = String(params.href || '').trim();
              if (!href) {
                return {
                  success: false,
                  message: $t('common.editorOp.hrefRequired'),
                };
              }
              editor
                .chain()
                .focus()
                .extendMarkRange('link')
                .setLink({ href })
                .run();
              return {
                success: true,
                message: $t('common.editorOp.linkSet', { href }),
              };
            },
          }),
          createParameterizedPageAIOperation({
            name: 'insert_table',
            label: $t('common.insertTable'),
            description: $t('common.editorToolDesc.insertTable'),
            readonly: false,
            params: {
              rows: buildEditorNumberParam($t('common.editorParam.tableRows')),
              cols: buildEditorNumberParam($t('common.editorParam.tableCols')),
            },
            action: async (params) => {
              const rows = resolveEditorIntParam(params.rows, {
                min: 1,
                max: 10,
                defaultValue: 3,
              });
              const cols = resolveEditorIntParam(params.cols, {
                min: 1,
                max: 10,
                defaultValue: 3,
              });
              editor
                .chain()
                .focus()
                .insertTable({ rows, cols, withHeaderRow: true })
                .run();
              return {
                success: true,
                message: $t('common.editorOp.tableInserted', { rows, cols }),
              };
            },
          }),
        ];

        return allowMutations ? [...editorOps, ...mutationOps] : editorOps;
      },
    });

    onCleanup(() => {
      unregister();
    });
  });
}
