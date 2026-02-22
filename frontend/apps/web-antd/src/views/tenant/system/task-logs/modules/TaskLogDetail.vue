<script lang="ts" setup>
defineOptions({ name: 'TenantTaskLogDetail' });

import type { tenantApi } from '#/api';

import { IconifyIcon } from '@vben/icons';

import {
  Descriptions,
  DescriptionsItem,
  Divider,
  Tag,
} from 'ant-design-vue';

import { getTaskLogDetailApi } from '#/api/tenant/task-log';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import { getQueueColor, getStatusColor } from '../data';

type TaskLogDetailInfo = tenantApi.TaskLogDetailInfo;

const { Drawer, detailData: detail } = useCrudDrawer<TaskLogDetailInfo>({
  detailApi: (id) => getTaskLogDetailApi(id as number),
});
</script>

<template>
  <Drawer
    :title="$t('tenant.system.taskLog.detail')"
    class="w-[600px]"
    :footer="false"
  >
    <template v-if="detail">
      <div class="mb-4">
        <div class="mb-2 flex items-center gap-2 text-base font-medium">
          <IconifyIcon icon="lucide:info" class="text-primary" />
          {{ $t('tenant.system.taskLog.basicInfo') }}
        </div>
        <Descriptions :column="2" bordered size="small">
          <DescriptionsItem :label="$t('tenant.system.taskLog.taskName')" :span="2">
            <code class="break-all rounded bg-accent px-1 py-0.5 text-xs">{{ detail.taskName }}</code>
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.system.taskLog.taskId')" :span="2">
            <code class="break-all rounded bg-accent px-1 py-0.5 text-xs">{{ detail.taskId }}</code>
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.system.taskLog.status.label')">
            <Tag :color="getStatusColor(detail.status)">
              {{ $t(`tenant.system.taskLog.status.${detail.status}`) }}
            </Tag>
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.system.taskLog.queue')">
            <Tag :color="getQueueColor(detail.queue)">
              {{ $t(`tenant.system.taskLog.queueNames.${detail.queue}`, detail.queue) }}
            </Tag>
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.system.taskLog.retryCount')">
            {{ detail.retryCount }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.system.taskLog.durationMs')">
            {{ detail.durationMs !== null ? `${detail.durationMs} ms` : '-' }}
          </DescriptionsItem>
        </Descriptions>
      </div>

      <Divider class="!my-4" />

      <div class="mb-4">
        <div class="mb-2 flex items-center gap-2 text-base font-medium">
          <IconifyIcon icon="lucide:clock" class="text-primary" />
          {{ $t('tenant.system.taskLog.timeInfo') }}
        </div>
        <Descriptions :column="1" bordered size="small">
          <DescriptionsItem :label="$t('tenant.system.taskLog.createdAt')">
            {{ formatDate(detail.createdAt) }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.system.taskLog.startedAt')">
            {{ detail.startedAt ? formatDate(detail.startedAt) : '-' }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('tenant.system.taskLog.finishedAt')">
            {{ detail.finishedAt ? formatDate(detail.finishedAt) : '-' }}
          </DescriptionsItem>
        </Descriptions>
      </div>

      <template v-if="detail.errorMessage || detail.traceback">
        <Divider class="!my-4" />
        <div>
          <div class="mb-2 flex items-center gap-2 text-base font-medium">
            <IconifyIcon icon="lucide:terminal" class="text-primary" />
            {{ $t('tenant.system.taskLog.resultInfo') }}
          </div>
          <Descriptions :column="1" bordered size="small">
            <DescriptionsItem
              v-if="detail.errorMessage"
              :label="$t('tenant.system.taskLog.errorMessage')"
            >
              <span class="text-destructive">{{ detail.errorMessage }}</span>
            </DescriptionsItem>
            <DescriptionsItem
              v-if="detail.traceback"
              :label="$t('tenant.system.taskLog.traceback')"
            >
              <pre class="m-0 max-h-60 overflow-auto whitespace-pre-wrap break-all rounded bg-destructive/5 p-2 text-xs text-destructive">{{ detail.traceback }}</pre>
            </DescriptionsItem>
          </Descriptions>
        </div>
      </template>
    </template>
  </Drawer>
</template>
