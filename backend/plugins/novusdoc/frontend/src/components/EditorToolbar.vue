<script lang="ts" setup>
import { computed } from 'vue'
import { Tooltip } from 'ant-design-vue'
import { IconifyIcon, $t } from '@novus/plugin-shared'
import type { Editor } from '@tiptap/core'

const props = defineProps<{
  editor: Editor | undefined
}>()

const isActive = (name: string, attrs?: Record<string, unknown>) =>
  props.editor?.isActive(name, attrs) ?? false

const canUndo = computed(() => props.editor?.can().undo() ?? false)
const canRedo = computed(() => props.editor?.can().redo() ?? false)
</script>

<template>
  <div v-if="editor" class="flex items-center gap-0.5 flex-wrap border-b border-border bg-background px-4 py-1.5 max-lg:flex-nowrap max-lg:overflow-x-auto max-lg:px-3 max-md:px-2" role="toolbar" aria-label="Editor formatting toolbar">
    <!-- Undo / Redo -->
    <Tooltip :title="$t('plugin.novusdoc.toolbar.undo')">
      <button class="nd-tbtn" :disabled="!canUndo" @click="editor?.chain().focus().undo().run()">
        <IconifyIcon icon="lucide:undo-2" class="size-4" />
      </button>
    </Tooltip>
    <Tooltip :title="$t('plugin.novusdoc.toolbar.redo')">
      <button class="nd-tbtn" :disabled="!canRedo" @click="editor?.chain().focus().redo().run()">
        <IconifyIcon icon="lucide:redo-2" class="size-4" />
      </button>
    </Tooltip>

    <span class="mx-1 h-5 w-px shrink-0 bg-border"></span>

    <!-- Text format -->
    <Tooltip :title="$t('plugin.novusdoc.toolbar.bold')">
      <button class="nd-tbtn" :class="{ '!bg-primary/[0.12] !text-primary': isActive('bold') }" @click="editor?.chain().focus().toggleBold().run()">
        <IconifyIcon icon="lucide:bold" class="size-4" />
      </button>
    </Tooltip>
    <Tooltip :title="$t('plugin.novusdoc.toolbar.italic')">
      <button class="nd-tbtn" :class="{ '!bg-primary/[0.12] !text-primary': isActive('italic') }" @click="editor?.chain().focus().toggleItalic().run()">
        <IconifyIcon icon="lucide:italic" class="size-4" />
      </button>
    </Tooltip>
    <Tooltip :title="$t('plugin.novusdoc.toolbar.underline')">
      <button class="nd-tbtn" :class="{ '!bg-primary/[0.12] !text-primary': isActive('underline') }" @click="editor?.chain().focus().toggleUnderline().run()">
        <IconifyIcon icon="lucide:underline" class="size-4" />
      </button>
    </Tooltip>
    <Tooltip :title="$t('plugin.novusdoc.toolbar.strikethrough')">
      <button class="nd-tbtn" :class="{ '!bg-primary/[0.12] !text-primary': isActive('strike') }" @click="editor?.chain().focus().toggleStrike().run()">
        <IconifyIcon icon="lucide:strikethrough" class="size-4" />
      </button>
    </Tooltip>
    <Tooltip :title="$t('plugin.novusdoc.toolbar.code')">
      <button class="nd-tbtn" :class="{ '!bg-primary/[0.12] !text-primary': isActive('code') }" @click="editor?.chain().focus().toggleCode().run()">
        <IconifyIcon icon="lucide:code" class="size-4" />
      </button>
    </Tooltip>
    <Tooltip :title="$t('plugin.novusdoc.toolbar.highlight')">
      <button class="nd-tbtn" :class="{ '!bg-primary/[0.12] !text-primary': isActive('highlight') }" @click="editor?.chain().focus().toggleHighlight().run()">
        <IconifyIcon icon="lucide:highlighter" class="size-4" />
      </button>
    </Tooltip>

    <span class="mx-1 h-5 w-px shrink-0 bg-border"></span>

    <!-- Headings -->
    <Tooltip :title="$t('plugin.novusdoc.toolbar.h1')">
      <button class="nd-tbtn" :class="{ '!bg-primary/[0.12] !text-primary': isActive('heading', { level: 1 }) }" @click="editor?.chain().focus().toggleHeading({ level: 1 }).run()">
        <IconifyIcon icon="lucide:heading-1" class="size-4" />
      </button>
    </Tooltip>
    <Tooltip :title="$t('plugin.novusdoc.toolbar.h2')">
      <button class="nd-tbtn" :class="{ '!bg-primary/[0.12] !text-primary': isActive('heading', { level: 2 }) }" @click="editor?.chain().focus().toggleHeading({ level: 2 }).run()">
        <IconifyIcon icon="lucide:heading-2" class="size-4" />
      </button>
    </Tooltip>
    <Tooltip :title="$t('plugin.novusdoc.toolbar.h3')">
      <button class="nd-tbtn" :class="{ '!bg-primary/[0.12] !text-primary': isActive('heading', { level: 3 }) }" @click="editor?.chain().focus().toggleHeading({ level: 3 }).run()">
        <IconifyIcon icon="lucide:heading-3" class="size-4" />
      </button>
    </Tooltip>

    <span class="mx-1 h-5 w-px shrink-0 bg-border"></span>

    <!-- Lists -->
    <Tooltip :title="$t('plugin.novusdoc.toolbar.bulletList')">
      <button class="nd-tbtn" :class="{ '!bg-primary/[0.12] !text-primary': isActive('bulletList') }" @click="editor?.chain().focus().toggleBulletList().run()">
        <IconifyIcon icon="lucide:list" class="size-4" />
      </button>
    </Tooltip>
    <Tooltip :title="$t('plugin.novusdoc.toolbar.orderedList')">
      <button class="nd-tbtn" :class="{ '!bg-primary/[0.12] !text-primary': isActive('orderedList') }" @click="editor?.chain().focus().toggleOrderedList().run()">
        <IconifyIcon icon="lucide:list-ordered" class="size-4" />
      </button>
    </Tooltip>
    <Tooltip :title="$t('plugin.novusdoc.toolbar.taskList')">
      <button class="nd-tbtn" :class="{ '!bg-primary/[0.12] !text-primary': isActive('taskList') }" @click="editor?.chain().focus().toggleTaskList().run()">
        <IconifyIcon icon="lucide:list-checks" class="size-4" />
      </button>
    </Tooltip>

    <span class="mx-1 h-5 w-px shrink-0 bg-border"></span>

    <!-- Block -->
    <Tooltip :title="$t('plugin.novusdoc.toolbar.blockquote')">
      <button class="nd-tbtn" :class="{ '!bg-primary/[0.12] !text-primary': isActive('blockquote') }" @click="editor?.chain().focus().toggleBlockquote().run()">
        <IconifyIcon icon="lucide:quote" class="size-4" />
      </button>
    </Tooltip>
    <Tooltip :title="$t('plugin.novusdoc.toolbar.codeBlock')">
      <button class="nd-tbtn" :class="{ '!bg-primary/[0.12] !text-primary': isActive('codeBlock') }" @click="editor?.chain().focus().toggleCodeBlock().run()">
        <IconifyIcon icon="lucide:file-code" class="size-4" />
      </button>
    </Tooltip>
    <Tooltip :title="$t('plugin.novusdoc.toolbar.horizontalRule')">
      <button class="nd-tbtn" @click="editor?.chain().focus().setHorizontalRule().run()">
        <IconifyIcon icon="lucide:minus" class="size-4" />
      </button>
    </Tooltip>

    <span class="mx-1 h-5 w-px shrink-0 bg-border"></span>

    <!-- Insert -->
    <Tooltip :title="$t('plugin.novusdoc.toolbar.table')">
      <button class="nd-tbtn" @click="editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()">
        <IconifyIcon icon="lucide:table" class="size-4" />
      </button>
    </Tooltip>
  </div>
</template>
