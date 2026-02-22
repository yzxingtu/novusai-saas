<script setup lang="ts">
/**
 * Mention 建议列表组件
 *
 * 输入 @ 触发搜索，显示用户列表浮窗
 * 支持键盘上下导航 + Enter 确认
 * 由 TipTap Mention extension suggestion 调用
 */
import { ref, watch } from 'vue';

export interface MentionItem {
  id: number;
  label: string;
  avatar?: string;
}

const props = defineProps<{
  items: MentionItem[];
  command: (item: { id: number; label: string }) => void;
}>();

const selectedIndex = ref(0);

watch(
  () => props.items,
  () => {
    selectedIndex.value = 0;
  },
);

function selectItem(index: number) {
  const item = props.items[index];
  if (item) {
    props.command({ id: item.id, label: item.label });
  }
}

function onKeyDown(event: KeyboardEvent): boolean {
  if (event.key === 'ArrowUp') {
    selectedIndex.value =
      (selectedIndex.value + props.items.length - 1) % props.items.length;
    return true;
  }
  if (event.key === 'ArrowDown') {
    selectedIndex.value = (selectedIndex.value + 1) % props.items.length;
    return true;
  }
  if (event.key === 'Enter') {
    selectItem(selectedIndex.value);
    return true;
  }
  return false;
}

defineExpose({ onKeyDown });
</script>

<template>
  <div
    v-if="items.length > 0"
    class="mention-list bg-card border-border rounded-xl border shadow-lg"
  >
    <button
      v-for="(item, index) in items"
      :key="item.id"
      class="mention-item"
      :class="{ active: index === selectedIndex }"
      @click="selectItem(index)"
      @mouseenter="selectedIndex = index"
    >
      <span
        v-if="item.avatar"
        class="mention-avatar"
        :style="{ backgroundImage: `url(${item.avatar})` }"
      />
      <span v-else class="mention-avatar-placeholder">
        {{ item.label.charAt(0).toUpperCase() }}
      </span>
      <span class="text-foreground text-sm">{{ item.label }}</span>
    </button>
  </div>
  <div v-else class="mention-list bg-card border-border rounded-xl border p-3 shadow-lg">
    <span class="text-muted-foreground text-xs">{{ $t('common.noData') }}</span>
  </div>
</template>

<style scoped>
.mention-list {
  padding: 0.25rem;
  min-width: 180px;
  max-height: 240px;
  overflow-y: auto;
}

.mention-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.375rem 0.5rem;
  border: none;
  background: transparent;
  border-radius: 0.375rem;
  cursor: pointer;
  transition: background 150ms ease-out;
}

.mention-item:hover,
.mention-item.active {
  background: hsl(var(--accent));
}

.mention-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background-size: cover;
  background-position: center;
  flex-shrink: 0;
}

.mention-avatar-placeholder {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: hsl(var(--primary) / 0.1);
  color: hsl(var(--primary));
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 600;
  flex-shrink: 0;
}
</style>
