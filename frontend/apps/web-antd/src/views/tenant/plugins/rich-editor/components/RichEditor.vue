<script setup lang="ts">
/**
 * RichEditor 核心组件
 *
 * 封装 TipTap useEditor + EditorContent
 * Props: content, readonly, placeholder
 * Emits: update:content (HTML)
 */
import { computed, onBeforeUnmount, ref, toRef, watch } from 'vue';

import { EditorContent, useEditor } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import Subscript from '@tiptap/extension-subscript';
import Superscript from '@tiptap/extension-superscript';
import Link from '@tiptap/extension-link';
import TextStyle from '@tiptap/extension-text-style';
import FontFamily from '@tiptap/extension-font-family';
import Placeholder from '@tiptap/extension-placeholder';
import Color from '@tiptap/extension-color';
import Highlight from '@tiptap/extension-highlight';
import TextAlign from '@tiptap/extension-text-align';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import Image from '@tiptap/extension-image';
import CodeBlockLowlight from '@tiptap/extension-code-block-lowlight';
import Table from '@tiptap/extension-table';
import TableRow from '@tiptap/extension-table-row';
import TableCell from '@tiptap/extension-table-cell';
import TableHeader from '@tiptap/extension-table-header';
import Collaboration from '@tiptap/extension-collaboration';
import CollaborationCursor from '@tiptap/extension-collaboration-cursor';
import { common, createLowlight } from 'lowlight';
import { Markdown } from 'tiptap-markdown';

import { $t } from '#/locales';

import { useEditorExport } from '../composables/use-editor-export';
import { useCollaboration } from '../composables/use-collaboration';

import EditorToolbar from './EditorToolbar.vue';

const lowlight = createLowlight(common);

const props = withDefaults(
  defineProps<{
    content?: string;
    readonly?: boolean;
    placeholder?: string;
    enableCollaboration?: boolean;
    enableAi?: boolean;
    documentId?: number;
    serverUrl?: string;
    token?: string;
    userId?: number;
    userName?: string;
    userColor?: string;
    documentTitle?: string;
  }>(),
  {
    content: '',
    readonly: false,
    placeholder: '',
    enableCollaboration: false,
    enableAI: false,
    documentId: undefined,
    serverUrl: '',
    token: '',
    userId: 0,
    userName: '',
    userColor: '#2196F3',
    documentTitle: '',
  },
);

const emit = defineEmits<{
  'update:content': [html: string];
  'aiAction': [action: string];
}>();

// ==================== 协作 ====================

const enableCollab = toRef(props, 'enableCollaboration');
const docId = toRef(props, 'documentId') as import('vue').Ref<number | undefined>;
const tokenRef = toRef(props, 'token');

const { ydoc, connected, onlineUsers } = useCollaboration({
  enabled: enableCollab,
  documentId: docId,
  serverUrl: props.serverUrl,
  token: tokenRef,
  user: {
    id: props.userId,
    name: props.userName,
    color: props.userColor,
  },
});

// 协作扩展（仅当启用时添加）
const collaborationExtensions = computed(() => {
  if (!enableCollab.value || !ydoc.value) return [];
  return [
    Collaboration.configure({
      document: ydoc.value,
    }),
    CollaborationCursor.configure({
      provider: null as unknown as Record<string, unknown>,
      user: {
        name: props.userName,
        color: props.userColor,
      },
    }),
  ];
});

const editor = useEditor({
  content: props.content,
  editable: !props.readonly,
  extensions: [
    StarterKit.configure({
      heading: { levels: [1, 2, 3, 4, 5, 6] },
      history: props.enableCollaboration ? false : undefined,
    }),
    Underline,
    Subscript,
    Superscript,
    Link.configure({
      openOnClick: false,
      HTMLAttributes: {
        class: 'text-primary underline cursor-pointer',
      },
    }),
    TextStyle,
    FontFamily,
    Placeholder.configure({
      placeholder: props.placeholder,
    }),
    Color,
    Highlight.configure({ multicolor: true }),
    TextAlign.configure({
      types: ['heading', 'paragraph'],
      alignments: ['left', 'center', 'right', 'justify'],
    }),
    TaskList,
    TaskItem.configure({ nested: true }),
    Image.configure({
      inline: false,
      allowBase64: true,
      HTMLAttributes: {
        class: 'rich-editor-image',
      },
    }),
    CodeBlockLowlight.configure({
      lowlight,
      defaultLanguage: 'plaintext',
      HTMLAttributes: {
        class: 'rich-editor-code-block',
      },
    }),
    Table.configure({
      resizable: true,
      HTMLAttributes: {
        class: 'rich-editor-table',
      },
    }),
    TableRow,
    TableCell,
    TableHeader,
    Markdown.configure({
      html: true,
      transformCopiedText: true,
      transformPastedText: true,
    }),
    ...collaborationExtensions.value,
  ],
  onUpdate: ({ editor: ed }: { editor: import('@tiptap/core').Editor }) => {
    emit('update:content', ed.getHTML());
  },
  editorProps: {
    attributes: {
      class: 'rich-editor-content outline-none min-h-[500px] prose prose-sm max-w-none',
    },
  },
});

// 外部 content 变化时同步（避免重复触发）
watch(
  () => props.content,
  (val) => {
    if (!editor.value) return;
    const currentHtml = editor.value.getHTML();
    if (val !== currentHtml) {
      editor.value.commands.setContent(val, false);
    }
  },
);

// readonly 切换
watch(
  () => props.readonly,
  (val) => {
    editor.value?.setEditable(!val);
  },
);

// ==================== 导出 ====================

const editorRef = ref(editor.value);
watch(editor, (val) => { editorRef.value = val; });

const {
  downloadMarkdown,
  downloadHTML,
  downloadJSON,
  exportPDF,
} = useEditorExport(editorRef as import('vue').Ref<import('@tiptap/core').Editor | undefined>);

const filename = computed(() => props.documentTitle || 'document');

function handleExportMarkdown() {
  downloadMarkdown(`${filename.value}.md`);
}
function handleExportHTML() {
  downloadHTML(`${filename.value}.html`);
}
function handleExportJSON() {
  downloadJSON(`${filename.value}.json`);
}
function handleExportPDF() {
  exportPDF(filename.value);
}

function handleAiAction(action: string) {
  emit('aiAction', action);
}

onBeforeUnmount(() => {
  editor.value?.destroy();
});
</script>

<template>
  <div class="rich-editor-wrapper">
    <!-- 工具栏 -->
    <EditorToolbar
      v-if="editor && !readonly"
      :editor="editor"
      :ai-enabled="enableAi"
      @toggle-fullscreen="() => {}"
      @export-markdown="handleExportMarkdown"
      @export-html="handleExportHTML"
      @export-json="handleExportJSON"
      @export-pdf="handleExportPDF"
      @ai-action="handleAiAction"
    />

    <!-- 协作状态栏 -->
    <div v-if="enableCollaboration" class="collaboration-bar">
      <span class="collab-status" :class="{ connected }">
        <span class="status-dot" />
        {{ connected ? $t('tenant.richEditor.collaboration.connected') : $t('tenant.richEditor.collaboration.connecting') }}
      </span>
      <span v-if="onlineUsers.length > 0" class="collab-users">
        <span
          v-for="u in onlineUsers"
          :key="u.id"
          class="collab-avatar"
          :style="{ backgroundColor: u.color }"
          :title="u.name"
        >
          {{ u.name.charAt(0).toUpperCase() }}
        </span>
      </span>
    </div>

    <!-- 编辑区域 -->
    <div class="rich-editor-body">
      <EditorContent :editor="editor" />
    </div>
  </div>
</template>

<style scoped>
.rich-editor-wrapper {
  border: 1px solid hsl(var(--border));
  border-radius: 0.75rem;
  overflow: hidden;
  background: hsl(var(--card));
}

.rich-editor-body {
  padding: 1.5rem 2rem;
  min-height: 500px;
}

/* TipTap 编辑区基础样式 */
:deep(.ProseMirror) {
  outline: none;
  min-height: 500px;
  color: hsl(var(--foreground));
  font-size: 16px;
  line-height: 1.8;
}

:deep(.ProseMirror p.is-editor-empty:first-child::before) {
  content: attr(data-placeholder);
  float: left;
  color: hsl(var(--muted-foreground));
  pointer-events: none;
  height: 0;
}

/* 标题样式 */
:deep(.ProseMirror h1) {
  font-size: 2rem;
  font-weight: 700;
  line-height: 1.3;
  margin: 1.5rem 0 0.75rem;
}
:deep(.ProseMirror h2) {
  font-size: 1.5rem;
  font-weight: 600;
  line-height: 1.4;
  margin: 1.25rem 0 0.5rem;
}
:deep(.ProseMirror h3) {
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1.5;
  margin: 1rem 0 0.5rem;
}
:deep(.ProseMirror h4) {
  font-size: 1.125rem;
  font-weight: 600;
  margin: 0.75rem 0 0.5rem;
}

/* 引用 */
:deep(.ProseMirror blockquote) {
  border-left: 3px solid hsl(var(--primary));
  padding-left: 1rem;
  color: hsl(var(--muted-foreground));
  margin: 1rem 0;
}

/* 代码 */
:deep(.ProseMirror code) {
  background: hsl(var(--muted));
  padding: 0.15rem 0.4rem;
  border-radius: 0.25rem;
  font-size: 0.875em;
}

/* 分割线 */
:deep(.ProseMirror hr) {
  border: none;
  border-top: 1px solid hsl(var(--border));
  margin: 1.5rem 0;
}

/* 链接 */
:deep(.ProseMirror a) {
  color: hsl(var(--primary));
  text-decoration: underline;
  cursor: pointer;
}

/* 列表 */
:deep(.ProseMirror ul),
:deep(.ProseMirror ol) {
  padding-left: 1.5rem;
  margin: 0.5rem 0;
}

:deep(.ProseMirror li) {
  margin: 0.25rem 0;
}

/* 待办事项 */
:deep(.ProseMirror ul[data-type='taskList']) {
  list-style: none;
  padding-left: 0;
}

:deep(.ProseMirror ul[data-type='taskList'] li) {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin: 0.25rem 0;
}

:deep(.ProseMirror ul[data-type='taskList'] li label) {
  flex-shrink: 0;
  margin-top: 0.25rem;
}

:deep(.ProseMirror ul[data-type='taskList'] li label input[type='checkbox']) {
  width: 1rem;
  height: 1rem;
  accent-color: hsl(var(--primary));
  cursor: pointer;
}

:deep(.ProseMirror ul[data-type='taskList'] li div) {
  flex: 1;
}

:deep(.ProseMirror ul[data-type='taskList'] li[data-checked='true'] > div) {
  text-decoration: line-through;
  color: hsl(var(--muted-foreground));
}

/* 高亮 */
:deep(.ProseMirror mark) {
  border-radius: 0.15rem;
  padding: 0.05rem 0.15rem;
}

/* 文字对齐 */
:deep(.ProseMirror [style*='text-align: center']) {
  text-align: center;
}
:deep(.ProseMirror [style*='text-align: right']) {
  text-align: right;
}
:deep(.ProseMirror [style*='text-align: justify']) {
  text-align: justify;
}

/* Mention */
:deep(.ProseMirror .mention) {
  background: hsl(var(--primary) / 0.1);
  color: hsl(var(--primary));
  border-radius: 0.25rem;
  padding: 0.1rem 0.3rem;
  font-weight: 500;
  cursor: pointer;
}

/* 图片 */
:deep(.ProseMirror .rich-editor-image) {
  border-radius: 0.5rem;
  max-width: 100%;
  height: auto;
  margin: 1rem 0;
  cursor: pointer;
  transition: box-shadow 150ms ease-out;
}

:deep(.ProseMirror .rich-editor-image:hover) {
  box-shadow: 0 4px 12px hsl(var(--foreground) / 0.1);
}

:deep(.ProseMirror .ProseMirror-selectednode .rich-editor-image),
:deep(.ProseMirror img.ProseMirror-selectednode) {
  outline: 2px solid hsl(var(--primary));
  outline-offset: 2px;
}

/* 代码块 */
:deep(.ProseMirror .rich-editor-code-block) {
  background: hsl(var(--muted));
  border-radius: 0.5rem;
  padding: 1rem 1.25rem;
  margin: 1rem 0;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.875rem;
  line-height: 1.6;
  overflow-x: auto;
  position: relative;
}

:deep(.ProseMirror .rich-editor-code-block code) {
  background: transparent;
  padding: 0;
  border-radius: 0;
  font-size: inherit;
  color: inherit;
}

/* 表格 */
:deep(.ProseMirror .rich-editor-table) {
  border-collapse: collapse;
  width: 100%;
  margin: 1rem 0;
  overflow: hidden;
  border-radius: 0.5rem;
  border: 1px solid hsl(var(--border));
}

:deep(.ProseMirror .rich-editor-table td),
:deep(.ProseMirror .rich-editor-table th) {
  border: 1px solid hsl(var(--border));
  padding: 0.5rem 0.75rem;
  vertical-align: top;
  min-width: 80px;
  position: relative;
}

:deep(.ProseMirror .rich-editor-table th) {
  background: hsl(var(--muted) / 0.5);
  font-weight: 600;
  text-align: left;
}

:deep(.ProseMirror .rich-editor-table td:hover),
:deep(.ProseMirror .rich-editor-table th:hover) {
  background: hsl(var(--accent) / 0.3);
}

:deep(.ProseMirror .rich-editor-table .selectedCell) {
  background: hsl(var(--primary) / 0.08);
}

/* 表格列宽拖拽手柄 */
:deep(.ProseMirror .column-resize-handle) {
  position: absolute;
  right: -2px;
  top: 0;
  bottom: -2px;
  width: 4px;
  background: hsl(var(--primary));
  pointer-events: none;
}

:deep(.ProseMirror.resize-cursor) {
  cursor: col-resize;
}

/* ==================== 协作状态栏 ==================== */

.collaboration-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.375rem 1rem;
  border-bottom: 1px solid hsl(var(--border));
  background: hsl(var(--muted) / 0.3);
  font-size: 0.75rem;
}

.collab-status {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  color: hsl(var(--muted-foreground));
}

.collab-status.connected {
  color: hsl(var(--success, 142 71% 45%));
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: hsl(var(--muted-foreground));
}

.collab-status.connected .status-dot {
  background: hsl(var(--success, 142 71% 45%));
  box-shadow: 0 0 4px hsl(var(--success, 142 71% 45%) / 0.5);
}

.collab-users {
  display: flex;
  gap: 0.25rem;
}

.collab-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  color: white;
  font-size: 0.625rem;
  font-weight: 600;
  cursor: default;
}

/* ==================== 协作光标 ==================== */

:deep(.collaboration-cursor__caret) {
  position: relative;
  margin-left: -1px;
  margin-right: -1px;
  border-left: 2px solid;
  border-right: 0;
  word-break: normal;
  pointer-events: none;
}

:deep(.collaboration-cursor__label) {
  position: absolute;
  top: -1.4em;
  left: -1px;
  font-size: 0.625rem;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
  color: white;
  padding: 0.1rem 0.3rem;
  border-radius: 0.25rem 0.25rem 0.25rem 0;
  user-select: none;
  pointer-events: none;
}
</style>
