<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';

import { $t } from '#/locales';

import {
  Popover,
  Button,
  Tag,
  Spin,
  Empty,
  Tooltip,
} from 'ant-design-vue';

import type { CrudRecordInfo } from '#/api/admin/crud-records';

import { getCrudRecordListApi } from '#/api/admin/crud-records';

import type { CrudConfig } from '../types';

const T = 'admin.dev.crudGenerator.records';
const HT = 'admin.dev.crudGenerator.history';

const emit = defineEmits<{
  restoreConfig: [config: CrudConfig];
}>();

const router = useRouter();
const open = ref(false);
const loading = ref(false);
const recentRecords = ref<CrudRecordInfo[]>([]);

function getTypeColor(type: string): string {
  const map: Record<string, string> = {
    preview: 'blue',
    generate: 'green',
    rollback: 'orange',
    delete: 'red',
  };
  return map[type] || 'default';
}

function getStatusColor(status: string): string {
  const map: Record<string, string> = {
    success: 'success',
    partial_failure: 'warning',
    failed: 'error',
    rolled_back: 'default',
  };
  return map[status] || 'default';
}

function getTypeLabel(type: string): string {
  return $t(`${T}.type.${type}`) || type;
}

function getStatusLabel(status: string): string {
  const map: Record<string, string> = {
    success: 'success',
    partial_failure: 'partialFailure',
    failed: 'failed',
    rolled_back: 'rolledBack',
  };
  return $t(`${T}.status.${map[status] || status}`) || status;
}

function formatTimeAgo(time: string | null): string {
  if (!time) return '-';
  const diff = Date.now() - new Date(time).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return $t(`${HT}.justNow`);
  if (minutes < 60) return $t(`${HT}.minutesAgo`, { n: minutes });
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return $t(`${HT}.hoursAgo`, { n: hours });
  const days = Math.floor(hours / 24);
  return $t(`${HT}.daysAgo`, { n: days });
}

async function fetchRecent() {
  loading.value = true;
  try {
    const res = await getCrudRecordListApi({
      'page[number]': 1,
      'page[size]': 10,
      'sort': '-created_at',
    });
    recentRecords.value = res.items || [];
  } catch {
    // ignore
  } finally {
    loading.value = false;
  }
}

function handleOpenChange(vis: boolean) {
  open.value = vis;
  if (vis) {
    fetchRecent();
  }
}

async function handleRestore(record: CrudRecordInfo) {
  try {
    const { getCrudRecordConfigApi } = await import('#/api/admin/crud-records');
    const res = await getCrudRecordConfigApi<CrudConfig>(record.id);
    if (res) {
      emit('restoreConfig', res);
      open.value = false;
    }
  } catch {
    // ignore
  }
}

function goToFullList() {
  open.value = false;
  router.push({ name: 'AdminDevCrudRecords' });
}

onMounted(() => {
  fetchRecent();
});
</script>

<template>
  <Popover
    v-model:open="open"
    trigger="click"
    placement="bottomRight"
    overlay-class-name="history-popover"
    @open-change="handleOpenChange"
  >
    <template #content>
      <div class="w-[380px]">
        <div class="mb-2 flex items-center justify-between">
          <span class="text-sm font-medium">{{ $t(`${HT}.title`) }}</span>
          <Button type="link" size="small" @click="fetchRecent">
            <span class="icon-[lucide--refresh-cw] mr-1 size-3" />
            {{ $t(`${HT}.refresh`) }}
          </Button>
        </div>

        <Spin :spinning="loading">
          <div v-if="recentRecords.length === 0 && !loading" class="py-4">
            <Empty :description="$t(`${HT}.noRecords`)" />
          </div>
          <div v-else class="max-h-[400px] space-y-1 overflow-y-auto">
            <div
              v-for="record in recentRecords"
              :key="record.id"
              class="hover:bg-accent/50 flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 transition-colors"
              @click="handleRestore(record)"
            >
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-1.5">
                  <Tag :color="getTypeColor(record.operation_type)" class="!m-0 !text-xs">
                    {{ getTypeLabel(record.operation_type) }}
                  </Tag>
                  <span class="truncate font-mono text-xs">
                    {{ record.module_name || record.table_name || '-' }}
                  </span>
                  <Tag :color="getStatusColor(record.status)" class="!m-0 !text-xs">
                    {{ getStatusLabel(record.status) }}
                  </Tag>
                </div>
                <div class="text-muted-foreground mt-0.5 flex items-center gap-2 text-xs">
                  <span>{{ record.operator_name || '-' }}</span>
                  <span>·</span>
                  <span>{{ record.file_count }} {{ $t(`${HT}.files`) }}</span>
                  <span>·</span>
                  <span>{{ formatTimeAgo(record.created_at) }}</span>
                </div>
              </div>
              <Tooltip :title="$t(`${T}.action.restoreConfig`)">
                <span class="icon-[lucide--undo-2] text-muted-foreground size-3.5 shrink-0" />
              </Tooltip>
            </div>
          </div>
        </Spin>

        <div class="mt-2 border-t pt-2">
          <Button type="link" size="small" block @click="goToFullList">
            {{ $t(`${HT}.viewAll`) }}
            <span class="icon-[lucide--arrow-right] ml-1 size-3" />
          </Button>
        </div>
      </div>
    </template>

    <Tooltip :title="$t(`${HT}.title`)">
      <Button size="small" type="text">
        <template #icon>
          <span class="icon-[lucide--history] size-4" />
        </template>
      </Button>
    </Tooltip>
  </Popover>
</template>
