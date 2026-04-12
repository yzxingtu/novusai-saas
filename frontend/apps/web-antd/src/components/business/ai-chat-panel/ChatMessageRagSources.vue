<script lang="ts" setup>
import type { ChatMessage, RagSource } from './types';

import { computed, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';
import { Modal } from 'ant-design-vue';

import { formatKnowledgeBaseName } from '#/components/business/ai-chat-panel/display-formatters';
import { $t } from '#/locales';

const props = withDefaults(
  defineProps<{
    compact?: boolean;
    msg: ChatMessage;
  }>(),
  {
    compact: false,
  },
);

const ragDetailOpen = ref(false);
const ragDetailItem = ref<null | RagSource>(null);
function openRagDetail(s: RagSource) {
  ragDetailItem.value = s;
  ragDetailOpen.value = true;
}

/** Group RAG hits by knowledge base for display / 按知识库分组展示引用 */
const ragGroups = computed(() => {
  const list = props.msg.ragSources ?? [];
  const groups = new Map<string, { items: RagSource[]; label: string }>();
  for (const s of list) {
    const label = formatKnowledgeBaseName(
      s.knowledge_base_name,
      s.knowledge_base_id,
    );
    const key = String(s.knowledge_base_id ?? label);
    if (!groups.has(key)) {
      groups.set(key, { label, items: [] });
    }
    groups.get(key)!.items.push(s);
  }
  return [...groups.values()];
});
</script>

<template>
  <!-- RAG sources -->
  <div v-if="msg.ragSources && msg.ragSources.length > 0 && !msg.streaming" :class="compact ? 'mt-1' : 'mt-1.5'">
    <details class="group">
      <summary
        class="flex cursor-pointer items-center text-muted-foreground hover:text-foreground"
        :class="compact ? 'gap-1 text-[11px]' : 'gap-1.5 text-xs'"
      >
        <IconifyIcon icon="lucide:book-open" :class="compact ? 'size-3' : 'size-3.5'" />
        <span
          >{{ $t('common.globalAiChat.ragSources') }} ({{ msg.ragSources.length }})</span
        >
      </summary>
      <div :class="compact ? 'mt-1 space-y-2 pl-4' : 'mt-1.5 space-y-2.5 pl-5'">
        <div
          v-for="(grp, gi) in ragGroups"
          :key="gi"
          class="rounded-md border border-border/30 bg-accent/40"
          :class="compact ? 'p-1.5' : 'p-2'"
        >
          <div
            class="mb-1 flex items-center gap-1 font-medium text-primary/80"
            :class="compact ? 'text-[10px]' : 'text-xs'"
          >
            <IconifyIcon icon="lucide:library" class="size-3 shrink-0" />
            {{ grp.label }}
          </div>
          <button
            v-for="(src, si) in grp.items"
            :key="si"
            type="button"
            class="block w-full rounded-md bg-accent/50 text-left text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            :class="compact ? 'mb-1 px-2 py-1 text-[11px]' : 'mb-1 px-2.5 py-1.5 text-xs'"
            @click="openRagDetail(src)"
          >
            <div class="font-medium text-foreground">{{ src.doc_name }}</div>
            <div :class="compact ? 'mt-0.5 line-clamp-2' : 'mt-0.5 line-clamp-2'">
              {{ src.snippet }}
            </div>
            <div class="mt-0.5 text-[10px] text-primary/70">
              {{ $t('common.globalAiChat.ragClickForDetail') }}
            </div>
          </button>
        </div>
      </div>
    </details>
  </div>

  <Modal
    v-model:open="ragDetailOpen"
    :title="$t('common.globalAiChat.ragSourceDetailTitle')"
    :footer="null"
    :width="compact ? '90vw' : 560"
    destroy-on-close
  >
    <div v-if="ragDetailItem" class="space-y-2 text-sm">
      <div v-if="ragDetailItem.knowledge_base_name || ragDetailItem.knowledge_base_id != null">
        <span class="text-muted-foreground">{{ $t('common.globalAiChat.ragKbLabel') }}:</span>
        {{
          formatKnowledgeBaseName(
            ragDetailItem.knowledge_base_name,
            ragDetailItem.knowledge_base_id,
          )
        }}
      </div>
      <div>
        <span class="text-muted-foreground">{{ $t('common.globalAiChat.ragDocLabel') }}:</span>
        {{ ragDetailItem.doc_name }}
      </div>
      <div
        v-if="ragDetailItem.page != null || ragDetailItem.heading"
        class="text-xs text-muted-foreground"
      >
        <template v-if="ragDetailItem.page != null">
          {{
            $t('common.globalAiChat.ragPageLabel', {
              page: ragDetailItem.page,
            })
          }}
        </template>
        <template v-if="ragDetailItem.heading">· {{ ragDetailItem.heading }}</template>
      </div>
      <div class="whitespace-pre-wrap rounded-md bg-muted/50 p-3 text-foreground">
        {{ ragDetailItem.snippet }}
      </div>
    </div>
  </Modal>
</template>
