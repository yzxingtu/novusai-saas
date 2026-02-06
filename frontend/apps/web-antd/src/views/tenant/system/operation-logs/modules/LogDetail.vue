<script lang="ts" setup>
defineOptions({ name: 'LogDetail' });
/**
 * 操作日志详情抽屉（租户端）
 */
import type { tenantApi } from '#/api';

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

import { getOperationLogDetailApi } from '#/api/tenant/operation-log';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import { getMethodColor, getStatusColor } from '../data';

type OperationLogInfo = tenantApi.OperationLogInfo;

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
    :title="$t('tenant.system.operationLog.detail')"
    class="w-[600px]"
    :footer="false"
  >
    <Spin :spinning="loading">
      <template v-if="detail">
        <!-- 用户信息 -->
        <div class="mb-4">
          <div class="mb-2 flex items-center gap-2 text-base font-medium">
            <IconifyIcon icon="lucide:user" class="text-primary" />
            {{ $t('tenant.system.operationLog.userInfo') }}
          </div>
          <Descriptions :column="2" bordered size="small">
            <DescriptionsItem
              :label="$t('tenant.system.operationLog.username')"
            >
              {{ detail.username || '-' }}
            </DescriptionsItem>
            <DescriptionsItem
              :label="$t('tenant.system.operationLog.userType')"
            >
              <Tag color="cyan">{{ detail.userType }}</Tag>
            </DescriptionsItem>
          </Descriptions>
        </div>

        <Divider class="!my-4" />

        <!-- 请求信息 -->
        <div class="mb-4">
          <div class="mb-2 flex items-center gap-2 text-base font-medium">
            <IconifyIcon icon="lucide:send" class="text-primary" />
            {{ $t('tenant.system.operationLog.requestInfo') }}
          </div>
          <Descriptions :column="2" bordered size="small">
            <DescriptionsItem :label="$t('tenant.system.operationLog.module')">
              <Tag color="blue">{{ detail.module }}</Tag>
            </DescriptionsItem>
            <DescriptionsItem :label="$t('tenant.system.operationLog.action')">
              <Tag color="purple">{{ detail.action }}</Tag>
            </DescriptionsItem>
            <DescriptionsItem :label="$t('tenant.system.operationLog.method')">
              <Tag :color="getMethodColor(detail.method)">
                {{ detail.method }}
              </Tag>
            </DescriptionsItem>
            <DescriptionsItem
              :label="$t('tenant.system.operationLog.createdAt')"
            >
              {{ formatDate(detail.createdAt) }}
            </DescriptionsItem>
            <DescriptionsItem
              :label="$t('tenant.system.operationLog.path')"
              :span="2"
            >
              <code class="break-all rounded bg-accent px-1 py-0.5 text-xs">
                {{ detail.path }}
              </code>
            </DescriptionsItem>
            <DescriptionsItem
              :label="$t('tenant.system.operationLog.queryParams')"
              :span="2"
            >
              <template v-if="detail.queryParams">
                <pre
                  class="m-0 max-h-40 overflow-auto whitespace-pre-wrap break-all rounded bg-accent p-2 text-xs"
                  >{{ JSON.stringify(detail.queryParams, null, 2) }}</pre
                >
              </template>
              <span v-else class="text-muted-foreground">-</span>
            </DescriptionsItem>
            <DescriptionsItem
              :label="$t('tenant.system.operationLog.requestBody')"
              :span="2"
            >
              <template v-if="detail.requestBody">
                <pre
                  class="m-0 max-h-40 overflow-auto whitespace-pre-wrap break-all rounded bg-accent p-2 text-xs"
                  >{{ JSON.stringify(detail.requestBody, null, 2) }}</pre
                >
              </template>
              <span v-else class="text-muted-foreground">-</span>
            </DescriptionsItem>
          </Descriptions>
        </div>

        <Divider class="!my-4" />

        <!-- 响应信息 -->
        <div class="mb-4">
          <div class="mb-2 flex items-center gap-2 text-base font-medium">
            <IconifyIcon icon="lucide:reply" class="text-primary" />
            {{ $t('tenant.system.operationLog.responseInfo') }}
          </div>
          <Descriptions :column="2" bordered size="small">
            <DescriptionsItem
              :label="$t('tenant.system.operationLog.statusCode')"
            >
              <Tag :color="statusCodeType">{{ detail.statusCode }}</Tag>
            </DescriptionsItem>
            <DescriptionsItem
              :label="$t('tenant.system.operationLog.responseCode')"
            >
              <Tag :color="detail.responseCode === 0 ? 'success' : 'error'">
                {{ detail.responseCode }}
              </Tag>
            </DescriptionsItem>
            <DescriptionsItem
              :label="$t('tenant.system.operationLog.durationMs')"
            >
              <span
                :class="
                  detail.durationMs > 1000 ? 'text-warning' : 'text-foreground'
                "
              >
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
            {{ $t('tenant.system.operationLog.clientInfo') }}
          </div>
          <Descriptions :column="1" bordered size="small">
            <DescriptionsItem :label="$t('tenant.system.operationLog.ip')">
              <code class="rounded bg-accent px-1 py-0.5 text-xs">
                {{ detail.ip }}
              </code>
            </DescriptionsItem>
          </Descriptions>
        </div>
      </template>
    </Spin>
  </Drawer>
</template>
