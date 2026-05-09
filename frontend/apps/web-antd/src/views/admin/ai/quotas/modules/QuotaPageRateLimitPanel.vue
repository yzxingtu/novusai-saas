<script lang="ts" setup>
import type {
  AIRateLimitDiagnosticInfo,
  AIRateLimitInfo,
} from '#/api/admin/ai-quotas';

import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Card,
  Empty,
  Pagination,
  Progress,
  Spin,
  Tag,
} from 'ant-design-vue';

import { $t } from '#/locales';
import { formatTokens } from '#/utils/format';

import {
  getRuntimeStatusColor,
  getRuntimeStatusText,
  getSourceColor,
  getSourceText,
} from '../data';

defineOptions({ name: 'QuotaPageRateLimitPanel' });

defineProps<{
  onRateLimitDelete: (item: AIRateLimitDiagnosticInfo) => Promise<void>;
  onRateLimitEdit: (item: AIRateLimitInfo) => void;
  onRateLimitPageChange: (page: number) => void;
  rateLimitLoading: boolean;
  rateLimitPage: number;
  rateLimitPageSize: number;
  rateLimits: AIRateLimitDiagnosticInfo[];
  rateLimitTotal: number;
}>();

function progressStatus(isExceeded: boolean, isWarning: boolean) {
  if (isExceeded) return 'exception';
  if (isWarning) return 'active';
  return 'success';
}
</script>

<template>
  <div class="mb-4 grid grid-cols-1 gap-3 xl:grid-cols-2">
    <Alert
      :message="$t('admin.ai.rateLimit.helper.deny')"
      show-icon
      type="error"
    />
    <Alert
      :message="$t('admin.ai.rateLimit.helper.inherit')"
      show-icon
      type="info"
    />
  </div>

  <Spin :spinning="rateLimitLoading">
    <div
      v-if="rateLimits.length > 0"
      class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
    >
      <Card
        v-for="item in rateLimits"
        :key="item.id"
        class="overflow-hidden border-border/60"
        :body-style="{ padding: '18px' }"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <div
                class="flex size-10 items-center justify-center rounded-2xl bg-success/10"
              >
                <IconifyIcon icon="lucide:timer" class="size-5 text-success" />
              </div>
              <div class="min-w-0">
                <div class="truncate text-base font-semibold text-foreground">
                  {{ item.model_name || `Model #${item.model_id}` }}
                </div>
                <div class="mt-1 flex flex-wrap items-center gap-1.5">
                  <Tag color="blue" class="!mr-0">
                    {{ item.tenant_name || `Tenant #${item.tenant_id}` }}
                  </Tag>
                  <Tag
                    :color="getRuntimeStatusColor(item.runtime_status)"
                    class="!mr-0"
                  >
                    {{ getRuntimeStatusText(item.runtime_status) }}
                  </Tag>
                  <Tag
                    :color="item.is_latest_model_rule ? 'success' : 'warning'"
                    class="!mr-0"
                  >
                    {{
                      item.is_latest_model_rule
                        ? $t('admin.ai.rateLimit.latestRule')
                        : $t('admin.ai.rateLimit.shadowedRule')
                    }}
                  </Tag>
                </div>
              </div>
            </div>
          </div>

          <div class="flex items-center gap-1">
            <Button
              v-access:code="['ai_quota:update_rate_limit']"
              size="small"
              type="text"
              @click="onRateLimitEdit(item)"
            >
              <template #icon>
                <IconifyIcon icon="lucide:pencil" class="size-4" />
              </template>
            </Button>
            <Button
              v-access:code="['ai_quota:delete_rate_limit']"
              danger
              size="small"
              type="text"
              @click="onRateLimitDelete(item)"
            >
              <template #icon>
                <IconifyIcon icon="lucide:trash-2" class="size-4" />
              </template>
            </Button>
          </div>
        </div>

        <div class="mt-4 grid grid-cols-1 gap-3">
          <div class="rounded-2xl bg-accent/10 p-4">
            <div class="mb-2 flex items-center justify-between text-sm">
              <span class="text-muted-foreground">
                {{ $t('admin.ai.rateLimit.currentRpm') }}
              </span>
              <span class="font-medium">
                {{
                  item.effective_rpm_limit == null
                    ? $t('admin.ai.rateLimit.noLimit')
                    : `${item.current_rpm} / ${item.effective_rpm_limit}`
                }}
              </span>
            </div>
            <Progress
              :percent="Math.min(item.rpm_usage_percent, 100)"
              :show-info="false"
              :status="progressStatus(item.is_exceeded, item.is_warning)"
            />
          </div>

          <div class="rounded-2xl bg-accent/10 p-4">
            <div class="mb-2 flex items-center justify-between text-sm">
              <span class="text-muted-foreground">
                {{ $t('admin.ai.rateLimit.currentTpm') }}
              </span>
              <span class="font-medium">
                {{
                  item.effective_tpm_limit == null
                    ? $t('admin.ai.rateLimit.noLimit')
                    : `${formatTokens(item.current_tpm)} / ${formatTokens(item.effective_tpm_limit)}`
                }}
              </span>
            </div>
            <Progress
              :percent="Math.min(item.tpm_usage_percent, 100)"
              :show-info="false"
              :status="progressStatus(item.is_exceeded, item.is_warning)"
            />
          </div>
        </div>

        <div class="mt-4 grid grid-cols-1 gap-2 text-sm">
          <div class="flex items-center justify-between gap-3">
            <span class="text-muted-foreground">
              {{ $t('admin.ai.rateLimit.configured') }}
            </span>
            <span class="font-medium text-foreground">
              RPM {{ item.configured_rpm_limit ?? '-' }} / TPM
              {{
                item.configured_tpm_limit == null
                  ? '-'
                  : formatTokens(item.configured_tpm_limit)
              }}
            </span>
          </div>
          <div class="flex items-center justify-between gap-3">
            <span class="text-muted-foreground">
              {{ $t('admin.ai.rateLimit.modelDefault') }}
            </span>
            <span class="font-medium text-foreground">
              RPM {{ item.model_default_rpm_limit ?? '-' }} / TPM
              {{
                item.model_default_tpm_limit == null
                  ? '-'
                  : formatTokens(item.model_default_tpm_limit)
              }}
            </span>
          </div>
          <div class="flex items-center justify-between gap-3">
            <span class="text-muted-foreground">
              {{ $t('admin.ai.rateLimit.effective') }}
            </span>
            <span class="flex flex-wrap items-center justify-end gap-1.5">
              <Tag :color="getSourceColor(item.rpm_source)" class="!mr-0">
                RPM {{ getSourceText(item.rpm_source) }}
              </Tag>
              <Tag :color="getSourceColor(item.tpm_source)" class="!mr-0">
                TPM {{ getSourceText(item.tpm_source) }}
              </Tag>
            </span>
          </div>
        </div>

        <div class="mt-4 text-xs text-muted-foreground">
          {{ $t('admin.ai.rateLimit.response') }}: HTTP
          {{ item.exhaustion_http_status }} / {{ item.exhaustion_error_code }}
          <div class="mt-1">
            {{ item.exhaustion_message_preview }}
          </div>
        </div>
      </Card>
    </div>
    <Empty v-else :description="$t('common.noData')" class="py-16" />
  </Spin>

  <div v-if="rateLimitTotal > rateLimitPageSize" class="mt-4 flex justify-end">
    <Pagination
      :current="rateLimitPage"
      :page-size="rateLimitPageSize"
      :total="rateLimitTotal"
      show-quick-jumper
      size="small"
      @change="onRateLimitPageChange"
    />
  </div>
</template>
