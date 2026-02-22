<script setup lang="ts">
/**
 * 文档卡片组件
 *
 * 显示文档标题、预览摘要、最后编辑时间、字数统计、状态标签
 * 悬停时 scale(1.01) + shadow-md 微动画
 */
import { computed } from 'vue';

import { Dropdown, Menu, Tag } from 'ant-design-vue';

import { $t } from '#/locales';

interface DocumentItem {
  id: number;
  title: string;
  content_html?: string;
  status: string;
  word_count: number;
  updated_at: string;
  owner_id: number;
  is_pinned?: boolean;
  is_starred?: boolean;
}

const props = defineProps<{
  document: DocumentItem;
}>();

const emit = defineEmits<{
  edit: [doc: DocumentItem];
  delete: [doc: DocumentItem];
}>();

const statusColor = computed(() => {
  const map: Record<string, string> = {
    draft: 'default',
    published: 'success',
    archived: 'warning',
  };
  return map[props.document.status] || 'default';
});

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    draft: $t('tenant.richEditor.status.draft'),
    published: $t('tenant.richEditor.status.published'),
    archived: $t('tenant.richEditor.status.archived'),
  };
  return map[props.document.status] || props.document.status;
});

const preview = computed(() => {
  if (!props.document.content_html) return '';
  const text = props.document.content_html.replace(/<[^>]*>/g, '');
  return text.slice(0, 120);
});

const formattedDate = computed(() => {
  if (!props.document.updated_at) return '';
  const d = new Date(props.document.updated_at);
  return d.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
});

function handleMenuClick(key: string) {
  if (key === 'edit') {
    emit('edit', props.document);
  } else if (key === 'delete') {
    emit('delete', props.document);
  }
}
</script>

<template>
  <div
    class="document-card bg-card hover:shadow-md border-border group cursor-pointer rounded-xl border p-4 transition-all duration-150 ease-out hover:scale-[1.01]"
    @click="emit('edit', document)"
  >
    <!-- 头部：标题 + 状态 -->
    <div class="mb-2 flex items-start justify-between">
      <h3 class="text-foreground line-clamp-1 flex-1 text-sm font-medium">
        {{ document.title || $t('tenant.richEditor.untitled') }}
      </h3>
      <div class="ml-2 flex items-center gap-1">
        <span
          v-if="document.is_pinned"
          class="icon-[lucide--pin] text-muted-foreground h-3.5 w-3.5"
        />
        <Tag :color="statusColor" class="!m-0 !text-xs">
          {{ statusLabel }}
        </Tag>
      </div>
    </div>

    <!-- 预览摘要 -->
    <p class="text-muted-foreground mb-3 line-clamp-2 text-xs leading-relaxed">
      {{ preview || $t('tenant.richEditor.noContent') }}
    </p>

    <!-- 底部：元信息 + 操作 -->
    <div class="text-muted-foreground flex items-center justify-between text-xs">
      <div class="flex items-center gap-3">
        <span class="flex items-center gap-1">
          <span class="icon-[lucide--calendar] h-3 w-3" />
          {{ formattedDate }}
        </span>
        <span class="flex items-center gap-1">
          <span class="icon-[lucide--type] h-3 w-3" />
          {{ document.word_count }}
        </span>
      </div>
      <Dropdown
        :trigger="['click']"
        placement="bottomRight"
        @click.stop
      >
        <span
          class="hover:bg-accent invisible rounded p-1 group-hover:visible"
          @click.stop
        >
          <span class="icon-[lucide--more-horizontal] h-4 w-4" />
        </span>
        <template #overlay>
          <Menu @click="({ key }) => handleMenuClick(String(key))">
            <Menu.Item key="edit">
              <span class="flex items-center gap-2">
                <span class="icon-[lucide--pencil] h-4 w-4" />
                {{ $t('common.edit') }}
              </span>
            </Menu.Item>
            <Menu.Item key="delete" class="!text-destructive">
              <span class="flex items-center gap-2">
                <span class="icon-[lucide--trash-2] h-4 w-4" />
                {{ $t('common.delete') }}
              </span>
            </Menu.Item>
          </Menu>
        </template>
      </Dropdown>
    </div>
  </div>
</template>

<style scoped>
.document-card {
  min-height: 120px;
}
</style>
