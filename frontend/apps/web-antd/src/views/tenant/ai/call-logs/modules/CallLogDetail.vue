<script lang="ts" setup>
defineOptions({ name: 'TenantCallLogDetail' });
/**
 * 调用日志详情抽屉
 */
import type { TenantAICallLogInfo } from '#/api/tenant/ai';

import { ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Descriptions, Drawer, Spin, Tag } from 'ant-design-vue';

import { getTenantAICallLogDetailApi } from '#/api/tenant/ai';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import { formatCost, getStatusText } from '../data';

const props = defineProps<{
  logId: null | number;
  open: boolean;
}>();

const emits = defineEmits<{ 'update:open': [value: boolean] }>();

const loading = ref(false);
const detail = ref<TenantAICallLogInfo | null>(null);

watch(
  () => props.logId,
  async (id) => {
    if (id) {
      loading.value = true;
      try {
        detail.value = await getTenantAICallLogDetailApi(id);
      } catch {
        detail.value = null;
      } finally {
        loading.value = false;
      }
    }
  },
);

function onClose() {
  emits('update:open', false);
}

function formatJson(data: unknown): string {
  if (!data) return '-';
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}
</script>

<template>
  <Drawer
    :open="open"
    :title="$t('tenant.ai.callLog.detailTitle')"
    width="650"
    @close="onClose"
  >
    <Spin :spinning="loading">
      <template v-if="detail">
        <Descriptions bordered :column="2" size="small">
          <Descriptions.Item :label="$t('tenant.ai.callLog.modelName')" :span="1">
            {{ detail.model_name || '-' }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('tenant.ai.callLog.providerName')" :span="1">
            {{ detail.provider_name || '-' }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('tenant.ai.callLog.status')" :span="1">
            <Tag
              :color="detail.status === 'success' ? 'success' : detail.status === 'failed' ? 'error' : 'warning'"
            >
              {{ getStatusText(detail.status) }}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item :label="$t('tenant.ai.callLog.createdAt')" :span="1">
            {{ formatDate(detail.created_at) }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('tenant.ai.callLog.inputTokens')" :span="1">
            {{ detail.input_tokens }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('tenant.ai.callLog.outputTokens')" :span="1">
            {{ detail.output_tokens }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('tenant.ai.callLog.totalTokens')" :span="1">
            {{ detail.total_tokens }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('tenant.ai.callLog.cost')" :span="1">
            {{ formatCost(detail.cost) }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('tenant.ai.callLog.latency')" :span="1">
            {{ detail.latency_ms ? `${detail.latency_ms}ms` : '-' }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('tenant.ai.callLog.requestType')" :span="1">
            {{ detail.request_type }}
          </Descriptions.Item>
        </Descriptions>

        <!-- 错误信息 -->
        <template v-if="detail.error_message">
          <div class="mt-4">
            <h4 class="mb-2 font-medium text-destructive">
              <IconifyIcon icon="lucide:alert-circle" class="mr-1 inline size-4" />
              {{ $t('tenant.ai.callLog.errorMessage') }}
            </h4>
            <pre class="rounded-lg bg-destructive/5 p-3 text-sm text-destructive">{{ detail.error_message }}</pre>
          </div>
        </template>

        <!-- 请求数据 -->
        <template v-if="detail.request_data">
          <div class="mt-4">
            <h4 class="mb-2 font-medium text-foreground">
              {{ $t('tenant.ai.callLog.requestData') }}
            </h4>
            <pre class="max-h-[300px] overflow-auto rounded-lg bg-accent p-3 text-xs">{{ formatJson(detail.request_data) }}</pre>
          </div>
        </template>

        <!-- 响应数据 -->
        <template v-if="detail.response_data">
          <div class="mt-4">
            <h4 class="mb-2 font-medium text-foreground">
              {{ $t('tenant.ai.callLog.responseData') }}
            </h4>
            <pre class="max-h-[300px] overflow-auto rounded-lg bg-accent p-3 text-xs">{{ formatJson(detail.response_data) }}</pre>
          </div>
        </template>
      </template>
    </Spin>
  </Drawer>
</template>
