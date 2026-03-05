<script lang="ts" setup>
/**
 * AI 浮动菜单 — 选中文本时弹出 AI 操作（Tiptap BubbleMenu 风格）
 *
 * 交互方式：
 * - 选中文字 → 浮动工具栏出现在选区上方 → 操作针对选中文字
 * - 未选中文字（光标在文中） → 底部浮动续写按钮 → 操作针对全文
 * - AI 结果以 ghost text 显示 → 采纳/丢弃
 */
import { ref, computed } from 'vue';
import { Button, Tooltip, Dropdown, Menu, Input } from 'ant-design-vue';
import { IconifyIcon, $t } from '@novus/plugin-shared';
import type { Editor } from '@tiptap/core';

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
  <!-- AI 菜单: 选中文字时显示（@tiptap/vue-3@3.x 移除了 BubbleMenu 组件，改用 v-show） -->
  <div
    v-show="props.editor && !props.editor.state.selection.empty"
    class="z-50"
  >
    <!-- AI generating state -->
    <div v-if="loading" class="nd-bm-bar flex items-center gap-1.5 rounded-[10px] border border-border bg-popover px-2.5 py-1.5 text-xs text-popover-foreground shadow-md">
      <span class="flex gap-0.5">
        <span class="nd-ai-dot size-[5px] rounded-full bg-primary"></span>
        <span class="nd-ai-dot size-[5px] rounded-full bg-primary"></span>
        <span class="nd-ai-dot size-[5px] rounded-full bg-primary"></span>
      </span>
      <span class="text-xs text-muted-foreground">{{ $t('plugin.novusdoc.ai.generating') }}</span>
      <button class="ml-1 flex size-5 cursor-pointer items-center justify-center rounded border-none bg-transparent text-muted-foreground hover:bg-accent" @click="emit('cancel')">
        <IconifyIcon icon="lucide:x" class="size-3" />
      </button>
    </div>

    <!-- Ghost text preview -->
    <div v-else-if="ghostText" class="flex max-w-[400px] flex-col gap-2 rounded-[10px] border border-border bg-popover px-2.5 py-2 shadow-md">
      <div class="max-h-[120px] overflow-y-auto whitespace-pre-wrap break-words text-xs leading-normal text-foreground">{{ ghostText.slice(0, 150) }}{{ ghostText.length > 150 ? '...' : '' }}</div>
      <div class="flex justify-end gap-1.5">
        <button class="flex cursor-pointer items-center gap-1 rounded-md border border-primary bg-primary px-2.5 py-1 text-xs text-primary-foreground transition-all hover:opacity-90" @click="emit('accept')">
          <IconifyIcon icon="lucide:check" class="size-3.5" />
          <span>{{ $t('plugin.novusdoc.ai.accept') }}</span>
        </button>
        <button class="flex cursor-pointer items-center gap-1 rounded-md border border-border bg-transparent px-2.5 py-1 text-xs text-foreground transition-all hover:bg-accent" @click="emit('dismiss')">
          <IconifyIcon icon="lucide:x" class="size-3.5" />
          <span>{{ $t('plugin.novusdoc.ai.dismiss') }}</span>
        </button>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="flex items-center gap-1.5 rounded-[10px] border border-border bg-popover px-2.5 py-1.5 text-xs text-destructive shadow-md">
      <IconifyIcon icon="lucide:alert-circle" class="size-3.5" />
      <span>{{ error }}</span>
      <button class="ml-1 flex size-5 cursor-pointer items-center justify-center rounded border-none bg-transparent text-muted-foreground hover:bg-accent" @click="emit('dismiss')">
        <IconifyIcon icon="lucide:x" class="size-3" />
      </button>
    </div>

    <!-- Row 1: Format buttons (常用格式工具) -->
    <div v-else class="flex flex-col gap-1">
      <div class="nd-bm-bar flex items-center gap-0.5 rounded-[10px] border border-border bg-popover px-1.5 py-1 text-xs text-popover-foreground shadow-md max-w-[480px]">
        <Tooltip :title="$t('plugin.novusdoc.toolbar.bold')" placement="top">
          <button class="nd-bm-icon flex size-7 cursor-pointer items-center justify-center rounded-md border-none bg-transparent text-muted-foreground transition-all hover:bg-accent hover:text-accent-foreground" :class="{ '!bg-primary/15 !text-primary': props.editor.isActive('bold') }" @click="props.editor.chain().focus().toggleBold().run()">
            <IconifyIcon icon="lucide:bold" class="size-3.5" />
          </button>
        </Tooltip>
        <Tooltip :title="$t('plugin.novusdoc.toolbar.italic')" placement="top">
          <button class="nd-bm-icon flex size-7 cursor-pointer items-center justify-center rounded-md border-none bg-transparent text-muted-foreground transition-all hover:bg-accent hover:text-accent-foreground" :class="{ '!bg-primary/15 !text-primary': props.editor.isActive('italic') }" @click="props.editor.chain().focus().toggleItalic().run()">
            <IconifyIcon icon="lucide:italic" class="size-3.5" />
          </button>
        </Tooltip>
        <Tooltip :title="$t('plugin.novusdoc.toolbar.underline')" placement="top">
          <button class="nd-bm-icon flex size-7 cursor-pointer items-center justify-center rounded-md border-none bg-transparent text-muted-foreground transition-all hover:bg-accent hover:text-accent-foreground" :class="{ '!bg-primary/15 !text-primary': props.editor.isActive('underline') }" @click="props.editor.chain().focus().toggleUnderline().run()">
            <IconifyIcon icon="lucide:underline" class="size-3.5" />
          </button>
        </Tooltip>
        <Tooltip :title="$t('plugin.novusdoc.toolbar.strikethrough')" placement="top">
          <button class="nd-bm-icon flex size-7 cursor-pointer items-center justify-center rounded-md border-none bg-transparent text-muted-foreground transition-all hover:bg-accent hover:text-accent-foreground" :class="{ '!bg-primary/15 !text-primary': props.editor.isActive('strike') }" @click="props.editor.chain().focus().toggleStrike().run()">
            <IconifyIcon icon="lucide:strikethrough" class="size-3.5" />
          </button>
        </Tooltip>
        <Tooltip :title="$t('plugin.novusdoc.toolbar.code')" placement="top">
          <button class="nd-bm-icon flex size-7 cursor-pointer items-center justify-center rounded-md border-none bg-transparent text-muted-foreground transition-all hover:bg-accent hover:text-accent-foreground" :class="{ '!bg-primary/15 !text-primary': props.editor.isActive('code') }" @click="props.editor.chain().focus().toggleCode().run()">
            <IconifyIcon icon="lucide:code" class="size-3.5" />
          </button>
        </Tooltip>
        <span class="mx-0.5 h-4 w-px bg-border"></span>
        <Tooltip :title="$t('plugin.novusdoc.toolbar.h1')" placement="top">
          <button class="nd-bm-icon flex size-7 cursor-pointer items-center justify-center rounded-md border-none bg-transparent text-muted-foreground transition-all hover:bg-accent hover:text-accent-foreground" :class="{ '!bg-primary/15 !text-primary': props.editor.isActive('heading', { level: 1 }) }" @click="props.editor.chain().focus().toggleHeading({ level: 1 }).run()">
            <span class="text-xs font-bold">H1</span>
          </button>
        </Tooltip>
        <Tooltip :title="$t('plugin.novusdoc.toolbar.h2')" placement="top">
          <button class="nd-bm-icon flex size-7 cursor-pointer items-center justify-center rounded-md border-none bg-transparent text-muted-foreground transition-all hover:bg-accent hover:text-accent-foreground" :class="{ '!bg-primary/15 !text-primary': props.editor.isActive('heading', { level: 2 }) }" @click="props.editor.chain().focus().toggleHeading({ level: 2 }).run()">
            <span class="text-xs font-bold">H2</span>
          </button>
        </Tooltip>
        <Tooltip :title="$t('plugin.novusdoc.toolbar.h3')" placement="top">
          <button class="nd-bm-icon flex size-7 cursor-pointer items-center justify-center rounded-md border-none bg-transparent text-muted-foreground transition-all hover:bg-accent hover:text-accent-foreground" :class="{ '!bg-primary/15 !text-primary': props.editor.isActive('heading', { level: 3 }) }" @click="props.editor.chain().focus().toggleHeading({ level: 3 }).run()">
            <span class="text-xs font-bold">H3</span>
          </button>
        </Tooltip>
      </div>

      <!-- Row 2: AI buttons -->
      <div class="nd-bm-bar flex items-center gap-0.5 rounded-[10px] border border-border bg-popover px-1.5 py-1 text-xs text-popover-foreground shadow-md max-w-[480px]">
        <Tooltip v-for="act in aiActions" :key="act.key" :title="$t(act.labelKey)" placement="bottom">
          <button class="nd-bm-icon flex size-7 cursor-pointer items-center justify-center rounded-md border-none bg-transparent text-muted-foreground transition-all hover:bg-accent hover:text-accent-foreground" @click="handleAction(act.key)">
            <IconifyIcon :icon="act.icon" class="size-3.5" />
          </button>
        </Tooltip>

        <span class="mx-0.5 h-4 w-px bg-border"></span>

        <!-- Translate dropdown -->
        <Dropdown :trigger="['click']">
          <template #overlay>
            <Menu>
              <Menu.Item key="en" @click="handleTranslate('English')">
                {{ $t('plugin.novusdoc.ai.lang.english') }}
              </Menu.Item>
              <Menu.Item key="zh" @click="handleTranslate('Chinese')">
                {{ $t('plugin.novusdoc.ai.lang.chinese') }}
              </Menu.Item>
              <Menu.Item key="ja" @click="handleTranslate('Japanese')">
                {{ $t('plugin.novusdoc.ai.lang.japanese') }}
              </Menu.Item>
              <Menu.Item key="ko" @click="handleTranslate('Korean')">
                {{ $t('plugin.novusdoc.ai.lang.korean') }}
              </Menu.Item>
            </Menu>
          </template>
          <Tooltip :title="$t('plugin.novusdoc.ai.translate')" placement="bottom">
            <button class="nd-bm-icon flex size-7 cursor-pointer items-center justify-center rounded-md border-none bg-transparent text-muted-foreground transition-all hover:bg-accent hover:text-accent-foreground">
              <IconifyIcon icon="lucide:languages" class="size-3.5" />
            </button>
          </Tooltip>
        </Dropdown>

        <span class="mx-0.5 h-4 w-px bg-border"></span>

        <!-- Custom prompt -->
        <Tooltip :title="$t('plugin.novusdoc.ai.custom')" placement="bottom">
          <button class="nd-bm-icon flex size-7 cursor-pointer items-center justify-center rounded-md border-none bg-transparent text-muted-foreground transition-all hover:bg-accent hover:text-accent-foreground" @click="showCustomInput = !showCustomInput">
            <IconifyIcon icon="lucide:message-square" class="size-3.5" />
          </button>
        </Tooltip>
      </div>
    </div>

    <!-- Custom instruction input -->
    <div v-if="showCustomInput && !loading && !ghostText" class="mt-1 flex gap-1.5 px-1.5 py-1">
      <Input
        v-model:value="customInstruction"
        size="small"
        :placeholder="$t('plugin.novusdoc.ai.customPlaceholder')"
        @pressEnter="handleCustom"
        class="w-[200px]"
      />
      <button class="flex cursor-pointer items-center gap-1 rounded-md border border-primary bg-primary px-2.5 py-1 text-xs text-primary-foreground transition-all hover:opacity-90" @click="handleCustom" :disabled="!customInstruction.trim()">
        <IconifyIcon icon="lucide:send" class="size-3" />
      </button>
    </div>
  </div>
</template>
