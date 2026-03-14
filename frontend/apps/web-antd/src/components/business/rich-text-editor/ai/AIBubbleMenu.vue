<script lang="ts" setup>
import type { Editor } from '@tiptap/core';


import { isTextSelection } from '@tiptap/core';
import { BubbleMenu } from '@tiptap/vue-3/menus';
import { Tooltip } from 'ant-design-vue';
import { IconifyIcon } from '@vben/icons';
import { $t } from '@vben/locales';

const props = defineProps<{
  editor: Editor;
  loading?: boolean;
}>();

const emit = defineEmits<{
  action: [feature: string];
}>();

function shouldShowBubble({ editor, state, from, to }: {
  editor: Editor; state: { selection: unknown }; from: number; to: number;
}): boolean {
  if (from === to) return false;
  if (!isTextSelection(state.selection as never)) return false;
  const text = editor.state.doc.textBetween(from, to, '');
  return text.trim().length > 0;
}

const formatActions = [
  { icon: 'lucide:bold', key: 'bold', cmd: 'toggleBold' },
  { icon: 'lucide:italic', key: 'italic', cmd: 'toggleItalic' },
  { icon: 'lucide:underline', key: 'underline', cmd: 'toggleUnderline' },
  { icon: 'lucide:strikethrough', key: 'strike', cmd: 'toggleStrike' },
  { icon: 'lucide:code', key: 'code', cmd: 'toggleCode' },
];

const aiActions = [
  { icon: 'lucide:pen-line', key: 'continue', labelKey: 'common.aiContinue' },
  { icon: 'lucide:sparkles', key: 'optimize', labelKey: 'common.aiOptimize' },
  { icon: 'lucide:spell-check', key: 'proofread', labelKey: 'common.aiProofread' },
  { icon: 'lucide:expand', key: 'expand', labelKey: 'common.aiExpand' },
  { icon: 'lucide:refresh-cw', key: 'rewrite', labelKey: 'common.aiRewrite' },
  { icon: 'lucide:file-text', key: 'summarize', labelKey: 'common.aiSummarize' },
  { icon: 'lucide:languages', key: 'translate', labelKey: 'common.aiTranslate' },
];

function runFormatCommand(editor: Editor, cmd: string) {
  const chain = editor.chain().focus();
  (chain as unknown as Record<string, () => { run(): void }>)[cmd]?.().run();
}
</script>

<template>
  <BubbleMenu
    :editor="editor"
    :should-show="shouldShowBubble"
    :tippy-options="{ duration: 100, theme: 'none', placement: 'top' }"
  >
    <div
      class="rounded-[10px] border border-border bg-popover p-1 shadow-md"
    >
      <div class="flex items-center gap-0.5">
        <Tooltip v-for="act in formatActions" :key="act.key" :title="$t(`common.${act.key}`)">
          <button
            class="rte-tbtn"
            :class="{ active: editor.isActive(act.key) }"
            @click="runFormatCommand(editor, act.cmd)"
          >
            <IconifyIcon :icon="act.icon" class="size-4" />
          </button>
        </Tooltip>
      </div>

      <div class="mt-1 flex items-center gap-0.5 border-t border-border pt-1">
        <Tooltip v-for="act in aiActions" :key="act.key" :title="$t(act.labelKey)">
          <button
            class="rte-tbtn"
            :disabled="loading"
            @click="emit('action', act.key)"
          >
            <IconifyIcon :icon="act.icon" class="size-4" />
          </button>
        </Tooltip>
      </div>

      <div v-if="loading" class="mt-1 flex items-center gap-1 border-t border-border px-2 pt-1">
        <span class="rte-ai-dot size-1.5 rounded-full bg-primary" />
        <span class="rte-ai-dot size-1.5 rounded-full bg-primary" />
        <span class="rte-ai-dot size-1.5 rounded-full bg-primary" />
        <span class="ml-1 text-xs text-muted-foreground">{{ $t('common.aiProcessing') }}</span>
      </div>
    </div>
  </BubbleMenu>
</template>
