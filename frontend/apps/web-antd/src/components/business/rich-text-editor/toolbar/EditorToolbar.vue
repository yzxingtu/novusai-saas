<script lang="ts" setup>
import type { Editor } from '@tiptap/core';

import { computed } from 'vue';

import { $t } from '@vben/locales';

import {
  triggerAttachmentUpload,
  triggerImageUpload,
} from '../useEditorUpload';
import ToolbarButton from './ToolbarButton.vue';

const props = defineProps<{
  editor: Editor | undefined;
  sourceMode?: boolean;
  upload?: boolean;
}>();

const emit = defineEmits<{
  toggleSource: [];
}>();

const isActive = (
  name: Record<string, unknown> | string,
  attrs?: Record<string, unknown>,
) => props.editor?.isActive(name as string, attrs) ?? false;

const canUndo = computed(() => props.editor?.can().undo() ?? false);
const canRedo = computed(() => props.editor?.can().redo() ?? false);

function onImageUpload() {
  if (props.editor) triggerImageUpload(props.editor);
}

function onAttachmentUpload() {
  if (props.editor) triggerAttachmentUpload(props.editor);
}

function onInsertLink() {
  const previousUrl = props.editor?.getAttributes('link').href;
  // Keep the lightweight native prompt here for editor link insertion.
  // eslint-disable-next-line no-alert
  const url = window.prompt('URL', previousUrl);
  if (url === null) return;
  if (url === '') {
    props.editor?.chain().focus().extendMarkRange('link').unsetLink().run();
    return;
  }
  props.editor
    ?.chain()
    .focus()
    .extendMarkRange('link')
    .setLink({ href: url })
    .run();
}
</script>

<template>
  <div
    v-if="editor"
    class="flex flex-wrap items-center gap-0.5 border-b border-border bg-background px-4 py-1.5 max-lg:flex-nowrap max-lg:overflow-x-auto max-lg:px-3 max-md:px-2"
    role="toolbar"
  >
    <!-- Undo / Redo -->
    <ToolbarButton
      icon="lucide:undo-2"
      :title="$t('common.undo')"
      :disabled="!canUndo"
      @click="editor?.chain().focus().undo().run()"
    />
    <ToolbarButton
      icon="lucide:redo-2"
      :title="$t('common.redo')"
      :disabled="!canRedo"
      @click="editor?.chain().focus().redo().run()"
    />

    <span class="mx-1 h-5 w-px shrink-0 bg-border"></span>

    <!-- Text format / 文本格式 -->
    <ToolbarButton
      icon="lucide:bold"
      :title="$t('common.bold')"
      :active="isActive('bold')"
      @click="editor?.chain().focus().toggleBold().run()"
    />
    <ToolbarButton
      icon="lucide:italic"
      :title="$t('common.italic')"
      :active="isActive('italic')"
      @click="editor?.chain().focus().toggleItalic().run()"
    />
    <ToolbarButton
      icon="lucide:underline"
      :title="$t('common.underline')"
      :active="isActive('underline')"
      @click="editor?.chain().focus().toggleUnderline().run()"
    />
    <ToolbarButton
      icon="lucide:strikethrough"
      :title="$t('common.strikethrough')"
      :active="isActive('strike')"
      @click="editor?.chain().focus().toggleStrike().run()"
    />
    <ToolbarButton
      icon="lucide:code"
      :title="$t('common.code')"
      :active="isActive('code')"
      @click="editor?.chain().focus().toggleCode().run()"
    />
    <ToolbarButton
      icon="lucide:highlighter"
      :title="$t('common.highlight')"
      :active="isActive('highlight')"
      @click="editor?.chain().focus().toggleHighlight().run()"
    />

    <span class="mx-1 h-5 w-px shrink-0 bg-border"></span>

    <!-- Headings / 标题 -->
    <ToolbarButton
      icon="lucide:heading-1"
      title="H1"
      :active="isActive('heading', { level: 1 })"
      @click="editor?.chain().focus().toggleHeading({ level: 1 }).run()"
    />
    <ToolbarButton
      icon="lucide:heading-2"
      title="H2"
      :active="isActive('heading', { level: 2 })"
      @click="editor?.chain().focus().toggleHeading({ level: 2 }).run()"
    />
    <ToolbarButton
      icon="lucide:heading-3"
      title="H3"
      :active="isActive('heading', { level: 3 })"
      @click="editor?.chain().focus().toggleHeading({ level: 3 }).run()"
    />

    <span class="mx-1 h-5 w-px shrink-0 bg-border"></span>

    <!-- Lists / 列表 -->
    <ToolbarButton
      icon="lucide:list"
      :title="$t('common.unorderedList')"
      :active="isActive('bulletList')"
      @click="editor?.chain().focus().toggleBulletList().run()"
    />
    <ToolbarButton
      icon="lucide:list-ordered"
      :title="$t('common.orderedList')"
      :active="isActive('orderedList')"
      @click="editor?.chain().focus().toggleOrderedList().run()"
    />
    <ToolbarButton
      icon="lucide:list-checks"
      :title="$t('common.taskList')"
      :active="isActive('taskList')"
      @click="editor?.chain().focus().toggleTaskList().run()"
    />

    <span class="mx-1 h-5 w-px shrink-0 bg-border"></span>

    <!-- Block / 块元素 -->
    <ToolbarButton
      icon="lucide:quote"
      :title="$t('common.blockquote')"
      :active="isActive('blockquote')"
      @click="editor?.chain().focus().toggleBlockquote().run()"
    />
    <ToolbarButton
      icon="lucide:file-code"
      :title="$t('common.codeBlock')"
      :active="isActive('codeBlock')"
      @click="editor?.chain().focus().toggleCodeBlock().run()"
    />
    <ToolbarButton
      icon="lucide:minus"
      :title="$t('common.horizontalRule')"
      @click="editor?.chain().focus().setHorizontalRule().run()"
    />

    <span class="mx-1 h-5 w-px shrink-0 bg-border"></span>

    <!-- Insert / 插入 -->
    <ToolbarButton
      v-if="upload !== false"
      icon="lucide:image"
      :title="$t('common.image')"
      @click="onImageUpload"
    />
    <ToolbarButton
      v-if="upload !== false"
      icon="lucide:paperclip"
      :title="$t('common.attachment')"
      @click="onAttachmentUpload"
    />
    <ToolbarButton
      icon="lucide:table"
      :title="$t('common.table')"
      @click="
        editor
          ?.chain()
          .focus()
          .insertTable({ rows: 3, cols: 3, withHeaderRow: true })
          .run()
      "
    />

    <span class="mx-1 h-5 w-px shrink-0 bg-border"></span>

    <!-- Text Align / 对齐 -->
    <ToolbarButton
      icon="lucide:align-left"
      :title="$t('common.alignLeft')"
      :active="isActive({ textAlign: 'left' })"
      @click="editor?.chain().focus().setTextAlign('left').run()"
    />
    <ToolbarButton
      icon="lucide:align-center"
      :title="$t('common.alignCenter')"
      :active="isActive({ textAlign: 'center' })"
      @click="editor?.chain().focus().setTextAlign('center').run()"
    />
    <ToolbarButton
      icon="lucide:align-right"
      :title="$t('common.alignRight')"
      :active="isActive({ textAlign: 'right' })"
      @click="editor?.chain().focus().setTextAlign('right').run()"
    />

    <span class="mx-1 h-5 w-px shrink-0 bg-border"></span>

    <!-- Subscript / Superscript -->
    <ToolbarButton
      icon="lucide:subscript"
      :title="$t('common.subscript')"
      :active="isActive('subscript')"
      @click="editor?.chain().focus().toggleSubscript().run()"
    />
    <ToolbarButton
      icon="lucide:superscript"
      :title="$t('common.superscript')"
      :active="isActive('superscript')"
      @click="editor?.chain().focus().toggleSuperscript().run()"
    />

    <span class="mx-1 h-5 w-px shrink-0 bg-border"></span>

    <!-- Link -->
    <ToolbarButton
      icon="lucide:link"
      :title="$t('common.link')"
      :active="isActive('link')"
      @click="onInsertLink"
    />
    <ToolbarButton
      v-if="isActive('link')"
      icon="lucide:unlink"
      :title="$t('common.removeLink')"
      @click="editor?.chain().focus().unsetLink().run()"
    />

    <span class="mx-1 h-5 w-px shrink-0 bg-border"></span>

    <!-- Source code / 源码模式 -->
    <ToolbarButton
      icon="lucide:code-xml"
      :title="
        sourceMode
          ? $t('common.wysiwyg') || 'WYSIWYG'
          : $t('common.sourceCode') || 'HTML'
      "
      :active="sourceMode"
      @click="emit('toggleSource')"
    />
  </div>
</template>
