<script lang="ts" setup>
/**
 * 斜杠命令浮动菜单（Phase A 最小可用版）
 *
 * 在编辑器中输入 "/" 时弹出命令菜单，选择后插入对应块。
 * 当前为静态命令列表，Phase B 会扩展 AI 命令。
 */
import { ref, computed, watch } from 'vue';
import { IconifyIcon, $t } from '@novus/plugin-shared';
import type { Editor } from '@tiptap/core';

const props = defineProps<{
  editor: Editor | undefined;
  visible: boolean;
  position: { top: number; left: number };
}>();

const emit = defineEmits<{
  close: [];
}>();

const filterText = ref('');
const selectedIndex = ref(0);

interface CommandItem {
  id: string;
  icon: string;
  label: string;
  action: () => void;
}

const commands = computed<CommandItem[]>(() => {
  if (!props.editor) return [];
  const ed = props.editor;
  const all: CommandItem[] = [
    { id: 'h1', icon: 'lucide:heading-1', label: $t('plugin.novusdoc.slash.heading1'), action: () => ed.chain().focus().toggleHeading({ level: 1 }).run() },
    { id: 'h2', icon: 'lucide:heading-2', label: $t('plugin.novusdoc.slash.heading2'), action: () => ed.chain().focus().toggleHeading({ level: 2 }).run() },
    { id: 'h3', icon: 'lucide:heading-3', label: $t('plugin.novusdoc.slash.heading3'), action: () => ed.chain().focus().toggleHeading({ level: 3 }).run() },
    { id: 'bullet', icon: 'lucide:list', label: $t('plugin.novusdoc.slash.bulletList'), action: () => ed.chain().focus().toggleBulletList().run() },
    { id: 'ordered', icon: 'lucide:list-ordered', label: $t('plugin.novusdoc.slash.orderedList'), action: () => ed.chain().focus().toggleOrderedList().run() },
    { id: 'task', icon: 'lucide:list-checks', label: $t('plugin.novusdoc.slash.taskList'), action: () => ed.chain().focus().toggleTaskList().run() },
    { id: 'quote', icon: 'lucide:quote', label: $t('plugin.novusdoc.slash.blockquote'), action: () => ed.chain().focus().toggleBlockquote().run() },
    { id: 'code', icon: 'lucide:file-code', label: $t('plugin.novusdoc.slash.codeBlock'), action: () => ed.chain().focus().toggleCodeBlock().run() },
    { id: 'hr', icon: 'lucide:minus', label: $t('plugin.novusdoc.slash.divider'), action: () => ed.chain().focus().setHorizontalRule().run() },
    { id: 'table', icon: 'lucide:table', label: $t('plugin.novusdoc.slash.table'), action: () => ed.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run() },
  ];

  if (!filterText.value) return all;
  const q = filterText.value.toLowerCase();
  return all.filter(c => c.label.toLowerCase().includes(q) || c.id.includes(q));
});

function selectCommand(cmd: CommandItem) {
  cmd.action();
  emit('close');
}

function handleKeydown(e: KeyboardEvent) {
  if (!props.visible) return;
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    selectedIndex.value = Math.min(selectedIndex.value + 1, commands.value.length - 1);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    selectedIndex.value = Math.max(selectedIndex.value - 1, 0);
  } else if (e.key === 'Enter') {
    e.preventDefault();
    const cmd = commands.value[selectedIndex.value];
    if (cmd) selectCommand(cmd);
  } else if (e.key === 'Escape') {
    emit('close');
  }
}

watch(() => props.visible, (v) => {
  if (v) {
    filterText.value = '';
    selectedIndex.value = 0;
  }
});
</script>

<template>
  <div
    v-if="visible && commands.length > 0"
    class="fixed z-[9000] min-w-[180px] rounded-lg border border-border bg-popover p-1 shadow-lg"
    :style="{ top: `${position.top}px`, left: `${position.left}px` }"
    @keydown="handleKeydown"
  >
    <div
      v-for="(cmd, idx) in commands"
      :key="cmd.id"
      class="flex cursor-pointer items-center gap-2 rounded-md px-3 py-1.5 text-[13px] text-popover-foreground transition-colors hover:bg-accent"
      :class="{ 'bg-primary/10 text-primary': idx === selectedIndex }"
      @click="selectCommand(cmd)"
      @mouseenter="selectedIndex = idx"
    >
      <IconifyIcon :icon="cmd.icon" class="size-4 text-muted-foreground" />
      <span>{{ cmd.label }}</span>
    </div>
  </div>
</template>
