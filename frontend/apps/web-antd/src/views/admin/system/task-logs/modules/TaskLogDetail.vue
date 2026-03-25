<script lang="ts" setup>
/**
 * 任务日志详情抽屉
 */
import type { adminApi } from '#/api';

import { IconifyIcon } from '@vben/icons';

import { Descriptions, DescriptionsItem, Divider, Tag } from 'ant-design-vue';

import { getTaskLogDetailApi } from '#/api/admin/task-log';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import {
  getBindingContextText,
  getEffectiveContextText,
  getOwnerContextText,
  getQueueColor,
  getRunKindText,
  getStatusColor,
  getTriggerSourceText,
} from '../data';

defineOptions({ name: 'TaskLogDetail' });

type TaskLogDetailInfo = adminApi.TaskLogDetailInfo;

const { Drawer, detailData: detail } = useCrudDrawer<TaskLogDetailInfo>({
  detailApi: (id) => getTaskLogDetailApi(id as number),
});
</script>

<template>
  <Drawer
    :title="$t('admin.system.taskLog.detail')"
    class="w-[720px]"
    :footer="false"
  >
    <template v-if="detail">
      <div class="mb-4 rounded-2xl border border-border/70 bg-card p-4">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="text-lg font-semibold text-foreground">
              {{ detail.taskName }}
            </div>
            <div class="mt-1 break-all text-xs text-muted-foreground">
              {{ detail.handlerPath || detail.taskId }}
            </div>
          </div>
          <div class="flex flex-wrap gap-2">
            <Tag :color="getStatusColor(detail.status)">
              {{ $t(`admin.system.taskLog.status.${detail.status}`) }}
            </Tag>
            <Tag v-if="detail.runKind" color="blue">
              {{ getRunKindText(detail.runKind) }}
            </Tag>
            <Tag v-if="detail.triggerSource" color="cyan">
              {{ getTriggerSourceText(detail.triggerSource) }}
            </Tag>
          </div>
        </div>
      </div>

      <div class="mb-4">
        <div class="mb-2 flex items-center gap-2 text-base font-medium">
          <IconifyIcon icon="lucide:info" class="text-primary" />
          {{ $t('admin.system.taskLog.basicInfo') }}
        </div>
        <Descriptions :column="2" bordered size="small">
          <DescriptionsItem
            :label="$t('admin.system.taskLog.taskName')"
            :span="2"
          >
            <code class="break-all rounded bg-accent px-1 py-0.5 text-xs">
              {{ detail.taskName }}
            </code>
          </DescriptionsItem>
          <DescriptionsItem
            v-if="detail.handlerPath"
            :label="$t('admin.system.taskLog.handlerPath')"
            :span="2"
          >
            <code class="break-all rounded bg-accent px-1 py-0.5 text-xs">
              {{ detail.handlerPath }}
            </code>
          </DescriptionsItem>
          <DescriptionsItem
            :label="$t('admin.system.taskLog.taskId')"
            :span="2"
          >
            <code class="break-all rounded bg-accent px-1 py-0.5 text-xs">
              {{ detail.taskId }}
            </code>
          </DescriptionsItem>
          <DescriptionsItem :label="$t('admin.system.taskLog.queue')">
            <Tag :color="getQueueColor(detail.queue)">
              {{
                $t(
                  `admin.system.taskLog.queueNames.${detail.queue}`,
                  detail.queue,
                )
              }}
            </Tag>
          </DescriptionsItem>
          <DescriptionsItem :label="$t('admin.system.taskLog.retryCount')">
            {{ detail.retryCount }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('admin.system.taskLog.durationMs')">
            <span
              :class="
                detail.durationMs && detail.durationMs > 5000
                  ? 'font-medium text-warning'
                  : 'text-foreground'
              "
            >
              {{ detail.durationMs !== null ? `${detail.durationMs} ms` : '-' }}
            </span>
          </DescriptionsItem>
        </Descriptions>
      </div>

      <Divider class="!my-4" />

      <div class="mb-4">
        <div class="mb-2 flex items-center gap-2 text-base font-medium">
          <IconifyIcon icon="lucide:link-2" class="text-primary" />
          {{ $t('admin.system.taskLog.relationInfo') }}
        </div>
        <Descriptions :column="2" bordered size="small">
          <DescriptionsItem :label="$t('admin.system.taskLog.taskDefinitionId')">
            {{ detail.taskDefinitionId ?? '-' }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('admin.system.taskLog.bindingId')">
            {{ getBindingContextText(detail.bindingId) }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('admin.system.taskLog.ownerTenantId')">
            {{ getOwnerContextText(detail.ownerTenantId) }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('admin.system.taskLog.effectiveTenantId')">
            {{ getEffectiveContextText(detail.effectiveTenantId) }}
          </DescriptionsItem>
        </Descriptions>
      </div>

      <Divider class="!my-4" />

      <!-- 时间信息 -->
      <div class="mb-4">
        <div class="mb-2 flex items-center gap-2 text-base font-medium">
          <IconifyIcon icon="lucide:clock" class="text-primary" />
          {{ $t('admin.system.taskLog.timeInfo') }}
        </div>
        <Descriptions :column="1" bordered size="small">
          <DescriptionsItem :label="$t('admin.system.taskLog.createdAt')">
            {{ formatDate(detail.createdAt) }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('admin.system.taskLog.startedAt')">
            {{ detail.startedAt ? formatDate(detail.startedAt) : '-' }}
          </DescriptionsItem>
          <DescriptionsItem :label="$t('admin.system.taskLog.finishedAt')">
            {{ detail.finishedAt ? formatDate(detail.finishedAt) : '-' }}
          </DescriptionsItem>
          <DescriptionsItem
            v-if="detail.traceId"
            :label="$t('admin.system.taskLog.traceId')"
          >
            <code class="break-all rounded bg-accent px-1 py-0.5 text-xs">
              {{ detail.traceId }}
            </code>
          </DescriptionsItem>
        </Descriptions>
      </div>

      <!-- 参数信息 -->
      <div v-if="detail.args || detail.kwargs" class="mb-4">
        <Divider class="!my-4" />
        <div class="mb-2 flex items-center gap-2 text-base font-medium">
          <IconifyIcon icon="lucide:braces" class="text-primary" />
          {{ $t('admin.system.taskLog.paramsInfo') }}
        </div>
        <Descriptions :column="1" bordered size="small">
          <DescriptionsItem :label="$t('admin.system.taskLog.args')">
            <template v-if="detail.args">
              <pre
                class="m-0 max-h-40 overflow-auto whitespace-pre-wrap break-all rounded bg-accent p-2 text-xs"
                >{{ JSON.stringify(detail.args, null, 2) }}</pre
              >
            </template>
            <span v-else class="text-muted-foreground">-</span>
          </DescriptionsItem>
          <DescriptionsItem :label="$t('admin.system.taskLog.kwargs')">
            <template v-if="detail.kwargs">
              <pre
                class="m-0 max-h-40 overflow-auto whitespace-pre-wrap break-all rounded bg-accent p-2 text-xs"
                >{{ JSON.stringify(detail.kwargs, null, 2) }}</pre
              >
            </template>
            <span v-else class="text-muted-foreground">-</span>
          </DescriptionsItem>
        </Descriptions>
      </div>

      <!-- 执行结果 -->
      <template v-if="detail.result || detail.errorMessage || detail.traceback">
        <Divider class="!my-4" />
        <div>
          <div class="mb-2 flex items-center gap-2 text-base font-medium">
            <IconifyIcon icon="lucide:terminal" class="text-primary" />
            {{ $t('admin.system.taskLog.resultInfo') }}
          </div>
          <Descriptions :column="1" bordered size="small">
            <DescriptionsItem
              v-if="detail.result"
              :label="$t('admin.system.taskLog.result')"
            >
              <pre
                class="m-0 max-h-40 overflow-auto whitespace-pre-wrap break-all rounded bg-accent p-2 text-xs"
                >{{ JSON.stringify(detail.result, null, 2) }}</pre
              >
            </DescriptionsItem>
            <DescriptionsItem
              v-if="detail.errorMessage"
              :label="$t('admin.system.taskLog.errorMessage')"
            >
              <span class="text-destructive">{{ detail.errorMessage }}</span>
            </DescriptionsItem>
            <DescriptionsItem
              v-if="detail.traceback"
              :label="$t('admin.system.taskLog.traceback')"
            >
              <pre
                class="m-0 max-h-60 overflow-auto whitespace-pre-wrap break-all rounded bg-destructive/5 p-2 text-xs text-destructive"
                >{{ detail.traceback }}</pre
              >
            </DescriptionsItem>
          </Descriptions>
        </div>
      </template>
    </template>
  </Drawer>
</template>
