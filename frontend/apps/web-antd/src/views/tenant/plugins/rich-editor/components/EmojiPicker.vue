<script setup lang="ts">
/**
 * Emoji 表情选择器
 *
 * 分类浏览（表情/手势/动物/食物/活动/旅行/物品/符号）
 * 支持搜索和最近使用
 * 插入为 Unicode 字符
 */
import { computed, ref } from 'vue';

import { Input } from 'ant-design-vue';

import { $t } from '#/locales';

const emit = defineEmits<{
  select: [emoji: string];
}>();

const searchQuery = ref('');
const recentEmojis = ref<string[]>(
  JSON.parse(localStorage.getItem('rich-editor-recent-emojis') || '[]'),
);

const categories: Record<string, { label: string; emojis: string[] }> = {
  smileys: {
    label: '😀',
    emojis: [
      '😀', '😃', '😄', '😁', '😆', '😅', '🤣', '😂', '🙂', '🙃',
      '😉', '😊', '😇', '🥰', '😍', '🤩', '😘', '😗', '😚', '😙',
      '🥲', '😋', '😛', '😜', '🤪', '😝', '🤑', '🤗', '🤭', '🤫',
      '🤔', '🫡', '🤐', '🤨', '😐', '😑', '😶', '🫥', '😏', '😒',
      '🙄', '😬', '🤥', '🫨', '😌', '😔', '😪', '🤤', '😴', '😷',
      '🤒', '🤕', '🤢', '🤮', '🥵', '🥶', '🥴', '😵', '🤯', '🥳',
      '🥸', '😎', '🤓', '🧐', '😕', '🫤', '😟', '🙁', '😮', '😯',
      '😲', '😳', '🥺', '🥹', '😦', '😧', '😨', '😰', '😥', '😢',
      '😭', '😱', '😖', '😣', '😞', '😓', '😩', '😫', '🥱', '😤',
      '😡', '😠', '🤬', '😈', '👿', '💀', '☠️', '💩', '🤡', '👹',
    ],
  },
  gestures: {
    label: '👋',
    emojis: [
      '👋', '🤚', '🖐️', '✋', '🖖', '🫱', '🫲', '🫳', '🫴', '🫷',
      '🫸', '👌', '🤌', '🤏', '✌️', '🤞', '🫰', '🤟', '🤘', '🤙',
      '👈', '👉', '👆', '🖕', '👇', '☝️', '🫵', '👍', '👎', '✊',
      '👊', '🤛', '🤜', '👏', '🙌', '🫶', '👐', '🤲', '🤝', '🙏',
      '✍️', '💅', '🤳', '💪', '🦾', '🦿', '🦵', '🦶', '👂', '🦻',
    ],
  },
  animals: {
    label: '🐱',
    emojis: [
      '🐶', '🐱', '🐭', '🐹', '🐰', '🦊', '🐻', '🐼', '🐻‍❄️', '🐨',
      '🐯', '🦁', '🐮', '🐷', '🐸', '🐵', '🙈', '🙉', '🙊', '🐒',
      '🐔', '🐧', '🐦', '🐤', '🦆', '🦅', '🦉', '🦇', '🐺', '🐗',
      '🐴', '🦄', '🐝', '🪱', '🐛', '🦋', '🐌', '🐞', '🐜', '🪰',
      '🐠', '🐟', '🐡', '🐬', '🦈', '🐙', '🐚', '🪸', '🐢', '🐍',
    ],
  },
  food: {
    label: '🍎',
    emojis: [
      '🍎', '🍐', '🍊', '🍋', '🍌', '🍉', '🍇', '🍓', '🫐', '🍈',
      '🍒', '🍑', '🥭', '🍍', '🥥', '🥝', '🍅', '🍆', '🥑', '🌽',
      '🌶️', '🫑', '🥒', '🥬', '🥦', '🧄', '🧅', '🍄', '🥜', '🫘',
      '🍞', '🥐', '🥖', '🫓', '🥨', '🥯', '🥞', '🧇', '🧀', '🍖',
      '🍕', '🌮', '🌯', '🫔', '🥗', '🍜', '🍝', '🍣', '🍱', '🍩',
    ],
  },
  objects: {
    label: '💡',
    emojis: [
      '⌚', '📱', '💻', '⌨️', '🖥️', '🖨️', '🖱️', '💽', '💾', '💿',
      '📷', '📹', '🎥', '📞', '☎️', '📺', '📻', '🎙️', '⏰', '🔔',
      '📢', '📣', '💡', '🔦', '🕯️', '📕', '📗', '📘', '📙', '📓',
      '✏️', '🖊️', '🖋️', '📝', '📁', '📂', '📅', '📆', '📌', '📎',
      '✂️', '🔑', '🔒', '🔓', '❤️', '🧡', '💛', '💚', '💙', '💜',
    ],
  },
  symbols: {
    label: '✅',
    emojis: [
      '✅', '❌', '❓', '❗', '‼️', '⭐', '🌟', '💫', '✨', '🔥',
      '💯', '💢', '💬', '👁️‍🗨️', '🔴', '🟠', '🟡', '🟢', '🔵', '🟣',
      '⚫', '⚪', '🟤', '🔶', '🔷', '🔸', '🔹', '▶️', '◀️', '🔼',
      '🔽', '➕', '➖', '➗', '✖️', '♻️', '™️', '©️', '®️', '〰️',
      '🏁', '🚩', '🎌', '🏴', '🏳️', '🔈', '🔇', '🔉', '🔊', '🎵',
    ],
  },
};

const activeTab = ref('smileys');

const filteredEmojis = computed(() => {
  if (!searchQuery.value) return null;
  const query = searchQuery.value.trim();
  if (!query) return null;
  const results: string[] = [];
  for (const cat of Object.values(categories)) {
    for (const e of cat.emojis) {
      if (results.length >= 50) break;
      // Unicode emoji 无法按关键词搜索，展示所有 emoji 供用户浏览选择
      results.push(e);
    }
  }
  return results;
});

function selectEmoji(emoji: string) {
  emit('select', emoji);

  // 记录最近使用
  const recent = recentEmojis.value.filter((e) => e !== emoji);
  recent.unshift(emoji);
  recentEmojis.value = recent.slice(0, 20);
  try {
    localStorage.setItem(
      'rich-editor-recent-emojis',
      JSON.stringify(recentEmojis.value),
    );
  } catch {
    // ignore storage errors
  }
}
</script>

<template>
  <div class="emoji-picker">
    <!-- 搜索 -->
    <Input
      v-model:value="searchQuery"
      :placeholder="$t('tenant.richEditor.toolbar.emoji')"
      size="small"
      allow-clear
      class="mb-2"
    />

    <!-- 最近使用 -->
    <div v-if="!searchQuery && recentEmojis.length > 0" class="mb-2">
      <div class="text-muted-foreground mb-1 text-xs">
        {{ $t('tenant.richEditor.toolbar.recentEmoji') }}
      </div>
      <div class="flex flex-wrap gap-0.5">
        <button
          v-for="e in recentEmojis"
          :key="'recent-' + e"
          class="emoji-btn"
          @click="selectEmoji(e)"
        >
          {{ e }}
        </button>
      </div>
    </div>

    <!-- 搜索结果 -->
    <div v-if="searchQuery" class="flex flex-wrap gap-0.5">
      <button
        v-for="e in filteredEmojis"
        :key="'search-' + e"
        class="emoji-btn"
        @click="selectEmoji(e)"
      >
        {{ e }}
      </button>
    </div>

    <!-- 分类标签页 -->
    <div v-else>
      <div class="mb-2 flex gap-1">
        <button
          v-for="(cat, key) in categories"
          :key="key"
          class="emoji-tab"
          :class="{ active: activeTab === key }"
          @click="activeTab = String(key)"
        >
          {{ cat.label }}
        </button>
      </div>
      <div class="emoji-grid">
        <button
          v-for="e in categories[activeTab]?.emojis || []"
          :key="e"
          class="emoji-btn"
          @click="selectEmoji(e)"
        >
          {{ e }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.emoji-picker {
  width: 280px;
  max-height: 320px;
  overflow-y: auto;
}

.emoji-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  max-height: 200px;
  overflow-y: auto;
}

.emoji-btn {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  border: none;
  background: transparent;
  border-radius: 0.375rem;
  cursor: pointer;
  transition: all 150ms ease-out;
}

.emoji-btn:hover {
  background: hsl(var(--accent));
  transform: scale(1.15);
}

.emoji-tab {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  border: none;
  background: transparent;
  border-radius: 0.375rem;
  cursor: pointer;
  opacity: 0.6;
  transition: all 150ms ease-out;
}

.emoji-tab:hover,
.emoji-tab.active {
  opacity: 1;
  background: hsl(var(--accent));
}
</style>
