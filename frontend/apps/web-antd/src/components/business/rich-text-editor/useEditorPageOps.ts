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

import {
  registerPageContext,
  registerPageOperations,
} from '#/components/business/ai-slide-panel';

export function useEditorPageOps(
  editorRef: ShallowRef<Editor | undefined>,
  pageKey: string | undefined,
) {
  if (!pageKey) return;

  let cleanupOps: (() => void) | undefined;
  let cleanupCtx: (() => void) | undefined;

  function register() {
    cleanupOps?.();
    cleanupCtx?.();
    const editor = editorRef.value;
    if (!editor) return;

    cleanupCtx = registerPageContext(pageKey!, () => ({
      page_key: pageKey!,
      page_title: 'Rich Text Editor',
      page_data: {
        entity_name: 'Rich Text Editor',
        entity_description:
          '富文本编辑器，支持通过 Ctrl+K AI 助手执行以下操作。\n'
          + '【内容读写】get_editor_text, get_editor_html, get_selection, insert_content, replace_content, append_content\n'
          + '【选区与历史】select_all, undo, redo\n'
          + '【文本格式】format_text (command: bold|italic|underline|strike|code|highlight), clear_formatting\n'
          + '【块级】set_heading (level 1-3), toggle_list (type bullet|ordered), toggle_blockquote, toggle_code_block, insert_horizontal_rule, set_text_align (align left|center|right|justify)\n'
          + '【链接与表格】manage_link (action set|unset, href?), insert_table (rows?, cols?)',
        has_editor: true,
        word_count: editor.storage.characterCount?.words?.() ?? 0,
      },
    }));

    cleanupOps = registerPageOperations(pageKey!, [
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
            message: `Editor has ${words} words`,
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
          const html = editor.getHTML();
          return {
            success: true,
            message: `HTML content retrieved (${html.length} chars)`,
            data: { html: html.slice(0, 8000) },
          };
        },
      },
      {
        name: 'insert_content',
        label: $t('common.insertContent'),
        description:
          'Insert content at the current cursor position. Supports plain text or HTML.',
        readonly: false,
        params: {
          content: {
            type: 'string',
            description: 'Content to insert',
          },
          format: {
            type: 'string',
            enum: ['text', 'html'],
            description: 'text (default) or html',
          },
        },
        handler: async (params: Record<string, unknown>) => {
          const content = String(params.content || '');
          if (!content)
            return { success: false, message: 'No content provided' };
          editor.chain().focus().insertContent(content).run();
          return {
            success: true,
            message: `Inserted ${content.length} characters`,
          };
        },
      },
      {
        name: 'replace_content',
        label: $t('common.replaceContent'),
        description:
          'Replace ALL editor content. WARNING: overwrites everything.',
        readonly: false,
        params: {
          content: {
            type: 'string',
            description: 'New content to replace everything',
          },
        },
        handler: async (params: Record<string, unknown>) => {
          const content = String(params.content || '');
          editor.commands.setContent(content);
          return {
            success: true,
            message: `Content replaced (${content.length} chars)`,
          };
        },
      },
      {
        name: 'append_content',
        label: $t('common.appendContent'),
        description: 'Append content to the end of the document.',
        readonly: false,
        params: {
          content: {
            type: 'string',
            description: 'Content to append at the end',
          },
        },
        handler: async (params: Record<string, unknown>) => {
          const content = String(params.content || '');
          if (!content)
            return { success: false, message: 'No content provided' };
          const endPos = editor.state.doc.content.size;
          editor.chain().focus().insertContentAt(endPos, content).run();
          return {
            success: true,
            message: `Appended ${content.length} chars`,
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
            message: `Selection: ${text.length} chars`,
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
          return { success: true, message: 'Selected all' };
        },
      },
      {
        name: 'undo',
        label: $t('common.undo'),
        description: 'Undo last change.',
        readonly: false,
        handler: async () => {
          const ok = editor.chain().focus().undo().run();
          return { success: ok, message: ok ? 'Undone' : 'Nothing to undo' };
        },
      },
      {
        name: 'redo',
        label: $t('common.redo'),
        description: 'Redo last undone change.',
        readonly: false,
        handler: async () => {
          const ok = editor.chain().focus().redo().run();
          return { success: ok, message: ok ? 'Redone' : 'Nothing to redo' };
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
          return { success: ok, message: ok ? `Toggled ${cmd}` : 'Failed' };
        },
      },
      {
        name: 'clear_formatting',
        label: $t('common.clearFormatting'),
        description: 'Clear all formatting in selection.',
        readonly: false,
        handler: async () => {
          editor.chain().focus().unsetAllMarks().run();
          return { success: true, message: 'Formatting cleared' };
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
          return { success: true, message: `Heading ${level} applied` };
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
          return { success: true, message: `List ${t} toggled` };
        },
      },
      {
        name: 'toggle_blockquote',
        label: $t('common.toggleBlockquote'),
        description: 'Toggle blockquote on current block.',
        readonly: false,
        handler: async () => {
          editor.chain().focus().toggleBlockquote().run();
          return { success: true, message: 'Blockquote toggled' };
        },
      },
      {
        name: 'toggle_code_block',
        label: $t('common.toggleCodeBlock'),
        description: 'Toggle code block on current block.',
        readonly: false,
        handler: async () => {
          editor.chain().focus().toggleCodeBlock().run();
          return { success: true, message: 'Code block toggled' };
        },
      },
      {
        name: 'insert_horizontal_rule',
        label: $t('common.insertHorizontalRule'),
        description: 'Insert a horizontal rule.',
        readonly: false,
        handler: async () => {
          editor.chain().focus().setHorizontalRule().run();
          return { success: true, message: 'Horizontal rule inserted' };
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
            return { success: false, message: 'Invalid align' };
          editor.chain().focus().setTextAlign(align).run();
          return { success: true, message: `Align ${align}` };
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
            return { success: true, message: 'Link removed' };
          }
          const href = String(params.href || '').trim();
          if (!href)
            return { success: false, message: 'href required when action is set' };
          editor.chain().focus().extendMarkRange('link').setLink({ href }).run();
          return { success: true, message: `Link set: ${href}` };
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
          return { success: true, message: `Table ${rows}x${cols} inserted` };
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
