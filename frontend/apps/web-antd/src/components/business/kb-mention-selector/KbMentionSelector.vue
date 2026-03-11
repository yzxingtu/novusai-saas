<script lang="ts" setup>
/**
 * Knowledge Base @ Mention Selector (Auxiliary Feature)
 * 知识库 @ 提及选择器（辅助功能）
 *
 * Displays selected KB tags in chat input area, click @ button to show selectable KB list.
 * 在对话输入区域显示已选知识库标签，点击 @ 按钮弹出可选知识库列表。
 * Shares between admin and tenant endpoints by passing different API functions via props.fetchApi.
 * 通过 props.fetchApi 传入不同的 API 函数，管理端和租户端共用。
 *
 * Note: Primary KB binding has migrated to Agent-level junction table (AgentKnowledgeBaseBinding),
 * this component serves as an auxiliary feature, allowing users to temporarily attach extra KBs.
 * 注意：主要 KB 绑定已迁移至 Agent 级别中间表（AgentKnowledgeBaseBinding），
 * 此组件仅作为辅助功能，允许用户临时附加额外知识库。
 */
import { ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Popover, Spin, Tag } from 'ant-design-vue';

import { $t } from '#/locales';
import { getScopeColor, getScopeText } from '#/utils/scope-helpers';

defineOptions({ name: 'KbMentionSelector' });

const props = defineProps<{
  fetchApi: () => Promise<unknown[]>;
}>();

export interface KBItem {
  id: number;
  name: string;
  scope: string;
  description: null | string;
}

const selectedKBs = defineModel<number[]>('selectedIds', { default: () => [] });

const kbList = ref<KBItem[]>([]);
const loading = ref(false);
const popoverVisible = ref(false);

async function loadKBList() {
  loading.value = true;
  try {
    kbList.value = (await props.fetchApi()) as KBItem[];
  } catch {
    kbList.value = [];
  } finally {
    loading.value = false;
  }
}

function toggleKB(id: number) {
  const idx = selectedKBs.value.indexOf(id);
  selectedKBs.value =
    idx === -1
      ? [...selectedKBs.value, id]
      : selectedKBs.value.filter((v) => v !== id);
}

function removeKB(id: number) {
  selectedKBs.value = selectedKBs.value.filter((v) => v !== id);
}

function getKBName(id: number): string {
  return kbList.value.find((kb) => kb.id === id)?.name ?? `KB#${id}`;
}

function onPopoverOpen(visible: boolean) {
  if (visible) loadKBList();
}
</script>

<template>
  <div class="flex flex-wrap items-center gap-1.5">
    <!-- Selected KB tags / 已选知识库标签 -->
    <Tag
      v-for="kbId in selectedKBs"
      :key="kbId"
      closable
      color="processing"
      class="m-0"
      @close="removeKB(kbId)"
    >
      <IconifyIcon icon="lucide:book-open" class="mr-0.5 inline size-3" />
      {{ getKBName(kbId) }}
    </Tag>

    <!-- @ button / @ 按钮 -->
    <Popover
      v-model:open="popoverVisible"
      trigger="click"
      placement="topLeft"
      :arrow="false"
      @open-change="onPopoverOpen"
    >
      <template #content>
        <div class="w-64">
          <div class="mb-2 text-xs font-medium text-muted-foreground">
            {{ $t('shared.kbMention.title') }}
          </div>
          <Spin v-if="loading" size="small" class="flex justify-center py-4" />
          <div
            v-else-if="kbList.length === 0"
            class="py-3 text-center text-xs text-muted-foreground"
          >
            {{ $t('shared.kbMention.empty') }}
          </div>
          <div v-else class="max-h-48 space-y-1 overflow-y-auto">
            <div
              v-for="kb in kbList"
              :key="kb.id"
              class="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-accent"
              :class="selectedKBs.includes(kb.id) ? 'bg-primary/10' : ''"
              @click="toggleKB(kb.id)"
            >
              <IconifyIcon
                :icon="
                  selectedKBs.includes(kb.id)
                    ? 'lucide:check-square'
                    : 'lucide:square'
                "
                class="size-4 shrink-0"
                :class="
                  selectedKBs.includes(kb.id)
                    ? 'text-primary'
                    : 'text-muted-foreground'
                "
              />
              <div class="min-w-0 flex-1">
                <div class="truncate text-foreground">{{ kb.name }}</div>
                <div
                  v-if="kb.description"
                  class="truncate text-xs text-muted-foreground"
                >
                  {{ kb.description }}
                </div>
              </div>
              <Tag :color="getScopeColor(kb.scope)" class="m-0 text-xs">
                {{ getScopeText(kb.scope) }}
              </Tag>
            </div>
          </div>
        </div>
      </template>

      <div
        class="flex size-7 cursor-pointer items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        :title="$t('shared.kbMention.title')"
      >
        <IconifyIcon icon="lucide:at-sign" class="size-4" />
      </div>
    </Popover>
  </div>
</template>
