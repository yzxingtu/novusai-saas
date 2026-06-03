<script lang="ts" setup>
import type { Editor } from '@tiptap/core';

import { $t } from '@vben/locales';

import {
  triggerAttachmentUpload,
  triggerImageUpload,
} from '../useEditorUpload';
import ToolbarButton from './ToolbarButton.vue';

const props = defineProps<{
  editor: Editor | undefined;
  upload?: boolean;
}>();

const isActive = (name: string, attrs?: Record<string, unknown>) =>
  props.editor?.isActive(name, attrs) ?? false;

function onImageUpload() {
  if (props.editor) triggerImageUpload(props.editor);
}

function onAttachmentUpload() {
  if (props.editor) triggerAttachmentUpload(props.editor);
}
</script>

<template>
  <div
    v-if="editor"
    class="flex items-center gap-0.5 border-b border-border px-2 py-1"
    role="toolbar"
  >
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

    <span class="mx-0.5 h-4 w-px shrink-0 bg-border"></span>

    <ToolbarButton
      icon="lucide:heading-2"
      :title="$t('common.heading2')"
      :active="isActive('heading', { level: 2 })"
      @click="editor?.chain().focus().toggleHeading({ level: 2 }).run()"
    />
    <ToolbarButton
      icon="lucide:heading-3"
      :title="$t('common.heading3')"
      :active="isActive('heading', { level: 3 })"
      @click="editor?.chain().focus().toggleHeading({ level: 3 }).run()"
    />

    <span class="mx-0.5 h-4 w-px shrink-0 bg-border"></span>

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

    <span class="mx-0.5 h-4 w-px shrink-0 bg-border"></span>

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
  </div>
</template>
