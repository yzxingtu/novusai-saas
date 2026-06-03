<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Dropdown,
  Empty,
  Menu,
  MenuItem,
  Pagination,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

export interface KnowledgeBaseCardAction {
  danger?: boolean;
  icon: string;
  key: string;
  label: string;
}

export interface KnowledgeBaseCardViewModel {
  createdAtText: string;
  createdAtTitle: string;
  description?: null | string;
  documentCount: number;
  embeddingModelName?: null | string;
  id: number;
  menuActions: KnowledgeBaseCardAction[];
  name: string;
  scopeColor?: string;
  scopeText?: null | string;
  statusColor: string;
  statusText: string;
  secondaryAction?: KnowledgeBaseCardAction;
  totalChunks: number;
  totalSizeText: string;
}

interface Props {
  cardClickable?: boolean;
  createLabel?: string;
  currentPage?: number;
  detailActionLabel?: string;
  emptyDescription: string;
  loading: boolean;
  pageSize?: number;
  recycleBinCount?: number;
  recycleBinTitle?: string;
  showCreate?: boolean;
  showRecycleBin?: boolean;
  statTitles?: {
    chunks: string;
    documents: string;
    size: string;
  };
  total?: number;
  value: KnowledgeBaseCardViewModel[];
}

withDefaults(defineProps<Props>(), {
  cardClickable: false,
  createLabel: '',
  currentPage: 1,
  detailActionLabel: '',
  pageSize: 12,
  recycleBinCount: 0,
  recycleBinTitle: '',
  showCreate: false,
  showRecycleBin: false,
  statTitles: () => ({
    chunks: '',
    documents: '',
    size: '',
  }),
  total: 0,
});

const emit = defineEmits<{
  create: [];
  menuAction: [actionKey: string, itemId: number];
  openRecycleBin: [];
  pageChange: [page: number];
  select: [itemId: number];
}>();

function onMenuClick(actionKey: number | string, itemId: number) {
  emit('menuAction', String(actionKey), itemId);
}

function onSelect(itemId: number) {
  emit('select', itemId);
}
</script>

<template>
  <Spin :spinning="loading">
    <div
      v-if="value.length === 0 && !loading"
      class="flex min-h-[300px] items-center justify-center"
    >
      <Empty :description="emptyDescription">
        <Button v-if="showCreate" type="primary" @click="emit('create')">
          <template #icon>
            <IconifyIcon icon="lucide:plus" class="size-4" />
          </template>
          {{ createLabel }}
        </Button>
      </Empty>
    </div>
    <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      <div
        v-for="item in value"
        :key="item.id"
        class="group rounded-xl border border-border/60 bg-card transition-all hover:border-primary/30 hover:shadow-md"
        :class="cardClickable ? 'cursor-pointer' : ''"
        @click="cardClickable && onSelect(item.id)"
      >
        <div class="flex items-start gap-3 p-4 pb-2">
          <div
            class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10"
          >
            <IconifyIcon icon="lucide:book-open" class="size-5 text-primary" />
          </div>
          <div class="min-w-0 flex-1">
            <h4
              class="cursor-pointer truncate text-sm font-semibold text-foreground hover:text-primary"
              @click="onSelect(item.id)"
            >
              {{ item.name }}
            </h4>
            <div class="mt-1 flex flex-wrap items-center gap-1.5">
              <Tag
                :color="item.statusColor"
                class="!mr-0 !text-[10px] !leading-4"
                style="padding: 0 5px"
              >
                {{ item.statusText }}
              </Tag>
              <Tag
                v-if="item.scopeText"
                :color="item.scopeColor || 'default'"
                class="!mr-0 !text-[10px] !leading-4"
                style="padding: 0 5px"
              >
                {{ item.scopeText }}
              </Tag>
            </div>
          </div>
          <Dropdown
            :trigger="['click']"
            placement="bottomRight"
            class="shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
          >
            <button
              class="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              @click.stop
            >
              <IconifyIcon icon="lucide:more-vertical" class="size-4" />
            </button>
            <template #overlay>
              <Menu
                @click="
                  (info: { key: string | number }) =>
                    onMenuClick(info.key, item.id)
                "
              >
                <MenuItem
                  v-for="action in item.menuActions"
                  :key="action.key"
                  :class="action.danger ? '!text-destructive' : ''"
                >
                  <div class="flex items-center gap-2">
                    <IconifyIcon :icon="action.icon" class="size-4" />
                    <span>{{ action.label }}</span>
                  </div>
                </MenuItem>
              </Menu>
            </template>
          </Dropdown>
        </div>

        <p
          v-if="item.description"
          class="mx-4 mb-2 line-clamp-2 text-xs leading-relaxed text-muted-foreground"
        >
          {{ item.description }}
        </p>
        <p v-else class="mx-4 mb-2 text-xs italic text-muted-foreground/50">
          —
        </p>

        <div
          v-if="item.embeddingModelName"
          class="mx-4 mb-3 flex items-center gap-1.5"
        >
          <div
            class="flex items-center gap-1.5 rounded-md bg-accent px-2 py-1 text-[11px] text-muted-foreground"
          >
            <IconifyIcon icon="lucide:cpu" class="size-3" />
            <span class="truncate">{{ item.embeddingModelName }}</span>
          </div>
        </div>

        <div
          class="flex items-center justify-between border-t border-border/50 px-4 py-3 text-[11px] text-muted-foreground"
        >
          <div class="flex items-center gap-3">
            <Tooltip :title="statTitles.documents">
              <span class="flex items-center gap-1">
                <IconifyIcon icon="lucide:file-text" class="size-3.5" />
                <span class="tabular-nums">{{ item.documentCount }}</span>
              </span>
            </Tooltip>
            <Tooltip :title="statTitles.chunks">
              <span class="flex items-center gap-1">
                <IconifyIcon icon="lucide:puzzle" class="size-3.5" />
                <span class="tabular-nums">{{ item.totalChunks }}</span>
              </span>
            </Tooltip>
            <Tooltip :title="statTitles.size">
              <span class="flex items-center gap-1">
                <IconifyIcon icon="lucide:hard-drive" class="size-3.5" />
                <span>{{ item.totalSizeText }}</span>
              </span>
            </Tooltip>
            <Tooltip :title="item.createdAtTitle">
              <span class="flex items-center gap-1">
                <IconifyIcon icon="lucide:clock" class="size-3.5" />
                <span>{{ item.createdAtText }}</span>
              </span>
            </Tooltip>
          </div>
          <div class="flex items-center gap-2">
            <button
              class="flex items-center gap-1 rounded-md px-2 py-1 text-primary transition-colors hover:bg-primary/10"
              @click.stop="onSelect(item.id)"
            >
              <IconifyIcon icon="lucide:eye" class="size-3" />
              <span v-if="detailActionLabel">{{ detailActionLabel }}</span>
            </button>
            <button
              v-if="item.secondaryAction"
              class="flex items-center gap-1 rounded-md px-2 py-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              @click.stop="onMenuClick(item.secondaryAction.key, item.id)"
            >
              <IconifyIcon :icon="item.secondaryAction.icon" class="size-3" />
              <span>{{ item.secondaryAction.label }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="(total || 0) > (pageSize || 12)" class="mt-4 flex justify-end">
      <Pagination
        :current="currentPage"
        :total="total"
        :page-size="pageSize"
        size="small"
        :show-size-changer="false"
        @change="(page) => emit('pageChange', page)"
      />
    </div>
    <div v-if="showRecycleBin" class="mt-3 flex items-center justify-end">
      <Tooltip :title="recycleBinTitle">
        <Badge :count="recycleBinCount" :offset="[-2, 2]" size="small">
          <Button @click="emit('openRecycleBin')">
            <template #icon>
              <IconifyIcon icon="lucide:trash-2" class="size-4" />
            </template>
          </Button>
        </Badge>
      </Tooltip>
    </div>
  </Spin>
</template>
