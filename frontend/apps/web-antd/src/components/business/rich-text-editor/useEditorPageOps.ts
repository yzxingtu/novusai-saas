/**
 * Auto-registers page operations for the rich text editor content.
 * 自动注册富文本编辑器页面的操作。
 * Any page that mounts RichTextEditor with a pageKey automatically gets
 * Ctrl+K AI capabilities to read/write editor content.
 * 挂载 RichTextEditor 且传入 pageKey 的页面将自动获得 Ctrl+K AI 读写能力。
 */

import type { Editor } from '@tiptap/core';
import type { ShallowRef } from 'vue';

import { onBeforeUnmount, watch } from 'vue';

import { $t } from '@vben/locales';
import MarkdownIt from 'markdown-it';

import {
  registerPageContext,
  registerPageOperations,
} from '#/components/business/ai-slide-panel';
import { normalizePageKey } from '#/components/business/ai-slide-panel/page-key-utils';
import { validateReplaceContentParams } from './replaceContentValidator';

const md = new MarkdownIt({ html: true, breaks: true });

const MD_PATTERNS = /^#{1,6}\s|^\*\*|^\- |\*\*.*\*\*|^\d+\.\s|^>\s|```/m;

/**
 * Normalize HTML for reliable string matching (e.g. replace_section old_html from LLM may have different escaping).
 * 规范化 HTML 以便可靠字符串匹配（如 replace_section 的 old_html 来自 LLM 时转义可能不同）。
 */
function normalizeHtmlForMatch(html: string): string {
  let s = html.trim();
  // Decode common entities
  s = s
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>');
  // Normalize JSON/backslash escaping that LLM may produce
  s = s.replace(/\\"/g, '"').replace(/\\&quot;/g, '"').replace(/\\\\&quot;/g, '"');
  return s;
}

/**
 * Fix broken table style that TipTap or AI may output (width: 0px → 100%).
 * 修复 TipTap 或 AI 可能输出的错误表格样式（width: 0px → 100%）。
 */
function fixTableWidthZero(html: string): string {
  return html.replace(
    /style="width:\s*0px;?"/gi,
    'style="width: 100%;"',
  );
}

/**
 * Sanitize table attributes so TipTap TableMap does not throw "No cell with offset X found".
 * Ensures colspan/rowspan are simple numeric attributes (e.g. colspan="1").
 * 清理表格属性，避免 TipTap TableMap 抛出 "No cell with offset X found"；确保 colspan/rowspan 为简单数字属性。
 */
function sanitizeTableAttributesForSetContent(html: string): string {
  return html
    .replace(/\bcolspan\s*=\s*["']?\\?"?\s*(\d+)\s*\\?"?["']?/gi, 'colspan="$1"')
    .replace(/\browspan\s*=\s*["']?\\?"?\s*(\d+)\s*\\?"?["']?/gi, 'rowspan="$1"');
}

/** Convert content to HTML. content_format="markdown" → render; else use as HTML (no auto-conversion). / 将内容转为 HTML。content_format=markdown 时渲染，否则按 HTML 使用（不自动转换） */
function toHtml(content: string, contentFormat?: string): string {
  return contentFormat === 'markdown' ? md.render(content) : content;
}

/** Used by validateReplaceContentParams; accepts format for content_format param. / 供 replace_content 校验使用 */
function ensureHtml(content: string, format?: string): string {
  return format === 'markdown' ? md.render(content) : content;
}

export function useEditorPageOps(
  editorRef: ShallowRef<Editor | undefined>,
  pageKey?: string | undefined,
) {
  const effectiveKey = pageKey || normalizePageKey(window.location.pathname);
  if (!effectiveKey) return;

  let cleanupOps: (() => void) | undefined;
  let cleanupCtx: (() => void) | undefined;

  function register() {
    cleanupOps?.();
    cleanupCtx?.();
    const editor = editorRef.value;
    if (!editor) return;

    /** ~2.4KB UTF-8 (≈800 CJK chars) to stay within page_data 8KB limit with available_operations. */
    const DOCUMENT_BODY_EXCERPT_LEN = 800;

    cleanupCtx = registerPageContext(effectiveKey, () => {
      const fullText = editor.getText?.() ?? '';
      const documentBodyText = fullText.slice(0, DOCUMENT_BODY_EXCERPT_LEN);
      const documentBodyLength = fullText.length;
      return {
        page_key: effectiveKey,
        page_title: 'Rich Text Editor',
        page_data: {
          entity_name: 'Rich Text Editor',
          entity_description:
            'HTML 富文本编辑器。正文摘要在 document_body_text；完整内容用 get_editor_html 获取。\n'
            + 'content 参数默认要求 HTML（如 <h1>标题</h1><p>正文</p>）；传 content_format="markdown" 可送 Markdown。\n'
            + '【局部编辑】先 get_editor_html 获取完整 HTML，再用 replace_section(old_html="旧片段", new_html="新片段") 只替换目标章节。\n'
            + '长文档时 get_editor_html 返回可能被截断，请用返回内容中的短且唯一的 HTML 片段作为 replace_section 的 old_html，勿用整篇作为 old_html。\n'
            + '【全文替换】仅当需要重写整篇文章时才用 replace_content。\n'
            + '【追加/插入】append_content 在末尾追加，insert_content 在光标处插入。',
          has_editor: true,
          word_count: editor.storage.characterCount?.words?.() ?? 0,
          document_body_text: documentBodyText,
          document_body_length: documentBodyLength,
        },
      };
    });

    cleanupOps = registerPageOperations(effectiveKey, [
      {
        name: 'get_editor_text',
        label: $t('common.getEditorText'),
        description:
          'Get the current editor plain text content for AI analysis.',
        readonly: true,
        handler: async () => {
          const text = editor.getText();
          const words = text.trim() ? text.trim().split(/\s+/).length : 0;
          return {
            success: true,
            message: $t('common.editorOp.editorWordCount', { count: words }),
            data: { text: text.slice(0, 6000), word_count: words },
          };
        },
      },
      {
        name: 'get_editor_html',
        label: $t('common.getEditorHTML'),
        description:
          'Get the current editor HTML content with formatting.',
        readonly: true,
        handler: async () => {
          const raw = editor.getHTML();
          const html = fixTableWidthZero(raw);
          const maxLen = 8000;
          const cut =
            html.length <= maxLen ? html : html.slice(0, maxLen);
          const lastClose = cut.lastIndexOf('>');
          const safe =
            lastClose >= 0 ? cut.slice(0, lastClose + 1) : cut;
          const hint = 'Use short, unique HTML snippets for replace_section old_html; avoid using the entire document.';
          return {
            success: true,
            message: $t('common.editorOp.htmlRetrieved', { count: html.length }),
            data: { html: safe, _hint: hint },
          };
        },
      },
      {
        name: 'insert_content',
        label: $t('common.insertContent'),
        description:
          'Insert content at cursor. content MUST be HTML by default; set content_format="markdown" to pass Markdown (auto-converted to HTML).',
        readonly: false,
        params: {
          content: {
            type: 'string',
            description: 'HTML content to insert (e.g. <h2>Title</h2><p>text</p>). Use content_format="markdown" for Markdown input.',
          },
          content_format: {
            type: 'string',
            enum: ['html', 'markdown'],
            description: 'Input format: "html" (default) or "markdown". Default is html.',
          },
        },
        handler: async (params: Record<string, unknown>) => {
          const raw = String(params.content || '');
          if (!raw)
            return { success: false, message: $t('common.editorOp.noContentProvided') };
          const fmt = String(params.content_format || 'html');
          const html = sanitizeTableAttributesForSetContent(
            fixTableWidthZero(toHtml(raw, fmt)),
          );
          editor.chain().focus().insertContent(html).run();
          return {
            success: true,
            message: $t('common.editorOp.insertedChars', { count: raw.length }),
          };
        },
      },
      {
        name: 'replace_content',
        label: $t('common.replaceContent'),
        description:
          'Replace ALL editor content. content MUST be HTML by default; set content_format="markdown" for Markdown input. Use ONLY when rewriting the ENTIRE document.',
        readonly: false,
        params: {
          content: {
            type: 'string',
            description: 'Complete HTML content for the full document. Use content_format="markdown" for Markdown.',
          },
          content_format: {
            type: 'string',
            enum: ['html', 'markdown'],
            description: 'Input format: "html" (default) or "markdown".',
          },
        },
        handler: async (params: Record<string, unknown>) => {
          const inputSize = String(params.content ?? '').trim().length;
          const fmt = String(params.content_format || 'html');
          const validation = validateReplaceContentParams(params, {
            ensureHtml: (s: string) => ensureHtml(s, fmt),
            fixTableWidthZero,
            sanitizeTableAttributesForSetContent,
          });
          if (!validation.valid) {
            console.warn(
              '[replace_content audit] page_key=%s operation_name=replace_content input_size=%d success=false error_type=%s',
              effectiveKey,
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
      },
      {
        name: 'replace_section',
        label: $t('common.replaceSection'),
        description:
          'Find a section by its old HTML snippet and replace it with new HTML. '
          + 'Use this for partial edits — only the matched section is replaced, '
          + 'the rest of the document is untouched. '
          + 'old_html should be a short unique HTML fragment from get_editor_html output.',
        readonly: false,
        params: {
          old_html: {
            type: 'string',
            description:
              'Existing HTML snippet to find (must be a unique substring of current content)',
          },
          new_html: {
            type: 'string',
            description: 'Replacement HTML. Use content_format="markdown" for Markdown.',
          },
          content_format: {
            type: 'string',
            enum: ['html', 'markdown'],
            description: 'Format of new_html: "html" (default) or "markdown".',
          },
        },
        handler: async (params: Record<string, unknown>) => {
          const oldSnippet = String(params.old_html || '').trim();
          const newSnippet = String(params.new_html || '').trim();
          if (!oldSnippet)
            return { success: false, message: $t('common.editorOp.oldHtmlRequired'), error_type: 'invalid_input' };
          if (!newSnippet)
            return { success: false, message: $t('common.editorOp.newHtmlRequired'), error_type: 'invalid_input' };

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
              message: $t('common.editorOp.oldHtmlNotFound') + ' Snippet matches multiple times; use a longer unique fragment.',
              error_type: 'non_unique_match',
            };
          }
          if (!normCurrent.includes(normOld)) {
            const snippetLen = 450;
            const excerpt = currentHtml.slice(0, snippetLen);
            return {
              success: false,
              message:
                $t('common.editorOp.oldHtmlNotFound')
                + ` First ${snippetLen} chars of current document:\n${excerpt}${currentHtml.length > snippetLen ? '...' : ''}`,
              error_type: 'target_not_found',
            };
          }

          // Normalize new_html so table attributes (colspan/rowspan) parse correctly and don't break TipTap TableMap
          const fmt = String(params.content_format || 'html');
          const newHtmlClean = toHtml(normalizeHtmlForMatch(newSnippet), fmt);
          const updatedNorm = normCurrent.replace(normOld, newHtmlClean);
          const updatedHtml = sanitizeTableAttributesForSetContent(
            fixTableWidthZero(updatedNorm),
          );

          try {
            editor.commands.setContent(updatedHtml);
          } catch (e) {
            const errMsg = e instanceof Error ? e.message : String(e);
            return {
              success: false,
              message: $t('common.editorOp.replacementInvalidStructure', { error: errMsg }),
              error_type: 'invalid_html',
            };
          }
          return {
            success: true,
            message: $t('common.editorOp.sectionReplaced', {
              old: oldSnippet.length,
              new: newSnippet.length,
            }),
          };
        },
      },
      {
        name: 'append_content',
        label: $t('common.appendContent'),
        description:
          'Append content to the end. content MUST be HTML by default; set content_format="markdown" for Markdown input.',
        readonly: false,
        params: {
          content: {
            type: 'string',
            description: 'HTML content to append (e.g. <p>new paragraph</p>). Use content_format="markdown" for Markdown.',
          },
          content_format: {
            type: 'string',
            enum: ['html', 'markdown'],
            description: 'Input format: "html" (default) or "markdown".',
          },
        },
        handler: async (params: Record<string, unknown>) => {
          const raw = String(params.content || '');
          if (!raw)
            return { success: false, message: $t('common.editorOp.noContentProvided') };
          const fmt = String(params.content_format || 'html');
          const html = sanitizeTableAttributesForSetContent(
            fixTableWidthZero(toHtml(raw, fmt)),
          );
          const endPos = editor.state.doc.content.size;
          editor.chain().focus().insertContentAt(endPos, html).run();
          return {
            success: true,
            message: $t('common.editorOp.appendedChars', { count: raw.length }),
          };
        },
      },
      // --- Selection & history ---
      {
        name: 'get_selection',
        label: $t('common.getSelection'),
        description: 'Get current selection text and position (from, to).',
        readonly: true,
        handler: async () => {
          const { from, to } = editor.state.selection;
          const text = editor.state.doc.textBetween(from, to, '');
          return {
            success: true,
            message: $t('common.editorOp.selectionChars', { count: text.length }),
            data: { text, from, to },
          };
        },
      },
      {
        name: 'select_all',
        label: $t('common.selectAll'),
        description: 'Select all editor content.',
        readonly: false,
        handler: async () => {
          editor.commands.selectAll();
          return { success: true, message: $t('common.editorOp.selectedAll') };
        },
      },
      {
        name: 'undo',
        label: $t('common.undo'),
        description: 'Undo last change.',
        readonly: false,
        handler: async () => {
          const ok = editor.chain().focus().undo().run();
          return { success: ok, message: ok ? $t('common.editorOp.undone') : $t('common.editorOp.nothingToUndo') };
        },
      },
      {
        name: 'redo',
        label: $t('common.redo'),
        description: 'Redo last undone change.',
        readonly: false,
        handler: async () => {
          const ok = editor.chain().focus().redo().run();
          return { success: ok, message: ok ? $t('common.editorOp.redone') : $t('common.editorOp.nothingToRedo') };
        },
      },
      // --- Text formatting ---
      {
        name: 'format_text',
        label: $t('common.formatText'),
        description: 'Apply or toggle format on selection: bold, italic, underline, strike, code, highlight.',
        readonly: false,
        params: {
          command: {
            type: 'string',
            enum: ['bold', 'italic', 'underline', 'strike', 'code', 'highlight'],
            description: 'Format command',
          },
        },
        handler: async (params: Record<string, unknown>) => {
          const cmd = String(params.command || 'bold');
          const chain = editor.chain().focus();
          const map: Record<string, () => boolean> = {
            bold: () => chain.toggleBold().run(),
            italic: () => chain.toggleItalic().run(),
            underline: () => chain.toggleUnderline().run(),
            strike: () => chain.toggleStrike().run(),
            code: () => chain.toggleCode().run(),
            highlight: () => chain.toggleHighlight().run(),
          };
          const run = map[cmd];
          const ok = run ? run() : false;
          return { success: ok, message: ok ? $t('common.editorOp.toggledFormat', { cmd }) : $t('common.editorOp.formatFailed') };
        },
      },
      {
        name: 'clear_formatting',
        label: $t('common.clearFormatting'),
        description: 'Clear all formatting in selection.',
        readonly: false,
        handler: async () => {
          editor.chain().focus().unsetAllMarks().run();
          return { success: true, message: $t('common.editorOp.formattingCleared') };
        },
      },
      // --- Block ---
      {
        name: 'set_heading',
        label: $t('common.setHeading'),
        description: 'Set current block as heading level 1, 2, or 3.',
        readonly: false,
        params: {
          level: {
            type: 'number',
            description: 'Heading level 1, 2, or 3',
          },
        },
        handler: async (params: Record<string, unknown>) => {
          const level = Math.min(3, Math.max(1, Number(params.level) || 1)) as 1 | 2 | 3;
          editor.chain().focus().toggleHeading({ level }).run();
          return { success: true, message: $t('common.editorOp.headingApplied', { level }) };
        },
      },
      {
        name: 'toggle_list',
        label: $t('common.toggleList'),
        description: 'Toggle bullet or ordered list.',
        readonly: false,
        params: {
          type: {
            type: 'string',
            enum: ['bullet', 'ordered'],
            description: 'bullet or ordered',
          },
        },
        handler: async (params: Record<string, unknown>) => {
          const t = String(params.type || 'bullet');
          if (t === 'ordered')
            editor.chain().focus().toggleOrderedList().run();
          else
            editor.chain().focus().toggleBulletList().run();
          return { success: true, message: $t('common.editorOp.listToggled', { type: t }) };
        },
      },
      {
        name: 'toggle_blockquote',
        label: $t('common.toggleBlockquote'),
        description: 'Toggle blockquote on current block.',
        readonly: false,
        handler: async () => {
          editor.chain().focus().toggleBlockquote().run();
          return { success: true, message: $t('common.editorOp.blockquoteToggled') };
        },
      },
      {
        name: 'toggle_code_block',
        label: $t('common.toggleCodeBlock'),
        description: 'Toggle code block on current block.',
        readonly: false,
        handler: async () => {
          editor.chain().focus().toggleCodeBlock().run();
          return { success: true, message: $t('common.editorOp.codeBlockToggled') };
        },
      },
      {
        name: 'insert_horizontal_rule',
        label: $t('common.insertHorizontalRule'),
        description: 'Insert a horizontal rule.',
        readonly: false,
        handler: async () => {
          editor.chain().focus().setHorizontalRule().run();
          return { success: true, message: $t('common.editorOp.horizontalRuleInserted') };
        },
      },
      {
        name: 'set_text_align',
        label: $t('common.setTextAlign'),
        description: 'Set text alignment: left, center, right, justify.',
        readonly: false,
        params: {
          align: {
            type: 'string',
            enum: ['left', 'center', 'right', 'justify'],
            description: 'Alignment',
          },
        },
        handler: async (params: Record<string, unknown>) => {
          const align = String(params.align || 'left');
          if (!['left', 'center', 'right', 'justify'].includes(align))
            return { success: false, message: $t('common.editorOp.invalidAlign') };
          editor.chain().focus().setTextAlign(align).run();
          return { success: true, message: $t('common.editorOp.alignApplied', { align }) };
        },
      },
      // --- Link & table ---
      {
        name: 'manage_link',
        label: $t('common.manageLink'),
        description: 'Set or unset link on selection. action: set (requires href) or unset.',
        readonly: false,
        params: {
          action: {
            type: 'string',
            enum: ['set', 'unset'],
            description: 'set or unset link',
          },
          href: {
            type: 'string',
            description: 'URL when action is set',
          },
        },
        handler: async (params: Record<string, unknown>) => {
          const action = String(params.action || 'set');
          if (action === 'unset') {
            editor.chain().focus().extendMarkRange('link').unsetLink().run();
            return { success: true, message: $t('common.editorOp.linkRemoved') };
          }
          const href = String(params.href || '').trim();
          if (!href)
            return { success: false, message: $t('common.editorOp.hrefRequired') };
          editor.chain().focus().extendMarkRange('link').setLink({ href }).run();
          return { success: true, message: $t('common.editorOp.linkSet', { href }) };
        },
      },
      {
        name: 'insert_table',
        label: $t('common.insertTable'),
        description: 'Insert a table. Optional rows (default 3), cols (default 3).',
        readonly: false,
        params: {
          rows: { type: 'number', description: 'Number of rows' },
          cols: { type: 'number', description: 'Number of columns' },
        },
        handler: async (params: Record<string, unknown>) => {
          const rows = Math.min(10, Math.max(1, Number(params.rows) || 3));
          const cols = Math.min(10, Math.max(1, Number(params.cols) || 3));
          editor
            .chain()
            .focus()
            .insertTable({ rows, cols, withHeaderRow: true })
            .run();
          return { success: true, message: $t('common.editorOp.tableInserted', { rows, cols }) };
        },
      },
    ]);
  }

  const unwatch = watch(
    editorRef,
    (ed) => {
      if (ed) register();
    },
    { immediate: true },
  );

  onBeforeUnmount(() => {
    cleanupOps?.();
    cleanupCtx?.();
    unwatch();
  });
}
