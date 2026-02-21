<script lang="ts" setup>
/**
 * 通知面板组件
 *
 * 在顶栏铃铛 Popover 中展示，支持分类 Tab 筛选、已读/未读、全部已读。
 */
defineOptions({ name: 'NotificationPanel' });

import type { NotificationItem } from '#/store/shared/notification';

import { computed, onMounted, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Badge, Button, Empty, Spin, Tabs } from 'ant-design-vue';

import { $t } from '#/locales';
import { useNotificationStore } from '#/store';
import { formatRelativeTime } from '#/utils/common';

const notifStore = useNotificationStore();

const activeTab = ref('all');

const CATEGORY_TABS = [
  { key: 'all', icon: 'lucide:bell' },
  { key: 'system', icon: 'lucide:monitor' },
  { key: 'ai', icon: 'lucide:sparkles' },
  { key: 'task', icon: 'lucide:list-checks' },
  { key: 'biz', icon: 'lucide:briefcase' },
  { key: 'audit', icon: 'lucide:shield' },
];

/** 按分类筛选的通知列表 */
const filteredNotifications = computed(() => {
  if (activeTab.value === 'all') {
    return notifStore.notifications;
  }
  return notifStore.notifications.filter(
    (n) => n.category === activeTab.value,
  );
});

/** 分类图标映射 */
function getCategoryIcon(category: string): string {
  const map: Record<string, string> = {
    system: 'lucide:monitor',
    ai: 'lucide:sparkles',
    task: 'lucide:list-checks',
    biz: 'lucide:briefcase',
    audit: 'lucide:shield',
  };
  return map[category] || 'lucide:bell';
}

/** 分类颜色映射 */
function getCategoryColor(category: string): string {
  const map: Record<string, string> = {
    system: 'text-blue-500',
    ai: 'text-purple-500',
    task: 'text-green-500',
    biz: 'text-orange-500',
    audit: 'text-red-500',
  };
  return map[category] || 'text-muted-foreground';
}

function handleMarkRead(item: NotificationItem) {
  if (!item.is_read) {
    notifStore.markRead(item.id);
  }
}

function handleMarkAllRead() {
  const category = activeTab.value === 'all' ? undefined : activeTab.value;
  notifStore.markAllRead(category);
}

function handleDelete(item: NotificationItem) {
  notifStore.deleteNotification(item.id);
}

// Tab 切换时加载
watch(activeTab, () => {
  const category = activeTab.value === 'all' ? undefined : activeTab.value;
  notifStore.loadNotifications(category);
});

onMounted(() => {
  notifStore.loadNotifications();
  notifStore.initSocketHandlers();
});
</script>

<template>
  <div class="w-[360px]">
    <!-- Tab 导航 -->
    <Tabs
      v-model:activeKey="activeTab"
      size="small"
      class="notification-tabs"
    >
      <Tabs.TabPane
        v-for="tab in CATEGORY_TABS"
        :key="tab.key"
        :tab="$t(`common.notification.category.${tab.key}`)"
      />
    </Tabs>

    <!-- 通知列表 -->
    <Spin :spinning="notifStore.loading">
      <div class="max-h-[400px] overflow-y-auto">
        <Empty
          v-if="filteredNotifications.length === 0"
          :description="$t('common.notification.empty')"
          class="py-8"
        />
        <div v-else class="divide-y divide-border/50">
          <div
            v-for="item in filteredNotifications"
            :key="item.id"
            class="flex cursor-pointer gap-3 px-4 py-3 transition-colors hover:bg-accent/30"
            :class="{ 'bg-primary/5': !item.is_read }"
            @click="handleMarkRead(item)"
          >
            <!-- 分类图标 -->
            <div class="flex-shrink-0 pt-0.5">
              <IconifyIcon
                :icon="getCategoryIcon(item.category)"
                class="size-4"
                :class="getCategoryColor(item.category)"
              />
            </div>
            <!-- 内容 -->
            <div class="min-w-0 flex-1">
              <div class="flex items-start justify-between gap-2">
                <span
                  class="text-sm"
                  :class="item.is_read ? 'text-muted-foreground' : 'font-medium text-foreground'"
                >
                  {{ item.title }}
                </span>
                <!-- 未读圆点 -->
                <Badge v-if="!item.is_read" status="processing" />
              </div>
              <p
                v-if="item.body"
                class="mt-0.5 line-clamp-2 text-xs text-muted-foreground"
              >
                {{ item.body }}
              </p>
              <span class="mt-1 text-[11px] text-muted-foreground/60">
                {{ item.created_at ? formatRelativeTime(item.created_at) : '' }}
              </span>
            </div>
            <!-- 删除 -->
            <button
              class="flex-shrink-0 self-start opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
              @click.stop="handleDelete(item)"
            >
              <IconifyIcon icon="lucide:x" class="size-3" />
            </button>
          </div>
        </div>
      </div>
    </Spin>

    <!-- 底部操作 -->
    <div class="flex items-center justify-between border-t border-border/50 px-4 py-2">
      <Button type="link" size="small" @click="handleMarkAllRead">
        {{ $t('common.notification.markAllRead') }}
      </Button>
    </div>
  </div>
</template>

<style scoped>
.notification-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 0;
  padding: 0 16px;
}
</style>
