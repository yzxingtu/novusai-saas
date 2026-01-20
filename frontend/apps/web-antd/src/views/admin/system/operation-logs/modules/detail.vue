<script lang="ts" setup>
/**
 * 操作日志详情抽屉
 */
import type { adminApi } from '#/api';

import { computed, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Descriptions,
  DescriptionsItem,
  Divider,
  Spin,
  Tag,
} from 'ant-design-vue';

import { getOperationLogDetailApi } from '#/api/admin/operation-log';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import { getMethodColor, getStatusColor } from '../data';

type OperationLogInfo = adminApi.OperationLogInfo;

const loading = ref(false);
const detail = ref<null | OperationLogInfo>(null);

const [Drawer, drawerApi] = useVbenDrawer({
  onOpenChange: async (isOpen) => {
    if (isOpen) {
      const data = drawerApi.getData<{ id: number }>();
      if (data?.id) {
        await loadDetail(data.id);
      }
    } else {
      detail.value = null;
    }
  },
});

async function loadDetail(id: number) {
  loading.value = true;
  try {
    detail.value = await getOperationLogDetailApi(id);
  } catch {
    detail.value = null;
  } finally {
    loading.value = false;
  }
}

/**
 * 响应状态颜色映射
 */
const statusCodeType = computed(() => {
  if (!detail.value) return 'default';
  return getStatusColor(detail.value.statusCode);
});
</script>

<template>
  <Drawer
    :title="$t('admin.system.operationLog.detail')"
    class="w-[600px]"
    :footer="false"
  >
    <Spin :spinning="loading">
      <template v-if="detail">
        <!-- 用户信息 -->
        <div class="mb-4">
          <div class="mb-2 flex items-center gap-2 text-base font-medium">
            <IconifyIcon icon="lucide:user" class="text-primary" />
            {{ $t('admin.system.operationLog.userInfo') }}
          </div>
          <Descriptions :column="2" bordered size="small">
            <DescriptionsItem :label="$t('admin.system.operationLog.username')">
              {{ detail.username || '-' }}
            </DescriptionsItem>
            <DescriptionsItem :label="$t('admin.system.operationLog.userType')">
              <Tag color="cyan">{{ detail.userType }}</Tag>
            </DescriptionsItem>
          </Descriptions>
        </div>

        <Divider class="!my-4" />

        <!-- 请求信息 -->
        <div class="mb-4">
          <div class="mb-2 flex items-center gap-2 text-base font-medium">
            <IconifyIcon icon="lucide:send" class="text-primary" />
            {{ $t('admin.system.operationLog.requestInfo') }}
          </div>
          <Descriptions :column="2" bordered size="small">
            <DescriptionsItem :label="$t('admin.system.operationLog.module')">
              <Tag color="blue">{{ detail.module }}</Tag>
            </DescriptionsItem>
            <DescriptionsItem :label="$t('admin.system.operationLog.action')">
              <Tag color="purple">{{ detail.action }}</Tag>
            </DescriptionsItem>
            <DescriptionsItem :label="$t('admin.system.operationLog.method')">
              <Tag :color="getMethodColor(detail.method)">
                {{ detail.method }}
              </Tag>
            </DescriptionsItem>
            <DescriptionsItem
              :label="$t('admin.system.operationLog.createdAt')"
            >
              {{ formatDate(detail.createdAt) }}
            </DescriptionsItem>
            <DescriptionsItem
              :label="$t('admin.system.operationLog.path')"
              :span="2"
            >
              <code class="break-all rounded bg-gray-100 px-1 py-0.5 text-xs">
                {{ detail.path }}
              </code>
            </DescriptionsItem>
          </Descriptions>
        </div>

        <Divider class="!my-4" />

        <!-- 响应信息 -->
        <div class="mb-4">
          <div class="mb-2 flex items-center gap-2 text-base font-medium">
            <IconifyIcon icon="lucide:reply" class="text-primary" />
            {{ $t('admin.system.operationLog.responseInfo') }}
          </div>
          <Descriptions :column="2" bordered size="small">
            <DescriptionsItem
              :label="$t('admin.system.operationLog.statusCode')"
            >
              <Tag :color="statusCodeType">{{ detail.statusCode }}</Tag>
            </DescriptionsItem>
            <DescriptionsItem
              :label="$t('admin.system.operationLog.responseCode')"
            >
              <Tag :color="detail.responseCode === 0 ? 'success' : 'error'">
                {{ detail.responseCode }}
              </Tag>
            </DescriptionsItem>
            <DescriptionsItem
              :label="$t('admin.system.operationLog.durationMs')"
            >
              <span :class="detail.durationMs > 1000 ? 'text-warning' : ''">
                {{ detail.durationMs }} ms
              </span>
            </DescriptionsItem>
          </Descriptions>
        </div>

        <Divider class="!my-4" />

        <!-- 客户端信息 -->
        <div>
          <div class="mb-2 flex items-center gap-2 text-base font-medium">
            <IconifyIcon icon="lucide:monitor" class="text-primary" />
            {{ $t('admin.system.operationLog.clientInfo') }}
          </div>
          <Descriptions :column="1" bordered size="small">
            <DescriptionsItem :label="$t('admin.system.operationLog.ip')">
              <code class="rounded bg-gray-100 px-1 py-0.5 text-xs">
                {{ detail.ip }}
              </code>
            </DescriptionsItem>
          </Descriptions>
        </div>
      </template>
    </Spin>
  </Drawer>
</template>
