<script lang="ts" setup>
import type { AICallLogInfo } from '#/api/admin/ai';

/**
 * 调用日志详情抽屉组件
 */
import { ref, watch } from 'vue';

import { Descriptions, Drawer, Spin, Tag } from 'ant-design-vue';

import { getAICallLogDetailApi } from '#/api/admin/ai';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

import {
  formatCost,
  getCallSourceColor,
  getCallSourceText,
  getStatusText,
  getTenantDisplayName,
} from '../data';

defineOptions({ name: 'CallLogDetail' });

const props = defineProps<{
  logId: null | number;
}>();

const visible = defineModel<boolean>('visible', { default: false });

const loading = ref(false);
const detail = ref<AICallLogInfo | null>(null);

watch([() => props.logId, visible], async ([id, isVisible]) => {
  if (id && isVisible) {
    await loadDetail(id);
  }
});

async function loadDetail(id: number) {
  loading.value = true;
  try {
    detail.value = await getAICallLogDetailApi(id);
  } finally {
    loading.value = false;
  }
}

function formatJson(data: unknown): string {
  if (!data) return '-';
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'failed': {
      return 'error';
    }
    case 'success': {
      return 'success';
    }
    default: {
      return 'warning';
    }
  }
}
</script>

<template>
  <Drawer
    v-model:open="visible"
    :destroy-on-close="true"
    :title="$t('admin.ai.callLog.detail.title')"
    width="640"
  >
    <Spin :spinning="loading">
      <template v-if="detail">
        <Descriptions :column="2" bordered size="small">
          <Descriptions.Item :label="$t('admin.ai.callLog.modelName')">
            {{ detail.model_name || '-' }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.callLog.providerName')">
            {{ detail.provider_name || '-' }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.callLog.source')">
            <Tag :color="getCallSourceColor(detail.tenant_id)">
              {{ getCallSourceText(detail.tenant_id) }}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.callLog.tenantName')">
            {{ getTenantDisplayName(detail.tenant_id, detail.tenant_name) }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.callLog.callerName')">
            {{ detail.caller_name || '-' }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.callLog.status')">
            <Tag :color="getStatusColor(detail.status)">
              {{ getStatusText(detail.status) }}
            </Tag>
          </Descriptions.Item>
          <!-- 路由覆写信息（模型被路由引擎替换时高亮显示） -->
          <Descriptions.Item
            v-if="
              detail.route_reason ||
              (detail.routed_model_id && detail.routed_model_id !== detail.model_id)
            "
            :label="$t('admin.ai.callLog.routedModel')"
            :span="2"
          >
            <span class="font-medium text-warning">
              {{
                detail.routed_model_name ||
                detail.model_name ||
                (detail.routed_model_id ? `#${detail.routed_model_id}` : '-')
              }}
            </span>
            <span
              v-if="detail.route_reason"
              class="ml-2 text-xs text-muted-foreground"
            >
              ({{ detail.route_reason }})
            </span>
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.callLog.inputTokens')">
            {{ detail.input_tokens }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.callLog.outputTokens')">
            {{ detail.output_tokens }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.callLog.totalTokens')">
            {{ detail.total_tokens }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.callLog.cost')">
            {{ formatCost(detail.cost) }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.callLog.latency')">
            {{ detail.latency_ms ? `${detail.latency_ms}ms` : '-' }}
          </Descriptions.Item>
          <Descriptions.Item :label="$t('admin.ai.callLog.createdAt')">
            {{ formatDate(detail.created_at) }}
          </Descriptions.Item>
        </Descriptions>

        <!-- Error message -->
        <template v-if="detail.error_message">
          <div class="mt-4">
            <div class="mb-1 font-medium text-destructive">
              {{ $t('admin.ai.callLog.errorMessage') }}
            </div>
            <pre
              class="rounded bg-destructive/5 p-3 text-xs text-destructive"
              >{{ detail.error_message }}</pre
            >
          </div>
        </template>

        <!-- Request data -->
        <template v-if="detail.request_data">
          <div class="mt-4">
            <div class="mb-1 font-medium text-foreground">
              {{ $t('admin.ai.callLog.detail.requestData') }}
            </div>
            <pre class="max-h-64 overflow-auto rounded bg-accent p-3 text-xs">{{
              formatJson(detail.request_data)
            }}</pre>
          </div>
        </template>

        <!-- Response data -->
        <template v-if="detail.response_data">
          <div class="mt-4">
            <div class="mb-1 font-medium text-foreground">
              {{ $t('admin.ai.callLog.detail.responseData') }}
            </div>
            <pre class="max-h-64 overflow-auto rounded bg-accent p-3 text-xs">{{
              formatJson(detail.response_data)
            }}</pre>
          </div>
        </template>
      </template>
    </Spin>
  </Drawer>
</template>
