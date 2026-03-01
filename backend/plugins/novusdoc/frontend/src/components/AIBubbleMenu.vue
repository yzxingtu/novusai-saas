<script lang="ts" setup>
/**
 * AI 浮动菜单 — 选中文本时弹出 AI 操作（Tiptap BubbleMenu 风格）
 *
 * 交互方式：
 * - 选中文字 → 浮动工具栏出现在选区上方 → 操作针对选中文字
 * - 未选中文字（光标在文中） → 底部浮动续写按钮 → 操作针对全文
 * - AI 结果以 ghost text 显示 → 采纳/丢弃
 */
import { ref } from 'vue';
import { Button, Tooltip, Dropdown, Menu, Input } from 'ant-design-vue';
import { IconifyIcon, $t } from '@novus/plugin-shared';
import type { Editor } from '@tiptap/core';
import { BubbleMenu } from '@tiptap/vue-3';

const props = defineProps<{
  editor: Editor;
  loading: boolean;
  ghostText: string;
  error: string;
}>();

const emit = defineEmits<{
  action: [feature: string, extra?: Record<string, string>];
  accept: [];
  dismiss: [];
  cancel: [];
}>();

const showCustomInput = ref(false);
const customInstruction = ref('');

const aiActions = [
  { key: 'continue', icon: 'lucide:pen-line', labelKey: 'plugin.novusdoc.ai.continue' },
  { key: 'optimize', icon: 'lucide:wand-2', labelKey: 'plugin.novusdoc.ai.optimize' },
  { key: 'proofread', icon: 'lucide:spell-check', labelKey: 'plugin.novusdoc.ai.proofread' },
  { key: 'expand', icon: 'lucide:expand', labelKey: 'plugin.novusdoc.ai.expand' },
  { key: 'rewrite', icon: 'lucide:refresh-cw', labelKey: 'plugin.novusdoc.ai.rewrite' },
  { key: 'summarize', icon: 'lucide:list', labelKey: 'plugin.novusdoc.ai.summarize' },
];

function handleAction(feature: string) {
  emit('action', feature);
}

function handleTranslate(lang: string) {
  emit('action', 'translate', { target_lang: lang });
}

function handleCustom() {
  if (customInstruction.value.trim()) {
    emit('action', 'custom', { instruction: customInstruction.value.trim() });
    showCustomInput.value = false;
    customInstruction.value = '';
  }
}
</script>

<template>
  <!-- Tiptap BubbleMenu: 选中文字时自动浮动显示 -->
  <BubbleMenu
    :editor="editor"
    :should-show="({ editor: e }) => !e.state.selection.empty"
    :tippy-options="{ duration: 150, placement: 'top', maxWidth: 'none', theme: 'none', arrow: false }"
    class="nd-ai-bubble-menu"
  >
    <!-- AI generating state -->
    <div v-if="loading" class="nd-ai-bm-bar nd-ai-bm-loading">
      <span class="nd-ai-bm-dots">
        <span class="nd-ai-dot"></span>
        <span class="nd-ai-dot"></span>
        <span class="nd-ai-dot"></span>
      </span>
      <span class="nd-ai-bm-text">{{ $t('plugin.novusdoc.ai.generating') }}</span>
      <button class="nd-ai-bm-close" @click="emit('cancel')">
        <IconifyIcon icon="lucide:x" class="size-3" />
      </button>
    </div>

    <!-- Ghost text preview -->
    <div v-else-if="ghostText" class="nd-ai-bm-bar nd-ai-bm-result">
      <div class="nd-ai-bm-preview">{{ ghostText.slice(0, 150) }}{{ ghostText.length > 150 ? '...' : '' }}</div>
      <div class="nd-ai-bm-result-actions">
        <button class="nd-ai-bm-btn nd-ai-bm-accept" @click="emit('accept')">
          <IconifyIcon icon="lucide:check" class="size-3.5" />
          <span>{{ $t('plugin.novusdoc.ai.accept') }}</span>
        </button>
        <button class="nd-ai-bm-btn nd-ai-bm-dismiss" @click="emit('dismiss')">
          <IconifyIcon icon="lucide:x" class="size-3.5" />
          <span>{{ $t('plugin.novusdoc.ai.dismiss') }}</span>
        </button>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="nd-ai-bm-bar nd-ai-bm-error">
      <IconifyIcon icon="lucide:alert-circle" class="size-3.5" />
      <span>{{ error }}</span>
      <button class="nd-ai-bm-close" @click="emit('dismiss')">
        <IconifyIcon icon="lucide:x" class="size-3" />
      </button>
    </div>

    <!-- Row 1: Format buttons (常用格式工具) -->
    <div v-else class="nd-ai-bm-rows">
      <div class="nd-ai-bm-bar">
        <Tooltip :title="$t('plugin.novusdoc.toolbar.bold')" placement="top">
          <button class="nd-ai-bm-icon" :class="{ 'nd-ai-bm-active': editor.isActive('bold') }" @click="editor.chain().focus().toggleBold().run()">
            <IconifyIcon icon="lucide:bold" class="size-3.5" />
          </button>
        </Tooltip>
        <Tooltip :title="$t('plugin.novusdoc.toolbar.italic')" placement="top">
          <button class="nd-ai-bm-icon" :class="{ 'nd-ai-bm-active': editor.isActive('italic') }" @click="editor.chain().focus().toggleItalic().run()">
            <IconifyIcon icon="lucide:italic" class="size-3.5" />
          </button>
        </Tooltip>
        <Tooltip :title="$t('plugin.novusdoc.toolbar.underline')" placement="top">
          <button class="nd-ai-bm-icon" :class="{ 'nd-ai-bm-active': editor.isActive('underline') }" @click="editor.chain().focus().toggleUnderline().run()">
            <IconifyIcon icon="lucide:underline" class="size-3.5" />
          </button>
        </Tooltip>
        <Tooltip :title="$t('plugin.novusdoc.toolbar.strikethrough')" placement="top">
          <button class="nd-ai-bm-icon" :class="{ 'nd-ai-bm-active': editor.isActive('strike') }" @click="editor.chain().focus().toggleStrike().run()">
            <IconifyIcon icon="lucide:strikethrough" class="size-3.5" />
          </button>
        </Tooltip>
        <Tooltip :title="$t('plugin.novusdoc.toolbar.code')" placement="top">
          <button class="nd-ai-bm-icon" :class="{ 'nd-ai-bm-active': editor.isActive('code') }" @click="editor.chain().focus().toggleCode().run()">
            <IconifyIcon icon="lucide:code" class="size-3.5" />
          </button>
        </Tooltip>
        <span class="nd-ai-bm-sep"></span>
        <Tooltip :title="$t('plugin.novusdoc.toolbar.h1')" placement="top">
          <button class="nd-ai-bm-icon" :class="{ 'nd-ai-bm-active': editor.isActive('heading', { level: 1 }) }" @click="editor.chain().focus().toggleHeading({ level: 1 }).run()">
            <span class="text-xs font-bold">H1</span>
          </button>
        </Tooltip>
        <Tooltip :title="$t('plugin.novusdoc.toolbar.h2')" placement="top">
          <button class="nd-ai-bm-icon" :class="{ 'nd-ai-bm-active': editor.isActive('heading', { level: 2 }) }" @click="editor.chain().focus().toggleHeading({ level: 2 }).run()">
            <span class="text-xs font-bold">H2</span>
          </button>
        </Tooltip>
        <Tooltip :title="$t('plugin.novusdoc.toolbar.h3')" placement="top">
          <button class="nd-ai-bm-icon" :class="{ 'nd-ai-bm-active': editor.isActive('heading', { level: 3 }) }" @click="editor.chain().focus().toggleHeading({ level: 3 }).run()">
            <span class="text-xs font-bold">H3</span>
          </button>
        </Tooltip>
      </div>

      <!-- Row 2: AI buttons -->
      <div class="nd-ai-bm-bar">
        <Tooltip v-for="act in aiActions" :key="act.key" :title="$t(act.labelKey)" placement="bottom">
          <button class="nd-ai-bm-icon" @click="handleAction(act.key)">
            <IconifyIcon :icon="act.icon" class="size-3.5" />
          </button>
        </Tooltip>

        <span class="nd-ai-bm-sep"></span>

        <!-- Translate dropdown -->
        <Dropdown :trigger="['click']">
          <template #overlay>
            <Menu>
              <Menu.Item key="en" @click="handleTranslate('English')">English</Menu.Item>
              <Menu.Item key="zh" @click="handleTranslate('中文')">中文</Menu.Item>
              <Menu.Item key="ja" @click="handleTranslate('日本語')">日本語</Menu.Item>
              <Menu.Item key="ko" @click="handleTranslate('한국어')">한국어</Menu.Item>
            </Menu>
          </template>
          <Tooltip :title="$t('plugin.novusdoc.ai.translate')" placement="bottom">
            <button class="nd-ai-bm-icon">
              <IconifyIcon icon="lucide:languages" class="size-3.5" />
            </button>
          </Tooltip>
        </Dropdown>

        <span class="nd-ai-bm-sep"></span>

        <!-- Custom prompt -->
        <Tooltip :title="$t('plugin.novusdoc.ai.custom')" placement="bottom">
          <button class="nd-ai-bm-icon" @click="showCustomInput = !showCustomInput">
            <IconifyIcon icon="lucide:message-square" class="size-3.5" />
          </button>
        </Tooltip>
      </div>
    </div>

    <!-- Custom instruction input -->
    <div v-if="showCustomInput && !loading && !ghostText" class="nd-ai-bm-custom">
      <Input
        v-model:value="customInstruction"
        size="small"
        :placeholder="$t('plugin.novusdoc.ai.customPlaceholder')"
        @pressEnter="handleCustom"
        class="nd-ai-bm-custom-input"
      />
      <button class="nd-ai-bm-btn nd-ai-bm-accept" @click="handleCustom" :disabled="!customInstruction.trim()">
        <IconifyIcon icon="lucide:send" class="size-3" />
      </button>
    </div>
  </BubbleMenu>
</template>

<style scoped>
/* 覆盖 Tippy 默认黑色背景 */
.nd-ai-bubble-menu {
  z-index: 50;
}
:deep(.tippy-box) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
:deep(.tippy-box .tippy-content) {
  padding: 0 !important;
}
:deep(.tippy-arrow) {
  display: none !important;
}

.nd-ai-bm-rows {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nd-ai-bm-bar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 4px 6px;
  border-radius: var(--nd-radius-md, 10px);
  background: hsl(var(--popover));
  border: 1px solid hsl(var(--border));
  box-shadow: var(--nd-shadow-md, 0 4px 16px rgba(0, 0, 0, 0.08));
  color: hsl(var(--popover-foreground));
  font-size: 12px;
  max-width: 480px;
}

.nd-ai-bm-active {
  background: hsl(var(--primary) / 0.15) !important;
  color: hsl(var(--primary)) !important;
}

.nd-ai-bm-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--nd-radius-sm, 6px);
  border: none;
  background: transparent;
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  transition: all var(--nd-transition-fast, 120ms ease);
}
.nd-ai-bm-icon:hover {
  background: hsl(var(--accent));
  color: hsl(var(--accent-foreground));
}

.nd-ai-bm-sep {
  width: 1px;
  height: 16px;
  background: hsl(var(--border));
  margin: 0 2px;
}

.nd-ai-bm-loading {
  gap: 6px;
  padding: 6px 10px;
}

.nd-ai-bm-text {
  font-size: 12px;
  color: hsl(var(--muted-foreground));
}

.nd-ai-bm-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  border: none;
  background: transparent;
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  margin-left: 4px;
}
.nd-ai-bm-close:hover {
  background: hsl(var(--accent));
}

/* Result preview */
.nd-ai-bm-result {
  flex-direction: column;
  gap: 8px;
  padding: 8px 10px;
  max-width: 400px;
}

.nd-ai-bm-preview {
  font-size: 12px;
  line-height: 1.5;
  color: hsl(var(--foreground));
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 120px;
  overflow-y: auto;
}

.nd-ai-bm-result-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}

.nd-ai-bm-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: var(--nd-radius-sm, 6px);
  border: 1px solid hsl(var(--border));
  font-size: 12px;
  cursor: pointer;
  transition: all var(--nd-transition-fast, 120ms ease);
  background: hsl(var(--background));
  color: hsl(var(--foreground));
}
.nd-ai-bm-btn:hover {
  background: hsl(var(--accent));
}

.nd-ai-bm-accept {
  background: hsl(var(--primary));
  color: hsl(var(--primary-foreground));
  border-color: hsl(var(--primary));
}
.nd-ai-bm-accept:hover {
  opacity: 0.9;
}

.nd-ai-bm-dismiss {
  background: transparent;
}

/* Error */
.nd-ai-bm-error {
  gap: 6px;
  padding: 6px 10px;
  color: hsl(var(--destructive));
  font-size: 12px;
}

/* Custom input */
.nd-ai-bm-custom {
  display: flex;
  gap: 6px;
  padding: 4px 6px;
  margin-top: 4px;
}

.nd-ai-bm-custom-input {
  width: 200px;
}

/* Typing dots */
.nd-ai-bm-dots {
  display: flex;
  gap: 3px;
}

.nd-ai-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: hsl(var(--primary));
  animation: nd-bm-typing 1.4s infinite ease-in-out;
}
.nd-ai-dot:nth-child(2) { animation-delay: 0.2s; }
.nd-ai-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes nd-bm-typing {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}
</style>
